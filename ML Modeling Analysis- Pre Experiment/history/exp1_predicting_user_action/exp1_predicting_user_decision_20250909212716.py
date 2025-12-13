# Experiment 1: Predicting user signal/noise decisions with temporal validation
import pandas as pd, numpy as np, matplotlib.pyplot as plt
from pathlib import Path
from sklearn.metrics import (accuracy_score, f1_score, precision_score, recall_score,
                             confusion_matrix, roc_auc_score, precision_recall_curve,
                             average_precision_score, brier_score_loss)
from sklearn.calibration import calibration_curve, CalibratedClassifierCV
from sklearn.model_selection import GridSearchCV
import xgboost as xgb
import warnings, os, math
warnings.filterwarnings('ignore')
plt.switch_backend('Agg')

# Configuration
RAW_PATH = 'data/exp1_raw.csv'
AGG_PATH = 'data/exp1_agg.csv'
OUT = Path('exp1_outputs'); OUT.mkdir(exist_ok=True)

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
        acc  = y_true[m].mean()   # empirical positive rate in the bin
        ece += m.mean() * abs(acc - conf)
    return ece

def best_threshold_f1(y_true, y_prob):
    """Find threshold in [0,1] maximizing F1 on y_true."""
    # scan 101 thresholds; could be refined but good enough
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
          f"stim={'stimulus' in feats}, dsrec={'ds_recommends_signal' in feats}, "
          f"sysconf={'system_confidence' in feats}, stim_rolls={sum(1 for f in feats if f.startswith('stimulus_mean_'))}")

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
raw_df = pd.read_csv(RAW_PATH)
agg_df = pd.read_csv(AGG_PATH)
raw_df.columns = raw_df.columns.str.lower().str.replace(' ', '_')
agg_df.columns = agg_df.columns.str.lower().str.replace(' ', '_')

# Filter DS trials & order
raw_df = raw_df.query('alert_system == 1').copy()
raw_df = raw_df.sort_values(['id','block','trial']).reset_index(drop=True)

# Labels + normalized DS mapping
raw_df['target'] = (raw_df['user_action'] == 'S').astype(int)
raw_df['alarm_output_norm'] = raw_df['alarm_output'].astype(str).str.strip().str.lower()
raw_df['ds_recommends_signal'] = (raw_df['alarm_output_norm'] == 'alarm').astype(int)
raw_df['ds_recommends_noise']  = (raw_df['alarm_output_norm'] == 'no alarm').astype(int)

# Agreement & correctness
raw_df['agrees_with_ds'] = (
    ((raw_df['user_action'] == 'S') & (raw_df['ds_recommends_signal'] == 1)) |
    ((raw_df['user_action'] == 'N') & (raw_df['ds_recommends_noise']  == 1))
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

# -------------- Rolling histories (shifted) --------------
rolling_windows = [1,3,7,14,21,40]
for w in rolling_windows:
    for base in ['signal_rate','user_ds_agreement_rate','ds_correct_rate',
                 'tp_rate','fp_rate','fn_rate','tn_rate','stimulus_mean','classification_time_mean']:
        merged_df[f'{base}_rolling_{w}'] = np.nan

for _, idx in merged_df.groupby('id').indices.items():
    sub = merged_df.loc[idx].copy()
    for w in rolling_windows:
        sub[f'signal_rate_rolling_{w}']       = sub['target'].rolling(w, min_periods=1).mean().shift(1)
        sub[f'user_ds_agreement_rate_rolling_{w}'] = sub['agrees_with_ds'].rolling(w, min_periods=1).mean().shift(1)
        sub[f'ds_correct_rate_rolling_{w}']   = sub['ds_was_correct'].rolling(w, min_periods=1).mean().shift(1)
        # user_correct_rate_rolling removed - redundant with tp_rate_rolling
        sub[f'tp_rate_rolling_{w}']           = sub['tp'].rolling(w, min_periods=1).mean().shift(1)
        sub[f'fp_rate_rolling_{w}']           = sub['fp'].rolling(w, min_periods=1).mean().shift(1)
        sub[f'fn_rate_rolling_{w}']           = sub['fn'].rolling(w, min_periods=1).mean().shift(1)
        sub[f'tn_rate_rolling_{w}']           = sub['tn'].rolling(w, min_periods=1).mean().shift(1)
        if 'stimulus' in sub:
            sub[f'stimulus_mean_rolling_{w}'] = sub['stimulus'].rolling(w, min_periods=1).mean().shift(1)
        if 'classification_time' in sub:
            sub[f'classification_time_mean_rolling_{w}'] = sub['classification_time'].rolling(w, min_periods=1).mean().shift(1)
    merged_df.loc[idx, sub.columns] = sub

# -------------- Trial-level extras --------------
merged_df['is_first_trial']         = (merged_df['trial'] == 1).astype(int)
merged_df['is_first_block']         = (merged_df['block'] == 1).astype(int)
# NOTE: per your request, we REMOVE the misnamed ds_confidence; we also do NOT compute system_confidence
merged_df['purchase_ds_block_num']  = merged_df.groupby('id')['block'].rank(method='dense')

# -------------- Feature sets (no leak) --------------
# Important: do NOT include 'is_signal_event' or any label-like current feature
base_simple = [
    'stimulus',                # current numeric system output
    'ds_recommends_signal',    # DS decision (Alarm / No Alarm)
    'trial','is_first_trial','block','is_first_block','purchase_ds_block_num',
    'system_d'
    # Note: avg_score_prev_blocks removed - redundant with confusion matrix features
]
if 'dependency_num' in merged_df.columns:
    base_simple.append('dependency_num')
dep_cols = [c for c in merged_df.columns if c.startswith('dep_')]
rolling_cols = [c for c in merged_df.columns if 'rolling_' in c]
FEATURES_NO_LEAK = [c for c in base_simple + dep_cols + rolling_cols if c in merged_df.columns]
TARGET = 'target'

# Agreement sanity print
agree = (((merged_df['ds_recommends_signal']==1) & (merged_df['user_action']=='S')) |
         ((merged_df['ds_recommends_signal']==0) & (merged_df['user_action']=='N'))).astype(int)
print(f"Agreement overall: {agree.sum():,}/{len(agree):,} = {agree.mean()*100:.2f}%")

# -------------- Chronological splits --------------
def per_user_chrono_split(df, user_col='id', order_cols=('block','trial'), test_ratio=0.2):
    test_mask = np.zeros(len(df), dtype=bool)
    for _, sub in df.sort_values(list(order_cols)).groupby(user_col, sort=False):
        n = len(sub); t = max(1, int(np.floor(n*test_ratio)))
        test_mask[sub.index[-t:]] = True
    return np.flatnonzero(~test_mask), np.flatnonzero(test_mask)

def chrono_cv_splits_on_train(df_train, user_col='id', order_cols=('block','trial'), n_folds=3):
    df = df_train.sort_values(list(order_cols)).reset_index(drop=True)
    splits = []
    for k in range(1, n_folds):   # (n_folds-1) CV folds: early->train, later->val
        tr_idx, va_idx = [], []
        for _, sub in df.groupby(user_col, sort=False):
            n = len(sub); bins = np.linspace(0, n, n_folds+1).astype(int)
            va_start, va_end = bins[k], bins[k+1]
            tr_idx.extend(sub.index[:va_start].tolist())
            if va_end > va_start: va_idx.extend(sub.index[va_start:va_end].tolist())
        splits.append((np.array(tr_idx), np.array(va_idx)))
    return splits

def carve_calibration_from_train(df_train, cal_ratio=0.1, user_col='id', order_cols=('block','trial')):
    """Return indices (relative to df_train) for train_core and cal_holdout, time-aware per user."""
    df = df_train.sort_values(list(order_cols)).reset_index(drop=True)
    train_core, cal_hold = [], []
    for _, sub in df.groupby(user_col, sort=False):
        n = len(sub); c = max(1, int(np.floor(n*cal_ratio)))
        cal_hold.extend(sub.index[-c:].tolist())
        train_core.extend(sub.index[:-c].tolist())
    return np.array(train_core), np.array(cal_hold)

# -------------- Train / evaluate (with calibration, threshold tuning, SHAP, per-user) --------------
def train_eval_xgb(df, feature_cols, tag, test_ratio=0.2, n_folds=3, calibrate=True, cal_ratio=0.1, cal_method='isotonic'):
    X = df[feature_cols]; y = df[TARGET]
    tr_full, te_full = per_user_chrono_split(df, 'id', ('block','trial'), test_ratio=test_ratio)
    Xtr_full, ytr_full = X.iloc[tr_full], y.iloc[tr_full]
    Xte, yte = X.iloc[te_full], y.iloc[te_full]
    test_ids = df.iloc[te_full]['id'].values

    # time-aware CV on train_core if calibrating; otherwise on full train
    if calibrate:
        tr_core_rel, cal_rel = carve_calibration_from_train(df.iloc[tr_full], cal_ratio=cal_ratio)
        Xtr_core, ytr_core = Xtr_full.iloc[tr_core_rel], ytr_full.iloc[tr_core_rel]
        Xcal, ycal         = Xtr_full.iloc[cal_rel],     ytr_full.iloc[cal_rel]
        cv_splits = chrono_cv_splits_on_train(df.iloc[tr_full].iloc[tr_core_rel], 'id', ('block','trial'), n_folds=n_folds)
        # Grid search commented out - using best parameters from previous runs
        # grid = GridSearchCV(
        #     xgb.XGBClassifier(random_state=42, eval_metric='logloss', n_jobs=-1, tree_method='hist'),
        #     {'n_estimators':[100,200],'max_depth':[3,6],'learning_rate':[0.1,0.2],'subsample':[0.8,1.0]},
        #     cv=cv_splits, scoring='f1', n_jobs=-1, refit=True, verbose=0
        # )
        # grid.fit(Xtr_core, ytr_core)
        # base_model = grid.best_estimator_
        
        # Use best parameters from previous grid search
        best_params = {'n_estimators': 100, 'max_depth': 3, 'learning_rate': 0.2, 'subsample': 1.0}
        base_model = xgb.XGBClassifier(random_state=42, eval_metric='logloss', n_jobs=-1, tree_method='hist', **best_params)
        base_model.fit(Xtr_core, ytr_core)
        calib = CalibratedClassifierCV(estimator=base_model, method=cal_method, cv='prefit')
        calib.fit(Xcal, ycal)
        clf = calib
        # threshold tuning on calibration holdout
        cal_proba = calib.predict_proba(Xcal)[:,1]
        t_star, best_f1_cal = best_threshold_f1(ycal.values, cal_proba)
    else:
        cv_splits = chrono_cv_splits_on_train(df.iloc[tr_full], 'id', ('block','trial'), n_folds=n_folds)
        # Use best parameters from previous grid search
        best_params = {'n_estimators': 100, 'max_depth': 3, 'learning_rate': 0.2, 'subsample': 1.0}
        base_model = xgb.XGBClassifier(random_state=42, eval_metric='logloss', n_jobs=-1, tree_method='hist', **best_params)
        base_model.fit(Xtr_full, ytr_full)
        clf = base_model
        t_star = 0.5

    # test predictions
    proba = clf.predict_proba(Xte)[:,1]
    pred05 = (proba >= 0.5).astype(int)
    predT  = (proba >= t_star).astype(int)

    # metrics @0.5
    acc = accuracy_score(yte, pred05)
    f1  = f1_score(yte, pred05, zero_division=0)
    prc = precision_score(yte, pred05, zero_division=0)
    rec = recall_score(yte, pred05)
    auc = roc_auc_score(yte, proba)
    brier = brier_score_loss(yte, proba)
    ece = ece_score(yte.values, proba)

    # metrics @t_star
    acc_t = accuracy_score(yte, predT)
    f1_t  = f1_score(yte, predT, zero_division=0)
    prc_t = precision_score(yte, predT, zero_division=0)
    rec_t = recall_score(yte, predT)

    cm = confusion_matrix(yte, pred05)
    save_cm_plot(cm, tag); save_pr_cal_plots(yte.values, proba, tag)

    # feature importances
    fi = (pd.DataFrame({'feature': feature_cols,
                        'importance': getattr(base_model, "feature_importances_", np.zeros(len(feature_cols)))})
          .sort_values('importance', ascending=False))
    fi.to_csv(OUT / f'feature_importance_{tag}.csv', index=False)

    # SHAP (base model)
    try:
        import shap
        shap_sample = Xte.sample(min(3000, len(Xte)), random_state=42)
        explainer = shap.TreeExplainer(base_model)
        shap_values = explainer.shap_values(shap_sample)
        shap.summary_plot(shap_values, shap_sample, show=False)
        plt.tight_layout(); plt.savefig(OUT / f'shap_summary_{tag}.png', dpi=200, bbox_inches='tight'); plt.close()
    except Exception as e:
        with open(OUT / f'shap_{tag}.txt','w') as f: f.write(f"SHAP skipped: {e}")

    # per-user test metrics (report tuned and 0.5)
    df_test = pd.DataFrame({
        'id': test_ids,
        'y_true': yte.values,
        'proba': proba,
        'pred05': pred05,
        'predT': predT
    })
    rows = []
    for uid, sub in df_test.groupby('id'):
        support = len(sub)
        acc05_u = (sub['pred05'] == sub['y_true']).mean()
        f105_u  = f1_score(sub['y_true'], sub['pred05'], zero_division=0)
        accT_u  = (sub['predT'] == sub['y_true']).mean()
        f1T_u   = f1_score(sub['y_true'], sub['predT'], zero_division=0)
        rows.append({'id': uid, 'support': support,
                     'acc_05': acc05_u, 'f1_05': f105_u,
                     'acc_tuned': accT_u, 'f1_tuned': f1T_u})
    per_user = pd.DataFrame(rows).sort_values('support', ascending=False)
    per_user.to_csv(OUT / f'per_user_metrics_{tag}.csv', index=False)

    print(f"[{tag}] Acc@0.5={acc:.4f}  F1@0.5={f1:.4f}  Prec@0.5={prc:.4f}  Rec@0.5={rec:.4f}  "
          f"AUC={auc:.4f}  Brier={brier:.4f}  ECE={ece:.4f}  Best={best_params}")
    if calibrate:
        print(f"       Tuned threshold t*={t_star:.2f}  Acc@t*={acc_t:.4f}  F1@t*={f1_t:.4f}  Prec@t*={prc_t:.4f}  Rec@t*={rec_t:.4f}")
    
    # Print top 10 feature importance
    if hasattr(base_model, 'feature_importances_'):
        fi = pd.DataFrame({'feature': feature_cols, 'importance': base_model.feature_importances_}).sort_values('importance', ascending=False)
        print(f"       Top 10 features: {', '.join([f'{f}({imp:.3f})' for f, imp in fi.head(10).values])}")

    return {
        'tag':tag,'acc':acc,'f1':f1,'prec':prc,'rec':rec,'auc':auc,'brier':brier,'ece':ece,
        'acc_tuned':acc_t,'f1_tuned':f1_t,'prec_tuned':prc_t,'rec_tuned':rec_t,'thresh':t_star,
        'cm':cm,'fi':fi
    }

# ------------------------ Runs (XGB) ------------------------
results = []

# Define feature sets (NOTE: system_confidence REMOVED everywhere)
feats_full = [c for c in FEATURES_NO_LEAK]  # no system_confidence anywhere
log_featset('full', feats_full)
results.append(train_eval_xgb(merged_df, feats_full, tag='full',
                              calibrate=CALIBRATE, cal_ratio=CAL_RATIO, cal_method=CAL_METHOD))

feats_no_stim = [f for f in FEATURES_NO_LEAK if f != 'stimulus']
log_featset('no_stimulus', feats_no_stim)
results.append(train_eval_xgb(merged_df, feats_no_stim, tag='no_stimulus',
                              calibrate=CALIBRATE, cal_ratio=CAL_RATIO, cal_method=CAL_METHOD))

feats_no_dsrec = [f for f in FEATURES_NO_LEAK if f != 'ds_recommends_signal']
log_featset('no_dsrec', feats_no_dsrec)
results.append(train_eval_xgb(merged_df, feats_no_dsrec, tag='no_dsrec',
                              calibrate=CALIBRATE, cal_ratio=CAL_RATIO, cal_method=CAL_METHOD))

feats_no_stim_no_dsrec = [f for f in FEATURES_NO_LEAK if f not in ['stimulus','ds_recommends_signal']]
log_featset('no_stimulus_no_dsrec', feats_no_stim_no_dsrec)
results.append(train_eval_xgb(merged_df, feats_no_stim_no_dsrec, tag='no_stimulus_no_dsrec',
                              calibrate=CALIBRATE, cal_ratio=CAL_RATIO, cal_method=CAL_METHOD))

# Strong ablation: remove ALL current-trial decision info (stimulus + DS rec); keep rollings
feats_no_current_bundle = [f for f in FEATURES_NO_LEAK if f not in ['stimulus','ds_recommends_signal']]
log_featset('no_current_stim_bundle', feats_no_current_bundle)
results.append(train_eval_xgb(merged_df, feats_no_current_bundle, tag='no_current_stim_bundle',
                              calibrate=CALIBRATE, cal_ratio=CAL_RATIO, cal_method=CAL_METHOD))

# ------------------------ Optional CatBoost (full only) ------------------------
try:
    import catboost as cb
    print("CatBoost detected — running CatBoost (full features).")
    # Build train/cal/test slices using same logic
    tr_full, te_full = per_user_chrono_split(merged_df, 'id', ('block','trial'), test_ratio=0.2)
    X = merged_df[feats_full]; y = merged_df[TARGET]
    Xtr_full, ytr_full = X.iloc[tr_full], y.iloc[tr_full]
    Xte, yte = X.iloc[te_full], y.iloc[te_full]

    tr_core_rel, cal_rel = carve_calibration_from_train(merged_df.iloc[tr_full], cal_ratio=CAL_RATIO)
    Xtr_core, ytr_core = Xtr_full.iloc[tr_core_rel], ytr_full.iloc[tr_core_rel]
    Xcal, ycal         = Xtr_full.iloc[cal_rel],     ytr_full.iloc[cal_rel]
    cv_splits = chrono_cv_splits_on_train(merged_df.iloc[tr_full].iloc[tr_core_rel], 'id', ('block','trial'), n_folds=3)

    # Use best parameters from previous grid search
    best_params_cat = {'iterations': 200, 'depth': 4, 'learning_rate': 0.1, 'l2_leaf_reg': 1}
    cat_base = cb.CatBoostClassifier(loss_function='Logloss', random_state=42, verbose=False, allow_writing_files=False, **best_params_cat)
    cat_base.fit(Xtr_core, ytr_core)

    if CALIBRATE:
        cat_cal = CalibratedClassifierCV(estimator=cat_base, method=CAL_METHOD, cv='prefit')
        cat_cal.fit(Xcal, ycal)
        proba = cat_cal.predict_proba(Xte)[:,1]
    else:
        proba = cat_base.predict_proba(Xte)[:,1]

    # thresholds
    if CALIBRATE:
        cal_proba = (cat_cal.predict_proba(Xcal)[:,1])
        t_star, _ = best_threshold_f1(ycal.values, cal_proba)
    else:
        t_star = 0.5

    pred05 = (proba >= 0.5).astype(int)
    predT  = (proba >= t_star).astype(int)

    # metrics
    acc = accuracy_score(yte, pred05)
    f1  = f1_score(yte, pred05, zero_division=0)
    prc = precision_score(yte, pred05, zero_division=0)
    rec = recall_score(yte, pred05)
    auc = roc_auc_score(yte, proba)
    brier = brier_score_loss(yte, proba)
    ece = ece_score(yte.values, proba)

    acc_t = accuracy_score(yte, predT)
    f1_t  = f1_score(yte, predT, zero_division=0)
    prc_t = precision_score(yte, predT, zero_division=0)
    rec_t = recall_score(yte, predT)

    cm = confusion_matrix(yte, pred05)
    save_cm_plot(cm, 'catboost_full'); save_pr_cal_plots(yte.values, proba, 'catboost_full')

    # Try SHAP on CatBoost base
    try:
        import shap
        shap_sample = Xte.sample(min(3000, len(Xte)), random_state=42)
        explainer = shap.TreeExplainer(cat_base)
        shap_values = explainer.shap_values(shap_sample)
        shap.summary_plot(shap_values, shap_sample, show=False)
        plt.tight_layout(); plt.savefig(OUT / f'shap_summary_catboost_full.png', dpi=200, bbox_inches='tight'); plt.close()
    except Exception as e:
        with open(OUT / f'shap_catboost_full.txt','w') as f: f.write(f"SHAP skipped: {e}")

    fi = pd.DataFrame({'feature': feats_full,
                       'importance': getattr(cat_base, "get_feature_importance", lambda: np.zeros(len(feats_full)))()})
    fi = fi.sort_values('importance', ascending=False)
    fi.to_csv(OUT / 'feature_importance_catboost_full.csv', index=False)

    results.append({'tag':'catboost_full','acc':acc,'f1':f1,'prec':prc,'rec':rec,'auc':auc,
                    'brier':brier,'ece':ece,'acc_tuned':acc_t,'f1_tuned':f1_t,
                    'prec_tuned':prc_t,'rec_tuned':rec_t,'thresh':t_star})
    print(f"[catboost_full] Acc@0.5={acc:.4f}  F1@0.5={f1:.4f}  AUC={auc:.4f}  Brier={brier:.4f}  ECE={ece:.4f}  Best={best_params_cat}")
    if CALIBRATE:
        print(f"                Tuned t*={t_star:.2f}  Acc@t*={acc_t:.4f}  F1@t*={f1_t:.4f}")
except Exception as e:
    print(f"CatBoost not available or failed: {e}")

# ------------------------ Summaries & PDF ------------------------
summary = (pd.DataFrame([{k:v for k,v in res.items()
                          if k in ['tag','acc','f1','prec','rec','auc','brier','ece',
                                   'acc_tuned','f1_tuned','prec_tuned','rec_tuned','thresh']}
                         for res in results])
           .sort_values('f1', ascending=False))
summary.to_csv(OUT/'summary_ablation.csv', index=False)
print("\nAblation summary:\n", summary.to_string(index=False))

# Optional PDF one-pager
def build_pdf():
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        from reportlab.lib.utils import ImageReader
        pdf_path = OUT / 'exp1_report.pdf'
        c = canvas.Canvas(str(pdf_path), pagesize=A4)
        W, H = A4
        c.setFont("Helvetica-Bold", 16); c.drawString(40, H-50, "Experiment 1 — User Decision Prediction")
        c.setFont("Helvetica", 10)
        c.drawString(40, H-70, f"Agreement (user vs DS): {agree.mean()*100:.2f}%   N={len(agree):,}")
        c.drawString(40, H-85, f"Calibration: {CAL_METHOD if CALIBRATE else 'off'}   Cal ratio per-user: {CAL_RATIO*100:.0f}%")
        y = H-110
        c.setFont("Helvetica-Bold", 11); c.drawString(40, y, "Ablation Summary (test set)"); y -= 16
        c.setFont("Helvetica", 9)
        for _, row in summary.iterrows():
            c.drawString(50, y, f"{row['tag']:>24}  | Acc@0.5={row['acc']:.4f}  F1@0.5={row['f1']:.4f}  "
                                f"AUC={row['auc']:.4f}  ECE={row['ece']:.4f}  "
                                f"t*={row['thresh']:.2f}  Acc@t*={row['acc_tuned']:.4f}  F1@t*={row['f1_tuned']:.4f}")
            y -= 14
            if y < 120: c.showPage(); y = H-60
        for tag in [r['tag'] for r in results]:
            img = OUT / f'cm_norm_{tag}.png'
            if img.exists():
                if y < 300: c.showPage(); y = H-60
                c.setFont("Helvetica-Bold", 10); c.drawString(40, y, f"Confusion (norm) — {tag}")
                c.drawImage(ImageReader(str(img)), 40, y-230, width=250, height=230, preserveAspectRatio=True, mask='auto')
                shap_img = OUT / f'shap_summary_{tag}.png'
                if shap_img.exists():
                    c.drawou fString(320, y, f"SHAP — {tag}")
                    c.drawImage(ImageReader(str(shap_img)), 320, y-230, width=240, height=230, preserveAspectRatio=True, mask='auto')
                y -= 250
        c.showPage(); c.save(); print(f"Saved PDF: {pdf_path}")
    except Exception as e:
        with open(OUT / 'exp1_report.txt','w') as f:
            f.write("Install reportlab to get a PDF.\n")
            f.write(f"Summary:\n{summary.to_string(index=False)}\n")
        print(f"PDF skipped: {e}. Wrote exp1_report.txt instead.")

build_pdf()
