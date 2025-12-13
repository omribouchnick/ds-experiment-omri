# Experiment 1 – within-user future prediction (no leakage) + ablations + SHAP + optional calibration
import pandas as pd, numpy as np, matplotlib.pyplot as plt
from pathlib import Path
from sklearn.metrics import (accuracy_score, f1_score, precision_score, recall_score,
                             confusion_matrix, roc_auc_score, precision_recall_curve,
                             average_precision_score)
from sklearn.calibration import calibration_curve, CalibratedClassifierCV
from sklearn.model_selection import GridSearchCV
import xgboost as xgb
import warnings, os
warnings.filterwarnings('ignore')
plt.switch_backend('Agg')

# ---------------- Config ----------------
RAW_PATH = 'data/exp1_raw.csv'
AGG_PATH = 'data/exp1_agg.csv'
OUT = Path('exp1_outputs'); OUT.mkdir(exist_ok=True)

# Toggle calibration
CALIBRATE = False          # <- set True to enable post-fit calibration
CAL_METHOD = 'isotonic'    # 'isotonic' or 'sigmoid'
CAL_RATIO = 0.10           # last 10% per-user of the training split used for calibration

# ---------------- Utils -----------------
def ece_score(y_true, y_prob, n_bins=15):
    """Expected Calibration Error."""
    bins = np.linspace(0.0, 1.0, n_bins+1)
    idx = np.digitize(y_prob, bins) - 1
    ece, total = 0.0, len(y_true)
    for b in range(n_bins):
        m = idx == b
        if not np.any(m): 
            continue
        conf = y_prob[m].mean()
        acc = (y_true[m] == (y_prob[m] >= 0.5)).mean()
        ece += (m.mean()) * abs(acc - conf)
    return ece

def log_featset(tag, feats):
    print(f"[{tag}] n_features={len(feats)}  "
          f"stim={'stimulus' in feats}, dsrec={'ds_recommends_signal' in feats}, dsconf={'ds_confidence' in feats}, "
          f"stim_rolls={sum(1 for f in feats if f.startswith('stimulus_mean_'))}")

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

merge_cols = ['id','block','avg_score_prev_blocks']
if dep_col is not None: merge_cols += [dep_col,'dependency_num']
merge_cols = [c for c in merge_cols if c in agg_df.columns]
merged_df = pd.merge(raw_df, agg_df[merge_cols].drop_duplicates(), on=['id','block'], how='left')

if dep_col is not None and dep_col in merged_df.columns:
    merged_df = pd.concat([merged_df, pd.get_dummies(merged_df[dep_col], prefix='dep')], axis=1)

# -------------- Rolling histories (shifted) --------------
rolling_windows = [1,3,7,14,21,50]
for w in rolling_windows:
    for base in ['signal_rate','agreement_rate','ds_correct_rate','user_correct_rate',
                 'tp_rate','fp_rate','fn_rate','tn_rate','stimulus_mean','classification_time_mean']:
        merged_df[f'{base}_rolling_{w}'] = np.nan

for _, idx in merged_df.groupby('id').indices.items():
    sub = merged_df.loc[idx].copy()
    for w in rolling_windows:
        sub[f'signal_rate_rolling_{w}']       = sub['target'].rolling(w, min_periods=1).mean().shift(1)
        sub[f'agreement_rate_rolling_{w}']    = sub['agrees_with_ds'].rolling(w, min_periods=1).mean().shift(1)
        sub[f'ds_correct_rate_rolling_{w}']   = sub['ds_was_correct'].rolling(w, min_periods=1).mean().shift(1)
        sub[f'user_correct_rate_rolling_{w}'] = sub['user_was_correct'].rolling(w, min_periods=1).mean().shift(1)
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
merged_df['is_first_trial'] = (merged_df['trial'] == 1).astype(int)
merged_df['is_first_block'] = (merged_df['block'] == 1).astype(int)
merged_df['ds_confidence']  = (merged_df['stimulus'] - 0.5).abs()
merged_df['purchase_ds_block_num'] = merged_df.groupby('id')['block'].rank(method='dense')

# -------------- Feature sets (no leak) --------------
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

# -------------- Train / evaluate (with optional calibration & SHAP) --------------
def train_eval_xgb(df, feature_cols, tag, test_ratio=0.2, n_folds=3, calibrate=False, cal_ratio=0.1, cal_method='isotonic'):
    X = df[feature_cols]; y = df[TARGET]
    tr_full, te_full = per_user_chrono_split(df, 'id', ('block','trial'), test_ratio=test_ratio)
    Xtr_full, ytr_full = X.iloc[tr_full], y.iloc[tr_full]
    Xte, yte = X.iloc[te_full], y.iloc[te_full]

    # Carve calibration holdout from training if calibrating
    if calibrate:
        tr_core_rel, cal_rel = carve_calibration_from_train(df.iloc[tr_full], cal_ratio=cal_ratio)
        Xtr_core, ytr_core = Xtr_full.iloc[tr_core_rel], ytr_full.iloc[tr_core_rel]
        Xcal, ycal = Xtr_full.iloc[cal_rel], ytr_full.iloc[cal_rel]
        # time-aware CV on train_core
        cv_splits = chrono_cv_splits_on_train(df.iloc[tr_full].iloc[tr_core_rel], 'id', ('block','trial'), n_folds=n_folds)
        # Grid on core
        grid = GridSearchCV(
            xgb.XGBClassifier(random_state=42, eval_metric='logloss', n_jobs=-1, tree_method='hist'),
            {'n_estimators':[100,200],'max_depth':[3,6],'learning_rate':[0.1,0.2],'subsample':[0.8,1.0]},
            cv=cv_splits, scoring='f1', n_jobs=-1, refit=True, verbose=0
        )
        grid.fit(Xtr_core, ytr_core)
        base_model = grid.best_estimator_
        # Calibrate
        calibrator = CalibratedClassifierCV(base_estimator=base_model, method=cal_method, cv='prefit')
        calibrator.fit(Xcal, ycal)
        clf = calibrator
        best_params = grid.best_params_
    else:
        # time-aware CV on full train
        cv_splits = chrono_cv_splits_on_train(df.iloc[tr_full], 'id', ('block','trial'), n_folds=n_folds)
        grid = GridSearchCV(
            xgb.XGBClassifier(random_state=42, eval_metric='logloss', n_jobs=-1, tree_method='hist'),
            {'n_estimators':[100,200],'max_depth':[3,6],'learning_rate':[0.1,0.2],'subsample':[0.8,1.0]},
            cv=cv_splits, scoring='f1', n_jobs=-1, refit=True, verbose=0
        )
        grid.fit(Xtr_full, ytr_full)
        clf = grid.best_estimator_
        base_model = clf
        best_params = grid.best_params_

    p = clf.predict(Xte)
    proba = clf.predict_proba(Xte)[:,1]
    acc  = accuracy_score(yte, p)
    f1   = f1_score(yte, p)
    prc  = precision_score(yte, p, zero_division=0)
    rec  = recall_score(yte, p)
    auc  = roc_auc_score(yte, proba)
    cm   = confusion_matrix(yte, p)
    ece  = ece_score(yte.values, proba)

    fi = (pd.DataFrame({'feature': feature_cols, 'importance': getattr(base_model, "feature_importances_", np.zeros(len(feature_cols)))})
          .sort_values('importance', ascending=False))
    fi.to_csv(OUT / f'feature_importance_{tag}.csv', index=False)

    # Plots
    save_cm_plot(cm, tag)
    save_pr_cal_plots(yte.values, proba, tag)

    # SHAP on the base (tree) model
    try:
        import shap
        shap_sample = Xte.sample(min(3000, len(Xte)), random_state=42)
        explainer = shap.TreeExplainer(base_model)
        shap_values = explainer.shap_values(shap_sample)
        shap.summary_plot(shap_values, shap_sample, show=False)
        plt.tight_layout(); plt.savefig(OUT / f'shap_summary_{tag}.png', dpi=200, bbox_inches='tight'); plt.close()
    except Exception as e:
        with open(OUT / f'shap_{tag}.txt','w') as f: f.write(f"SHAP skipped: {e}")

    print(f"[{tag}] Acc={acc:.4f}  F1={f1:.4f}  Prec={prc:.4f}  Rec={rec:.4f}  AUC={auc:.4f}  ECE={ece:.4f}  Best={best_params}")
    return {'tag':tag,'acc':acc,'f1':f1,'prec':prc,'rec':rec,'auc':auc,'ece':ece,'cm':cm,'fi':fi,'model':clf}

# ------------------------ Runs ------------------------
results = []

# Define feature sets
feats_full = FEATURES_NO_LEAK
log_featset('full', feats_full)
results.append(train_eval_xgb(merged_df, feats_full, tag='full', calibrate=CALIBRATE, cal_ratio=CAL_RATIO, cal_method=CAL_METHOD))

feats_no_stim = [f for f in FEATURES_NO_LEAK if f != 'stimulus']
log_featset('no_stimulus', feats_no_stim)
results.append(train_eval_xgb(merged_df, feats_no_stim, tag='no_stimulus', calibrate=CALIBRATE, cal_ratio=CAL_RATIO, cal_method=CAL_METHOD))

feats_no_dsrec = [f for f in FEATURES_NO_LEAK if f != 'ds_recommends_signal']
log_featset('no_dsrec', feats_no_dsrec)
results.append(train_eval_xgb(merged_df, feats_no_dsrec, tag='no_dsrec', calibrate=CALIBRATE, cal_ratio=CAL_RATIO, cal_method=CAL_METHOD))

feats_no_stim_no_dsrec = [f for f in FEATURES_NO_LEAK if f not in ['stimulus','ds_recommends_signal']]
log_featset('no_stimulus_no_dsrec', feats_no_stim_no_dsrec)
results.append(train_eval_xgb(merged_df, feats_no_stim_no_dsrec, tag='no_stimulus_no_dsrec', calibrate=CALIBRATE, cal_ratio=CAL_RATIO, cal_method=CAL_METHOD))

# NEW: drop current stimulus bundle (keep all rolling)
feats_no_current_bundle = [f for f in FEATURES_NO_LEAK if f not in ['stimulus','ds_recommends_signal','ds_confidence']]
log_featset('no_current_stim_bundle', feats_no_current_bundle)
results.append(train_eval_xgb(merged_df, feats_no_current_bundle, tag='no_current_stim_bundle', calibrate=CALIBRATE, cal_ratio=CAL_RATIO, cal_method=CAL_METHOD))

# Summaries
summary = (pd.DataFrame([{k:v for k,v in res.items() if k in ['tag','acc','f1','prec','rec','auc','ece']} for res in results])
          .sort_values('f1', ascending=False))
summary.to_csv(OUT/'summary_ablation.csv', index=False)
print("\nAblation summary:\n", summary.to_string(index=False))

# Optional PDF one-pager (requires reportlab)
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
        y = H-100
        c.setFont("Helvetica-Bold", 11); c.drawString(40, y, "Ablation Summary (test set)"); y -= 16
        c.setFont("Helvetica", 9)
        for _, row in summary.iterrows():
            c.drawString(50, y, f"{row['tag']:>24}  | Acc={row['acc']:.4f}  F1={row['f1']:.4f}  AUC={row['auc']:.4f}  ECE={row['ece']:.4f}")
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
                    c.drawString(320, y, f"SHAP — {tag}")
                    c.drawImage(ImageReader(str(shap_img)), 320, y-230, width=240, height=230, preserveAspectRatio=True, mask='auto')
                y -= 250
        c.showPage(); c.save(); print(f"Saved PDF: {pdf_path}")
    except Exception as e:
        with open(OUT / 'exp1_report.txt','w') as f:
            f.write("Install reportlab to get a PDF.\n")
            f.write(f"Summary:\n{summary.to_string(index=False)}\n")
        print(f"PDF skipped: {e}. Wrote exp1_report.txt instead.")

build_pdf()
