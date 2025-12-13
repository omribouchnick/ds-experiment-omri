# exp1_two_splits_ablation.py
# Unified runner: DS & Non-DS blocks, two split modes, clean ablations, XGBoost + cached hyperparams.
# Key choices:
# - No raw stimulus: use p_signal only (Bayes SDT: logit P(S|x) = log(pi/(1-pi)) + d'*(x-6)).
# - Rolling features strictly shift(1) per user (no current-trial leakage).
# - Drop redundant "correct/incorrect" conditionals; keep only the informative ones.
# - Per-ablation retrain (train and test on the same feature set), cache best params.
# - Two split modes:
#     1) pooled_chrono_70_30: last 30% trials per user → test (temporal generalization within users)
#     2) holdout_ids_70_30: 70% user IDs train / 30% user IDs test (new users; still rolling within-test-user)
# - Outputs: summaries, feature-importance (top15), PR/Calibration plots, confusion matrices, leak reports.

import os, json, warnings, random
from pathlib import Path
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from sklearn.metrics import (
    accuracy_score, f1_score, precision_score, recall_score,
    roc_auc_score, average_precision_score, confusion_matrix, brier_score_loss
)
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.model_selection import GridSearchCV

import xgboost as xgb

# ---------------- CONFIG ----------------
RAW_PATH = 'data/exp1_raw.csv'
AGG_PATH = 'data/exp1_agg.csv'
OUT = Path('exp1_experiment_outputs'); OUT.mkdir(parents=True, exist_ok=True)
PARAMS_STORE = OUT / 'best_params.json'

SEED = 42
random.seed(SEED); np.random.seed(SEED)

CENTER_M = 6.0                       # SDT neutral point
ROLLING_WINDOWS = [1, 3, 7, 14, 21, 40]

# Short, robust grid (cached per (block, split, ablation))
XGB_PARAM_GRID = {
    'n_estimators': [100, 200],
    'max_depth': [3, 6],
    'learning_rate': [0.1, 0.2],
    'subsample': [0.8, 1.0],
}

CALIBRATE = True
CAL_METHOD = 'isotonic'
CAL_RATIO = 0.10

# ---------------- UTILS ----------------
def print_header(msg):
    bar = "=" * len(msg)
    print(f"\n{bar}\n{msg}\n{bar}")

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

def best_threshold_f1(y_true, y_prob):
    ts = np.linspace(0, 1, 101)
    best_t, best_f1 = 0.5, -1.0
    for t in ts:
        p = (y_prob >= t).astype(int)
        f1 = f1_score(y_true, p, zero_division=0)
        if f1 > best_f1:
            best_f1, best_t = f1, t
    return float(best_t), float(best_f1)

def save_cm_plot(cm, tag):
    cmn = cm.astype(float) / cm.sum(axis=1, keepdims=True)
    fig, ax = plt.subplots(figsize=(4, 4))
    ax.imshow(cmn, cmap='Blues', vmin=0, vmax=1)
    ax.set(xticks=[0,1], yticks=[0,1],
           xticklabels=['Noise','Signal'], yticklabels=['Noise','Signal'],
           xlabel='Predicted', ylabel='True', title=f'Confusion (norm) — {tag}')
    for (i, j), v in np.ndenumerate(cmn):
        ax.text(j, i, f'{v:.2f}', ha='center', va='center', fontsize=10)
    fig.tight_layout(); fig.savefig(OUT / f'cm_norm_{tag}.png', dpi=200); plt.close(fig)

def save_pr_cal_plots(y_true, proba, tag):
    # PR
    from sklearn.metrics import precision_recall_curve, average_precision_score
    pr_p, pr_r, _ = precision_recall_curve(y_true, proba)
    ap = average_precision_score(y_true, proba)
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.plot(pr_r, pr_p)
    ax.set(xlabel='Recall', ylabel='Precision', title=f'Precision–Recall (AP={ap:.3f}) — {tag}')
    fig.tight_layout(); fig.savefig(OUT / f'pr_{tag}.png', dpi=200); plt.close(fig)
    # Calibration
    prob_true, prob_pred = calibration_curve(y_true, proba, n_bins=10, strategy='quantile')
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.plot([0, 1], [0, 1], '--', lw=1)
    ax.plot(prob_pred, prob_true, marker='o')
    ax.set(xlabel='Predicted prob', ylabel='Observed positive rate', title=f'Calibration — {tag}')
    fig.tight_layout(); fig.savefig(OUT / f'cal_{tag}.png', dpi=200); plt.close(fig)

def load_params_store():
    if PARAMS_STORE.exists():
        with open(PARAMS_STORE, 'r') as f:
            return json.load(f)
    return {}

def save_params_store(d):
    with open(PARAMS_STORE, 'w') as f:
        json.dump(d, f, indent=2)

# ---------------- LOAD & PREP ----------------
def load_data():
    raw = pd.read_csv(RAW_PATH)
    agg = pd.read_csv(AGG_PATH)
    raw.columns = raw.columns.str.lower().str.replace(' ', '_')
    agg.columns = agg.columns.str.lower().str.replace(' ', '_')
    return raw, agg

def prepare_block(raw, agg, block_type="DS"):
    if block_type.upper() == "DS":
        df = raw.query("alert_system == 1").copy()
    else:
        df = raw.query("alert_system == 0").copy()

    df = df.sort_values(['id', 'block', 'trial']).reset_index(drop=True)
    df['target'] = (df['user_action'] == 'S').astype(int)

    # DS current rec (present only in DS blocks)
    if 'alarm_output' in df.columns:
        s = df['alarm_output'].astype(str).str.strip().str.lower()
        df['ds_recommends_signal'] = (s == 'alarm').astype(int)
    else:
        df['ds_recommends_signal'] = np.nan

    # Meta
    df['is_first_trial']  = (df['trial'] == 1).astype(int)
    df['is_first_block']  = (df['block'] == 1).astype(int)
    df['purchase_ds_block_num'] = df.groupby('id')['block'].rank(method='dense')

    # Dependency (fixed, allowed within the block)
    dep_col = next((c for c in ['dependency','dependency_agg','dep','user_dependency','dependency_level'] if c in agg.columns), None)
    dep_map = {'independent':1,'low':2,'medium':3,'high':4,'full':5}
    if dep_col:
        a = agg[['id','block',dep_col]].drop_duplicates().copy()
        a['dependency_num'] = a[dep_col].astype(str).str.strip().str.lower().map(dep_map)
        df = df.merge(a[['id','block','dependency_num']].drop_duplicates(),
                      on=['id','block'], how='left')
    else:
        df['dependency_num'] = np.nan

    return df

# ---------------- p_signal (Bayes SDT) ----------------
# logit P(S|x) = log(pi/(1-pi)) + d'*(x - CENTER_M)
def compute_p_signal(df, train_prior_pi, center=CENTER_M):
    pi = float(np.clip(train_prior_pi, 1e-6, 1-1e-6))
    z = np.log(pi/(1.0-pi)) + df['system_d'].astype(float) * (df['stimulus'].astype(float) - center)
    return 1.0 / (1.0 + np.exp(-z))

# ---------------- ROLLING FEATURES ----------------
def add_rolling_features(df):
    # System indication (current; only for building historical confusion; not used directly as a feature)
    df['system_indicates_signal'] = (df['stimulus'] >= CENTER_M).astype(int)

    # Per-trial confusion bits (for rolling ONLY)
    df['tp'] = ((df['user_action']=='S') & (df['event_type']=='S')).astype(int)
    df['fp'] = ((df['user_action']=='S') & (df['event_type']=='N')).astype(int)

    df['system_tp'] = ((df['system_indicates_signal']==1) & (df['event_type']=='S')).astype(int)
    df['system_fp'] = ((df['system_indicates_signal']==1) & (df['event_type']=='N')).astype(int)

    has_ds = df['ds_recommends_signal'].notna().any()
    if has_ds:
        df['ds_tp'] = ((df['ds_recommends_signal']==1) & (df['event_type']=='S')).astype(int)
        df['ds_fp'] = ((df['ds_recommends_signal']==1) & (df['event_type']=='N')).astype(int)
        df['user_ds_agreement'] = (
            ((df['ds_recommends_signal']==1) & (df['user_action']=='S')) |
            ((df['ds_recommends_signal']==0) & (df['user_action']=='N'))
        ).astype(int)

    # Conditional user TPs (the non-redundant ones only)
    df['user_tp_given_system_signal'] = ((df['user_action']=='S') & (df['event_type']=='S') & (df['system_indicates_signal']==1)).astype(int)
    df['user_tp_given_system_noise']  = ((df['user_action']=='S') & (df['event_type']=='S') & (df['system_indicates_signal']==0)).astype(int)
    if has_ds:
        df['user_tp_given_ds_alarm']    = ((df['user_action']=='S') & (df['event_type']=='S') & (df['ds_recommends_signal']==1)).astype(int)
        df['user_tp_given_ds_no_alarm'] = ((df['user_action']=='S') & (df['event_type']=='S') & (df['ds_recommends_signal']==0)).astype(int)

    # Pre-create rolling targets
    bases = ['signal_rate','tp_rate','fp_rate']
    sys_bases = ['system_tp_rate','system_fp_rate']
    cond_sys = ['user_tp_given_system_signal_rate','user_tp_given_system_noise_rate']
    cols = bases + sys_bases + cond_sys

    ds_bases = []
    if has_ds:
        ds_bases = ['ds_tp_rate','ds_fp_rate','user_ds_agreement_rate',
                    'user_tp_given_ds_alarm_rate','user_tp_given_ds_no_alarm_rate']
        cols += ds_bases

    # rolling mean of p_signal as a "stimulus history" proxy
    if 'p_signal' in df.columns:
        cols += ['p_signal_mean']

    for w in ROLLING_WINDOWS:
        for c in cols:
            df[f'{c}_rolling_{w}'] = np.nan

    # Per-user strictly-shifted rolling
    for uid, sub in df.groupby('id', sort=False):
        s = sub.copy()
        for w in ROLLING_WINDOWS:
            s[f'signal_rate_rolling_{w}'] = s['target'].rolling(w, min_periods=1).mean().shift(1)
            s[f'tp_rate_rolling_{w}']     = s['tp'].rolling(w, min_periods=1).mean().shift(1)
            s[f'fp_rate_rolling_{w}']     = s['fp'].rolling(w, min_periods=1).mean().shift(1)

            s[f'system_tp_rate_rolling_{w}'] = s['system_tp'].rolling(w, min_periods=1).mean().shift(1)
            s[f'system_fp_rate_rolling_{w}'] = s['system_fp'].rolling(w, min_periods=1).mean().shift(1)

            s[f'user_tp_given_system_signal_rate_rolling_{w}'] = s['user_tp_given_system_signal'].rolling(w, min_periods=1).mean().shift(1)
            s[f'user_tp_given_system_noise_rate_rolling_{w}']  = s['user_tp_given_system_noise'].rolling(w, min_periods=1).mean().shift(1)

            if has_ds:
                s[f'ds_tp_rate_rolling_{w}'] = s['ds_tp'].rolling(w, min_periods=1).mean().shift(1)
                s[f'ds_fp_rate_rolling_{w}'] = s['ds_fp'].rolling(w, min_periods=1).mean().shift(1)
                s[f'user_ds_agreement_rate_rolling_{w}'] = s['user_ds_agreement'].rolling(w, min_periods=1).mean().shift(1)
                s[f'user_tp_given_ds_alarm_rate_rolling_{w}']    = s['user_tp_given_ds_alarm'].rolling(w, min_periods=1).mean().shift(1)
                s[f'user_tp_given_ds_no_alarm_rate_rolling_{w}'] = s['user_tp_given_ds_no_alarm'].rolling(w, min_periods=1).mean().shift(1)

            if 'p_signal' in s:
                s[f'p_signal_mean_rolling_{w}'] = s['p_signal'].rolling(w, min_periods=1).mean().shift(1)

        df.loc[s.index, s.columns] = s

    return df

# ---------------- SPLITS ----------------
def per_user_chrono_split(df, test_ratio=0.3, user_col='id', order_cols=('block','trial')):
    test_mask = np.zeros(len(df), dtype=bool)
    for _, sub in df.sort_values(list(order_cols)).groupby(user_col, sort=False):
        n = len(sub); t = max(1, int(np.floor(n*test_ratio)))
        test_mask[sub.index[-t:]] = True
    return np.flatnonzero(~test_mask), np.flatnonzero(test_mask)

def holdout_ids_split(df, user_col='id', train_ratio=0.7, seed=SEED):
    uids = df[user_col].dropna().unique()
    rng = np.random.RandomState(seed)
    rng.shuffle(uids)
    k = int(np.floor(len(uids)*train_ratio))
    train_ids = set(uids[:k]); test_ids = set(uids[k:])
    tr_idx = df.index[df[user_col].isin(train_ids)].values
    te_idx = df.index[df[user_col].isin(test_ids)].values
    return tr_idx, te_idx

def chrono_cv_splits_on_train(df_train, n_folds=3, user_col='id', order_cols=('block','trial')):
    df = df_train.sort_values(list(order_cols)).reset_index(drop=True)
    splits = []
    for k in range(1, n_folds):
        tr_idx, va_idx = [], []
        for _, sub in df.groupby(user_col, sort=False):
            n = len(sub)
            bins = np.linspace(0, n, n_folds + 1).astype(int)
            va_start, va_end = bins[k], bins[k+1]
            tr_idx.extend(sub.index[:va_start].tolist())
            if va_end > va_start:
                va_idx.extend(sub.index[va_start:va_end].tolist())
        splits.append((np.array(tr_idx), np.array(va_idx)))
    return splits

def carve_calibration_from_train(df_train, cal_ratio=0.1, user_col='id', order_cols=('block','trial')):
    df = df_train.sort_values(list(order_cols)).reset_index(drop=True)
    train_core, cal_hold = [], []
    for _, sub in df.groupby(user_col, sort=False):
        n = len(sub); c = max(1, int(np.floor(n*cal_ratio)))
        cal_hold.extend(sub.index[-c:].tolist())
        train_core.extend(sub.index[:-c].tolist())
    return np.array(train_core), np.array(cal_hold)

# ---------------- FEATURES & ABLATIONS ----------------
def build_feature_sets(df, block_type='DS'):
    # Base current-trial + meta (NO raw stimulus)
    base = [
        'p_signal',
        'trial','is_first_trial','block','is_first_block','purchase_ds_block_num',
        'system_d','dependency_num'
    ]
    if block_type.upper() == 'DS' and df['ds_recommends_signal'].notna().any():
        base.insert(1, 'ds_recommends_signal')  # after p_signal

    rolling_cols = [c for c in df.columns if 'rolling_' in c]
    features_full = [c for c in base + rolling_cols if c in df.columns]

    # Disjoint groups for "hard" ablations
    stim_hist = {c for c in df.columns if c.startswith('p_signal_mean_rolling_') or
                 c.startswith('system_tp_rate_rolling_') or
                 c.startswith('system_fp_rate_rolling_') or
                 c.startswith('user_tp_given_system_')}
    # DS-derived rolling
    ds_hist = {c for c in df.columns if c.startswith('ds_tp_rate_rolling_') or
               c.startswith('ds_fp_rate_rolling_') or
               c.startswith('user_ds_agreement_rate_rolling_') or
               c.startswith('user_tp_given_ds_')}

    # Build sets
    feat_sets = {
        'full': features_full,
        'no_stim': [f for f in features_full if f != 'p_signal'],
        'no_historical': [f for f in base if f in df.columns],
        'no_stim_hard': [f for f in features_full if f != 'p_signal' and f not in stim_hist],
    }
    if block_type.upper() == 'DS' and df['ds_recommends_signal'].notna().any():
        feat_sets['no_ds'] = [f for f in features_full if f != 'ds_recommends_signal']
        feat_sets['no_stim_and_ds'] = [f for f in features_full if f not in ('p_signal','ds_recommends_signal')]

    # Trim to requested counts:
    #  DS: use 5 variants (full, no_stim, no_ds, no_stim_and_ds, no_stim_hard, no_historical) -> pick 5
    #  NONDS: use 4 variants (full, no_stim, no_stim_hard, no_historical)
    if block_type.upper() == 'DS':
        order = ['full','no_stim','no_ds','no_stim_and_ds','no_stim_hard','no_historical']
        feat_sets = {k:feat_sets[k] for k in order if k in feat_sets}
    else:
        order = ['full','no_stim','no_stim_hard','no_historical']
        feat_sets = {k:feat_sets[k] for k in order if k in feat_sets}

    # Sanity: ensure no raw 'stimulus' sneaks in
    for k, vs in feat_sets.items():
        assert not any(v == 'stimulus' or v.startswith('stimulus_') for v in vs), f"Raw stimulus leaked into {k}"
    return feat_sets

# ---------------- PARAMS (CACHE) ----------------
def get_or_fit_best_params(key, X, y, cv_splits):
    store = load_params_store()
    if key in store:
        return store[key]
    grid = GridSearchCV(
        xgb.XGBClassifier(random_state=SEED, eval_metric='logloss', n_jobs=-1, tree_method='hist'),
        XGB_PARAM_GRID, cv=cv_splits, scoring='f1', n_jobs=-1, refit=True, verbose=1
    )
    grid.fit(X, y)
    best = grid.best_params_
    store[key] = best
    save_params_store(store)
    return best

# ---------------- LEAK CHECKS ----------------
def leak_checks(df_tr, df_te, feature_cols, tag):
    msgs = []
    roll_cols = [c for c in feature_cols if 'rolling_' in c]

    def check_first_trials(df, splitname):
        if not roll_cols:
            return
        first_trial_idx = df.groupby('id')['trial'].idxmin()
        bad = df.loc[first_trial_idx, roll_cols].notna().any(axis=None)
        if bad:
            msgs.append(f"{splitname}: rolling features non-NaN at user's first trial.")
        # also block boundary
        first_in_block_idx = df.sort_values(['id','block','trial']).groupby(['id','block']).head(1).index
        bad_block = df.loc[first_in_block_idx, roll_cols].notna().any(axis=None)
        if bad_block:
            msgs.append(f"{splitname}: rolling features non-NaN at first trial of some blocks.")
    check_first_trials(df_tr, 'Train')
    check_first_trials(df_te, 'Test')

    # disallow current event_type-derived columns (we only allow their *rolling* versions)
    ban = ['tp','fp','system_tp','system_fp','user_tp_given_system_signal','user_tp_given_system_noise',
           'ds_tp','ds_fp','user_ds_agreement','user_tp_given_ds_alarm','user_tp_given_ds_no_alarm']
    touched = [c for c in feature_cols if c in ban]
    if touched:
        msgs.append(f"Feature leak: current-event columns present: {touched}")

    if msgs:
        with open(OUT / f'leak_reports_{tag}.txt','w') as f:
            f.write("\n".join(msgs))
    else:
        with open(OUT / f'leak_reports_{tag}.txt','w') as f:
            f.write("No issues detected.")
    return msgs

# ---------------- TRAIN / EVAL ----------------
def train_eval_xgb(df, feature_cols, run_key, n_folds=3):
    # split
    split_mode = run_key['split_mode']
    if split_mode == 'pooled_chrono_70_30':
        tr_idx, te_idx = per_user_chrono_split(df, test_ratio=0.3)
    elif split_mode == 'holdout_ids_70_30':
        tr_idx, te_idx = holdout_ids_split(df, train_ratio=0.7)
    else:
        raise ValueError("Unknown split_mode")

    df_tr, df_te = df.iloc[tr_idx].copy(), df.iloc[te_idx].copy()

    # prior & p_signal
    prior_pi = df_tr['target'].mean()
    df_tr['p_signal'] = compute_p_signal(df_tr, prior_pi, center=CENTER_M)
    df_te['p_signal'] = compute_p_signal(df_te, prior_pi, center=CENTER_M)

    # rolling
    df_tr = add_rolling_features(df_tr)
    df_te = add_rolling_features(df_te)

    # leak checks
    tag_base = f"{run_key['block_type']}_{split_mode}_{run_key['ablation']}"
    leaks = leak_checks(df_tr, df_te, feature_cols, tag_base)
    if leaks:
        print(f"[Leak warnings] {tag_base}: {' | '.join(leaks)}")

    # matrices
    Xtr, ytr = df_tr[feature_cols], df_tr['target'].astype(int).values
    Xte, yte = df_te[feature_cols], df_te['target'].astype(int).values

    # calib carve & CV
    if CALIBRATE:
        tr_core_rel, cal_rel = carve_calibration_from_train(df_tr, cal_ratio=CAL_RATIO)
        Xtr_core, ytr_core = Xtr.iloc[tr_core_rel], ytr[tr_core_rel]
        Xcal, ycal = Xtr.iloc[cal_rel], ytr[cal_rel]
        cv_splits = chrono_cv_splits_on_train(df_tr.iloc[tr_core_rel], n_folds=n_folds)
        params_key = f"{run_key['block_type']}|{split_mode}|{run_key['ablation']}"
        best_params = get_or_fit_best_params(params_key, Xtr_core, ytr_core, cv_splits)
        base = xgb.XGBClassifier(random_state=SEED, eval_metric='logloss', n_jobs=-1, tree_method='hist', **best_params)
        base.fit(Xtr_core, ytr_core)
        clf = CalibratedClassifierCV(estimator=base, method=CAL_METHOD, cv='prefit')
        clf.fit(Xcal, ycal)
        cal_proba = clf.predict_proba(Xcal)[:, 1]
        t_star, _ = best_threshold_f1(ycal, cal_proba)
        base_est = base
    else:
        cv_splits = chrono_cv_splits_on_train(df_tr, n_folds=n_folds)
        params_key = f"{run_key['block_type']}|{split_mode}|{run_key['ablation']}"
        best_params = get_or_fit_best_params(params_key, Xtr, ytr, cv_splits)
        clf = xgb.XGBClassifier(random_state=SEED, eval_metric='logloss', n_jobs=-1, tree_method='hist', **best_params)
        clf.fit(Xtr, ytr)
        t_star = 0.5
        base_est = clf

    # predict
    proba = clf.predict_proba(Xte)[:, 1]
    pred05 = (proba >= 0.5).astype(int)
    predT  = (proba >= t_star).astype(int)

    # metrics
    acc = accuracy_score(yte, pred05)
    f1  = f1_score(yte, pred05, zero_division=0)
    prc = precision_score(yte, pred05, zero_division=0)
    rec = recall_score(yte, pred05)
    auc = roc_auc_score(yte, proba)
    ap  = average_precision_score(yte, proba)
    brier = brier_score_loss(yte, proba)
    ece = ece_score(yte, proba)

    acc_t = accuracy_score(yte, predT)
    f1_t  = f1_score(yte, predT, zero_division=0)
    prc_t = precision_score(yte, predT, zero_division=0)
    rec_t = recall_score(yte, predT)

    print(f"\n[{run_key['block_type']} | {split_mode} | {run_key['ablation']}] "
          f"n_train={len(ytr):,}, n_test={len(yte):,}, pi_train={df_tr['target'].mean():.3f}, pi_test={df_te['target'].mean():.3f}")
    print(f"  Acc={acc:.3f} | F1={f1:.3f} | Prec={prc:.3f} | Rec={rec:.3f} | AUC={auc:.3f} | AP={ap:.3f} | ECE={ece:.3f}")

    # plots & FI
    cm = confusion_matrix(yte, pred05)
    save_cm_plot(cm, tag_base); save_pr_cal_plots(yte, proba, tag_base)

    fi_df = None
    if hasattr(base_est, 'feature_importances_'):
        fi_df = (pd.DataFrame({'feature': feature_cols, 'importance': base_est.feature_importances_})
                 .sort_values('importance', ascending=False))
        fi_df.head(15).to_csv(OUT / f'feature_importance_top15_{tag_base}.csv', index=False)

    return {
        'tag': tag_base,
        'n_train': int(len(ytr)),
        'n_test': int(len(yte)),
        'p_signal_train': float(df_tr['target'].mean()),
        'p_signal_test': float(df_te['target'].mean()),
        'acc': acc, 'f1': f1, 'prec': prc, 'rec': rec,
        'auc': auc, 'ap': ap, 'brier': brier, 'ece': ece,
        'acc_tuned': acc_t, 'f1_tuned': f1_t, 'prec_tuned': prc_t, 'rec_tuned': rec_t, 'thresh': t_star,
    }

# ---------------- RUNNER ----------------
def run_block(block_type, split_mode):
    raw, agg = load_data()
    df = prepare_block(raw, agg, block_type=block_type)

    print_header(f"{block_type.upper()} BLOCKS — {split_mode} — base stats")
    print(f"Trials: {len(df):,} | Pos rate p(S): {df['target'].mean():.4f}")

    # Build features once (names), after a temporary p_signal + rolling to expose all columns
    tmp = df.copy()
    tmp_prior = tmp['target'].mean()
    tmp['p_signal'] = compute_p_signal(tmp, tmp_prior, center=CENTER_M)
    tmp = add_rolling_features(tmp)
    feature_sets = build_feature_sets(tmp, block_type=block_type)

    results = []
    for ablation, feats in feature_sets.items():
        run_key = {'block_type': block_type.upper(), 'split_mode': split_mode, 'ablation': ablation}
        res = train_eval_xgb(df.copy(), feats, run_key, n_folds=3)
        results.append(res)

    # Save summary
    summ = (pd.DataFrame(results)
              .sort_values(['tag'], ascending=True))
    out_csv = OUT / f"summary_{block_type.upper()}_{split_mode}.csv"
    summ.to_csv(out_csv, index=False)
    print("\n" + "="*74)
    print(f"SUMMARY SAVED → {out_csv}")
    print("="*74)

def main():
    # DS blocks
    run_block('DS', 'pooled_chrono_70_30')
    run_block('DS', 'holdout_ids_70_30')
    # NON-DS blocks
    run_block('NONDS', 'pooled_chrono_70_30')
    run_block('NONDS', 'holdout_ids_70_30')
    print_header(f"ALL DONE — results in {OUT}/")

if __name__ == '__main__':
    main()
