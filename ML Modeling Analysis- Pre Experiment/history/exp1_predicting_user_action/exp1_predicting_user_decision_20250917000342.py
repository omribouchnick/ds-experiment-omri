# exp1_runner_70_30.py
# ------------------------------------------------------------
# Two split modes only:
#   1) pooled_chrono_70_30   (per-user chronological, last 30% test)
#   2) holdout_ids_70_30     (70% users train, 30% users test)
#
# Outputs:
#   exp1_experiment_outputs/
#     summary_<BLOCK>_<SPLIT>.csv
#     fi_top15_<BLOCK>_<SPLIT>_<ABLATION>.csv
#     leak_reports_<BLOCK>_<SPLIT>.txt
# ------------------------------------------------------------
import os, json, warnings, random
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# ------------------ Config ------------------
RAW_PATH = "data/exp1_raw.csv"
AGG_PATH = "/data/exp1_agg.csv"

OUT = Path("exp1_experiment_outputs")
OUT.mkdir(parents=True, exist_ok=True)

SEED = 42
random.seed(SEED); np.random.seed(SEED)

# Posterior mapping constants (equal-variance SDT)
CENTER_M = 6.0          # neutral criterion
ROLLING_WINDOWS = [1, 3, 7, 14, 21, 40]

# XGBoost (short, robust configuration)
import xgboost as xgb
XGB_PARAMS = dict(
    random_state=SEED,
    eval_metric="logloss",
    n_jobs=-1,
    tree_method="hist",
    n_estimators=200,
    max_depth=6,
    learning_rate=0.1,
    subsample=0.9,
    reg_lambda=1.0,
)

from sklearn.metrics import (
    accuracy_score, f1_score, precision_score, recall_score,
    roc_auc_score, average_precision_score
)

# ------------------ Utils ------------------
def ece_score(y_true, y_prob, n_bins=15):
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    idx = np.digitize(y_prob, bins) - 1
    ece = 0.0
    for b in range(n_bins):
        m = idx == b
        if not np.any(m):
            continue
        conf = y_prob[m].mean()
        acc  = y_true[m].mean()
        ece += m.mean() * abs(acc - conf)
    return float(ece)

def print_header(msg):
    bar = "=" * len(msg)
    print(f"\n{bar}\n{msg}\n{bar}")

# ------------------ Data loading & prep ------------------
def load_data():
    raw = pd.read_csv(RAW_PATH)
    agg = pd.read_csv(AGG_PATH)

    raw.columns = raw.columns.str.lower().str.replace(' ', '_')
    agg.columns = agg.columns.str.lower().str.replace(' ', '_')
    return raw, agg

def prepare_block(raw, agg, block_type="DS"):
    # Filter to DS or NONDS
    if block_type.upper() == "DS":
        df = raw.query("alert_system == 1").copy()
    else:
        df = raw.query("alert_system == 0").copy()

    # Order chronologically
    df = df.sort_values(['id', 'block', 'trial']).reset_index(drop=True)

    # Label: user decision S (signal) vs N (noise)
    df['target'] = (df['user_action'] == 'S').astype(int)

    # DS recommendation (only exists in DS blocks)
    if 'alarm_output' in df.columns:
        s = df['alarm_output'].astype(str).str.strip().str.lower()
        df['ds_recommends_signal'] = (s == 'alarm').astype(int)
    else:
        df['ds_recommends_signal'] = np.nan

    # Meta flags
    df['is_first_trial']  = (df['trial'] == 1).astype(int)
    df['is_first_block']  = (df['block'] == 1).astype(int)
    df['purchase_ds_block_num'] = df.groupby('id')['block'].rank(method='dense')

    # Dependency (prev block) if provided in agg
    dep_col = next((c for c in ['dependency','dependency_agg','dep','user_dependency','dependency_level'] if c in agg.columns), None)
    dep_map = {'independent':1, 'low':2, 'medium':3, 'high':4, 'full':5}
    if dep_col:
        a = agg[['id','block',dep_col]].drop_duplicates().copy()
        a['dependency_num'] = a[dep_col].astype(str).str.strip().str.lower().map(dep_map)
        a['dependency_num_prev_block'] = a.groupby('id')['dependency_num'].shift(1)
        df = df.merge(a[['id','block','dependency_num_prev_block']].drop_duplicates(),
                      on=['id','block'], how='left')
    else:
        df['dependency_num_prev_block'] = np.nan

    return df

# ------------------ Posterior P(S|x) ------------------
# logit P(S|x) = log(pi/(1-pi)) + d' * (x - CENTER_M)
def compute_p_signal(df, train_prior_pi, center=CENTER_M):
    pi = float(np.clip(train_prior_pi, 1e-6, 1-1e-6))
    z = np.log(pi/(1.0-pi)) + df['system_d'].astype(float) * (df['stimulus'].astype(float) - center)
    return 1.0 / (1.0 + np.exp(-z))

# ------------------ Rolling features (strict shift) ------------------
def add_rolling_features(df, use_posterior=True):
    """
    Adds leak-safe rolling features per user with shift(1).
    Also computes user/system/DS confusion components per trial.
    """
    # Build confusion bits
    df['tp'] = ((df['user_action']=='S') & (df['event_type']=='S')).astype(int)
    df['fp'] = ((df['user_action']=='S') & (df['event_type']=='N')).astype(int)
    df['fn'] = ((df['user_action']=='N') & (df['event_type']=='S')).astype(int)

    df['system_indicates_signal'] = (df['stimulus'] >= CENTER_M).astype(int)
    df['system_tp'] = ((df['system_indicates_signal']==1) & (df['event_type']=='S')).astype(int)
    df['system_fp'] = ((df['system_indicates_signal']==1) & (df['event_type']=='N')).astype(int)
    df['system_fn'] = ((df['system_indicates_signal']==0) & (df['event_type']=='S')).astype(int)

    has_ds = df['ds_recommends_signal'].notna().any()
    if has_ds:
        df['ds_tp'] = ((df['ds_recommends_signal']==1) & (df['event_type']=='S')).astype(int)
        df['ds_fp'] = ((df['ds_recommends_signal']==1) & (df['event_type']=='N')).astype(int)
        df['ds_fn'] = ((df['ds_recommends_signal']==0) & (df['event_type']=='S')).astype(int)

    # Pre-create columns
    bases = ['signal_rate','tp_rate','fp_rate','fn_rate']
    sys_bases = ['system_tp_rate','system_fp_rate','system_fn_rate']
    ds_bases = ['ds_tp_rate','ds_fp_rate','ds_fn_rate']
    cond = ['user_tp_given_system_signal_rate','user_tp_given_system_noise_rate']

    cols = bases + sys_bases + cond
    if has_ds:
        cols += ds_bases
    if use_posterior and 'p_signal' in df.columns:
        cols += ['p_signal_mean']

    for w in ROLLING_WINDOWS:
        for c in cols:
            df[f'{c}_rolling_{w}'] = np.nan

    # Per-user rolling with strict temporal shift
    for uid, sub in df.groupby('id', sort=False):
        s = sub.copy()
        s['user_tp_given_system_signal'] = ((s['user_action']=='S') & (s['event_type']=='S') & (s['system_indicates_signal']==1)).astype(int)
        s['user_tp_given_system_noise']  = ((s['user_action']=='S') & (s['event_type']=='S') & (s['system_indicates_signal']==0)).astype(int)

        for w in ROLLING_WINDOWS:
            s[f'signal_rate_rolling_{w}'] = s['target'].rolling(w, min_periods=1).mean().shift(1)
            s[f'tp_rate_rolling_{w}']     = s['tp'].rolling(w, min_periods=1).mean().shift(1)
            s[f'fp_rate_rolling_{w}']     = s['fp'].rolling(w, min_periods=1).mean().shift(1)
            s[f'fn_rate_rolling_{w}']     = s['fn'].rolling(w, min_periods=1).mean().shift(1)

            s[f'system_tp_rate_rolling_{w}'] = s['system_tp'].rolling(w, min_periods=1).mean().shift(1)
            s[f'system_fp_rate_rolling_{w}'] = s['system_fp'].rolling(w, min_periods=1).mean().shift(1)
            s[f'system_fn_rate_rolling_{w}'] = s['system_fn'].rolling(w, min_periods=1).mean().shift(1)

            s[f'user_tp_given_system_signal_rate_rolling_{w}'] = s['user_tp_given_system_signal'].rolling(w, min_periods=1).mean().shift(1)
            s[f'user_tp_given_system_noise_rate_rolling_{w}']  = s['user_tp_given_system_noise'].rolling(w, min_periods=1).mean().shift(1)

            if has_ds:
                s[f'ds_tp_rate_rolling_{w}'] = s['ds_tp'].rolling(w, min_periods=1).mean().shift(1)
                s[f'ds_fp_rate_rolling_{w}'] = s['ds_fp'].rolling(w, min_periods=1).mean().shift(1)
                s[f'ds_fn_rate_rolling_{w}'] = s['ds_fn'].rolling(w, min_periods=1).mean().shift(1)

            if use_posterior and 'p_signal' in s.columns:
                s[f'p_signal_mean_rolling_{w}'] = s['p_signal'].rolling(w, min_periods=1).mean().shift(1)

        df.loc[s.index, s.columns] = s

    return df

# ------------------ Feature sets / ablations ------------------
def build_feature_sets(df, block_type="DS"):
    # Base simple features
    base = [
        'p_signal',
        'trial','is_first_trial','block','is_first_block','purchase_ds_block_num',
        'system_d',
        'dependency_num_prev_block'
    ]
    if block_type.upper()=="DS" and df['ds_recommends_signal'].notna().any():
        base.insert(1, 'ds_recommends_signal')

    rolling = [c for c in df.columns if 'rolling_' in c]
    full = [c for c in base + rolling if c in df.columns]

    stim_current = {'p_signal'}
    stim_hist = {c for c in df.columns if c.startswith('p_signal_mean_rolling_')}
    sys_from_stim_hist = {c for c in df.columns if c.startswith('system_tp_rate_') or
                                             c.startswith('system_fp_rate_') or
                                             c.startswith('system_fn_rate_') or
                                             c.startswith('user_tp_given_system_')}

    sets = {
        'full': full,
        'no_stim': [f for f in full if f not in stim_current],
        'no_stim_hard': [f for f in full if f not in (stim_current | stim_hist | sys_from_stim_hist)],
        'no_historical': [f for f in base if f in df.columns],
    }
    if block_type.upper() == "DS" and df['ds_recommends_signal'].notna().any():
        sets['no_ds'] = [f for f in full if f != 'ds_recommends_signal']
        sets['no_stim_and_ds'] = [f for f in sets['no_stim'] if f != 'ds_recommends_signal']

    return sets

# ------------------ Splits ------------------
def split_pooled_chrono_70_30(df):
    """Per-user chronological: last 30% of each user's rows go to test."""
    test_mask = np.zeros(len(df), dtype=bool)
    for _, sub in df.groupby('id', sort=False):
        n = len(sub)
        t = max(1, int(np.floor(n * 0.30)))
        test_mask[sub.index[-t:]] = True
    return np.flatnonzero(~test_mask), np.flatnonzero(test_mask)

def split_holdout_ids_70_30(df):
    users = df['id'].drop_duplicates().sample(frac=1.0, random_state=SEED).tolist()
    k = int(len(users) * 0.70)
    u_tr, u_te = set(users[:k]), set(users[k:])
    return df.index[df['id'].isin(u_tr)].values, df.index[df['id'].isin(u_te)].values

# ------------------ Leakage checks ------------------
def leakage_checks(df_tr, df_te, feature_cols, user_col='id'):
    warnings = []

    roll_cols = [c for c in feature_cols if 'rolling_' in c]
    if not roll_cols:
        return warnings

    # (1) first trial per user must be NaN in rolling features
    first_tr_idx = df_tr.groupby(user_col)['trial'].idxmin()
    first_te_idx = df_te.groupby(user_col)['trial'].idxmin()
    if not df_tr.loc[first_tr_idx, roll_cols].isna().all().all():
        warnings.append("Train: first-trial rolling features contain non-NaNs.")
    if not df_te.loc[first_te_idx, roll_cols].isna().all().all():
        warnings.append("Test: first-trial rolling features contain non-NaNs.")

    # (2) first trial in each block per user must be NaN in rolling features
    tr_block_first = df_tr.sort_values(['id','block','trial']).groupby(['id','block']).head(1).index
    te_block_first = df_te.sort_values(['id','block','trial']).groupby(['id','block']).head(1).index
    if not df_tr.loc[tr_block_first, roll_cols].isna().all().all():
        warnings.append("Train: first trial in some blocks has non-NaN rolling features.")
    if not df_te.loc[te_block_first, roll_cols].isna().all().all():
        warnings.append("Test: first trial in some blocks has non-NaN rolling features.")

    return warnings

# ------------------ Train/Eval ------------------
def fit_eval_xgb(Xtr, ytr, Xte, yte):
    clf = xgb.XGBClassifier(**XGB_PARAMS)
    clf.fit(Xtr, ytr)
    proba = clf.predict_proba(Xte)[:, 1]
    pred  = (proba >= 0.5).astype(int)
    return clf, proba, pred

def evaluate(y_true, proba, pred):
    return dict(
        acc  = accuracy_score(y_true, pred),
        f1   = f1_score(y_true, pred, zero_division=0),
        prec = precision_score(y_true, pred, zero_division=0),
        rec  = recall_score(y_true, pred),
        auc  = roc_auc_score(y_true, proba),
        ap   = average_precision_score(y_true, proba),
        ece  = ece_score(y_true, proba),
    )

# ------------------ Pipeline for one split mode ------------------
def run_for_split(block_type, split_mode):
    """
    split_mode ∈ {"pooled_chrono_70_30", "holdout_ids_70_30"}
    """
    raw, agg = load_data()
    df = prepare_block(raw, agg, block_type=block_type)

    # Base stats
    print_header(f"{block_type} BLOCKS — {split_mode} — base stats")
    print(f"Trials: {len(df):,} | Pos rate p(S): {df['target'].mean():.4f}")

    # Build temp to discover feature names (needs p_signal + rolling)
    tmp = df.copy()
    # provisional prior (global) just to compute columns; not used for training
    tmp_pi = tmp['target'].mean()
    tmp['p_signal'] = compute_p_signal(tmp, tmp_pi, center=CENTER_M)
    tmp = add_rolling_features(tmp, use_posterior=True)
    feature_sets = build_feature_sets(tmp, block_type=block_type)

    # Choose split indices
    if split_mode == "pooled_chrono_70_30":
        tr_idx, te_idx = split_pooled_chrono_70_30(df)
    elif split_mode == "holdout_ids_70_30":
        tr_idx, te_idx = split_holdout_ids_70_30(df)
    else:
        raise ValueError("Unknown split_mode")

    df_tr = df.iloc[tr_idx].copy()
    df_te = df.iloc[te_idx].copy()

    # Compute train-only prior, then p_signal on BOTH splits using that prior
    prior_pi = df_tr['target'].mean()
    for part in (df_tr, df_te):
        part['p_signal'] = compute_p_signal(part, prior_pi, center=CENTER_M)

    # Add rolling (after p_signal exists)
    df_tr = add_rolling_features(df_tr, use_posterior=True)
    df_te = add_rolling_features(df_te, use_posterior=True)

    results = []
    leak_lines = []

    for tag, feats in feature_sets.items():
        # Subset features that actually exist
        feats = [f for f in feats if f in df_tr.columns]

        # Leakage checks
        leaks = leakage_checks(df_tr, df_te, feats, user_col='id')
        if leaks:
            leak_lines.append(f"[{tag}] " + " | ".join(leaks))

        # Train/evaluate
        Xtr = df_tr[feats]
        ytr = df_tr['target'].astype(int).values
        Xte = df_te[feats]
        yte = df_te['target'].astype(int).values

        clf, proba, pred = fit_eval_xgb(Xtr, ytr, Xte, yte)
        metrics = evaluate(yte, proba, pred)

        # Save top-15 feature importances (if available)
        if hasattr(clf, "feature_importances_"):
            fi = (pd.DataFrame({"feature": feats, "importance": clf.feature_importances_})
                    .sort_values("importance", ascending=False)
                    .head(15))
            fi.to_csv(OUT / f'fi_top15_{block_type}_{split_mode}_{tag}.csv', index=False)

        # Append row
        results.append({
            "block": block_type,
            "split": split_mode,
            "ablation": tag,
            "n_train": int(len(Xtr)),
            "n_test": int(len(Xte)),
            "pi_train": float(df_tr['target'].mean()),
            "pi_test": float(df_te['target'].mean()),
            **metrics
        })

        # Console print for this ablation
        print(f"\n[{block_type} | {split_mode} | {tag}] "
              f"n_train={len(Xtr):,}, n_test={len(Xte):,}, "
              f"pi_train={results[-1]['pi_train']:.3f}, pi_test={results[-1]['pi_test']:.3f}\n"
              f"  Acc={metrics['acc']:.3f} | F1={metrics['f1']:.3f} | "
              f"Prec={metrics['prec']:.3f} | Rec={metrics['rec']:.3f} | "
              f"AUC={metrics['auc']:.3f} | AP={metrics['ap']:.3f} | ECE={metrics['ece']:.3f}")

    # Save summary CSV
    summary = pd.DataFrame(results).sort_values(["split","ablation"])
    out_csv = OUT / f"summary_{block_type}_{split_mode}.csv"
    summary.to_csv(out_csv, index=False)

    # Save leak report text if any
    if leak_lines:
        with open(OUT / f'leak_reports_{block_type}_{split_mode}.txt', 'w') as f:
            f.write("\n".join(leak_lines))

    print_header(f"SUMMARY SAVED → {out_csv}")
    if leak_lines:
        print("Leakage warnings written to",
              OUT / f'leak_reports_{block_type}_{split_mode}.txt')

    return summary

# ------------------ Main ------------------
if __name__ == "__main__":
    # DS blocks
    _ = run_for_split(block_type="DS", split_mode="pooled_chrono_70_30")
    _ = run_for_split(block_type="DS", split_mode="holdout_ids_70_30")

    # NON-DS blocks
    _ = run_for_split(block_type="NONDS", split_mode="pooled_chrono_70_30")
    _ = run_for_split(block_type="NONDS", split_mode="holdout_ids_70_30")

    print_header("ALL DONE — results in exp1_experiment_outputs/")


# import os
# import json
# from pathlib import Path
# import warnings
# warnings.filterwarnings("ignore")

# import numpy as np
# import pandas as pd
# import matplotlib.pyplot as plt

# from sklearn.metrics import (
#     accuracy_score, f1_score, precision_score, recall_score,
#     roc_auc_score, confusion_matrix, precision_recall_curve,
#     average_precision_score, brier_score_loss
# )
# from sklearn.calibration import CalibratedClassifierCV, calibration_curve
# from sklearn.model_selection import GridSearchCV

# import xgboost as xgb

# # =============================================================
# # Config
# # =============================================================
# RAW_PATH = 'data/exp1_raw.csv'
# AGG_PATH = 'data/exp1_agg.csv'
# OUT = Path('exp1_unified_outputs'); OUT.mkdir(exist_ok=True)
# PARAMS_STORE = OUT / 'best_params.json'

# CALIBRATE = True
# CAL_METHOD = 'isotonic'
# CAL_RATIO = 0.10      # fraction of each user's train reserved for calibration

# # Small, fast grid (short options)
# XGB_PARAM_GRID = {
#     'n_estimators': [100, 200],
#     'max_depth': [3, 6],
#     'learning_rate': [0.1, 0.2],
#     'subsample': [0.8, 1.0]
# }

# ROLLING_WINDOWS = [1, 3, 7, 14, 21, 40]
# CENTER_M = 6.0  # neutral point on the stimulus scale (equal-variance SDT)

# # Controls
# SAVE_SHAP = False  # set True if you want SHAP plots (requires shap)
# TRAIN_PER_USER_MODELS = False  # optional experiment (heavy)

# # =============================================================
# # Utilities
# # =============================================================

# def ece_score(y_true, y_prob, n_bins=15):
#     bins = np.linspace(0.0, 1.0, n_bins + 1)
#     idx = np.digitize(y_prob, bins) - 1
#     ece = 0.0
#     for b in range(n_bins):
#         m = idx == b
#         if not np.any(m):
#             continue
#         conf = y_prob[m].mean()
#         acc  = y_true[m].mean()
#         ece += m.mean() * abs(acc - conf)
#     return float(ece)


# def best_threshold_f1(y_true, y_prob):
#     ts = np.linspace(0, 1, 101)
#     best_t, best_f1 = 0.5, -1.0
#     for t in ts:
#         p = (y_prob >= t).astype(int)
#         f1 = f1_score(y_true, p, zero_division=0)
#         if f1 > best_f1:
#             best_f1, best_t = f1, t
#     return float(best_t), float(best_f1)


# def save_cm_plot(cm, tag):
#     cmn = cm.astype(float) / cm.sum(axis=1, keepdims=True)
#     fig, ax = plt.subplots(figsize=(4, 4))
#     ax.imshow(cmn, cmap='Blues', vmin=0, vmax=1)
#     ax.set(xticks=[0, 1], yticks=[0, 1],
#            xticklabels=['Noise', 'Signal'], yticklabels=['Noise', 'Signal'],
#            xlabel='Predicted', ylabel='True', title=f'Confusion (norm) — {tag}')
#     for (i, j), v in np.ndenumerate(cmn):
#         ax.text(j, i, f'{v:.2f}', ha='center', va='center', fontsize=10)
#     fig.tight_layout(); fig.savefig(OUT / f'cm_norm_{tag}.png', dpi=200); plt.close(fig)


# def save_pr_cal_plots(y_true, proba, tag):
#     # PR curve
#     pr_p, pr_r, _ = precision_recall_curve(y_true, proba)
#     ap = average_precision_score(y_true, proba)
#     fig, ax = plt.subplots(figsize=(5, 4))
#     ax.plot(pr_r, pr_p)
#     ax.set(xlabel='Recall', ylabel='Precision', title=f'Precision–Recall (AP={ap:.3f}) — {tag}')
#     fig.tight_layout(); fig.savefig(OUT / f'pr_{tag}.png', dpi=200); plt.close(fig)

#     # Calibration curve
#     prob_true, prob_pred = calibration_curve(y_true, proba, n_bins=10, strategy='quantile')
#     fig, ax = plt.subplots(figsize=(5, 4))
#     ax.plot([0, 1], [0, 1], '--', lw=1)
#     ax.plot(prob_pred, prob_true, marker='o')
#     ax.set(xlabel='Predicted probability', ylabel='Observed positive rate', title=f'Calibration — {tag}')
#     fig.tight_layout(); fig.savefig(OUT / f'cal_{tag}.png', dpi=200); plt.close(fig)


# def load_params_store():
#     if PARAMS_STORE.exists():
#         with open(PARAMS_STORE, 'r') as f:
#             return json.load(f)
#     return {}


# def save_params_store(d):
#     with open(PARAMS_STORE, 'w') as f:
#         json.dump(d, f, indent=2)


# # =============================================================
# # Posterior mapping: P(S|x) under equal-variance SDT
# # logit P(S|x) = log(pi/(1-pi)) + d' * (x - m)
# # - pi: prior P(S) estimated on the *train* split only
# # - d': row-level sensitivity from 'system_d'
# # - m: neutral point (CENTER_M)
# # =============================================================

# def compute_posterior(df, prior_pi, center_m=CENTER_M, dprime_col='system_d', stim_col='stimulus'):
#     dprime = df[dprime_col].astype(float)
#     x = df[stim_col].astype(float)
#     # clamp pi to (0,1) for stability
#     prior_pi = float(np.clip(prior_pi, 1e-6, 1-1e-6))
#     logit_prior = np.log(prior_pi / (1.0 - prior_pi))
#     z = logit_prior + dprime * (x - center_m)
#     p = 1.0 / (1.0 + np.exp(-z))
#     return p, z


# # =============================================================
# # Data prep per block type (DS / Non-DS)
# # =============================================================

# def prepare_data(block_type='DS'):
#     raw_df = pd.read_csv(RAW_PATH)
#     agg_df = pd.read_csv(AGG_PATH)

#     raw_df.columns = raw_df.columns.str.lower().str.replace(' ', '_')
#     agg_df.columns = agg_df.columns.str.lower().str.replace(' ', '_')

#     if block_type.upper() == 'DS':
#         df = raw_df.query('alert_system == 1').copy()
#     else:
#         df = raw_df.query('alert_system == 0').copy()

#     # Order chronologically
#     df = df.sort_values(['id', 'block', 'trial']).reset_index(drop=True)

#     # Labels
#     df['target'] = (df['user_action'] == 'S').astype(int)

#     # DS decision (only relevant for DS blocks)
#     if 'alarm_output' in df.columns:
#         df['alarm_output_norm'] = df['alarm_output'].astype(str).str.strip().str.lower()
#         df['ds_recommends_signal'] = (df['alarm_output_norm'] == 'alarm').astype(int)
#         df['ds_recommends_noise']  = (df['alarm_output_norm'] == 'no alarm').astype(int)
#     else:
#         df['ds_recommends_signal'] = np.nan
#         df['ds_recommends_noise'] = np.nan

#     # Agreement
#     if 'ds_recommends_signal' in df.columns and df['ds_recommends_signal'].notna().any():
#         df['agrees_with_ds'] = (
#             ((df['user_action'] == 'S') & (df['ds_recommends_signal'] == 1)) |
#             ((df['user_action'] == 'N') & (df['ds_recommends_noise']  == 1))
#         ).astype(int)
#     else:
#         df['agrees_with_ds'] = 0

#     # User confusion matrix
#     df['tp'] = ((df['user_action']=='S') & (df['event_type']=='S')).astype(int)
#     df['fp'] = ((df['user_action']=='S') & (df['event_type']=='N')).astype(int)
#     df['tn'] = ((df['user_action']=='N') & (df['event_type']=='N')).astype(int)
#     df['fn'] = ((df['user_action']=='N') & (df['event_type']=='S')).astype(int)

#     # System confusion (classic 6.0 split retained; may be excluded in hard ablations)
#     if 'stimulus' in df.columns:
#         df['system_indicates_signal'] = (df['stimulus'] >= 6.0).astype(int)
#         df['system_tp'] = ((df['system_indicates_signal']==1) & (df['event_type']=='S')).astype(int)
#         df['system_fp'] = ((df['system_indicates_signal']==1) & (df['event_type']=='N')).astype(int)
#         df['system_tn'] = ((df['system_indicates_signal']==0) & (df['event_type']=='N')).astype(int)
#         df['system_fn'] = ((df['system_indicates_signal']==0) & (df['event_type']=='S')).astype(int)
#     else:
#         for c in ['system_indicates_signal','system_tp','system_fp','system_tn','system_fn']:
#             df[c] = 0

#     # Merge dependency (use previous block only to avoid leakage)
#     dep_col = next((c for c in ['dependency','dependency_agg','dep','user_dependency','dependency_level'] if c in agg_df.columns), None)
#     dep_map_num = {'independent':1,'low':2,'medium':3,'high':4,'full':5}

#     if dep_col is not None:
#         agg_tmp = agg_df[['id','block',dep_col]].drop_duplicates().copy()
#         agg_tmp['dependency_num'] = agg_tmp[dep_col].astype(str).str.strip().str.lower().map(dep_map_num)
#         agg_tmp['dependency_num_prev_block'] = agg_tmp.groupby('id')['dependency_num'].shift(1)
#         df = pd.merge(df, agg_tmp[['id','block','dependency_num_prev_block']].drop_duplicates(), on=['id','block'], how='left')
#     else:
#         df['dependency_num_prev_block'] = np.nan

#     # Meta flags
#     df['is_first_trial'] = (df['trial'] == 1).astype(int)
#     df['is_first_block'] = (df['block'] == 1).astype(int)
#     df['purchase_ds_block_num'] = df.groupby('id')['block'].rank(method='dense')

#     return df


# # =============================================================
# # Chronological splits
# # =============================================================

# def per_user_chrono_split(df, user_col='id', order_cols=('block','trial'), test_ratio=0.2):
#     test_mask = np.zeros(len(df), dtype=bool)
#     for _, sub in df.sort_values(list(order_cols)).groupby(user_col, sort=False):
#         n = len(sub)
#         t = max(1, int(np.floor(n * test_ratio)))
#         test_mask[sub.index[-t:]] = True
#     return np.flatnonzero(~test_mask), np.flatnonzero(test_mask)


# def chrono_cv_splits_on_train(df_train, user_col='id', order_cols=('block','trial'), n_folds=3):
#     df = df_train.sort_values(list(order_cols)).reset_index(drop=True)
#     splits = []
#     for k in range(1, n_folds):
#         tr_idx, va_idx = [], []
#         for _, sub in df.groupby(user_col, sort=False):
#             n = len(sub)
#             bins = np.linspace(0, n, n_folds + 1).astype(int)
#             va_start, va_end = bins[k], bins[k+1]
#             tr_idx.extend(sub.index[:va_start].tolist())
#             if va_end > va_start:
#                 va_idx.extend(sub.index[va_start:va_end].tolist())
#         splits.append((np.array(tr_idx), np.array(va_idx)))
#     return splits


# def carve_calibration_from_train(df_train, cal_ratio=0.1, user_col='id', order_cols=('block','trial')):
#     df = df_train.sort_values(list(order_cols)).reset_index(drop=True)
#     train_core, cal_hold = [], []
#     for _, sub in df.groupby(user_col, sort=False):
#         n = len(sub)
#         c = max(1, int(np.floor(n * cal_ratio)))
#         cal_hold.extend(sub.index[-c:].tolist())
#         train_core.extend(sub.index[:-c].tolist())
#     return np.array(train_core), np.array(cal_hold)


# # =============================================================
# # Feature engineering (rolling)
# # =============================================================

# def add_rolling_features(df, use_posterior=True):
#     # Create empty cols
#     bases = ['signal_rate','tp_rate','fp_rate','fn_rate']
#     sys_bases = ['system_tp_rate','system_fp_rate','system_fn_rate']
#     ds_bases = ['ds_tp_rate','ds_fp_rate','ds_fn_rate']
#     cond_bases = ['user_tp_given_system_signal_rate','user_tp_given_system_noise_rate']

#     roll_cols_to_make = bases + sys_bases + cond_bases
#     if (df['ds_recommends_signal'].notna()).any():
#         roll_cols_to_make += ds_bases

#     # Optional rolling for posterior instead of raw stimulus
#     if use_posterior:
#         roll_cols_to_make += ['p_signal_mean']

#     for w in ROLLING_WINDOWS:
#         for base in roll_cols_to_make:
#             df[f'{base}_rolling_{w}'] = np.nan

#     # Conditional per-user computations (shifted!)
#     for user_id, group in df.groupby('id'):
#         sub = group.copy()
#         for w in ROLLING_WINDOWS:
#             sub[f'signal_rate_rolling_{w}'] = sub['target'].rolling(w, min_periods=1).mean().shift(1)
#             sub[f'tp_rate_rolling_{w}'] = sub['tp'].rolling(w, min_periods=1).mean().shift(1)
#             sub[f'fp_rate_rolling_{w}'] = sub['fp'].rolling(w, min_periods=1).mean().shift(1)
#             sub[f'fn_rate_rolling_{w}'] = sub['fn'].rolling(w, min_periods=1).mean().shift(1)

#             # System-based
#             sub[f'system_tp_rate_rolling_{w}'] = sub['system_tp'].rolling(w, min_periods=1).mean().shift(1)
#             sub[f'system_fp_rate_rolling_{w}'] = sub['system_fp'].rolling(w, min_periods=1).mean().shift(1)
#             sub[f'system_fn_rate_rolling_{w}'] = sub['system_fn'].rolling(w, min_periods=1).mean().shift(1)

#             # DS-based
#             if (df['ds_recommends_signal'].notna()).any():
#                 # Build DS confusion bits if not already
#                 sub['ds_tp'] = ((sub['ds_recommends_signal']==1) & (sub['event_type']=='S')).astype(int)
#                 sub['ds_fp'] = ((sub['ds_recommends_signal']==1) & (sub['event_type']=='N')).astype(int)
#                 sub['ds_fn'] = ((sub['ds_recommends_signal']==0) & (sub['event_type']=='S')).astype(int)
#                 sub[f'ds_tp_rate_rolling_{w}'] = sub['ds_tp'].rolling(w, min_periods=1).mean().shift(1)
#                 sub[f'ds_fp_rate_rolling_{w}'] = sub['ds_fp'].rolling(w, min_periods=1).mean().shift(1)
#                 sub[f'ds_fn_rate_rolling_{w}'] = sub['ds_fn'].rolling(w, min_periods=1).mean().shift(1)

#             # Conditional user TP given system indication
#             sub['user_tp_given_system_signal'] = ((sub['user_action']=='S') & (sub['event_type']=='S') & (sub['system_indicates_signal']==1)).astype(int)
#             sub['user_tp_given_system_noise'] = ((sub['user_action']=='S') & (sub['event_type']=='S') & (sub['system_indicates_signal']==0)).astype(int)
#             sub[f'user_tp_given_system_signal_rate_rolling_{w}'] = sub['user_tp_given_system_signal'].rolling(w, min_periods=1).mean().shift(1)
#             sub[f'user_tp_given_system_noise_rate_rolling_{w}'] = sub['user_tp_given_system_noise'].rolling(w, min_periods=1).mean().shift(1)

#             if use_posterior and 'p_signal' in sub:
#                 sub[f'p_signal_mean_rolling_{w}'] = sub['p_signal'].rolling(w, min_periods=1).mean().shift(1)

#         df.loc[sub.index, sub.columns] = sub

#     return df


# # =============================================================
# # Feature sets / ablations
# # =============================================================

# def build_feature_sets(df, block_type='DS'):
#     base_simple = [
#         'p_signal',               # posterior from stimulus
#         'trial','is_first_trial','block','is_first_block','purchase_ds_block_num',
#         'system_d',              # sensitivity parameter
#         'dependency_num_prev_block'
#     ]

#     if block_type.upper() == 'DS' and df['ds_recommends_signal'].notna().any():
#         base_simple.insert(1, 'ds_recommends_signal')

#     rolling_cols = [c for c in df.columns if 'rolling_' in c]

#     features_full = [c for c in base_simple + rolling_cols if c in df.columns]

#     # Ablation helpers
#     stim_current = {'p_signal'}
#     stim_hist = {c for c in df.columns if c.startswith('p_signal_mean_rolling_')}
#     sys_from_stim_hist = {c for c in df.columns if c.startswith('system_tp_rate_') or
#                                               c.startswith('system_fp_rate_') or
#                                               c.startswith('system_fn_rate_') or
#                                               c.startswith('user_tp_given_system_')}

#     feature_sets = {
#         'full': features_full,
#         'no_stim': [f for f in features_full if f not in stim_current],
#         'no_stim_hard': [f for f in features_full if f not in (stim_current | stim_hist | sys_from_stim_hist)],
#         'no_historical': [f for f in base_simple if f in df.columns],
#     }

#     if block_type.upper() == 'DS' and df['ds_recommends_signal'].notna().any():
#         feature_sets['no_ds'] = [f for f in features_full if f != 'ds_recommends_signal']
#         feature_sets['no_stim_and_ds'] = [f for f in feature_sets['no_stim'] if f != 'ds_recommends_signal']

#     return feature_sets


# # =============================================================
# # Param selection (cache best per (block_type, ablation))
# # =============================================================

# def get_or_fit_best_params(key, X, y, cv_splits):
#     store = load_params_store()
#     if key in store:
#         return store[key]

#     grid = GridSearchCV(
#         xgb.XGBClassifier(random_state=42, eval_metric='logloss', n_jobs=-1, tree_method='hist'),
#         XGB_PARAM_GRID, cv=cv_splits, scoring='f1', n_jobs=-1, refit=True, verbose=1
#     )
#     grid.fit(X, y)
#     best = grid.best_params_
#     store[key] = best
#     save_params_store(store)
#     return best


# # =============================================================
# # Train / evaluate one feature set
# # =============================================================

# def train_eval_xgb(df, feature_cols, tag, test_ratio=0.2, n_folds=3, calibrate=True, cal_ratio=0.1, block_type='DS', prior_pi=None):
#     # Chronological split
#     tr_full, te_full = per_user_chrono_split(df, 'id', ('block','trial'), test_ratio=test_ratio)
#     df_tr = df.iloc[tr_full].copy()
#     df_te = df.iloc[te_full].copy()

#     # Compute train prior for P(S)
#     if prior_pi is None:
#         prior_pi = df_tr['target'].mean()

#     # Compute posterior mapping on both splits with *train prior*
#     if 'stimulus' in df.columns and 'system_d' in df.columns:
#         df_tr['p_signal'], _ = compute_posterior(df_tr, prior_pi, center_m=CENTER_M)
#         df_te['p_signal'], _ = compute_posterior(df_te, prior_pi, center_m=CENTER_M)

#     # Rolling features — do after p_signal exists
#     df_tr = add_rolling_features(df_tr, use_posterior=True)
#     df_te = add_rolling_features(df_te, use_posterior=True)

#     # Leakage checks (simple)
#     leak_report = []
#     roll_cols = [c for c in feature_cols if 'rolling_' in c]
#     if roll_cols:
#         first_trials_tr = df_tr.groupby('id')['trial'].idxmin()
#         first_trials_te = df_te.groupby('id')['trial'].idxmin()
#         if not df_tr.loc[first_trials_tr, roll_cols].isna().all().all():
#             leak_report.append('Train: first-trial rolling features contain non-NaN values.')
#         if not df_te.loc[first_trials_te, roll_cols].isna().all().all():
#             leak_report.append('Test: first-trial rolling features contain non-NaN values.')

#     # Build matrices
#     Xtr = df_tr[feature_cols].copy()
#     ytr = df_tr['target'].astype(int).values
#     Xte = df_te[feature_cols].copy()
#     yte = df_te['target'].astype(int).values

#     # CV on training core (with calibration holdout)
#     if calibrate:
#         tr_core_rel, cal_rel = carve_calibration_from_train(df_tr, cal_ratio=cal_ratio)
#         Xtr_core, ytr_core = Xtr.iloc[tr_core_rel], ytr[tr_core_rel]
#         Xcal, ycal = Xtr.iloc[cal_rel], ytr[cal_rel]
#         cv_splits = chrono_cv_splits_on_train(df_tr.iloc[tr_core_rel], 'id', ('block','trial'), n_folds=n_folds)
#         key = f"{block_type}:{tag}"
#         best_params = get_or_fit_best_params(key, Xtr_core, ytr_core, cv_splits)
#         base_model = xgb.XGBClassifier(random_state=42, eval_metric='logloss', n_jobs=-1, tree_method='hist', **best_params)
#         base_model.fit(Xtr_core, ytr_core)
#         clf = CalibratedClassifierCV(estimator=base_model, method=CAL_METHOD, cv='prefit')
#         clf.fit(Xcal, ycal)
#         cal_proba = clf.predict_proba(Xcal)[:, 1]
#         t_star, _ = best_threshold_f1(ycal, cal_proba)
#     else:
#         cv_splits = chrono_cv_splits_on_train(df_tr, 'id', ('block','trial'), n_folds=n_folds)
#         key = f"{block_type}:{tag}"
#         best_params = get_or_fit_best_params(key, Xtr, ytr, cv_splits)
#         clf = xgb.XGBClassifier(random_state=42, eval_metric='logloss', n_jobs=-1, tree_method='hist', **best_params)
#         clf.fit(Xtr, ytr)
#         t_star = 0.5

#     # Predict
#     proba = clf.predict_proba(Xte)[:, 1]
#     pred05 = (proba >= 0.5).astype(int)
#     predT  = (proba >= t_star).astype(int)

#     # Metrics
#     acc = accuracy_score(yte, pred05)
#     f1  = f1_score(yte, pred05, zero_division=0)
#     prc = precision_score(yte, pred05, zero_division=0)
#     rec = recall_score(yte, pred05)
#     auc = roc_auc_score(yte, proba)
#     ap = average_precision_score(yte, proba)
#     brier = brier_score_loss(yte, proba)
#     ece = ece_score(yte, proba)

#     acc_t = accuracy_score(yte, predT)
#     f1_t  = f1_score(yte, predT, zero_division=0)
#     prc_t = precision_score(yte, predT, zero_division=0)
#     rec_t = recall_score(yte, predT)

#     cm = confusion_matrix(yte, pred05)
#     tag_full = f"{block_type}_{tag}"
#     save_cm_plot(cm, tag_full); save_pr_cal_plots(yte, proba, tag_full)

#     # Feature importance from base model if available
#     base_est = getattr(clf, 'base_estimator', None)
#     if base_est is None:  # when no calibration
#         base_est = clf
#     if hasattr(base_est, 'feature_importances_'):
#         fi = (pd.DataFrame({'feature': feature_cols, 'importance': base_est.feature_importances_})
#                 .sort_values('importance', ascending=False))
#         fi.head(15).to_csv(OUT / f'feature_importance_top15_{tag_full}.csv', index=False)

#     # Optional SHAP (off by default)
#     if SAVE_SHAP and hasattr(base_est, 'get_booster'):
#         try:
#             import shap
#             shap_sample = Xte.sample(min(3000, len(Xte)), random_state=42)
#             explainer = shap.TreeExplainer(base_est)
#             shap_values = explainer.shap_values(shap_sample)
#             shap.summary_plot(shap_values, shap_sample, show=False)
#             plt.tight_layout(); plt.savefig(OUT / f'shap_summary_{tag_full}.png', dpi=200, bbox_inches='tight'); plt.close()
#         except Exception as e:
#             with open(OUT / f'shap_{tag_full}.txt','w') as f:
#                 f.write(f"SHAP skipped: {e}")

#     # Base rates & sizes
#     base_rates = {
#         'n_train': int(len(df_tr)),
#         'n_test': int(len(df_te)),
#         'pi_train': float(df_tr['target'].mean()),
#         'pi_test': float(df_te['target'].mean()),
#     }

#     # Persist summary row
#     summary = {
#         'tag': tag_full,
#         'n_train': base_rates['n_train'],
#         'n_test': base_rates['n_test'],
#         'p_signal_train': base_rates['pi_train'],
#         'p_signal_test': base_rates['pi_test'],
#         'acc': acc, 'f1': f1, 'prec': prc, 'rec': rec, 'auc': auc, 'ap': ap, 'brier': brier, 'ece': ece,
#         'acc_tuned': acc_t, 'f1_tuned': f1_t, 'prec_tuned': prc_t, 'rec_tuned': rec_t, 'thresh': t_star,
#         'leak_warnings': '; '.join(leak_report) if leak_report else ''
#     }

#     return summary


# # =============================================================
# # Feature-mismatch artifact check (DS only)
# # =============================================================

# def feature_mismatch_check_ds(df, test_ratio=0.2):
#     """Train Model A with full features, Model B without DS+stim.
#     Evaluate both on the SAME rows where DS+stim are masked at test time.
#     """
#     tr_full, te_full = per_user_chrono_split(df, 'id', ('block','trial'), test_ratio=test_ratio)
#     df_tr = df.iloc[tr_full].copy()
#     df_te = df.iloc[te_full].copy()

#     # Prior from train
#     prior_pi = df_tr['target'].mean()
#     for part in (df_tr, df_te):
#         part['p_signal'], _ = compute_posterior(part, prior_pi, center_m=CENTER_M)
#     df_tr = add_rolling_features(df_tr, use_posterior=True)
#     df_te = add_rolling_features(df_te, use_posterior=True)

#     feature_sets = build_feature_sets(pd.concat([df_tr, df_te], axis=0), block_type='DS')

#     # Model A: train on full
#     feats_full = feature_sets['full']
#     XtrA, ytrA = df_tr[feats_full], df_tr['target']
#     cvA = chrono_cv_splits_on_train(df_tr, 'id', ('block','trial'), n_folds=3)
#     keyA = 'DS:artifact_full'
#     bestA = get_or_fit_best_params(keyA, XtrA, ytrA, cvA)
#     modelA = xgb.XGBClassifier(random_state=42, eval_metric='logloss', n_jobs=-1, tree_method='hist', **bestA)
#     modelA.fit(XtrA, ytrA)

#     # Mask DS+stim at test for Model A (set to NaN; XGBoost handles missing)
#     XteA = df_te[feats_full].copy()
#     for c in ['p_signal','ds_recommends_signal']:
#         if c in XteA.columns:
#             XteA[c] = np.nan

#     # Model B: train with no_stim_and_ds features
#     feats_B = feature_sets.get('no_stim_and_ds', feature_sets['no_stim'])
#     XtrB, ytrB = df_tr[feats_B], df_tr['target']
#     cvB = chrono_cv_splits_on_train(df_tr, 'id', ('block','trial'), n_folds=3)
#     keyB = 'DS:artifact_nostimds'
#     bestB = get_or_fit_best_params(keyB, XtrB, ytrB, cvB)
#     modelB = xgb.XGBClassifier(random_state=42, eval_metric='logloss', n_jobs=-1, tree_method='hist', **bestB)
#     modelB.fit(XtrB, ytrB)

#     # Evaluate on same rows
#     probaA = modelA.predict_proba(XteA)[:, 1]
#     probaB = modelB.predict_proba(df_te[feats_B])[:, 1]
#     yte = df_te['target'].values

#     def quick_metrics(p):
#         pred = (p >= 0.5).astype(int)
#         return {
#             'acc': accuracy_score(yte, pred),
#             'f1': f1_score(yte, pred, zero_division=0),
#             'auc': roc_auc_score(yte, p),
#             'ap': average_precision_score(yte, p)
#         }

#     return {
#         'ModelA_full_but_masked': quick_metrics(probaA),
#         'ModelB_trained_without_DSstim': quick_metrics(probaB),
#         'n_test': int(len(yte)),
#         'pi_test': float(yte.mean())
#     }


# # =============================================================
# # Run pipeline for a block type
# # =============================================================

# def run_block(block_type='DS', test_ratio=0.2):
#     df = prepare_data(block_type)

#     # Print base rates
#     print(f"\n=== {block_type} BLOCKS: base stats ===")
#     print(f"Trials: {len(df):,} | Pos rate p(S): {df['target'].mean():.4f}")

#     # Build once to know names (will recompute inside per run)
#     tmp_pi = df['target'].mean()
#     df_tmp = df.copy()
#     df_tmp['p_signal'], _ = compute_posterior(df_tmp, tmp_pi, center_m=CENTER_M)
#     df_tmp = add_rolling_features(df_tmp, use_posterior=True)
#     feature_sets = build_feature_sets(df_tmp, block_type=block_type)

#     results = []
#     for tag, feats in feature_sets.items():
#         print(f"\n[{block_type}] Running XGB for feature set: {tag} (n_features={len(feats)})")
#         res = train_eval_xgb(df.copy(), feats, tag=tag, test_ratio=test_ratio, n_folds=3,
#                              calibrate=CALIBRATE, cal_ratio=CAL_RATIO, block_type=block_type)
#         results.append(res)

#     # Save summary CSV
#     summ = pd.DataFrame(results).sort_values('f1', ascending=False)
#     summ.to_csv(OUT / f'summary_{block_type.lower()}.csv', index=False)

#     # Bar chart (F1 and AUC)
#     fig, ax = plt.subplots(figsize=(7, 4))
#     ax.bar(range(len(summ)), summ['f1'], label='F1')
#     ax.plot(range(len(summ)), summ['auc'], marker='o', label='AUC')
#     ax.set_xticks(range(len(summ)))
#     ax.set_xticklabels(summ['tag'], rotation=30, ha='right')
#     ax.set_ylabel('Score'); ax.set_title(f'{block_type} — Ablation Performance')
#     ax.legend()
#     fig.tight_layout(); fig.savefig(OUT / f'ablation_{block_type.lower()}.png', dpi=200); plt.close(fig)

#     # Artifact check (DS only)
#     if block_type.upper() == 'DS':
#         art = feature_mismatch_check_ds(df.copy(), test_ratio=test_ratio)
#         with open(OUT / 'artifact_check_ds.json','w') as f:
#             json.dump(art, f, indent=2)
#         print("\n[Artifact check — DS]", json.dumps(art, indent=2))

#     return summ


# # =============================================================
# # Optional: per-user models (heavy). Trains one model per user with 30/20 split.
# # =============================================================

# def run_per_user_models(block_type='DS', tag='full', train_trials=30, test_trials=20):
#     df = prepare_data(block_type)

#     # Build features names on a quick temp view
#     tmp_pi = df['target'].mean()
#     df_tmp = df.copy()
#     df_tmp['p_signal'], _ = compute_posterior(df_tmp, tmp_pi, center_m=CENTER_M)
#     df_tmp = add_rolling_features(df_tmp, use_posterior=True)
#     feature_sets = build_feature_sets(df_tmp, block_type=block_type)
#     feats = feature_sets[tag]

#     rows = []
#     for uid, sub in df.groupby('id'):
#         sub = sub.sort_values(['block','trial']).reset_index(drop=True)
#         if len(sub) < (train_trials + test_trials):
#             continue
#         tr = sub.iloc[:train_trials].copy()
#         te = sub.iloc[train_trials:train_trials+test_trials].copy()

#         prior_pi = tr['target'].mean()
#         for part in (tr, te):
#             part['p_signal'], _ = compute_posterior(part, prior_pi, center_m=CENTER_M)
#         tr = add_rolling_features(tr, use_posterior=True)
#         te = add_rolling_features(te, use_posterior=True)

#         Xtr, ytr = tr[feats], tr['target']
#         Xte, yte = te[feats], te['target']

#         cv = chrono_cv_splits_on_train(tr, 'id', ('block','trial'), n_folds=3)
#         key = f"{block_type}:per_user:{tag}"
#         best = get_or_fit_best_params(key, Xtr, ytr, cv)
#         clf = xgb.XGBClassifier(random_state=42, eval_metric='logloss', n_jobs=-1, tree_method='hist', **best)
#         clf.fit(Xtr, ytr)

#         proba = clf.predict_proba(Xte)[:,1]
#         pred = (proba >= 0.5).astype(int)
#         rows.append({
#             'id': uid,
#             'support': len(yte),
#             'acc': accuracy_score(yte, pred),
#             'f1': f1_score(yte, pred, zero_division=0),
#             'auc': roc_auc_score(yte, proba),
#             'ap': average_precision_score(yte, proba)
#         })

#     out = pd.DataFrame(rows).sort_values('support', ascending=False)
#     out.to_csv(OUT / f'per_user_models_{block_type.lower()}_{tag}.csv', index=False)
#     return out


# # =============================================================
# # Entrypoint
# # =============================================================
# if __name__ == '__main__':
#     # Example runs:
#     # More conservative split (more test) — set test_ratio=0.4 to mimic 30/20 style
#     ds_summary = run_block('DS', test_ratio=0.2)
#     nonds_summary = run_block('NONDS', test_ratio=0.2)

#     if TRAIN_PER_USER_MODELS:
#         run_per_user_models('DS', tag='full', train_trials=30, test_trials=20)
#         run_per_user_models('NONDS', tag='full', train_trials=30, test_trials=20)

#     print("\nAll outputs saved under:", OUT)
