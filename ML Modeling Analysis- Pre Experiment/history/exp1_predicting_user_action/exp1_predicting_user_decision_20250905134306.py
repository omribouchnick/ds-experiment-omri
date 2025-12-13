# Experiment 1 – updated: within-user future prediction + ablations
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from sklearn.metrics import (
    classification_report, confusion_matrix, roc_auc_score, precision_recall_curve,
    average_precision_score, RocCurveDisplay
)
from sklearn.calibration import calibration_curve
from sklearn.model_selection import GridSearchCV
import xgboost as xgb
import warnings
warnings.filterwarnings('ignore')
plt.switch_backend('Agg')

# ----------------------------- I/O -----------------------------
raw_path = 'data/exp1_raw.csv'
agg_path = 'data/exp1_agg.csv'
outdir = Path('exp1_outputs'); outdir.mkdir(exist_ok=True)

# ----------------------------- Load ----------------------------
raw_df = pd.read_csv(raw_path)
agg_df = pd.read_csv(agg_path)

raw_df.columns = raw_df.columns.str.lower().str.replace(' ', '_')
agg_df.columns = agg_df.columns.str.lower().str.replace(' ', '_')

raw_df = raw_df.query('alert_system == 1').copy()
raw_df = raw_df.sort_values(['id','block','trial']).reset_index(drop=True)

# ---------------------- Targets & core cols --------------------
raw_df['target'] = (raw_df['user_action'] == 'S').astype(int)
raw_df['is_signal_event'] = (raw_df['event_type'] == 'S').astype(int)
raw_df['ds_recommends_signal'] = (raw_df['alarm_output'] == 'Alarm').astype(int)
raw_df['ds_recommends_noise']  = (raw_df['alarm_output'] == 'No Alarm').astype(int)

raw_df['agrees_with_ds'] = (raw_df['user_action'] == raw_df['alarm_output'].map({'Alarm':'S','No Alarm':'N'})).astype(int)
raw_df['agrees_with_ds_prev'] = raw_df.groupby('id')['agrees_with_ds'].shift(1).fillna(0)

raw_df['ds_was_correct'] = (raw_df['alarm_output'].map({'Alarm':'S','No Alarm':'N'}) == raw_df['event_type']).astype(int)
raw_df['user_was_correct'] = (raw_df['user_action'] == raw_df['event_type']).astype(int)

raw_df['tp'] = ((raw_df['user_action'] == 'S') & (raw_df['event_type'] == 'S')).astype(int)
raw_df['fp'] = ((raw_df['user_action'] == 'S') & (raw_df['event_type'] == 'N')).astype(int)
raw_df['tn'] = ((raw_df['user_action'] == 'N') & (raw_df['event_type'] == 'N')).astype(int)
raw_df['fn'] = ((raw_df['user_action'] == 'N') & (raw_df['event_type'] == 'S')).astype(int)

# -------------------------- Merge agg --------------------------
agg_df = agg_df.rename(columns={
    'how_much_did_the_automation_help_you_in_the_task?': 'help_score',
    'how_good_was_the_automation_in_distinguishing_between_blue_and_orange_vibranium_strains?': 'distinguishing_score'
})
if {'help_score','distinguishing_score'}.issubset(agg_df.columns):
    agg_df['avg_score'] = agg_df[['help_score','distinguishing_score']].mean(axis=1)
    agg_df['avg_score_prev_blocks'] = agg_df.groupby('id')['avg_score'].shift(1)
    agg_df = agg_df.drop(columns=[c for c in ['help_score','distinguishing_score','avg_score'] if c in agg_df.columns])

dep_map_num = {'Independent':1,'Low':2,'Medium':3,'High':4,'Full':5}
if 'dependency' in agg_df.columns:
    agg_df['dependency_num'] = agg_df['dependency'].map(dep_map_num)

merged_df = pd.merge(
    raw_df,
    agg_df[['id','block','dependency','avg_score_prev_blocks','dependency_num']].drop_duplicates(),
    on=['id','block'], how='left'
)
dep_dummies = pd.get_dummies(merged_df['dependency'], prefix='dep')
merged_df = pd.concat([merged_df, dep_dummies], axis=1)

# -------------------- Rolling histories (once) -----------------
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

# --------------------- Trial-level extras ---------------------
merged_df['is_first_trial'] = (merged_df['trial'] == 1).astype(int)
merged_df['is_first_block'] = (merged_df['block'] == 1).astype(int)
merged_df['ds_confidence'] = (merged_df['stimulus'] - 0.5).abs()
merged_df['purchase_ds_block_num'] = merged_df.groupby('id')['block'].rank(method='dense')

# ----------------------- Features list ------------------------
simple_cols = [
    'stimulus','ds_confidence','ds_recommends_signal','is_signal_event',
    'trial','is_first_trial','block','is_first_block','purchase_ds_block_num',
    'system_d','dependency_num','avg_score_prev_blocks'
]
rolling_cols = (
    [f'signal_rate_rolling_{w}' for w in rolling_windows] +
    [f'agreement_rate_rolling_{w}' for w in rolling_windows] +
    [f'ds_correct_rate_rolling_{w}' for w in rolling_windows] +
    [f'user_correct_rate_rolling_{w}' for w in rolling_windows] +
    [f'tp_rate_rolling_{w}' for w in rolling_windows] +
    [f'fp_rate_rolling_{w}' for w in rolling_windows] +
    [f'fn_rate_rolling_{w}' for w in rolling_windows] +
    [f'tn_rate_rolling_{w}' for w in rolling_windows] +
    [f'stimulus_mean_rolling_{w}' for w in rolling_windows] +
    [f'classification_time_mean_rolling_{w}' for w in rolling_windows]
)
dep_cols = [c for c in merged_df.columns if c.startswith('dep_')]

feature_columns_all = [c for c in simple_cols + rolling_cols + dep_cols if c in merged_df.columns]
target = 'target'

# -------------------- Agreement numbers -----------------------
ds_sig_1 = (merged_df['ds_recommends_signal'] == 1)
agree = ((~ds_sig_1 & (merged_df['user_action'] == 'N')) | (ds_sig_1 & (merged_df['user_action'] == 'S'))).astype(int)
overall_agree = agree.mean()
count_agree = int(agree.sum())
count_total = int(agree.shape[0])

print(f"Agreement: {count_agree}/{count_total} = {overall_agree*100:.2f}%")

# ================= Splitting helpers (no leakage) =============

def per_user_chrono_split(df, user_col='id', order_cols=('block','trial'), test_ratio=0.2):
    test_mask = np.zeros(len(df), dtype=bool)
    for uid, sub in df.sort_values(list(order_cols)).groupby(user_col, sort=False):
        n = len(sub)
        t = max(1, int(np.floor(n * test_ratio)))
        test_idx = sub.index[-t:]
        test_mask[df.index.get_indexer_for(test_idx)] = True
    train_idx = np.where(~test_mask)[0]
    test_idx = np.where(test_mask)[0]
    return train_idx, test_idx

def chrono_cv_splits(df, user_col='id', order_cols=('block','trial'), n_folds=3):
    # fold k validates on the kth time bin per user; trains on all previous bins
    df = df.copy()
    df['_order'] = df.groupby(user_col).cumcount()
    splits = []
    for k in range(1, n_folds):  # yields (n_folds-1) folds
        train_mask = np.zeros(len(df), dtype=bool)
        val_mask = np.zeros(len(df), dtype=bool)
        for uid, sub in df.sort_values(list(order_cols)).groupby(user_col, sort=False):
            bins = np.linspace(0, len(sub), n_folds+1).astype(int)
            val_range = range(bins[k], bins[k+1])
            val_idx = sub.index[list(val_range)] if len(val_range)>0 else []
            train_idx = sub.index[:bins[k]]
            val_mask[df.index.get_indexer_for(val_idx)] = True
            train_mask[df.index.get_indexer_for(train_idx)] = True
        splits.append((
            np.where(train_mask)[0],
            np.where(val_mask)[0]
        ))
    return splits

# --------------------- Train/eval function --------------------
def train_xgb_with_timecv(df, features, drop_features=None, test_ratio=0.2, n_folds=3, tag='full'):
    use_features = [f for f in features if drop_features is None or f not in drop_features]
    X = df[use_features]
    y = df[target]

    train_idx, test_idx = per_user_chrono_split(df, 'id', ('block','trial'), test_ratio=test_ratio)
    X_train, y_train = X.iloc[train_idx], y.iloc[train_idx]
    X_test,  y_test  = X.iloc[test_idx],  y.iloc[test_idx]

    cv_splits = chrono_cv_splits(df.iloc[train_idx].assign(_row_ix=np.arange(len(train_idx))).set_index('_row_ix'),
                                 user_col='id', order_cols=('block','trial'), n_folds=n_folds)
    # Remap split indices to absolute indices
    mapped_splits = []
    for tr_rel, va_rel in cv_splits:
        mapped_splits.append((train_idx[tr_rel], train_idx[va_rel]))

    param_grid = {
        'n_estimators': [100, 200],
        'max_depth': [3, 6],
        'learning_rate': [0.1, 0.2],
        'subsample': [0.8, 1.0]
    }
    model = xgb.XGBClassifier(
        random_state=42, eval_metric='logloss', n_jobs=-1, tree_method='hist'
    )
    grid = GridSearchCV(
        estimator=model, param_grid=param_grid, cv=mapped_splits,
        scoring='f1', n_jobs=-1, verbose=0, refit=True
    )
    grid.fit(X_train, y_train)

    y_pred = grid.predict(X_test)
    y_proba = grid.predict_proba(X_test)[:,1]
    acc = (y_pred == y_test).mean()
    f1 = (2 * ( (y_pred & y_test).sum() ) ) / ( (y_pred.sum() + y_test.sum()) ) if (y_pred.sum() + y_test.sum())>0 else 0
    auc = roc_auc_score(y_test, y_proba)
    cm = confusion_matrix(y_test, y_pred)

    fi = pd.DataFrame({'feature': use_features, 'importance': grid.best_estimator_.feature_importances_}) \
         .sort_values('importance', ascending=False)

    print(f"[{tag}] Test Acc={acc:.4f}, F1={f1:.4f}, AUC={auc:.4f}, Best={grid.best_params_}")

    # saving plots
    # normalized confusion
    cmn = cm.astype(float) / cm.sum(axis=1, keepdims=True)
    fig, ax = plt.subplots(figsize=(4,4))
    im = ax.imshow(cmn, interpolation='nearest', cmap='Blues')
    ax.figure.colorbar(im, ax=ax)
    ax.set(xticks=[0,1], yticks=[0,1], xticklabels=['Noise','Signal'], yticklabels=['Noise','Signal'],
           ylabel='True', xlabel='Predicted', title=f'Confusion (norm) — {tag}')
    for (i,j), v in np.ndenumerate(cmn):
        ax.text(j,i, f'{v:.2f}', ha='center', va='center', fontsize=10)
    fig.tight_layout()
    fig.savefig(outdir / f'cm_norm_{tag}.png', dpi=200)
    plt.close(fig)

    # PR curve
    p, r, thr = precision_recall_curve(y_test, y_proba)
    ap = average_precision_score(y_test, y_proba)
    fig, ax = plt.subplots(figsize=(5,4))
    ax.plot(r, p)
    ax.set_xlabel('Recall'); ax.set_ylabel('Precision')
    ax.set_title(f'Precision–Recall (AP={ap:.3f}) — {tag}')
    fig.tight_layout()
    fig.savefig(outdir / f'pr_{tag}.png', dpi=200)
    plt.close(fig)

    # Calibration
    prob_true, prob_pred = calibration_curve(y_test, y_proba, n_bins=10, strategy='quantile')
    fig, ax = plt.subplots(figsize=(5,4))
    ax.plot([0,1],[0,1],'--', linewidth=1)
    ax.plot(prob_pred, prob_true, marker='o')
    ax.set_xlabel('Predicted probability'); ax.set_ylabel('Observed positive rate')
    ax.set_title(f'Calibration — {tag}')
    fig.tight_layout()
    fig.savefig(outdir / f'cal_{tag}.png', dpi=200)
    plt.close(fig)

    # per-user agreement distribution
    test_users = merged_df.iloc[test_idx]['id'].values
    test_df = merged_df.iloc[test_idx].copy()
    test_df['y_pred'] = y_pred
    agree_user = test_df.groupby('id').apply(lambda g: ((g['ds_recommends_signal']==1) & (g['user_action']=='S') | ((g['ds_recommends_signal']==0) & (g['user_action']=='N'))).mean())
    fig, ax = plt.subplots(figsize=(6,3))
    ax.hist(agree_user.values, bins=20)
    ax.set_title(f'Per-user agreement distribution — test — {tag}')
    ax.set_xlabel('Agreement'); ax.set_ylabel('Users')
    fig.tight_layout()
    fig.savefig(outdir / f'agree_users_{tag}.png', dpi=200)
    plt.close(fig)

    # agreement vs DS confidence buckets
    test_df['ds_conf_bucket'] = pd.cut(test_df['ds_confidence'], bins=[0,0.1,0.2,0.3,0.4,0.5], right=False)
    agg_conf = test_df.groupby('ds_conf_bucket').apply(lambda g: ((g['ds_recommends_signal']==1) & (g['user_action']=='S') | ((g['ds_recommends_signal']==0) & (g['user_action']=='N'))).mean())
    fig, ax = plt.subplots(figsize=(6,3))
    ax.plot(range(len(agg_conf)), agg_conf.values, marker='o')
    ax.set_xticks(range(len(agg_conf))); ax.set_xticklabels(agg_conf.index.astype(str), rotation=45)
    ax.set_ylim(0,1); ax.set_ylabel('Agreement'); ax.set_title(f'Agreement vs DS confidence — {tag}')
    fig.tight_layout()
    fig.savefig(outdir / f'agree_vs_conf_{tag}.png', dpi=200)
    plt.close(fig)

    return {
        'grid': grid, 'metrics': {'acc': acc,'f1': f1,'auc': auc,'cm': cm},
        'feat_importance': fi, 'test_index': test_idx
    }

# ---------------------- Run: full features ---------------------
res_full = train_xgb_with_timecv(merged_df, feature_columns_all, drop_features=None, test_ratio=0.2, n_folds=3, tag='full')

# ---------------------- Run: ablation --------------------------
drop_big = ['stimulus']  # optionally also try: ['stimulus','ds_recommends_signal']
res_nostim = train_xgb_with_timecv(merged_df, feature_columns_all, drop_features=drop_big, test_ratio=0.2, n_folds=3, tag='no_stimulus')

# ------------------- Print quick comparison -------------------
def brief(r, name):
    m = r['metrics']; return f"{name:12s} | Acc {m['acc']:.4f} | F1 {m['f1']:.4f} | AUC {m['auc']:.4f}"

print(brief(res_full, 'Full'))
print(brief(res_nostim, 'No stimulus'))
print("Top 10 features (full):")
print(res_full['feat_importance'].head(10).to_string(index=False))
print("Top 10 features (no stimulus):")
print(res_nostim['feat_importance'].head(10).to_string(index=False))
