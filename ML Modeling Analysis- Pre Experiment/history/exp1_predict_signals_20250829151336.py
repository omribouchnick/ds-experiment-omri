# Experiment 1: Predicting User Signal/Noise Decisions at Trial Level
# Using historical behavior patterns and DS interaction history

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

print("=== EXPERIMENT 1: PREDICTING USER SIGNAL/NOISE DECISIONS AT TRIAL LEVEL ===")

# 1. LOAD DATA
print("\n=== 1. LOAD DATA ===")
raw_df = pd.read_csv('exp1_raw.csv')
agg_df = pd.read_csv('exp1_agg.csv')
print(f"Raw data shape: {raw_df.shape}")
print(f"Raw data columns: {list(raw_df.columns)}")
print(f"Aggregated data shape: {agg_df.shape}")
print(f"Aggregated data columns: {list(agg_df.columns)}")

# 2. DATA CLEANING AND PREPARATION
print("\n=== 2. DATA CLEANING AND PREPARATION ===")
# Clean column names
raw_df.columns = raw_df.columns.str.lower().str.replace(' ', '_')
agg_df.columns = agg_df.columns.str.lower().str.replace(' ', '_')

# Filter for alert system trials only
raw_df = raw_df.query('alert_system == 1').copy()

# Sort by user ID and trial order
raw_df = raw_df.sort_values(['id', 'block', 'counterbalance_block']).reset_index(drop=True)

print(f"Data cleaned and sorted")
print(f"Filtered data shape: {raw_df.shape}")

# 3. TARGET VARIABLE AND BASIC FEATURES
print("\n=== 3. TARGET VARIABLE AND BASIC FEATURES ===")
# Target: user_action (S = Signal, N = Noise)
raw_df['target'] = (raw_df['user_action'] == 'S').astype(int)  # 1 = Signal, 0 = Noise

# Basic features from current trial
raw_df['is_signal_event'] = (raw_df['event_type'] == 'S').astype(int)
raw_df['ds_recommends_signal'] = (raw_df['system_d'] == 'S').astype(int)
raw_df['ds_recommends_noise'] = (raw_df['system_d'] == 'N').astype(int)

# Agreement with DS
raw_df['agrees_with_ds'] = (raw_df['user_action'] == raw_df['system_d']).astype(int)
raw_df['disagrees_with_ds'] = (raw_df['user_action'] != raw_df['system_d']).astype(int)

# DS was correct
raw_df['ds_was_correct'] = (raw_df['system_d'] == raw_df['event_type']).astype(int)
raw_df['ds_was_wrong'] = (raw_df['system_d'] != raw_df['event_type']).astype(int)

# User was correct
raw_df['user_was_correct'] = (raw_df['user_action'] == raw_df['event_type']).astype(int)
raw_df['user_was_wrong'] = (raw_df['user_action'] != raw_df['event_type']).astype(int)

# Confusion matrix elements
raw_df['tp'] = ((raw_df['user_action'] == 'S') & (raw_df['event_type'] == 'S')).astype(int)
raw_df['fp'] = ((raw_df['user_action'] == 'S') & (raw_df['event_type'] == 'N')).astype(int)
raw_df['tn'] = ((raw_df['user_action'] == 'N') & (raw_df['event_type'] == 'N')).astype(int)
raw_df['fn'] = ((raw_df['user_action'] == 'N') & (raw_df['event_type'] == 'S')).astype(int)

print(f"Basic features created")
print(f"Target distribution:")
print(f"  Signal (1): {raw_df['target'].sum()} trials ({raw_df['target'].mean()*100:.1f}%)")
print(f"  Noise (0): {(raw_df['target']==0).sum()} trials ({(1-raw_df['target'].mean())*100:.1f}%)")

# 4. ROLLING HISTORICAL FEATURES
print("\n=== 4. ROLLING HISTORICAL FEATURES ===")
# Define rolling windows
rolling_windows = [1, 3, 7, 14, 21, 50]

# Initialize columns for rolling features
for window in rolling_windows:
    # Historical signal/noise decisions
    raw_df[f'signal_rate_rolling_{window}'] = np.nan
    raw_df[f'noise_rate_rolling_{window}'] = np.nan
    
    # Historical agreement with DS
    raw_df[f'agreement_rate_rolling_{window}'] = np.nan
    raw_df[f'disagreement_rate_rolling_{window}'] = np.nan
    
    # Historical DS performance
    raw_df[f'ds_correct_rate_rolling_{window}'] = np.nan
    raw_df[f'ds_wrong_rate_rolling_{window}'] = np.nan
    
    # Historical user performance
    raw_df[f'user_correct_rate_rolling_{window}'] = np.nan
    raw_df[f'user_wrong_rate_rolling_{window}'] = np.nan
    
    # Historical performance metrics
    raw_df[f'tp_rate_rolling_{window}'] = np.nan
    raw_df[f'fp_rate_rolling_{window}'] = np.nan
    raw_df[f'tn_rate_rolling_{window}'] = np.nan
    raw_df[f'fn_rate_rolling_{window}'] = np.nan
    
    # Historical stimulus patterns
    raw_df[f'stimulus_h_mean_rolling_{window}'] = np.nan
    raw_df[f'stimulus_h_std_rolling_{window}'] = np.nan
    
    # Historical response times
    raw_df[f'classification_time_mean_rolling_{window}'] = np.nan
    raw_df[f'classification_time_std_rolling_{window}'] = np.nan

# Calculate rolling features for each user
print("Calculating rolling historical features...")
for user_id in raw_df['id'].unique():
    user_data = raw_df[raw_df['id'] == user_id].copy()
    
    for window in rolling_windows:
        # Rolling signal/noise rates
        user_data[f'signal_rate_rolling_{window}'] = user_data['target'].rolling(window=window, min_periods=1).mean().shift(1)
        user_data[f'noise_rate_rolling_{window}'] = (1 - user_data['target']).rolling(window=window, min_periods=1).mean().shift(1)
        
        # Rolling agreement rates
        user_data[f'agreement_rate_rolling_{window}'] = user_data['agrees_with_ds'].rolling(window=window, min_periods=1).mean().shift(1)
        user_data[f'disagreement_rate_rolling_{window}'] = user_data['disagrees_with_ds'].rolling(window=window, min_periods=1).mean().shift(1)
        
        # Rolling DS performance
        user_data[f'ds_correct_rate_rolling_{window}'] = user_data['ds_was_correct'].rolling(window=window, min_periods=1).mean().shift(1)
        user_data[f'ds_wrong_rate_rolling_{window}'] = user_data['ds_was_wrong'].rolling(window=window, min_periods=1).mean().shift(1)
        
        # Rolling user performance
        user_data[f'user_correct_rate_rolling_{window}'] = user_data['user_was_correct'].rolling(window=window, min_periods=1).mean().shift(1)
        user_data[f'user_wrong_rate_rolling_{window}'] = user_data['user_was_wrong'].rolling(window=window, min_periods=1).mean().shift(1)
        
        # Rolling performance metrics
        user_data[f'tp_rate_rolling_{window}'] = user_data['tp'].rolling(window=window, min_periods=1).mean().shift(1)
        user_data[f'fp_rate_rolling_{window}'] = user_data['fp'].rolling(window=window, min_periods=1).mean().shift(1)
        user_data[f'tn_rate_rolling_{window}'] = user_data['tn'].rolling(window=window, min_periods=1).mean().shift(1)
        user_data[f'fn_rate_rolling_{window}'] = user_data['fn'].rolling(window=window, min_periods=1).mean().shift(1)
        
        # Rolling stimulus patterns
        user_data[f'stimulus_h_mean_rolling_{window}'] = user_data['stimulus_h'].rolling(window=window, min_periods=1).mean().shift(1)
        user_data[f'stimulus_h_std_rolling_{window}'] = user_data['stimulus_h'].rolling(window=window, min_periods=1).std().shift(1)
        
        # Rolling response times
        user_data[f'classification_time_mean_rolling_{window}'] = user_data['classification_time'].rolling(window=window, min_periods=1).mean().shift(1)
        user_data[f'classification_time_std_rolling_{window}'] = user_data['classification_time'].rolling(window=window, min_periods=1).std().shift(1)
    
    # Update the main dataframe
    raw_df.loc[raw_df['id'] == user_id] = user_data

print(f"Rolling historical features calculated for {len(rolling_windows)} windows")

# 5. TRIAL-LEVEL FEATURES
print("\n=== 5. TRIAL-LEVEL FEATURES ===")
# Trial position features
raw_df['trial_number'] = raw_df.groupby('id').cumcount() + 1
raw_df['is_first_trial'] = (raw_df['trial_number'] == 1).astype(int)

# Block position features
raw_df['block_number'] = raw_df.groupby('id')['block'].rank(method='dense')
raw_df['is_first_block'] = (raw_df['block_number'] == 1).astype(int)

# Stimulus difficulty (absolute value)
raw_df['stimulus_difficulty'] = np.abs(raw_df['stimulus_h'])

# DS confidence (how certain is the DS recommendation)
raw_df['ds_confidence'] = np.abs(raw_df['stimulus_h'])  # Higher stimulus = more confident DS

print(f"Trial-level features created")

# 6. FEATURE SELECTION AND TARGET
print("\n=== 6. FEATURE SELECTION AND TARGET ===")
# Target variable
target = 'target'

# Feature columns: historical + current trial features
feature_columns = [
    # Current trial features
    'stimulus_h', 'stimulus_difficulty', 'ds_confidence',
    'ds_recommends_signal', 'ds_recommends_noise',
    'is_signal_event', 'trial_number', 'is_first_trial',
    'block_number', 'is_first_block',
    
    # Rolling historical features (1, 3, 7, 14, 21, 50 trials back)
    'signal_rate_rolling_1', 'signal_rate_rolling_3', 'signal_rate_rolling_7', 'signal_rate_rolling_14', 'signal_rate_rolling_21', 'signal_rate_rolling_50',
    'noise_rate_rolling_1', 'noise_rate_rolling_3', 'noise_rate_rolling_7', 'noise_rate_rolling_14', 'noise_rate_rolling_21', 'noise_rate_rolling_50',
    'agreement_rate_rolling_1', 'agreement_rate_rolling_3', 'agreement_rate_rolling_7', 'agreement_rate_rolling_14', 'agreement_rate_rolling_21', 'agreement_rate_rolling_50',
    'disagreement_rate_rolling_1', 'disagreement_rate_rolling_3', 'disagreement_rate_rolling_7', 'disagreement_rate_rolling_14', 'disagreement_rate_rolling_21', 'disagreement_rate_rolling_50',
    'ds_correct_rate_rolling_1', 'ds_correct_rate_rolling_3', 'ds_correct_rate_rolling_7', 'ds_correct_rate_rolling_14', 'ds_correct_rate_rolling_21', 'ds_correct_rate_rolling_50',
    'ds_wrong_rate_rolling_1', 'ds_wrong_rate_rolling_3', 'ds_wrong_rate_rolling_7', 'ds_wrong_rate_rolling_14', 'ds_wrong_rate_rolling_21', 'ds_wrong_rate_rolling_50',
    'user_correct_rate_rolling_1', 'user_correct_rate_rolling_3', 'user_correct_rate_rolling_7', 'user_correct_rate_rolling_14', 'user_correct_rate_rolling_21', 'user_correct_rate_rolling_50',
    'user_wrong_rate_rolling_1', 'user_wrong_rate_rolling_3', 'user_wrong_rate_rolling_7', 'user_wrong_rate_rolling_14', 'user_wrong_rate_rolling_21', 'user_wrong_rate_rolling_50',
    'tp_rate_rolling_1', 'tp_rate_rolling_3', 'tp_rate_rolling_7', 'tp_rate_rolling_14', 'tp_rate_rolling_21', 'tp_rate_rolling_50',
    'fp_rate_rolling_1', 'fp_rate_rolling_3', 'fp_rate_rolling_7', 'fp_rate_rolling_14', 'fp_rate_rolling_21', 'fp_rate_rolling_50',
    'tn_rate_rolling_1', 'tn_rate_rolling_3', 'tn_rate_rolling_7', 'tn_rate_rolling_14', 'tn_rate_rolling_21', 'tn_rate_rolling_50',
    'fn_rate_rolling_1', 'fn_rate_rolling_3', 'fn_rate_rolling_7', 'fn_rate_rolling_14', 'fn_rate_rolling_21', 'fn_rate_rolling_50',
    'stimulus_h_mean_rolling_1', 'stimulus_h_mean_rolling_3', 'stimulus_h_mean_rolling_7', 'stimulus_h_mean_rolling_14', 'stimulus_h_mean_rolling_21', 'stimulus_h_mean_rolling_50',
    'stimulus_h_std_rolling_1', 'stimulus_h_std_rolling_3', 'stimulus_h_std_rolling_7', 'stimulus_h_std_rolling_14', 'stimulus_h_std_rolling_21', 'stimulus_h_std_rolling_50',
    'classification_time_mean_rolling_1', 'classification_time_mean_rolling_3', 'classification_time_mean_rolling_7', 'classification_time_mean_rolling_14', 'classification_time_mean_rolling_21', 'classification_time_mean_rolling_50',
    'classification_time_std_rolling_1', 'classification_time_std_rolling_3', 'classification_time_std_rolling_7', 'classification_time_std_rolling_14', 'classification_time_std_rolling_21', 'classification_time_std_rolling_50'
]

# Filter features that exist in the dataframe
feature_columns = [c for c in feature_columns if c in raw_df.columns]

X = raw_df[feature_columns]
y = raw_df[target]

print(f"Target variable: {target}")
print(f"Target distribution:")
print(f"  Signal (1): {y.sum()} trials ({y.mean()*100:.1f}%)")
print(f"  Noise (0): {(y==0).sum()} trials ({(1-y.mean())*100:.1f}%)")
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
key_features = [f for f in feature_columns if 'rolling_7' in f or 'stimulus' in f or 'ds_' in f]
key_features = key_features[:20]  # Limit to 20 for readability

if len(key_features) > 1:
    plt.figure(figsize=(16, 12))
    corr = X_clean[key_features].corr()
    mask = np.triu(np.ones_like(corr, dtype=bool))
    sns.heatmap(corr, mask=mask, annot=True, cmap='coolwarm', center=0, 
                square=True, linewidths=0.5, cbar_kws={"shrink": .8}, fmt='.2f')
    plt.title('Feature Correlation Heatmap - Key Features (Trial Level)')
    plt.tight_layout()
    plt.savefig('exp1_signals_correlation_heatmap.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Correlation heatmap saved as 'exp1_signals_correlation_heatmap.png'")

# Distribution plots for key features
features_to_plot = [
    'stimulus_h', 'stimulus_difficulty', 'ds_confidence',
    'signal_rate_rolling_7', 'agreement_rate_rolling_7', 'ds_correct_rate_rolling_7'
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
plt.savefig('exp1_signals_feature_distributions.png', dpi=300, bbox_inches='tight')
plt.close()
print("✓ Feature distributions saved as 'exp1_signals_feature_distributions.png'")

# 8. DATA SPLIT
print("\n=== 8. DATA SPLIT ===")
X_train, X_test, y_train, y_test = train_test_split(X_clean, y_clean, test_size=0.2, random_state=42, stratify=y_clean)
print(f"Train: {X_train.shape}, Test: {X_test.shape}")
print(f"Train signal rate: {y_train.mean():.3f}")
print(f"Test signal rate: {y_test.mean():.3f}")

# 9. MODELING (CLASSIFICATION)
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
    plt.title('Top 20 Feature Importances (Random Forest) - Trial Level Signal Prediction')
    plt.tight_layout()
    plt.savefig('exp1_signals_feature_importance_RF.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Feature importance plot saved as 'exp1_signals_feature_importance_RF.png'")

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
print(f"  True Negatives: {cm[0,0]} (Correctly predicted noise)")
print(f"  False Positives: {cm[0,1]} (Incorrectly predicted signal)")
print(f"  False Negatives: {cm[1,0]} (Incorrectly predicted noise)")
print(f"  True Positives: {cm[1,1]} (Correctly predicted signal)")

# 12. ROLLING WINDOW ANALYSIS
print("\n=== 12. ROLLING WINDOW ANALYSIS ===")
print("Analyzing the impact of different rolling window sizes...")

# Group features by window size
window_analysis = {}
for col in X_clean.columns:
    if 'rolling_' in col:
        window_size = col.split('rolling_')[-1]
        if window_size not in window_analysis:
            window_analysis[window_size] = []
        window_analysis[window_size].append(col)

# Calculate average importance for each window size
if 'RandomForest' in results:
    rf_model = results['RandomForest']['model']
    feature_importance = pd.DataFrame({
        'feature': X_clean.columns,
        'importance': rf_model.feature_importances_
    })
    
    print("\nRolling Window Impact Analysis:")
    for window_size in sorted(window_analysis.keys(), key=int):
        window_features = window_analysis[window_size]
        window_importance = feature_importance[feature_importance['feature'].isin(window_features)]['importance'].mean()
        print(f"  Window {window_size:2s}: Average importance = {window_importance:.4f}")
        
        # Show top 3 features for this window
        top_features = feature_importance[feature_importance['feature'].isin(window_features)].nlargest(3, 'importance')
        for _, row in top_features.iterrows():
            print(f"    - {row['feature']:35s}: {row['importance']:.4f}")

# 13. FINAL INSIGHTS
print("\n=== 13. FINAL INSIGHTS ===")
print("Key Features for Signal/Noise Prediction:")
print("- Historical signal/noise decision patterns (rolling windows: 1, 3, 7, 14, 21, 50 trials)")
print("- Historical agreement/disagreement with DS")
print("- Historical DS and user performance")
print("- Current trial context (stimulus strength, DS recommendation)")
print("- Trial and block position information")

print(f"\nDataset Summary:")
print(f"- Total trials: {len(raw_df)}")
print(f"- Users: {raw_df['id'].nunique()}")
print(f"- Signal rate: {y.mean()*100:.1f}%")
print(f"- Features: {len(feature_columns)}")
print(f"- Training samples: {len(X_train)}")
print(f"- Test samples: {len(X_test)}")

print("\nSignal prediction analysis complete!")
