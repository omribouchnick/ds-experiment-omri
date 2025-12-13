# Experiment 1 – within-user future prediction (leakage-safe) + ablations
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from sklearn.metrics import (
    accuracy_score, f1_score, precision_score, recall_score,
    confusion_matrix, roc_auc_score, precision_recall_curve, average_precision_score
)
from sklearn.calibration import calibration_curve
from sklearn.model_selection import GridSearchCV
import xgboost as xgb
import warnings
warnings.filterwarnings('ignore')
plt.switch_backend('Agg')

# ----------------------------- Paths -----------------------------
RAW_PATH = 'data/exp1_raw.csv'
AGG_PATH = 'data/exp1_agg.csv'
OUT = Path('exp1_outputs'); OUT.mkdir(exist_ok=True)

# ----------------------------- Load ------------------------------
raw_df = pd.read_csv(RAW_PATH)
agg_df = pd.read_csv(AGG_PATH)
raw_df.columns = raw_df.columns.str.lower().str.replace(' ', '_')
agg_df.columns = agg_df.columns.str.lower().str.replace(' ', '_')

# ----------------------- Filter & sort ---------------------------
raw_df = raw_df.query('alert_system == 1').copy()
raw_df = raw_df.sort_values(['id','block','trial']).reset_index(drop=True)

# ------------------------ Targets & core -------------------------
raw_df['target'] = (raw_df['user_action'] == 'S').astype(int)
# normalize alarm_output values (IMPORTANT)
raw_df['alarm_output_norm'] = raw_df['alarm_output'].astype(str).str.strip().str.lower()

raw_df['is_signal_event']       = (raw_df['event_type'] == 'S').astype(int)                # keep for "oracle" ablation only
raw_df['ds_recommends_signal']  = (raw_df['alarm_output_norm'] == 'alarm').astype(int)
raw_df['ds_recommends_noise']   = (raw_df['alarm_output_norm'] == 'no alarm').astype(int)

raw_df['agrees_with_ds'] = (
    (raw_df['user_action'] == 'S') & (raw_df['ds_recommends_signal'] == 1) |
    (raw_df['user_action'] == 'N') & (raw_df['ds_recommends_noise']  == 1)
).astype(int)
raw_df['agrees_with_ds_prev'] = raw_df.groupby('id')['agrees_with_ds'].shift(1).fillna(0)

raw_df['ds_was_correct'] = (
    raw_df['alarm_output_norm'].map({'alarm':'S','no alarm':'N'}) == raw_df['event_type']
).astype(int)
raw_df['user_was_correct'] = (raw_df['user_action'] == raw_df['event_type']).astype(int)

raw_df['tp'] = ((raw_df['user_action']=='S') & (raw_df['event_type']=='S')).astype(int)
raw_df['fp'] = ((raw_df['user_action']=='S') & (raw_df['event_type']=='N')).astype(int)
raw_df['tn'] = ((raw_df['user_action']=='N') & (raw_df['event_type']=='N')).astype(int)
raw_df['fn'] = ((raw_df['user_action']=='N') & (raw_df['event_type']=='S')).astype(int)

# ------------------------ Merge aggregated -----------------------
agg_df = agg_df.rename(columns={
    'how_much_did_the_automation_help_you_in_the_task?': 'help_score',
    'how_good_was_the_automation_in_distinguishing_between_blue_and_orange_vibranium_strains?': 'distinguishing_score'
})
if {'help_score','distinguishing_score'}.issubset(agg_df.columns):
    agg_df['avg_score'] = agg_df[['help_score','distinguishing_score']].mean(axis=1)
    agg_df['avg_score_prev_blocks'] = agg_df.groupby('id')['avg_score'].shift(1)
    agg_df = agg_df.drop(columns=[c for c in ['help_score','distinguishing_score','avg_score'] if c in agg_df.columns])

dep_col = None
for cand in ['dependency','dependency_agg','dep','user_dependency','dependency_level']:
    if cand in agg_df.columns: dep_col = cand; break

dep_map_num = {'independent':1,'low':2,'medium':3,'high':4,'full':5}
if dep_col is not None:
    agg_df['dependency_num'] = agg_df[dep_col].astype(str).str.strip().str.lower().map(dep_map_num)

merge_cols = ['id','block','avg_score_prev_blocks']
if dep_col is not None: merge_cols += [dep_col,'dependency_num']
merge_cols = [c for c in merge_cols if c in agg_df.columns]

merged_df = pd.merge(raw_df, agg_df[merge_cols].drop_duplicates(), on=['id','block'], how='left')
if dep_col is not None and dep_col in merged_df.columns:
    merged_df = pd.concat([merged_df, pd.get_dummies(merged_df[dep_col], prefix='dep')], axis=1)

# ----------------------- Rolling histories -----------------------
rolling_windows = [1,3,7,14,21,50]
# pre-create columns
for w in rolling_windows:
    for base in [
        'signal_rate','agreement_rate','ds_correct_rate','user_correct_rate',
        'tp_rate','fp_rate','fn_rate','tn_rate','stimulus_mean','classification_time_mean'
    ]:
        merged_df[f'{base}_rolling_{w}'] = np.nan

# fill per-user, shifted by 1 (no leakage)
for uid, idx in merged_df.groupby('id').indices.items():
    sub = merged_df.loc[idx].copy()
    for w in rolling_windows:
        sub[f'signal_rate_rolling_{w}']           = sub['target'].rolling(w, min_periods=1).mean().shift(1)
        sub[f'agreement_rate_rolling_{w}']        = sub['agrees_with_ds'].rolling(w, min_periods=1).mean().shift(1)
        sub[f'ds_correct_rate_rolling_{w}']       = sub['ds_was_correct'].rolling(w, min_periods=1).mean().shift(1)
        sub[f'user_correct_rate_rolling_{w}']     = sub['user_was_correct'].rolling(w, min_periods=1).mean().shift(1)
        sub[f'tp_rate_rolling_{w}']               = sub['tp'].rolling(w, min_periods=1).mean().shift(1)
        sub[f'fp_rate_rolling_{w}']               = sub['fp'].rolling(w, min_periods=1).mean().shift(1)
        sub[f'fn_rate_rolling_{w}']               = sub['fn'].rolling(w, min_periods=1).mean().shift(1)
        sub[f'tn_rate_rolling_{w}']               = sub['tn'].rolling(w, min_periods=1).mean().shift(1)
        if 'stimulus' in sub:
            sub[f'stimulus_mean_rolling_{w}']     = sub['stimulus'].rolling(w, min_periods=1).mean().shift(1)
        if 'classification_time' in sub:
            sub[f'classification_time_mean_rolling_{w}'] = sub['classification_time'].rolling(w, min_periods=1).mean().shift(1)
    merged_df.loc[idx, sub.columns] = sub

# ---------------------- Trial-level extras ----------------------
merged_df['is_first_trial'] = (merged_df['trial'] == 1).astype(int)
merged_df['is_first_block'] = (merged_df['block'] == 1).astype(int)
merged_df['ds_confidence']  = (merged_df['stimulus'] - 0.5).abs()
merged_df['purchase_ds_block_num'] = merged_df.groupby('id')['block'].rank(method='dense')

# ----------------------- Feature sets ---------------------------
# No-leak base: exclude is_signal_event
base_simple = [
    'stimulus','ds_confidence','ds_recommends_signal',
    'trial','is_first_trial','block','is_first_block','purchase_ds_block_num',
    'system_d','avg_score_prev_blocks'
]
if 'dependency_num' in merged_df.columns:
    base_simple.append('dependency_num')
dep_cols = [c for c in merged_df.columns if c.startswith('dep_')]
rolling_cols = [c for c in merged_df.columns if 'rolling_' in c]

FEATURES_NO_LEAK = [c for c in base_simple + dep_cols + rolling_cols if c in merged_df.columns]
FEATURES_ORACLE  = FEATURES_NO_LEAK + (['is_signal_event'] if 'is_signal_event' in merged_df.columns else [])

TARGET = 'target'

# ---------------------- Agreement sanity check ------------------
agree = (
    ((merged_df['ds_recommends_signal']==1) & (merged_df['user_action']=='S')) |
    ((merged_df['ds_recommends_signal']==0) & (merged_df['user_action']=='N'))
).astype(int)
print(f"Agreement overall: {agree.sum():,}/{len(agree):,} = {agree.mean()*100:.2f}%")

# -------------------- Chronological split utils ----------------
def per_user_chrono_split(df, user_col='id', order_cols=('block','trial'), test_ratio=0.2):
    test_mask = np.zeros(len(df), dtype=bool)
    for _, sub in df.sort_values(list(order_cols)).groupby(user_col, sort=False):
        n = len(sub); t = max(1, int(np.floor(n*test_ratio)))
        test_mask[sub.index[-t:]] = True
    train_idx = np.flatnonzero(~test_mask)
    test_idx  = np.flatnonzero(test_mask)
    return train_idx, test_idx

def chrono_cv_splits_on_train(df_train, user_col='id', order_cols=('block','trial'), n_folds=3):
    df = df_train.sort_values(list(order_cols)).reset_index(drop=True)
    # return splits as lists of indices relative to df_train (0..len-1)
    splits = []
    # Map original index to 0..len-1
    pos = {idx:i for i,idx in enumerate(df.index)}
    for k in range(1, n_folds):  # yields (n_folds-1) folds
        tr_idx_rel, va_idx_rel = [], []
        for _, sub in df.groupby(user_col, sort=False):
            n = len(sub)
            bins = np.linspace(0, n, n_folds+1).astype(int)
            va_start, va_end = bins[k], bins[k+1]
            tr_idx_rel.extend(sub.index[:va_start].tolist())
            if va_end > va_start:
                va_idx_rel.extend(sub.index[va_start:va_end].tolist())
        splits.append((np.array(tr_idx_rel), np.array(va_idx_rel)))
    return splits

# --------------------- Train/eval function ---------------------
def train_eval_xgb(df, feature_cols, tag, test_ratio=0.2, n_folds=3):
    X = df[feature_cols]; y = df[TARGET]
    tr_full, te_full = per_user_chrono_split(df, 'id', ('block','trial'), test_ratio=test_ratio)
    Xtr, ytr = X.iloc[tr_full], y.iloc[tr_full]
    Xte, yte = X.iloc[te_full], y.iloc[te_full]

    # build time-aware CV splits relative to Xtr
    train_df_for_cv = df.iloc[tr_full].copy()
    cv_rel = chrono_cv_splits_on_train(train_df_for_cv, 'id', ('block','trial'), n_folds=n_folds)
    # map relative (0..len(train)-1) to absolute positions in Xtr (which is already 0..len-1)
    cv_splits = cv_rel  # they already index into Xtr

    grid = GridSearchCV(
        xgb.XGBClassifier(random_state=42, eval_metric='logloss', n_jobs=-1, tree_method='hist'),
        {'n_estimators':[100,200], 'max_depth':[3,6], 'learning_rate':[0.1,0.2], 'subsample':[0.8,1.0]},
        cv=cv_splits, scoring='f1', n_jobs=-1, refit=True, verbose=0
    )
    grid.fit(Xtr, ytr)
    model = grid.best_estimator_

    p = model.predict(Xte)
    proba = model.predict_proba(Xte)[:,1]
    acc  = accuracy_score(yte, p)
    f1   = f1_score(yte, p)
    prc  = precision_score(yte, p, zero_division=0)
    rec  = recall_score(yte, p)
    auc  = roc_auc_score(yte, proba)
    cm   = confusion_matrix(yte, p)

    fi = (pd.DataFrame({'feature': feature_cols, 'importance': model.feature_importances_})
            .sort_values('importance', ascending=False))
    fi.to_csv(OUT / f'feature_importance_{tag}.csv', index=False)

    # ---- Plots ----
    cmn = cm.astype(float) / cm.sum(axis=1, keepdims=True)
    fig, ax = plt.subplots(figsize=(4,4))
    im = ax.imshow(cmn, cmap='Blues', vmin=0, vmax=1)
    ax.set(xticks=[0,1], yticks=[0,1], xticklabels=['Noise','Signal'], yticklabels=['Noise','Signal'],
           xlabel='Predicted', ylabel='True', title=f'Confusion (norm) — {tag}')
    for (i,j), v in np.ndenumerate(cmn): ax.text(j,i,f'{v:.2f}',ha='center',va='center',fontsize=10)
    fig.tight_layout(); fig.savefig(OUT / f'cm_norm_{tag}.png', dpi=200); plt.close(fig)

    pr_p, pr_r, _ = precision_recall_curve(yte, proba)
    ap = average_precision_score(yte, proba)
    fig, ax = plt.subplots(figsize=(5,4))
    ax.plot(pr_r, pr_p)
    ax.set(xlabel='Recall', ylabel='Precision', title=f'Precision–Recall (AP={ap:.3f}) — {tag}')
    fig.tight_layout(); fig.savefig(OUT / f'pr_{tag}.png', dpi=200); plt.close(fig)

    prob_true, prob_pred = calibration_curve(yte, proba, n_bins=10, strategy='quantile')
    fig, ax = plt.subplots(figsize=(5,4))
    ax.plot([0,1],[0,1],'--',lw=1)
    ax.plot(prob_pred, prob_true, marker='o')
    ax.set(xlabel='Predicted probability', ylabel='Observed positive rate', title=f'Calibration — {tag}')
    fig.tight_layout(); fig.savefig(OUT / f'cal_{tag}.png', dpi=200); plt.close(fig)

    # Agreement vs DS confidence on test
    test_df = df.iloc[te_full].copy()
    test_df['ds_confidence'] = (test_df['stimulus'] - 0.5).abs()
    test_df['agree'] = (
        ((test_df['ds_recommends_signal']==1) & (test_df['user_action']=='S')) |
        ((test_df['ds_recommends_signal']==0) & (test_df['user_action']=='N'))
    )
    test_df['conf_bin'] = pd.cut(test_df['ds_confidence'], bins=[0,0.1,0.2,0.3,0.4,0.5], right=False)
    by_conf = test_df.groupby('conf_bin')['agree'].mean()
    fig, ax = plt.subplots(figsize=(6,3))
    ax.plot(range(len(by_conf)), by_conf.values, marker='o')
    ax.set_xticks(range(len(by_conf))); ax.set_xticklabels(by_conf.index.astype(str), rotation=45)
    ax.set_ylim(0,1); ax.set_ylabel('Agreement'); ax.set_title(f'Agreement vs DS confidence — {tag}')
    fig.tight_layout(); fig.savefig(OUT / f'agree_vs_conf_{tag}.png', dpi=200); plt.close(fig)

    print(f"[{tag}] Acc={acc:.4f}  F1={f1:.4f}  Prec={prc:.4f}  Rec={rec:.4f}  AUC={auc:.4f}  Best={grid.best_params_}")
    return {'acc':acc,'f1':f1,'prec':prc,'rec':rec,'auc':auc,'cm':cm,'fi':fi,'model':model}

# --------------------------- Runs ------------------------------
# 1) Main, leakage-safe features
res_full = train_eval_xgb(merged_df, FEATURES_NO_LEAK, tag='full')

# 2) Ablations
res_no_stim             = train_eval_xgb(merged_df, [f for f in FEATURES_NO_LEAK if f != 'stimulus'], tag='no_stimulus')
res_no_stim_no_dsrec    = train_eval_xgb(merged_df, [f for f in FEATURES_NO_LEAK if f not in ['stimulus','ds_recommends_signal']], tag='no_stimulus_no_dsrec')

# 3) Oracle/leak (for reference ONLY) – includes true event label
if 'is_signal_event' in merged_df.columns:
    res_oracle = train_eval_xgb(merged_df, FEATURES_ORACLE, tag='oracle_leak')

# 4) Rolling-window study (cumulative)
def keep_windows(features, windows_keep):
    out = []
    for f in features:
        if 'rolling_' not in f: out.append(f); continue
        if any(f.endswith(f'_{w}') for w in windows_keep): out.append(f)
    return out

cumulative_sets = [[1],[1,3],[1,3,7],[1,3,7,14],[1,3,7,14,21],[1,3,7,14,21,50]]
rows = []
for ws in cumulative_sets:
    feats = keep_windows(FEATURES_NO_LEAK, ws)
    r = train_eval_xgb(merged_df, feats, tag=f'windows_{"-".join(map(str,ws))}')
    rows.append((tuple(ws), r['acc'], r['f1'], r['auc']))

pd.DataFrame(rows, columns=['windows','acc','f1','auc']).to_csv(OUT/'rolling_window_study.csv', index=False)
print("Saved rolling_window_study.csv")
