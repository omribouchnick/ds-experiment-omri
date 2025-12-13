# Predicting purchase of DS at each trial level based on historical behavior.

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, classification_report, confusion_matrix
import warnings
warnings.filterwarnings('ignore')
plt.switch_backend('Agg')

print("=== EXPERIMENT 2: PREDICTING DS PURCHASE AT TRIAL LEVEL ===")

# 1. LOAD DATA
print("\n=== 1. LOAD DATA ===")
raw_df = pd.read_csv('exp2_raw.csv')
print(f"Raw data shape: {raw_df.shape}")
print(f"Raw data columns: {list(raw_df.columns)}")

# 2. DATA CLEANING AND PREPARATION
print("\n=== 2. DATA CLEANING AND PREPARATION ===")
# Sort by user ID and trial to ensure proper ordering for rolling calculations
raw_df = raw_df.sort_values(['id', 'trial']).reset_index(drop=True)

# Create binary indicators (but these are constant per user, so we'll remove them later)
raw_df['isBinary'] = (raw_df['system_type'] == 'binary').astype(int)
raw_df['isIntegrated'] = (raw_df['system_type'] == 'integrated').astype(int)
raw_df['high_sensitivity'] = (raw_df['system_sensitivity'] == 'high').astype(int)

print(f"Data sorted and binary indicators created")
print(f"Note: System characteristics are constant per user (will be removed)")

# 3. FEATURE ENGINEERING ON TRIAL LEVEL
print("\n=== 3. FEATURE ENGINEERING ON TRIAL LEVEL ===")
def safe_eq(a, b):
    return (a == b) & ~(pd.isna(a) | pd.isna(b))

# Define difficulty and human_conf from previous trials only (no data leakage)
raw_df['prev_stimulus_s'] = raw_df.groupby('id')['stimulus_s'].shift(1)
raw_df['prev_human_p'] = raw_df.groupby('id')['human_p'].shift(1)

# Previous trial difficulty and human confidence (available before current purchase decision)
raw_df['difficulty'] = np.abs(raw_df['prev_stimulus_s'])
raw_df['human_conf'] = np.where(pd.notna(raw_df['prev_human_p']), np.abs(raw_df['prev_human_p'] - 0.5), np.nan)

# Confusion matrix elements (from previous trial only - no future info)
# Shift classification, event, and human confidence columns by 1 within each user to get previous trial's values
raw_df['prev_classification'] = raw_df.groupby('id')['classification'].shift(1)
raw_df['prev_event'] = raw_df.groupby('id')['event'].shift(1)
raw_df['prev_human_conf'] = raw_df.groupby('id')['human_conf'].shift(1)

# Note: prev_human_conf is the confidence from the previous trial, which is the only confidence value
# that could have been "seen" by the human before the current purchase decision.
# On the first trial for each user, these will be NaN (unseen).

raw_df['tp'] = safe_eq(raw_df['prev_classification'], 'Blue') & safe_eq(raw_df['prev_event'], 'Blue')
raw_df['fp'] = safe_eq(raw_df['prev_classification'], 'Blue') & safe_eq(raw_df['prev_event'], 'Orange')
raw_df['tn'] = safe_eq(raw_df['prev_classification'], 'Orange') & safe_eq(raw_df['prev_event'], 'Orange')
raw_df['fn'] = safe_eq(raw_df['prev_classification'], 'Orange') & safe_eq(raw_df['prev_event'], 'Blue')

print(f"Basic trial-level features created (all from previous trials - no data leakage)")

# 4. ROLLING HISTORICAL FEATURES
print("\n=== 4. ROLLING HISTORICAL FEATURES ===")

# Define rolling windows
rolling_windows = [3, 7, 14, 21, 50]

# Initialize columns for rolling features
for window in rolling_windows:
    # Historical performance metrics
    raw_df[f'tp_rolling_{window}'] = np.nan
    raw_df[f'fp_rolling_{window}'] = np.nan
    raw_df[f'tn_rolling_{window}'] = np.nan
    raw_df[f'fn_rolling_{window}'] = np.nan
    raw_df[f'accuracy_rolling_{window}'] = np.nan
    raw_df[f'f1_rolling_{window}'] = np.nan
    raw_df[f'precision_rolling_{window}'] = np.nan
    raw_df[f'recall_rolling_{window}'] = np.nan
    
    # Historical purchase behavior
    raw_df[f'purchase_rate_rolling_{window}'] = np.nan
    raw_df[f'purchase_count_rolling_{window}'] = np.nan
    
    # Historical timing and scores
    raw_df[f'time_mean_rolling_{window}'] = np.nan
    raw_df[f'score_mean_rolling_{window}'] = np.nan
    raw_df[f'score_max_rolling_{window}'] = np.nan
    raw_df[f'difficulty_mean_rolling_{window}'] = np.nan
    raw_df[f'human_conf_mean_rolling_{window}'] = np.nan

# Calculate rolling features for each user
print("Calculating rolling historical features...")
for user_id in raw_df['id'].unique():
    user_data = raw_df[raw_df['id'] == user_id].copy()
    
    for window in rolling_windows:
        # Rolling confusion matrix
        user_data[f'tp_rolling_{window}'] = user_data['tp'].rolling(window=window, min_periods=1).sum().shift(1)
        user_data[f'fp_rolling_{window}'] = user_data['fp'].rolling(window=window, min_periods=1).sum().shift(1)
        user_data[f'tn_rolling_{window}'] = user_data['tn'].rolling(window=window, min_periods=1).sum().shift(1)
        user_data[f'fn_rolling_{window}'] = user_data['fn'].rolling(window=window, min_periods=1).sum().shift(1)
        
        # Rolling purchase behavior
        user_data[f'purchase_rate_rolling_{window}'] = user_data['pd'].rolling(window=window, min_periods=1).mean().shift(1)
        user_data[f'purchase_count_rolling_{window}'] = user_data['pd'].rolling(window=window, min_periods=1).sum().shift(1)
        
        # Rolling performance metrics
        user_data[f'time_mean_rolling_{window}'] = user_data['time'].rolling(window=window, min_periods=1).mean().shift(1)
        user_data[f'score_mean_rolling_{window}'] = user_data['score'].rolling(window=window, min_periods=1).mean().shift(1)
        user_data[f'score_max_rolling_{window}'] = user_data['score'].rolling(window=window, min_periods=1).max().shift(1)
        user_data[f'difficulty_mean_rolling_{window}'] = user_data['difficulty'].rolling(window=window, min_periods=1).mean().shift(1)
        user_data[f'human_conf_mean_rolling_{window}'] = user_data['human_conf'].rolling(window=window, min_periods=1).mean().shift(1)
        
        # Calculate derived metrics from rolling confusion matrix
        tp_col = f'tp_rolling_{window}'
        fp_col = f'fp_rolling_{window}'
        tn_col = f'tn_rolling_{window}'
        fn_col = f'fn_rolling_{window}'
        
        # Accuracy
        user_data[f'accuracy_rolling_{window}'] = np.where(
            (user_data[tp_col] + user_data[fp_col] + user_data[tn_col] + user_data[fn_col]) > 0,
            (user_data[tp_col] + user_data[tn_col]) / (user_data[tp_col] + user_data[fp_col] + user_data[tn_col] + user_data[fn_col]),
            np.nan
        )
        
        # Precision
        user_data[f'precision_rolling_{window}'] = np.where(
            (user_data[tp_col] + user_data[fp_col]) > 0,
            user_data[tp_col] / (user_data[tp_col] + user_data[fp_col]),
            np.nan
        )
        
        # Recall
        user_data[f'recall_rolling_{window}'] = np.where(
            (user_data[tp_col] + user_data[fn_col]) > 0,
            user_data[tp_col] / (user_data[tp_col] + user_data[fn_col]),
            np.nan
        )
        
        # F1
        user_data[f'f1_rolling_{window}'] = np.where(
            (user_data[f'precision_rolling_{window}'] + user_data[f'recall_rolling_{window}']) > 0,
            2 * (user_data[f'precision_rolling_{window}'] * user_data[f'recall_rolling_{window}']) / 
            (user_data[f'precision_rolling_{window}'] + user_data[f'recall_rolling_{window}']),
            np.nan
        )
    
    # Update the main dataframe
    raw_df.loc[raw_df['id'] == user_id] = user_data

print(f"Rolling historical features calculated for {len(rolling_windows)} windows")

# 5. TRIAL-LEVEL FEATURES
print("\n=== 5. TRIAL-LEVEL FEATURES ===")

# Trial position features
raw_df['trial_number'] = raw_df.groupby('id').cumcount() + 1
raw_df['is_first_trial'] = (raw_df['trial_number'] == 1).astype(int)

# NO CURRENT TRIAL FEATURES - only historical and trial position (no data leakage)
print(f"Trial-level features created - NO current trial features (no data leakage)")

# Fill NaN values with appropriate defaults
for window in rolling_windows:
    # For first trials, set historical metrics to 0 or neutral values
    raw_df[f'purchase_rate_rolling_{window}'] = raw_df[f'purchase_rate_rolling_{window}'].fillna(0)
    raw_df[f'purchase_count_rolling_{window}'] = raw_df[f'purchase_count_rolling_{window}'].fillna(0)
    raw_df[f'time_mean_rolling_{window}'] = raw_df[f'time_mean_rolling_{window}'].fillna(raw_df['time'].mean())
    raw_df[f'score_mean_rolling_{window}'] = raw_df[f'score_mean_rolling_{window}'].fillna(raw_df['score'].mean())
    raw_df[f'score_max_rolling_{window}'] = raw_df[f'score_max_rolling_{window}'].fillna(raw_df['score'].mean())
    raw_df[f'difficulty_mean_rolling_{window}'] = raw_df[f'difficulty_mean_rolling_{window}'].fillna(raw_df['difficulty'].mean())
    raw_df[f'human_conf_mean_rolling_{window}'] = raw_df[f'human_conf_mean_rolling_{window}'].fillna(0.5)
    
    # For confusion matrix metrics, set to neutral values
    raw_df[f'accuracy_rolling_{window}'] = raw_df[f'accuracy_rolling_{window}'].fillna(0.5)
    raw_df[f'precision_rolling_{window}'] = raw_df[f'precision_rolling_{window}'].fillna(0.5)
    raw_df[f'recall_rolling_{window}'] = raw_df[f'recall_rolling_{window}'].fillna(0.5)
    raw_df[f'f1_rolling_{window}'] = raw_df[f'f1_rolling_{window}'].fillna(0.5)

print(f"NaN values handled for all rolling features")

# 6. FEATURE SELECTION AND TARGET
print("\n=== 6. FEATURE SELECTION AND TARGET ===")

# Target variable: whether DS was purchased in this trial
target = 'pd'

# Feature columns: ONLY historical features (no current trial - no data leakage)
feature_columns = [
    # Trial position
    'trial_number', 'is_first_trial',
    
    # Rolling historical features (3, 7, 14, 21, 50 trials back) - ALL from previous trials
    'purchase_rate_rolling_3', 'purchase_rate_rolling_7', 'purchase_rate_rolling_14', 'purchase_rate_rolling_21', 'purchase_rate_rolling_50',
    'purchase_count_rolling_3', 'purchase_count_rolling_7', 'purchase_count_rolling_14', 'purchase_count_rolling_21', 'purchase_count_rolling_50',
    'accuracy_rolling_3', 'accuracy_rolling_7', 'accuracy_rolling_14', 'accuracy_rolling_21', 'accuracy_rolling_50',
    'f1_rolling_3', 'f1_rolling_7', 'f1_rolling_14', 'f1_rolling_21', 'f1_rolling_50',
    'precision_rolling_3', 'precision_rolling_7', 'precision_rolling_14', 'precision_rolling_21', 'precision_rolling_50',
    'recall_rolling_3', 'recall_rolling_7', 'recall_rolling_14', 'recall_rolling_21', 'recall_rolling_50',
    'time_mean_rolling_3', 'time_mean_rolling_7', 'time_mean_rolling_14', 'time_mean_rolling_21', 'time_mean_rolling_50',
    'score_mean_rolling_3', 'score_mean_rolling_7', 'score_mean_rolling_14', 'score_mean_rolling_21', 'score_mean_rolling_50',
    'score_max_rolling_3', 'score_max_rolling_7', 'score_max_rolling_14', 'score_max_rolling_21', 'score_max_rolling_50',
    'difficulty_mean_rolling_3', 'difficulty_mean_rolling_7', 'difficulty_mean_rolling_14', 'difficulty_mean_rolling_21', 'difficulty_mean_rolling_50',
    'human_conf_mean_rolling_3', 'human_conf_mean_rolling_7', 'human_conf_mean_rolling_14', 'human_conf_mean_rolling_21', 'human_conf_mean_rolling_50'
]

# Filter features that exist in the dataframe
feature_columns = [c for c in feature_columns if c in raw_df.columns]

X = raw_df[feature_columns]
y = raw_df[target]

print(f"Target variable: {target}")
print(f"Target distribution:")
print(f"  Purchase (1): {y.sum()} trials ({y.mean()*100:.1f}%)")
print(f"  No Purchase (0): {(y==0).sum()} trials ({(1-y.mean())*100:.1f}%)")
print(f"Feature columns for modeling: {len(feature_columns)}")
print(f"Features shape: {X.shape}")
print(f"Target shape: {y.shape}")

# Check for NaN values
print(f"\n=== NaN CHECK ===")
nan_counts = X.isnull().sum()
print("NaN counts per feature:")
for col, count in nan_counts.items():
    if count > 0:
        print(f"  {col}: {count}")

# Remove rows with any NaN values in features
X_clean = X.dropna()
y_clean = y[X_clean.index]
print(f"\nAfter removing NaN: X={X_clean.shape}, y={y_clean.shape}")

# 7. VISUALIZATIONS
print("\n=== 7. VISUALIZATIONS ===")

# Correlation heatmap for key features
key_features = [f for f in feature_columns if 'rolling_7' in f or 'current_' in f or 'trial_' in f]
key_features = key_features[:20]  # Limit to 20 for readability

if len(key_features) > 1:
    plt.figure(figsize=(16, 12))
    corr = X_clean[key_features].corr()
    mask = np.triu(np.ones_like(corr, dtype=bool))
    sns.heatmap(corr, mask=mask, annot=True, cmap='coolwarm', center=0, 
                square=True, linewidths=0.5, cbar_kws={"shrink": .8}, fmt='.2f')
    plt.title('Feature Correlation Heatmap - Key Features (Trial Level)')
    plt.tight_layout()
    plt.savefig('exp2_purchase_correlation_heatmap.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Correlation heatmap saved as 'exp2_purchase_correlation_heatmap.png'")

# Distribution plots for key features
features_to_plot = [
    'current_difficulty', 'current_human_conf', 'current_high_sensitivity',
    'trial_number', 'purchase_rate_rolling_7', 'accuracy_rolling_7', 'f1_rolling_7'
]
features_to_plot = [f for f in features_to_plot if f in X_clean.columns]

ncols = 4
nrows = int(np.ceil(len(features_to_plot) / ncols))
fig, axes = plt.subplots(nrows, ncols, figsize=(20, 5 * nrows))
axes = axes.flatten()

for i, feat in enumerate(features_to_plot):
    axes[i].hist(X_clean[feat], bins=30, alpha=0.7, edgecolor='black')
    axes[i].set_title(f'{feat} Distribution')
    axes[i].set_xlabel(feat)
    axes[i].set_ylabel('Frequency')

for j in range(i+1, len(axes)):
    axes[j].axis('off')

plt.tight_layout()
plt.savefig('exp2_purchase_feature_distributions.png', dpi=300, bbox_inches='tight')
plt.close()
print("✓ Feature distributions saved as 'exp2_purchase_feature_distributions.png'")

# 8. DATA SPLIT
print("\n=== 8. DATA SPLIT ===")
X_train, X_test, y_train, y_test = train_test_split(X_clean, y_clean, test_size=0.2, random_state=42, stratify=y_clean)
print(f"Train: {X_train.shape}, Test: {X_test.shape}")
print(f"Train purchase rate: {y_train.mean():.3f}")
print(f"Test purchase rate: {y_test.mean():.3f}")

# 9. MODELING (CLASSIFICATION MODELS)
print("\n=== 9. MODELING (CLASSIFICATION) ===")
models = {
    'LogisticRegression': LogisticRegression(random_state=42, max_iter=1000),
    'RandomForest': RandomForestClassifier(n_estimators=100, random_state=42),
    'GradientBoosting': GradientBoostingClassifier(n_estimators=100, random_state=42)
}

results = {}
for name, model in models.items():
    print(f"\nTraining {name}...")
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    y_pred_proba = model.predict_proba(X_test)[:, 1] if hasattr(model, 'predict_proba') else None
    
    # Classification metrics
    accuracy = accuracy_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred)
    
    # Cross-validation
    cv_accuracy = cross_val_score(model, X_train, y_train, cv=5, scoring='accuracy').mean()
    cv_f1 = cross_val_score(model, X_train, y_train, cv=5, scoring='f1').mean()
    
    results[name] = {
        'model': model,
        'accuracy': accuracy,
        'f1': f1,
        'cv_accuracy': cv_accuracy,
        'cv_f1': cv_f1,
        'y_pred': y_pred,
        'y_pred_proba': y_pred_proba
    }
    
    print(f"{name}: Test Accuracy={accuracy:.3f}, Test F1={f1:.3f}")
    print(f"         CV Accuracy={cv_accuracy:.3f}, CV F1={cv_f1:.3f}")

# Find best model by F1 score
best_model_name = max(results.keys(), key=lambda x: results[x]['cv_f1'])
print(f"\nBest model by CV F1: {best_model_name}")

# HYPERPARAMETER TUNING FOR RANDOM FOREST
print("\n=== 9.5. HYPERPARAMETER TUNING ===")
if 'RandomForest' in results:
    print("Tuning Random Forest hyperparameters...")
    
    from sklearn.model_selection import GridSearchCV
    from sklearn.metrics import make_scorer, f1_score
    
    # Define parameter grid for Random Forest
    param_grid = {
        'n_estimators': [100, 200, 300],
        'max_depth': [10, 20, None],
        'min_samples_split': [2, 5, 10],
        'min_samples_leaf': [1, 2, 4],
        'class_weight': ['balanced', 'balanced_subsample', None]
    }
    
    # Use F1 score as the optimization metric
    f1_scorer = make_scorer(f1_score)
    
    # Grid search with cross-validation
    rf_tuned = RandomForestClassifier(random_state=42)
    grid_search = GridSearchCV(
        estimator=rf_tuned,
        param_grid=param_grid,
        scoring=f1_scorer,
        cv=5,
        n_jobs=-1,
        verbose=1
    )
    
    # Fit the grid search
    grid_search.fit(X_train, y_train)
    
    print(f"Best parameters: {grid_search.best_params_}")
    print(f"Best CV F1 score: {grid_search.best_score_:.3f}")
    
    # Get the best tuned model
    best_rf_tuned = grid_search.best_estimator_
    
    # Evaluate tuned model
    y_pred_tuned = best_rf_tuned.predict(X_test)
    y_pred_proba_tuned = best_rf_tuned.predict_proba(X_test)[:, 1]
    
    accuracy_tuned = accuracy_score(y_test, y_pred_tuned)
    f1_tuned = f1_score(y_test, y_pred_tuned)
    
    print(f"\nTuned Random Forest Performance:")
    print(f"  Test Accuracy: {accuracy_tuned:.3f}")
    print(f"  Test F1 Score: {f1_tuned:.3f}")
    print(f"  Improvement in F1: {f1_tuned - results['RandomForest']['f1']:.3f}")
    
    # Update results with tuned model
    results['RandomForest_Tuned'] = {
        'model': best_rf_tuned,
        'accuracy': accuracy_tuned,
        'f1': f1_tuned,
        'cv_accuracy': grid_search.best_score_,
        'cv_f1': grid_search.best_score_,
        'y_pred': y_pred_tuned,
        'y_pred_proba': y_pred_proba_tuned,
        'best_params': grid_search.best_params_
    }
    
    # Update best model if tuned version is better
    if f1_tuned > results[best_model_name]['f1']:
        best_model_name = 'RandomForest_Tuned'
        print(f"Tuned Random Forest is now the best model!")
else:
    print("Random Forest not available for tuning")

print(f"\nFinal best model by CV F1: {best_model_name}")

# 10. FEATURE IMPORTANCE
print("\n=== 10. FEATURE IMPORTANCE ===")
if 'RandomForest' in results:
    rf_model = results['RandomForest']['model']
    feature_importance = pd.DataFrame({
        'feature': X_clean.columns,
        'importance': rf_model.feature_importances_
    }).sort_values('importance', ascending=False)

    print("Random Forest Feature Importances (Trial Level):")
    for i, (_, row) in enumerate(feature_importance.head(20).iterrows(), 1):
        print(f"  {i:2d}. {row['feature']:40s} - {row['importance']:.4f}")

    plt.figure(figsize=(14, 10))
    sns.barplot(data=feature_importance.head(20), x='importance', y='feature', palette='plasma')
    plt.title('Top 20 Feature Importances (Random Forest) - Trial Level Purchase Prediction')
    plt.tight_layout()
    plt.savefig('exp2_purchase_feature_importance_RF.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Feature importance plot saved as 'exp2_purchase_feature_importance_RF.png'")

# 11. DETAILED EVALUATION
print("\n=== 11. DETAILED EVALUATION ===")
best_model = results[best_model_name]['model']
y_pred_best = results[best_model_name]['y_pred']

print(f"Best Model: {best_model_name}")
print(f"Test Set Performance:")
print(f"  Accuracy: {accuracy_score(y_test, y_pred_best):.3f}")
print(f"  F1 Score: {f1_score(y_test, y_pred_best):.3f}")

print(f"\nClassification Report:")
print(classification_report(y_test, y_pred_best))

# Confusion Matrix
cm = confusion_matrix(y_test, y_pred_best)
print(f"\nConfusion Matrix:")
print(f"  True Negatives: {cm[0,0]} (Correctly predicted no purchase)")
print(f"  False Positives: {cm[0,1]} (Incorrectly predicted purchase)")
print(f"  False Negatives: {cm[1,0]} (Incorrectly predicted no purchase)")
print(f"  True Positives: {cm[1,1]} (Correctly predicted purchase)")

# 12. SHAP ANALYSIS
print("\n=== 12. SHAP ANALYSIS ===")
try:
    import shap
    explainer = shap.TreeExplainer(best_model)
    shap_values = explainer.shap_values(X_test)
    
    # For binary classification, shap_values might be a list
    if isinstance(shap_values, list):
        shap_values = shap_values[1]  # Use positive class (purchase)
    
    plt.figure(figsize=(14, 10))
    shap.summary_plot(shap_values, X_test, feature_names=X_clean.columns, show=False)
    plt.title('SHAP Summary Plot - Trial Level Purchase Prediction')
    plt.tight_layout()
    plt.savefig('exp2_purchase_shap_summary.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ SHAP summary plot saved as 'exp2_purchase_shap_summary.png'")
    
    # SHAP feature importance
    shap_importance = np.abs(shap_values).mean(0)
    shap_feature_importance = pd.DataFrame({
        'feature': X_clean.columns,
        'shap_importance': shap_importance
    }).sort_values('shap_importance', ascending=False)
    
    print("\nTop 15 Most Important Features (SHAP) - Trial Level:")
    for i, (_, row) in enumerate(shap_feature_importance.head(15).iterrows(), 1):
        print(f"{i:2d}. {row['feature']:40s} - {row['shap_importance']:.4f}")
        
except ImportError:
    print("SHAP not available. Skipping SHAP analysis.")

# 13. FINAL INSIGHTS
print("\n=== 13. FINAL INSIGHTS ===")
print("Key Features for Purchase Prediction:")
print("- Historical purchase behavior (rolling windows: 3, 7, 21, 50 trials)")
print("- Historical performance metrics (accuracy, F1, precision, recall)")
print("- Current trial context (difficulty, human confidence, system type)")
print("- Trial position and timing information")

print(f"\nDataset Summary:")
print(f"- Total trials: {len(raw_df)}")
print(f"- Users: {raw_df['id'].nunique()}")
print(f"- Purchase rate: {y.mean()*100:.1f}%")
print(f"- Features: {len(feature_columns)}")
print(f"- Training samples: {len(X_train)}")
print(f"- Test samples: {len(X_test)}")

print("\nPurchase prediction analysis complete!")