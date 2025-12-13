# Comprehensive Experiment 1: Multiple Split Strategies and Grid Search
# Non-DS blocks with different temporal splits and user-based splits
import pandas as pd, numpy as np, matplotlib.pyplot as plt
from pathlib import Path
from sklearn.metrics import (accuracy_score, f1_score, precision_score, recall_score,
                             confusion_matrix, roc_auc_score, precision_recall_curve,
                             average_precision_score, brier_score_loss)
from sklearn.calibration import calibration_curve, CalibratedClassifierCV
from sklearn.model_selection import GridSearchCV
import xgboost as xgb
import catboost as cb
import warnings, os, math
warnings.filterwarnings('ignore')
plt.switch_backend('Agg')

# Configuration
RAW_PATH = 'data/exp1_raw.csv'
AGG_PATH = 'data/exp1_agg.csv'
OUT = Path('exp1_comprehensive_outputs'); OUT.mkdir(exist_ok=True)

# Calibration settings
CALIBRATE = True
CAL_METHOD = 'isotonic'
CAL_RATIO = 0.10

# Utility functions
def ece_score(y_true, y_prob, n_bins=15):
    """Expected Calibration Error (unweighted binning by count proportion)."""
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
    return ece

def best_threshold_f1(y_true, y_prob):
    """Find threshold in [0,1] maximizing F1 on y_true."""
    ts = np.linspace(0, 1, 101)
    best_t, best_f1 = 0.5, -1.0
    for t in ts:
        p = (y_prob >= t).astype(int)
        f1 = f1_score(y_true, p, zero_division=0)
        if f1 > best_f1:
            best_f1, best_t = f1, t
    return float(best_t), float(best_f1)

def log_featset(tag, feats):
    print(f"[{tag}] n_features={len(feats)}  "
          f"stim={'stimulus' in feats}, stim_rolls={sum(1 for f in feats if f.startswith('stimulus_mean_'))}")

def save_cm_plot(cm, tag):
    cmn = cm.astype(float) / cm.sum(axis=1, keepdims=True)
    fig, ax = plt.subplots(figsize=(4,4))
    ax.imshow(cmn, cmap='Blues', vmin=0, vmax=1)
    ax.set(xticks=[0,1], yticks=[0,1], xticklabels=['Noise','Signal'], yticklabels=['Noise','Signal'],
           xlabel='Predicted', ylabel='True', title=f'Confusion (norm) — {tag}')
    for (i,j), v in np.ndenumerate(cmn): ax.text(j,i,f'{v:.2f}',ha='center',va='center',fontsize=10)
    fig.tight_layout(); fig.savefig(OUT / f'cm_norm_{tag}.png', dpi=200); plt.close(fig)

def save_pr_cal_plots(y_true, proba, tag):
    pr_p, pr_r, _ = precision_recall_curve(y_true, proba)
    ap = average_precision_score(y_true, proba)
    fig, ax = plt.subplots(figsize=(5,4))
    ax.plot(pr_r, pr_p)
    ax.set(xlabel='Recall', ylabel='Precision', title=f'Precision–Recall (AP={ap:.3f}) — {tag}')
    fig.tight_layout(); fig.savefig(OUT / f'pr_{tag}.png', dpi=200); plt.close(fig)

    prob_true, prob_pred = calibration_curve(y_true, proba, n_bins=10, strategy='quantile')
    fig, ax = plt.subplots(figsize=(5,4))
    ax.plot([0,1],[0,1],'--',lw=1); ax.plot(prob_pred, prob_true, marker='o')
    ax.set(xlabel='Predicted probability', ylabel='Observed positive rate', title=f'Calibration — {tag}')
    fig.tight_layout(); fig.savefig(OUT / f'cal_{tag}.png', dpi=200); plt.close(fig)

# ------------- Load & basic prep --------------
print("Loading and preprocessing data...")
raw_df = pd.read_csv(RAW_PATH)
agg_df = pd.read_csv(AGG_PATH)
raw_df.columns = raw_df.columns.str.lower().str.replace(' ', '_')
agg_df.columns = agg_df.columns.str.lower().str.replace(' ', '_')

# Filter NON-DS trials & order
raw_df = raw_df.query('alert_system == 0').copy()
raw_df = raw_df.sort_values(['id','block','trial']).reset_index(drop=True)

# Labels (NO DS features)
raw_df['target'] = (raw_df['user_action'] == 'S').astype(int)

# User confusion matrix
raw_df['tp'] = ((raw_df['user_action']=='S') & (raw_df['event_type']=='S')).astype(int)
raw_df['fp'] = ((raw_df['user_action']=='S') & (raw_df['event_type']=='N')).astype(int)
raw_df['tn'] = ((raw_df['user_action']=='N') & (raw_df['event_type']=='N')).astype(int)
raw_df['fn'] = ((raw_df['user_action']=='N') & (raw_df['event_type']=='S')).astype(int)

# System confusion matrix (using stimulus threshold 6.0 for best accuracy)
raw_df['system_indicates_signal'] = (raw_df['stimulus'] >= 6.0).astype(int)
raw_df['system_tp'] = ((raw_df['system_indicates_signal']==1) & (raw_df['event_type']=='S')).astype(int)
raw_df['system_fp'] = ((raw_df['system_indicates_signal']==1) & (raw_df['event_type']=='N')).astype(int)
raw_df['system_tn'] = ((raw_df['system_indicates_signal']==0) & (raw_df['event_type']=='N')).astype(int)
raw_df['system_fn'] = ((raw_df['system_indicates_signal']==0) & (raw_df['event_type']=='S')).astype(int)

# Conditional user TP rates (NO DS features)
raw_df['user_tp_given_system_signal'] = ((raw_df['user_action']=='S') & (raw_df['event_type']=='S') & (raw_df['system_indicates_signal']==1)).astype(int)
raw_df['user_tp_given_system_noise'] = ((raw_df['user_action']=='S') & (raw_df['event_type']=='S') & (raw_df['system_indicates_signal']==0)).astype(int)

# -------------- Merge aggregated (robust) --------------
agg_df = agg_df.rename(columns={
    'how_much_did_the_automation_help_you_in_the_task?': 'help_score',
    'how_good_was_the_automation_in_distinguishing_between_blue_and_orange_vibranium_strains?': 'distinguishing_score'
})
if {'help_score','distinguishing_score'}.issubset(agg_df.columns):
    agg_df['avg_score'] = agg_df[['help_score','distinguishing_score']].mean(axis=1)
    agg_df['avg_score_prev_blocks'] = agg_df.groupby('id')['avg_score'].shift(1)
    agg_df = agg_df.drop(columns=[c for c in ['help_score','distinguishing_score','avg_score'] if c in agg_df.columns])

dep_col = next((c for c in ['dependency','dependency_agg','dep','user_dependency','dependency_level'] if c in agg_df.columns), None)
dep_map_num = {'independent':1,'low':2,'medium':3,'high':4,'full':5}
if dep_col is not None:
    agg_df['dependency_num'] = agg_df[dep_col].astype(str).str.strip().str.lower().map(dep_map_num)

merge_cols = ['id','block']
if dep_col is not None: merge_cols += [dep_col,'dependency_num']
merge_cols = [c for c in merge_cols if c in agg_df.columns]
merged_df = pd.merge(raw_df, agg_df[merge_cols].drop_duplicates(), on=['id','block'], how='left')

if dep_col is not None and dep_col in merged_df.columns:
    merged_df = pd.concat([merged_df, pd.get_dummies(merged_df[dep_col], prefix='dep')], axis=1)

# -------------- Rolling histories (shifted) - NO DS FEATURES --------------
def create_rolling_features(df, rolling_windows):
    for w in rolling_windows:
        for base in ['signal_rate',
                     'tp_rate','fp_rate','fn_rate',
                     'system_tp_rate','system_fp_rate','system_fn_rate',
                     'user_tp_given_system_signal_rate','user_tp_given_system_noise_rate',
                     'stimulus_mean','classification_time_mean']:
            df[f'{base}_rolling_{w}'] = np.nan

    for _, idx in df.groupby('id').indices.items():
        sub = df.loc[idx].copy()
        for w in rolling_windows:
            sub[f'signal_rate_rolling_{w}'] = sub['target'].rolling(w, min_periods=1).mean().shift(1)
            sub[f'tp_rate_rolling_{w}'] = sub['tp'].rolling(w, min_periods=1).mean().shift(1)
            sub[f'fp_rate_rolling_{w}'] = sub['fp'].rolling(w, min_periods=1).mean().shift(1)
            sub[f'fn_rate_rolling_{w}'] = sub['fn'].rolling(w, min_periods=1).mean().shift(1)
            sub[f'system_tp_rate_rolling_{w}'] = sub['system_tp'].rolling(w, min_periods=1).mean().shift(1)
            sub[f'system_fp_rate_rolling_{w}'] = sub['system_fp'].rolling(w, min_periods=1).mean().shift(1)
            sub[f'system_fn_rate_rolling_{w}'] = sub['system_fn'].rolling(w, min_periods=1).mean().shift(1)
            sub[f'user_tp_given_system_signal_rate_rolling_{w}'] = sub['user_tp_given_system_signal'].rolling(w, min_periods=1).mean().shift(1)
            sub[f'user_tp_given_system_noise_rate_rolling_{w}'] = sub['user_tp_given_system_noise'].rolling(w, min_periods=1).mean().shift(1)
            if 'stimulus' in sub:
                sub[f'stimulus_mean_rolling_{w}'] = sub['stimulus'].rolling(w, min_periods=1).mean().shift(1)
            if 'classification_time' in sub:
                sub[f'classification_time_mean_rolling_{w}'] = sub['classification_time'].rolling(w, min_periods=1).mean().shift(1)
        df.loc[idx, sub.columns] = sub
    return df

# -------------- Trial-level extras --------------
merged_df['is_first_trial'] = (merged_df['trial'] == 1).astype(int)
merged_df['is_first_block'] = (merged_df['block'] == 1).astype(int)
merged_df['purchase_ds_block_num'] = merged_df.groupby('id')['block'].rank(method='dense')

# -------------- Feature sets (no leak) - NO DS FEATURES --------------
base_simple = [
    'stimulus',
    'trial','is_first_trial','block','is_first_block','purchase_ds_block_num',
    'system_d'
]
if 'dependency_num' in merged_df.columns:
    base_simple.append('dependency_num')
dep_cols = [c for c in merged_df.columns if c.startswith('dep_')]
TARGET = 'target'

# -------------- Split Strategies --------------
def per_user_chrono_split(df, user_col='id', order_cols=('block','trial'), test_ratio=0.2):
    """Temporal split: first 80% of trials per user for training, last 20% for testing"""
    test_mask = np.zeros(len(df), dtype=bool)
    for _, sub in df.sort_values(list(order_cols)).groupby(user_col, sort=False):
        n = len(sub); t = max(1, int(np.floor(n*test_ratio)))
        test_mask[sub.index[-t:]] = True
    return np.flatnonzero(~test_mask), np.flatnonzero(test_mask)

def per_user_30_20_split(df, user_col='id', order_cols=('block','trial')):
    """30-20 split: first 30 trials per user for training, last 20 trials for testing"""
    test_mask = np.zeros(len(df), dtype=bool)
    for _, sub in df.sort_values(list(order_cols)).groupby(user_col, sort=False):
        n = len(sub)
        if n >= 50:  # Only users with at least 50 trials
            test_mask[sub.index[-20:]] = True  # Last 20 trials
    return np.flatnonzero(~test_mask), np.flatnonzero(test_mask)

def user_based_split(df, user_col='id', test_ratio=0.2, random_state=42):
    """User-based split: train on some users, test on other users"""
    np.random.seed(random_state)
    unique_users = df[user_col].unique()
    n_test_users = max(1, int(len(unique_users) * test_ratio))
    test_users = np.random.choice(unique_users, size=n_test_users, replace=False)
    test_mask = df[user_col].isin(test_users)
    return np.flatnonzero(~test_mask), np.flatnonzero(test_mask)

def chrono_cv_splits_on_train(df_train, user_col='id', order_cols=('block','trial'), n_folds=3):
    df = df_train.sort_values(list(order_cols)).reset_index(drop=True)
    splits = []
    for k in range(1, n_folds):
        tr_idx, va_idx = [], []
        for _, sub in df.groupby(user_col, sort=False):
            n = len(sub); bins = np.linspace(0, n, n_folds+1).astype(int)
            va_start, va_end = bins[k], bins[k+1]
            tr_idx.extend(sub.index[:va_start].tolist())
            if va_end > va_start: va_idx.extend(sub.index[va_start:va_end].tolist())
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

# -------------- Train / evaluate with grid search --------------
def train_eval_with_grid_search(df, feature_cols, tag, split_strategy, split_params, 
                               test_ratio=0.2, n_folds=3, calibrate=True, cal_ratio=0.1, cal_method='isotonic'):
    X = df[feature_cols]; y = df[TARGET]
    
    # Apply split strategy
    if split_strategy == 'temporal':
        tr_full, te_full = per_user_chrono_split(df, 'id', ('block','trial'), test_ratio=test_ratio)
    elif split_strategy == '30_20':
        tr_full, te_full = per_user_30_20_split(df, 'id', ('block','trial'))
    elif split_strategy == 'user_based':
        tr_full, te_full = user_based_split(df, 'id', test_ratio=test_ratio, random_state=42)
    else:
        raise ValueError(f"Unknown split strategy: {split_strategy}")
    
    Xtr_full, ytr_full = X.iloc[tr_full], y.iloc[tr_full]
    Xte, yte = X.iloc[te_full], y.iloc[te_full]
    test_ids = df.iloc[te_full]['id'].values

    print(f"  Split: {len(tr_full)} train, {len(te_full)} test")

    # Grid search parameters
    xgb_params = {
        'n_estimators': [100, 200],
        'max_depth': [3, 6],
        'learning_rate': [0.1, 0.2],
        'subsample': [0.8, 1.0]
    }
    
    cat_params = {
        'iterations': [200, 400],
        'depth': [4, 6],
        'learning_rate': [0.1, 0.2],
        'l2_leaf_reg': [1, 3]
    }

    results = []
    
    # XGBoost with grid search
    if calibrate:
        tr_core_rel, cal_rel = carve_calibration_from_train(df.iloc[tr_full], cal_ratio=cal_ratio)
        Xtr_core, ytr_core = Xtr_full.iloc[tr_core_rel], ytr_full.iloc[tr_core_rel]
        Xcal, ycal = Xtr_full.iloc[cal_rel], ytr_full.iloc[cal_rel]
        cv_splits = chrono_cv_splits_on_train(df.iloc[tr_full].iloc[tr_core_rel], 'id', ('block','trial'), n_folds=n_folds)
    else:
        Xtr_core, ytr_core = Xtr_full, ytr_full
        Xcal, ycal = None, None
        cv_splits = chrono_cv_splits_on_train(df.iloc[tr_full], 'id', ('block','trial'), n_folds=n_folds)

    # XGBoost Grid Search
    print(f"  Running XGBoost grid search for {tag}...")
    xgb_grid = GridSearchCV(
        xgb.XGBClassifier(random_state=42, eval_metric='logloss', n_jobs=-1, tree_method='hist'),
        xgb_params, cv=cv_splits, scoring='f1', n_jobs=-1, refit=True, verbose=0
    )
    xgb_grid.fit(Xtr_core, ytr_core)
    xgb_model = xgb_grid.best_estimator_
    
    if calibrate:
        xgb_calib = CalibratedClassifierCV(estimator=xgb_model, method=cal_method, cv='prefit')
        xgb_calib.fit(Xcal, ycal)
        xgb_clf = xgb_calib
        cal_proba = xgb_calib.predict_proba(Xcal)[:,1]
        t_star, _ = best_threshold_f1(ycal.values, cal_proba)
    else:
        xgb_clf = xgb_model
        t_star = 0.5

    # Evaluate XGBoost
    proba = xgb_clf.predict_proba(Xte)[:,1]
    pred05 = (proba >= 0.5).astype(int)
    predT = (proba >= t_star).astype(int)

    acc = accuracy_score(yte, pred05)
    f1 = f1_score(yte, pred05, zero_division=0)
    prc = precision_score(yte, pred05, zero_division=0)
    rec = recall_score(yte, pred05)
    auc = roc_auc_score(yte, proba)
    brier = brier_score_loss(yte, proba)
    ece = ece_score(yte.values, proba)

    acc_t = accuracy_score(yte, predT)
    f1_t = f1_score(yte, predT, zero_division=0)
    prc_t = precision_score(yte, predT, zero_division=0)
    rec_t = recall_score(yte, predT)

    cm = confusion_matrix(yte, pred05)
    save_cm_plot(cm, f'{tag}_xgb')
    save_pr_cal_plots(yte.values, proba, f'{tag}_xgb')

    # Feature importance
    fi = pd.DataFrame({'feature': feature_cols, 'importance': xgb_model.feature_importances_}).sort_values('importance', ascending=False)
    fi.to_csv(OUT / f'feature_importance_{tag}_xgb.csv', index=False)

    results.append({
        'model': 'XGBoost', 'tag': tag, 'split': split_strategy,
        'acc': acc, 'f1': f1, 'prec': prc, 'rec': rec, 'auc': auc, 'brier': brier, 'ece': ece,
        'acc_tuned': acc_t, 'f1_tuned': f1_t, 'prec_tuned': prc_t, 'rec_tuned': rec_t, 'thresh': t_star,
        'best_params': xgb_grid.best_params_, 'n_train': len(tr_full), 'n_test': len(te_full)
    })

    print(f"  XGBoost: Acc={acc:.4f}, F1={f1:.4f}, AUC={auc:.4f}, Best params: {xgb_grid.best_params_}")

    # CatBoost Grid Search
    print(f"  Running CatBoost grid search for {tag}...")
    cat_grid = GridSearchCV(
        cb.CatBoostClassifier(loss_function='Logloss', random_state=42, verbose=False, allow_writing_files=False),
        cat_params, cv=cv_splits, scoring='f1', n_jobs=-1, refit=True, verbose=0
    )
    cat_grid.fit(Xtr_core, ytr_core)
    cat_model = cat_grid.best_estimator_

    if calibrate:
        cat_calib = CalibratedClassifierCV(estimator=cat_model, method=cal_method, cv='prefit')
        cat_calib.fit(Xcal, ycal)
        cat_clf = cat_calib
        cal_proba = cat_calib.predict_proba(Xcal)[:,1]
        t_star_cat, _ = best_threshold_f1(ycal.values, cal_proba)
    else:
        cat_clf = cat_model
        t_star_cat = 0.5

    # Evaluate CatBoost
    proba_cat = cat_clf.predict_proba(Xte)[:,1]
    pred05_cat = (proba_cat >= 0.5).astype(int)
    predT_cat = (proba_cat >= t_star_cat).astype(int)

    acc_cat = accuracy_score(yte, pred05_cat)
    f1_cat = f1_score(yte, pred05_cat, zero_division=0)
    prc_cat = precision_score(yte, pred05_cat, zero_division=0)
    rec_cat = recall_score(yte, pred05_cat)
    auc_cat = roc_auc_score(yte, proba_cat)
    brier_cat = brier_score_loss(yte, proba_cat)
    ece_cat = ece_score(yte.values, proba_cat)

    acc_t_cat = accuracy_score(yte, predT_cat)
    f1_t_cat = f1_score(yte, predT_cat, zero_division=0)
    prc_t_cat = precision_score(yte, predT_cat, zero_division=0)
    rec_t_cat = recall_score(yte, predT_cat)

    cm_cat = confusion_matrix(yte, pred05_cat)
    save_cm_plot(cm_cat, f'{tag}_cat')
    save_pr_cal_plots(yte.values, proba_cat, f'{tag}_cat')

    # Feature importance
    fi_cat = pd.DataFrame({'feature': feature_cols, 'importance': cat_model.get_feature_importance()}).sort_values('importance', ascending=False)
    fi_cat.to_csv(OUT / f'feature_importance_{tag}_cat.csv', index=False)

    results.append({
        'model': 'CatBoost', 'tag': tag, 'split': split_strategy,
        'acc': acc_cat, 'f1': f1_cat, 'prec': prc_cat, 'rec': rec_cat, 'auc': auc_cat, 'brier': brier_cat, 'ece': ece_cat,
        'acc_tuned': acc_t_cat, 'f1_tuned': f1_t_cat, 'prec_tuned': prc_t_cat, 'rec_tuned': rec_t_cat, 'thresh': t_star_cat,
        'best_params': cat_grid.best_params_, 'n_train': len(tr_full), 'n_test': len(te_full)
    })

    print(f"  CatBoost: Acc={acc_cat:.4f}, F1={f1_cat:.4f}, AUC={auc_cat:.4f}, Best params: {cat_grid.best_params_}")

    return results

# -------------- Main Experiment Loop --------------
print("Starting comprehensive experiments...")
print(f"Non-DS blocks only (alert_system == 0): {len(merged_df):,} trials")
print(f"Signal decisions: {merged_df['target'].sum():,}/{len(merged_df):,} = {merged_df['target'].mean()*100:.2f}%")

# Create rolling features for different window sizes
rolling_windows_80_20 = [1,3,7,14,21,40]
rolling_windows_30_20 = [1,3,7,14,21,30]

# Create datasets with different rolling windows
df_80_20 = create_rolling_features(merged_df.copy(), rolling_windows_80_20)
df_30_20 = create_rolling_features(merged_df.copy(), rolling_windows_30_20)

# Define feature sets
rolling_cols_80_20 = [c for c in df_80_20.columns if 'rolling_' in c]
rolling_cols_30_20 = [c for c in df_30_20.columns if 'rolling_' in c]

feats_80_20 = [c for c in base_simple + dep_cols + rolling_cols_80_20 if c in df_80_20.columns]
feats_30_20 = [c for c in base_simple + dep_cols + rolling_cols_30_20 if c in df_30_20.columns]
feats_no_historical = [c for c in base_simple + dep_cols if c in merged_df.columns]

all_results = []

# Experiment 1: 80/20 Temporal Split
print("\n=== EXPERIMENT 1: 80/20 Temporal Split ===")
log_featset('80_20_full', feats_80_20)
all_results.extend(train_eval_with_grid_search(df_80_20, feats_80_20, '80_20_full', 'temporal', {}, test_ratio=0.2))

log_featset('80_20_no_historical', feats_no_historical)
all_results.extend(train_eval_with_grid_search(merged_df, feats_no_historical, '80_20_no_historical', 'temporal', {}, test_ratio=0.2))

# Experiment 2: 30/20 Split
print("\n=== EXPERIMENT 2: 30/20 Split ===")
log_featset('30_20_full', feats_30_20)
all_results.extend(train_eval_with_grid_search(df_30_20, feats_30_20, '30_20_full', '30_20', {}))

log_featset('30_20_no_historical', feats_no_historical)
all_results.extend(train_eval_with_grid_search(merged_df, feats_no_historical, '30_20_no_historical', '30_20', {}))

# Experiment 3: User-based Split
print("\n=== EXPERIMENT 3: User-based Split ===")
log_featset('user_full', feats_80_20)
all_results.extend(train_eval_with_grid_search(df_80_20, feats_80_20, 'user_full', 'user_based', {}, test_ratio=0.2))

log_featset('user_no_historical', feats_no_historical)
all_results.extend(train_eval_with_grid_search(merged_df, feats_no_historical, 'user_no_historical', 'user_based', {}, test_ratio=0.2))

# -------------- Results Analysis --------------
print("\n=== RESULTS ANALYSIS ===")
results_df = pd.DataFrame(all_results)
results_df.to_csv(OUT / 'comprehensive_results.csv', index=False)

print("\nComprehensive Results Summary:")
print("=" * 80)
for split in ['temporal', '30_20', 'user_based']:
    print(f"\n{split.upper()} SPLIT:")
    split_results = results_df[results_df['split'] == split]
    for _, row in split_results.iterrows():
        print(f"  {row['model']:8} {row['tag']:20} | Acc={row['acc']:.4f} F1={row['f1']:.4f} AUC={row['auc']:.4f} | Train={row['n_train']:5d} Test={row['n_test']:4d}")

print("\nBest performing models by F1 score:")
best_results = results_df.loc[results_df.groupby(['split', 'model'])['f1'].idxmax()]
for _, row in best_results.iterrows():
    print(f"  {row['split']:12} {row['model']:8} {row['tag']:20} | F1={row['f1']:.4f} Acc={row['acc']:.4f} AUC={row['auc']:.4f}")

print(f"\nAll results saved to: {OUT}")
print("Experiment completed!")
