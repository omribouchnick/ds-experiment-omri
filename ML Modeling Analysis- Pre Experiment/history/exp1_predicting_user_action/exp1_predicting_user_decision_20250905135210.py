# Experiment 1 – within-user future prediction + ablations + robust dependency handling
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from sklearn.metrics import (
    confusion_matrix, roc_auc_score, precision_recall_curve, average_precision_score
)
from sklearn.calibration import calibration_curve
from sklearn.model_selection import GridSearchCV
import xgboost as xgb
import warnings
warnings.filterwarnings('ignore')
plt.switch_backend('Agg')

# Paths
RAW_PATH = 'data/exp1_raw.csv'
AGG_PATH = 'data/exp1_agg.csv'
OUT = Path('exp1_outputs'); OUT.mkdir(exist_ok=True)

# Load
raw_df = pd.read_csv(RAW_PATH)
agg_df = pd.read_csv(AGG_PATH)
raw_df.columns = raw_df.columns.str.lower().str.replace(' ', '_')
agg_df.columns = agg_df.columns.str.lower().str.replace(' ', '_')

# Filter DS trials and order
raw_df = raw_df.query('alert_system == 1').copy()
raw_df = raw_df.sort_values(['id','block','trial']).reset_index(drop=True)

# Labels and trial features
raw_df['target'] = (raw_df['user_action'] == 'S').astype(int)
raw_df['is_signal_event'] = (raw_df['event_type'] == 'S').astype(int)
raw_df['ds_recommends_signal'] = (raw_df['alarm_output'] == 'alarm').astype(int)
raw_df['ds_recommends_noise']  = (raw_df['alarm_output'] == 'no alarm').astype(int)
raw_df['agrees_with_ds'] = (raw_df['user_action'] == raw_df['alarm_output'].map({'alarm':'S','no alarm':'N'})).astype(int)
raw_df['agrees_with_ds_prev'] = raw_df.groupby('id')['agrees_with_ds'].shift(1).fillna(0)
raw_df['ds_was_correct'] = (raw_df['alarm_output'].map({'alarm':'S','no alarm':'N'}) == raw_df['event_type']).astype(int)
raw_df['user_was_correct'] = (raw_df['user_action'] == raw_df['event_type']).astype(int)
raw_df['tp'] = ((raw_df['user_action']=='S') & (raw_df['event_type']=='S')).astype(int)
raw_df['fp'] = ((raw_df['user_action']=='S') & (raw_df['event_type']=='N')).astype(int)
raw_df['tn'] = ((raw_df['user_action']=='N') & (raw_df['event_type']=='N')).astype(int)
raw_df['fn'] = ((raw_df['user_action']=='N') & (raw_df['event_type']=='S')).astype(int)

# Merge aggregated data (robust)
agg_df = agg_df.rename(columns={
    'how_much_did_the_automation_help_you_in_the_task?': 'help_score',
    'how_good_was_the_automation_in_distinguishing_between_blue_and_orange_vibranium_strains?': 'distinguishing_score'
})
if {'help_score','distinguishing_score'}.issubset(agg_df.columns):
    agg_df['avg_score'] = agg_df[['help_score','distinguishing_score']].mean(axis=1)
    agg_df['avg_score_prev_blocks'] = agg_df.groupby('id')['avg_score'].shift(1)
    agg_df = agg_df.drop(columns=[c for c in ['help_score','distinguishing_score','avg_score'] if c in agg_df.columns])

# Handle dependency column
dep_col = 'dependency' if 'dependency' in agg_df.columns else None
dep_map_num = {'independent':1,'low':2,'medium':3,'high':4,'full':5}

if dep_col is not None:
    agg_df['dependency_num'] = agg_df[dep_col].str.strip().str.lower().map(dep_map_num)

# Merge data
merge_cols = ['id','block','avg_score_prev_blocks']
if dep_col is not None: 
    merge_cols += [dep_col,'dependency_num']
merge_cols = [c for c in merge_cols if c in agg_df.columns]

merged_df = pd.merge(raw_df, agg_df[merge_cols].drop_duplicates(), on=['id','block'], how='left')

# Create dependency one-hots if available
dep_dummies = pd.DataFrame(index=merged_df.index)
if dep_col is not None and dep_col in merged_df.columns:
    dep_dummies = pd.get_dummies(merged_df[dep_col], prefix='dep')
    merged_df = pd.concat([merged_df, dep_dummies], axis=1)

# Rolling histories
rolling_windows = [1,3,7,14,21,50]
for w in rolling_windows:
    merged_df[f'signal_rate_rolling_{w}'] = np.nan
    merged_df[f'agreement_rate_rolling_{w}'] = np.nan
    merged_df[f'ds_correct_rate_rolling_{w}'] = np.nan
    merged_df[f'user_correct_rate_rolling_{w}'] = np.nan
    merged_df[f'tp_rate_rolling_{w}'] = np.nan
    merged_df[f'fp_rate_rolling_{w}'] = np.nan
    merged_df[f'fn_rate_rolling_{w}'] = np.nan
    merged_df[f'tn_rate_rolling_{w}'] = np.nan
    merged_df[f'stimulus_mean_rolling_{w}'] = np.nan
    merged_df[f'classification_time_mean_rolling_{w}'] = np.nan

for uid, idx in merged_df.groupby('id').indices.items():
    sub = merged_df.loc[idx].copy()
    for w in rolling_windows:
        sub[f'signal_rate_rolling_{w}'] = sub['target'].rolling(w, min_periods=1).mean().shift(1)
        sub[f'agreement_rate_rolling_{w}'] = sub['agrees_with_ds'].rolling(w, min_periods=1).mean().shift(1)
        sub[f'ds_correct_rate_rolling_{w}'] = sub['ds_was_correct'].rolling(w, min_periods=1).mean().shift(1)
        sub[f'user_correct_rate_rolling_{w}'] = sub['user_was_correct'].rolling(w, min_periods=1).mean().shift(1)
        sub[f'tp_rate_rolling_{w}'] = sub['tp'].rolling(w, min_periods=1).mean().shift(1)
        sub[f'fp_rate_rolling_{w}'] = sub['fp'].rolling(w, min_periods=1).mean().shift(1)
        sub[f'fn_rate_rolling_{w}'] = sub['fn'].rolling(w, min_periods=1).mean().shift(1)
        sub[f'tn_rate_rolling_{w}'] = sub['tn'].rolling(w, min_periods=1).mean().shift(1)
        if 'stimulus' in sub:
            sub[f'stimulus_mean_rolling_{w}'] = sub['stimulus'].rolling(w, min_periods=1).mean().shift(1)
        if 'classification_time' in sub:
            sub[f'classification_time_mean_rolling_{w}'] = sub['classification_time'].rolling(w, min_periods=1).mean().shift(1)
    merged_df.loc[idx, sub.columns] = sub

# Trial-level extras
merged_df['is_first_trial'] = (merged_df['trial'] == 1).astype(int)
merged_df['is_first_block'] = (merged_df['block'] == 1).astype(int)
merged_df['ds_confidence'] = (merged_df['stimulus'] - 0.5).abs()
merged_df['purchase_ds_block_num'] = merged_df.groupby('id')['block'].rank(method='dense')

# Feature lists (select only those that exist)
simple_cols = [
    'stimulus','ds_confidence','ds_recommends_signal','is_signal_event',
    'trial','is_first_trial','block','is_first_block','purchase_ds_block_num',
    'system_d','avg_score_prev_blocks'
]
if 'dependency_num' in merged_df.columns: simple_cols.append('dependency_num')
rolling_cols = (
    [f'signal_rate_rolling_{w}' for w in rolling_windows] +
    [f'agreement_rate_rolling_{w}' for w in rolling_windows] +
    [f'ds_correct_rate_rolling_{w}' for w in rolling_windows] +
    [f'user_correct_rate_rolling_{w}' for w in rolling_windows] +
    [f'tp_rate_rolling_{w}' for w in rolling_windows] +
    [f'fp_rate_rolling_{w}' for w in rolling_windows] +
    [f'fn_rate_rolling_{w}' for w in rolling_windows] +
    [f'tn_rate_rolling_{w}' for w in rolling_windows] +
    [f'stimulus_mean_rolling_{w}' for w in rolling_windows if f'stimulus_mean_rolling_{w}' in merged_df] +
    [f'classification_time_mean_rolling_{w}' for w in rolling_windows if f'classification_time_mean_rolling_{w}' in merged_df]
)
dep_cols = [c for c in merged_df.columns if c.startswith('dep_')]

feature_columns_all = [c for c in simple_cols + rolling_cols + dep_cols if c in merged_df.columns]
target = 'target'

# Agreement sanity
ds_sig_1 = (merged_df['ds_recommends_signal'] == 1)
agree = ((~ds_sig_1 & (merged_df['user_action'] == 'N')) | (ds_sig_1 & (merged_df['user_action'] == 'S'))).astype(int)
print(f"Agreement overall: {agree.sum():,}/{len(agree):,} = {agree.mean()*100:.2f}%")

# Per-user chronological split
def per_user_chrono_split(df, user_col='id', order_cols=('block','trial'), test_ratio=0.2):
    test_mask = np.zeros(len(df), dtype=bool)
    for uid, sub in df.sort_values(list(order_cols)).groupby(user_col, sort=False):
        n = len(sub); t = max(1, int(np.floor(n*test_ratio)))
        test_mask[sub.index[-t:]] = True
    train_idx = np.flatnonzero(~test_mask)
    test_idx  = np.flatnonzero(test_mask)
    return train_idx, test_idx

# Time-aware per-user CV on the training set
def chrono_cv_splits_on_train(df_train, user_col='id', order_cols=('block','trial'), n_folds=3):
    df = df_train.sort_values(list(order_cols)).reset_index(drop=True)
    splits = []
    for k in range(1, n_folds):  # (n_folds-1) splits
        tr_indices = []
        va_indices = []
        for _, sub in df.groupby(user_col, sort=False):
            n = len(sub)
            bins = np.linspace(0, n, n_folds+1).astype(int)
            va_start, va_end = bins[k], bins[k+1]
            tr_indices.extend(sub.index[:va_start].tolist())
            if va_end > va_start:
                va_indices.extend(sub.index[va_start:va_end].tolist())
        splits.append((tr_indices, va_indices))
    return splits

# Train + evaluate (optionally drop features for ablation)
def run_xgb_timeaware(df, features, drop=None, tag='full', test_ratio=0.2, n_folds=3):
    feats = [f for f in features if drop is None or f not in drop]
    X = df[feats]; y = df[target]
    tr_idx, te_idx = per_user_chrono_split(df, 'id', ('block','trial'), test_ratio=test_ratio)
    Xtr, ytr = X.iloc[tr_idx], y.iloc[tr_idx]
    Xte, yte = X.iloc[te_idx], y.iloc[te_idx]

    # Use simple 3-fold CV instead of time-aware CV
    grid = GridSearchCV(
        xgb.XGBClassifier(random_state=42, eval_metric='logloss', n_jobs=-1, tree_method='hist'),
        {
            'n_estimators':[100,200],
            'max_depth':[3,6],
            'learning_rate':[0.1,0.2],
            'subsample':[0.8,1.0]
        },
        cv=3, scoring='f1', n_jobs=-1, refit=True, verbose=0
    )
    grid.fit(Xtr, ytr)
    model = grid.best_estimator_

    p = model.predict(Xte)
    proba = model.predict_proba(Xte)[:,1]
    acc = (p == yte).mean()
    f1  = (2 * ( (p & yte).sum() )) / ( (p.sum() + yte.sum()) ) if (p.sum()+yte.sum())>0 else 0
    auc = roc_auc_score(yte, proba)
    cm  = confusion_matrix(yte, p)

    fi = pd.DataFrame({'feature': feats, 'importance': model.feature_importances_}).sort_values('importance', ascending=False)
    fi.to_csv(OUT / f'feature_importance_{tag}.csv', index=False)

    # Plots
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

    pr_true, pr_pred = calibration_curve(yte, proba, n_bins=10, strategy='quantile')
    fig, ax = plt.subplots(figsize=(5,4))
    ax.plot([0,1],[0,1],'--',lw=1)
    ax.plot(pr_pred, pr_true, marker='o')
    ax.set(xlabel='Predicted probability', ylabel='Observed positive rate', title=f'Calibration — {tag}')
    fig.tight_layout(); fig.savefig(OUT / f'cal_{tag}.png', dpi=200); plt.close(fig)

    # Agreement vs DS confidence on test
    test_df = df.iloc[te_idx].copy()
    test_df['ds_confidence'] = (test_df['stimulus'] - 0.5).abs()
    test_df['agree'] = ((test_df['ds_recommends_signal']==1) & (test_df['user_action']=='S')) | \
                       ((test_df['ds_recommends_signal']==0) & (test_df['user_action']=='N'))
    test_df['conf_bin'] = pd.cut(test_df['ds_confidence'], bins=[0,0.1,0.2,0.3,0.4,0.5], right=False)
    by_conf = test_df.groupby('conf_bin')['agree'].mean()
    fig, ax = plt.subplots(figsize=(6,3))
    ax.plot(range(len(by_conf)), by_conf.values, marker='o')
    ax.set_xticks(range(len(by_conf))); ax.set_xticklabels(by_conf.index.astype(str), rotation=45)
    ax.set_ylim(0,1); ax.set_ylabel('Agreement'); ax.set_title(f'Agreement vs DS confidence — {tag}')
    fig.tight_layout(); fig.savefig(OUT / f'agree_vs_conf_{tag}.png', dpi=200); plt.close(fig)

    # Per-user agreement distribution in test
    per_user = test_df.groupby('id')['agree'].mean()
    fig, ax = plt.subplots(figsize=(6,3))
    ax.hist(per_user.values, bins=20)
    ax.set(xlabel='Agreement', ylabel='Users', title=f'Per-user agreement (test) — {tag}')
    fig.tight_layout(); fig.savefig(OUT / f'agree_users_{tag}.png', dpi=200); plt.close(fig)

    print(f"[{tag}] Acc={acc:.4f}  F1={f1:.4f}  AUC={auc:.4f}  Best={grid.best_params_}")
    return {'acc':acc,'f1':f1,'auc':auc,'cm':cm,'fi':fi,'model':model}

# Full model
res_full = run_xgb_timeaware(merged_df, feature_columns_all, drop=None, tag='full')

# Ablations
res_no_stim = run_xgb_timeaware(merged_df, feature_columns_all, drop=['stimulus'], tag='no_stimulus')
res_no_stim_norec = run_xgb_timeaware(merged_df, feature_columns_all, drop=['stimulus','ds_recommends_signal'], tag='no_stimulus_no_dsrec')

# Rolling-window study (cumulative: {1}, {1,3}, {1,3,7}, ...)
def keep_windows(features, windows_keep):
    out = []
    for f in features:
        if 'rolling_' not in f:
            out.append(f)
            continue
        keep = False
        for w in windows_keep:
            if f.endswith(f'_{w}'):
                keep = True; break
        if keep: out.append(f)
    return out

cumulative_sets = [[1],[1,3],[1,3,7],[1,3,7,14],[1,3,7,14,21],[1,3,7,14,21,50]]
win_results = []
for ws in cumulative_sets:
    feats = keep_windows(feature_columns_all, ws)
    r = run_xgb_timeaware(merged_df, feats, drop=None, tag=f'windows_{"-".join(map(str,ws))}')
    win_results.append((tuple(ws), r['acc'], r['f1'], r['auc']))

pd.DataFrame(win_results, columns=['windows','acc','f1','auc']).to_csv(OUT/'rolling_window_study.csv', index=False)
print("Saved rolling_window_study.csv")
