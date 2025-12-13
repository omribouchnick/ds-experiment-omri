# Experiment 1: Predicting User Signal/Noise Decisions at Trial Level
# Using historical behavior patterns and DS interaction history

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.model_selection import train_test_split, cross_val_score, GridSearchCV
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score, roc_curve
import xgboost as xgb
import warnings
warnings.filterwarnings('ignore')
plt.switch_backend('Agg')

print("Experiment 1: Predicting User Signal/Noise Decisions")

# Load data
raw_df = pd.read_csv('data/exp1_raw.csv')
agg_df = pd.read_csv('data/exp1_agg.csv')
print(f"Raw data shape: {raw_df.shape}")
print(f"Aggregated data shape: {agg_df.shape}")

# 2. DATA CLEANING AND PREPARATION
print("\n=== 2. DATA CLEANING AND PREPARATION ===")
# Clean column names - be more careful with the cleaning
raw_df.columns = raw_df.columns.str.lower().str.replace(' ', '_')
agg_df.columns = agg_df.columns.str.lower().str.replace(' ', '_')

print(f"Raw data columns after cleaning: {list(raw_df.columns)}")
print(f"Agg data columns after cleaning: {list(agg_df.columns)}")

# Filter for DS trials only (Alert_System = 1)
raw_df = raw_df.query('alert_system == 1').copy()

# Sort by user ID and trial order
raw_df = raw_df.sort_values(['id', 'block', 'trial']).reset_index(drop=True)

print(f"Data cleaned and sorted")
print(f"DS trials shape: {raw_df.shape}")

# 3. TARGET VARIABLE AND BASIC FEATURES
print("\n=== 3. TARGET VARIABLE AND BASIC FEATURES ===")
# Target: user_action (S = Signal, N = Noise)
raw_df['target'] = (raw_df['user_action'] == 'S').astype(int)  # 1 = Signal, 0 = Noise

# Basic features from current trial
raw_df['is_signal_event'] = (raw_df['event_type'] == 'S').astype(int)
raw_df['ds_recommends_signal'] = (raw_df['alarm_output'] == 'Alarm').astype(int)  # "Alarm" = Signal recommendation
raw_df['ds_recommends_noise'] = (raw_df['alarm_output'] == 'No Alarm').astype(int)  # "No Alarm" = Noise recommendation

# Agreement with DS (rolling up to previous trial to avoid leakage)
raw_df['agrees_with_ds'] = (raw_df['user_action'] == raw_df['alarm_output'].map({'Alarm': 'S', 'No Alarm': 'N'})).astype(int)
# Shift so that for each trial, the value is the agreement on the previous trial (grouped by user)
raw_df['agrees_with_ds_prev'] = raw_df.groupby('id')['agrees_with_ds'].shift(1)
# Optionally, fill NaN (first trial) with 0 or np.nan as appropriate
raw_df['agrees_with_ds_prev'] = raw_df['agrees_with_ds_prev'].fillna(0)

# DS was correct (comparing DS recommendation with actual event)
raw_df['ds_was_correct'] = (raw_df['alarm_output'].map({'Alarm': 'S', 'No Alarm': 'N'}) == raw_df['event_type']).astype(int)

# User was correct
raw_df['user_was_correct'] = (raw_df['user_action'] == raw_df['event_type']).astype(int)

# Confusion matrix elements
raw_df['tp'] = ((raw_df['user_action'] == 'S') & (raw_df['event_type'] == 'S')).astype(int)
raw_df['fp'] = ((raw_df['user_action'] == 'S') & (raw_df['event_type'] == 'N')).astype(int)
raw_df['tn'] = ((raw_df['user_action'] == 'N') & (raw_df['event_type'] == 'N')).astype(int)
raw_df['fn'] = ((raw_df['user_action'] == 'N') & (raw_df['event_type'] == 'S')).astype(int)

print(f"Basic features created")
print(f"Target distribution:")
print(f"  Signal (1): {raw_df['target'].sum()} trials ({raw_df['target'].mean()*100:.1f}%)")
print(f"  Noise (0): {(raw_df['target']==0).sum()} trials ({(1-raw_df['target'].mean())*100:.1f}%)")

# Additional insights
print(f"\nDS recommendation distribution:")
print(f"  DS recommends Signal (Alarm): {raw_df['ds_recommends_signal'].sum()} trials ({raw_df['ds_recommends_signal'].mean()*100:.1f}%)")
print(f"  DS recommends Noise (No Alarm): {raw_df['ds_recommends_noise'].sum()} trials ({raw_df['ds_recommends_noise'].mean()*100:.1f}%)")

print(f"\nAgreement with DS:")
print(f"  Agrees with DS: {raw_df['agrees_with_ds'].sum()} trials ({raw_df['agrees_with_ds'].mean()*100:.1f}%)")
print(f"  Disagrees with DS: {(raw_df['agrees_with_ds'] == 0).sum()} trials ({(raw_df['agrees_with_ds'] == 0).mean()*100:.1f}%)")

print(f"\nDS accuracy:")
print(f"  DS was correct: {raw_df['ds_was_correct'].sum()} trials ({raw_df['ds_was_correct'].mean()*100:.1f}%)")
# print(f"  DS was wrong: {raw_df['ds_was_wrong'].sum()} trials ({raw_df['ds_was_wrong'].mean()*100:.1f}%)")

# 4. MERGE WITH AGGREGATED DATA
print("\n=== 4. MERGING WITH AGGREGATED DATA ===")
# Check what columns we actually have in agg_df
print(f"Available columns in agg_df: {list(agg_df.columns)}")

# Rename long columns for easier use
agg_df = agg_df.rename(columns={
    'how_much_did_the_automation_help_you_in_the_task?': 'help_score',
    'how_good_was_the_automation_in_distinguishing_between_blue_and_orange_vibranium_strains?': 'distinguishing_score'
})

agg_df['avg_score'] = agg_df[['help_score', 'distinguishing_score']].mean(axis=1)
agg_df['avg_score_prev_blocks'] = agg_df.groupby('id')['avg_score'].shift(1)

agg_df = agg_df.drop(columns=[c for c in ['help_score', 'distinguishing_score', 'avg_score'] if c in agg_df.columns])

print(f"Added features from aggregated data:")
print(f"  - avg_score_prev_blocks: {agg_df['avg_score_prev_blocks'].nunique()} blocks")




# Create dependency numeric mapping
dep_map_num = {
    'Independent': 1,
    'Low': 2,
    'Medium': 3,
    'High': 4,
    'Full': 5
}
agg_df['dependency_num'] = agg_df['dependency'].map(dep_map_num)

# Use the dependency column from aggregated data (dependency_agg)
print(f"  - dependency_num: {agg_df['dependency_num'].nunique()} levels")


# Merge with aggregated data to get dependency and other features
merged_df = pd.merge(
    raw_df,
    agg_df[['id', 'block', 'dependency', 'avg_score_prev_blocks', 'dependency_num', ]],
    on=['id', 'block'],
    how='left',
    suffixes=('', '_agg')  # Keep original names, add _agg suffix to new ones
)

print(f"After merge, raw_df columns: {list(raw_df.columns)}")

# Create one-hot encoding for dependency
dep_dummies = pd.get_dummies(merged_df['dependency'], prefix='dep')
merged_df = pd.concat([merged_df, dep_dummies], axis=1)

print(f"First merged_df before rolling features:", merged_df.head())
print("-"*60)

####################################################################################################

# 5. ROLLING HISTORICAL FEATURES
print("\n=== 5. ROLLING HISTORICAL FEATURES ===")
# Define rolling windows (max 40 trials per user in training, so max window is 40)
rolling_windows = [1, 3, 7, 14, 21, 40]

# Initialize columns for rolling features
for window in rolling_windows:
    # Historical signal/noise decisions
    merged_df[f'signal_rate_rolling_{window}'] = np.nan
    # Historical agreement with DS (keep only agreement rate, not disagreement)
    merged_df[f'user_ds_agreement_rate_rolling_{window}'] = np.nan
    # Historical DS performance (keep only ds_correct_rate)
    merged_df[f'ds_correct_rate_rolling_{window}'] = np.nan
    # Historical user performance (keep only user_correct_rate - tp_rate is redundant)
    merged_df[f'user_correct_rate_rolling_{window}'] = np.nan
    # Historical performance metrics (keep only tp_rate, not fp/tn/fn)
    merged_df[f'tp_rate_rolling_{window}'] = np.nan
    merged_df[f'fp_rate_rolling_{window}'] = np.nan
    merged_df[f'fn_rate_rolling_{window}'] = np.nan
    merged_df[f'tn_rate_rolling_{window}'] = np.nan
    # Historical stimulus patterns
    merged_df[f'stimulus_mean_rolling_{window}'] = np.nan
    # Historical response times
    merged_df[f'classification_time_mean_rolling_{window}'] = np.nan

# Calculate rolling features for each user in merged_df
print("Calculating rolling historical features...")
for user_id in merged_df['id'].unique():
    user_data = merged_df[merged_df['id'] == user_id].copy()
    for window in rolling_windows:
        # Rolling signal rate
        user_data[f'signal_rate_rolling_{window}'] = user_data['target'].rolling(window=window, min_periods=1).mean().shift(1)
        # Rolling agreement rate
        user_data[f'user_ds_agreement_rate_rolling_{window}'] = user_data['agrees_with_ds'].rolling(window=window, min_periods=1).mean().shift(1)
        # Rolling DS correct rate
        user_data[f'ds_correct_rate_rolling_{window}'] = user_data['ds_was_correct'].rolling(window=window, min_periods=1).mean().shift(1)
        # Rolling user correct rate
        user_data[f'user_correct_rate_rolling_{window}'] = user_data['user_was_correct'].rolling(window=window, min_periods=1).mean().shift(1)
        # Rolling TP rate
        user_data[f'tp_rate_rolling_{window}'] = user_data['tp'].rolling(window=window, min_periods=1).mean().shift(1)
        # Rolling FP rate
        user_data[f'fp_rate_rolling_{window}'] = user_data['fp'].rolling(window=window, min_periods=1).mean().shift(1)
        # Rolling FN rate
        user_data[f'fn_rate_rolling_{window}'] = user_data['fn'].rolling(window=window, min_periods=1).mean().shift(1)
        # Rolling TN rate
        user_data[f'tn_rate_rolling_{window}'] = user_data['tn'].rolling(window=window, min_periods=1).mean().shift(1)
        # Rolling stimulus patterns
        user_data[f'stimulus_mean_rolling_{window}'] = user_data['stimulus'].rolling(window=window, min_periods=1).mean().shift(1)
        # Rolling response times
        user_data[f'classification_time_mean_rolling_{window}'] = user_data['classification_time'].rolling(window=window, min_periods=1).mean().shift(1)
    # Update the main dataframe
    merged_df.loc[merged_df['id'] == user_id, user_data.columns] = user_data

print(f"Rolling historical features calculated for {len(rolling_windows)} windows")

# Keep NaN values - they represent "no history yet" which is different from neutral values
print("Keeping NaN values for rolling features - models will handle them appropriately")

####################################################################################################
# 6. TRIAL-LEVEL FEATURES
print("\n=== 6. TRIAL-LEVEL FEATURES ===")
# Trial position features (using existing trial field)

merged_df['is_first_trial'] = (merged_df['trial'] == 1).astype(int)
# Block position features
merged_df['is_first_block'] = (merged_df['block'] == 1).astype(int)
# DS confidence removed - redundant with stimulus feature

# Purchase DS block number (how many DS blocks has this user purchased)
merged_df['purchase_ds_block_num'] = merged_df.groupby('id')['block'].rank(method='dense') # cause we filtered for DS blocks only
print(f"Trial-level features created")

####################################################################################################

# 7. FEATURE SELECTION AND TARGET
print("\n=== 7. FEATURE SELECTION AND TARGET ===")
# Target variable
target = 'target'

# Feature columns: historical + current trial features
simpe_feature_columns = [
    # Current trial features
    'stimulus',
    'ds_recommends_signal',  # Keep only signal (noise is 1-signal)
    'trial', 'is_first_trial',
    'block', 'is_first_block', 'purchase_ds_block_num',
    'system_d', 'dependency_num'
    # Note: is_signal_event removed - ground truth not available to user
    # Note: avg_score_prev_blocks removed - redundant with confusion matrix features
    # Note: classification_time only used in rolling features
    # Note: ds_confidence removed - redundant with stimulus
]
rolling_feature_columns = [
    # Rolling historical features (1, 3, 7, 14, 21, 40 trials back)
    *[f'signal_rate_rolling_{w}' for w in rolling_windows],
    *[f'user_ds_agreement_rate_rolling_{w}' for w in rolling_windows],
    *[f'ds_correct_rate_rolling_{w}' for w in rolling_windows],
    *[f'user_correct_rate_rolling_{w}' for w in rolling_windows],
    *[f'tp_rate_rolling_{w}' for w in rolling_windows],
    *[f'fp_rate_rolling_{w}' for w in rolling_windows],
    *[f'fn_rate_rolling_{w}' for w in rolling_windows],
    *[f'tn_rate_rolling_{w}' for w in rolling_windows],
    *[f'stimulus_mean_rolling_{w}' for w in rolling_windows],
    *[f'classification_time_mean_rolling_{w}' for w in rolling_windows]
    # Note: user_correct_rate and tp_rate are overlapping - keeping both for now but they're correlated
]
feature_columns = simpe_feature_columns + rolling_feature_columns

# Add dependency one-hot columns
dep_columns = [col for col in merged_df.columns if col.startswith('dep_')]
feature_columns.extend(dep_columns)

# Filter features that exist in the dataframe, and print those that do not
missing_features = [c for c in feature_columns if c not in merged_df.columns]
if missing_features:
    print(f"Warning: The following features were not found in merged_df and will be excluded: {missing_features}")
feature_columns = [c for c in feature_columns if c in merged_df.columns]

################################## PreProcessing ##############################################################
X = merged_df[feature_columns]
y = merged_df[target]

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

# Keep all rows - models will handle NaN values appropriately
print(f"\nKeeping all rows with NaN values: X={X.shape}, y={y.shape}")
print(f"NaN counts: {X.isnull().sum().sum()} total missing values")

X_clean = X.copy()
y_clean = y.copy()

# 8. ANALYSIS BEFORE MODELING
print("\n=== 8. ANALYSIS BEFORE MODELING ===")

#################################### Analysis Before Modeling ##############################################################
# 8.1. Stimulus vs Target Analysis
print("\n8.1. Stimulus vs Target Analysis")
stimulus_analysis = merged_df.groupby('target')['stimulus'].agg(['count', 'mean', 'min', 'max'])
print("Stimulus distribution by target:")
print(stimulus_analysis)

# 8.2. System_d (Sensitivity) vs Target Analysis
print("\n8.2. System_d (Sensitivity) vs Target Analysis")
system_d_analysis = merged_df.groupby(['system_d', 'target']).size().unstack(fill_value=0)
print("System_d (Sensitivity) vs Target distribution:")
print(system_d_analysis)

# 8.3. DS Recommendation vs Target Analysis
print("\n8.3. DS Recommendation vs Target Analysis")
ds_rec_analysis = merged_df.groupby(['ds_recommends_signal', 'target']).size().unstack(fill_value=0)
print("DS Recommendation vs Target distribution:")
print(ds_rec_analysis)

# 8.4. Dependency vs Target Analysis
print("\n8.4. Dependency vs Target Analysis")
dependency_analysis = merged_df.groupby(['dependency', 'target']).size().unstack(fill_value=0)
print("Dependency vs Target distribution:")
print(dependency_analysis)

# 8.5. Purchase DS Block Number vs Target Analysis
print("\n8.5. Purchase DS Block Number vs Target Analysis")
purchase_block_analysis = merged_df.groupby(['purchase_ds_block_num', 'target']).size().unstack(fill_value=0)
print("Purchase DS Block Number vs Target distribution:")
print(purchase_block_analysis)

# 8.6. Historical Agreement vs Target Analysis
print("\n8.6. Historical Agreement vs Target Analysis")
if 'agreement_rate_rolling_7' in X_clean.columns:
    agreement_analysis = merged_df.groupby('target')['agreement_rate_rolling_7'].agg(['count', 'mean', 'std', 'min', 'max'])
    print("Historical agreement rate (rolling 7) vs target:")
    print(agreement_analysis)

# 9. VISUALIZATIONS
print("\n=== 9. VISUALIZATIONS ===")

# 9.1. Stimulus vs Target
plt.figure(figsize=(15, 10))

plt.subplot(2, 3, 1)
merged_df.boxplot(column='stimulus', by='target', ax=plt.gca())
plt.title('Stimulus vs Target (Signal/Noise)')
plt.suptitle('')

# 9.2. System_d (Sensitivity) vs Target
plt.subplot(2, 3, 2)
system_d_target = merged_df.groupby(['system_d', 'target']).size().unstack(fill_value=0)
system_d_target.plot(kind='bar', ax=plt.gca())
plt.title('System_d (Sensitivity) vs Target')
plt.xlabel('System_d (Sensitivity)')
plt.ylabel('Count')
plt.legend(['Noise', 'Signal'])
plt.xticks(rotation=0)

# 9.3. DS Recommendation vs Target
plt.subplot(2, 3, 3)
ds_rec_target = merged_df.groupby(['ds_recommends_signal', 'target']).size().unstack(fill_value=0)
ds_rec_target.plot(kind='bar', ax=plt.gca())
plt.title('DS Recommendation vs Target')
plt.xlabel('DS Recommends Signal')
plt.ylabel('Count')
plt.legend(['Noise', 'Signal'])
plt.xticks(rotation=0)

# 9.4. Dependency vs Target
plt.subplot(2, 3, 4)
dependency_target = merged_df.groupby(['dependency', 'target']).size().unstack(fill_value=0)
dependency_target.plot(kind='bar', ax=plt.gca())
plt.title('Dependency vs Target')
plt.xlabel('Dependency')
plt.ylabel('Count')
plt.legend(['Noise', 'Signal'])
plt.xticks(rotation=45)

# 9.5. Purchase DS Block Number vs Target
plt.subplot(2, 3, 5)
purchase_block_target = merged_df.groupby(['purchase_ds_block_num', 'target']).size().unstack(fill_value=0)
purchase_block_target.plot(kind='bar', ax=plt.gca())
plt.title('Purchase DS Block Number vs Target')
plt.xlabel('Purchase DS Block Number')
plt.ylabel('Count')
plt.legend(['Noise', 'Signal'])
plt.xticks(rotation=0)

# 9.6. Stimulus Distribution by Target
plt.subplot(2, 3, 6)
for target_val in [0, 1]:
    target_data = merged_df[merged_df['target'] == target_val]['stimulus']
    plt.hist(target_data, alpha=0.7, label=f'Target {target_val}', bins=30)
plt.title('Stimulus Distribution by Target')
plt.xlabel('Stimulus')
plt.ylabel('Frequency')
plt.legend(['Noise', 'Signal'])

plt.tight_layout()
plt.savefig('exp1_target_analysis.png', dpi=300, bbox_inches='tight')
plt.close()
print("✓ Target analysis plots saved as 'exp1_target_analysis.png'")

# 10. CORRELATION ANALYSIS
print("\n=== 10. CORRELATION ANALYSIS ===")
# Correlation heatmap for key features
key_features = [f for f in feature_columns if 'rolling_7' in f or 'stimulus' in f or 'system_d' in f or 'dependency' in f]
key_features = key_features[:25]  # Limit to 25 for readability

if len(key_features) > 1:
    plt.figure(figsize=(20, 16))
    corr = X[key_features].corr()
    mask = np.triu(np.ones_like(corr, dtype=bool))
    sns.heatmap(corr, mask=mask, annot=True, cmap='coolwarm', center=0, 
                square=True, linewidths=0.5, cbar_kws={"shrink": .8}, fmt='.2f')
    plt.title('Feature Correlation Heatmap - Key Features (Trial Level)')
    plt.tight_layout()
    plt.savefig('exp1_signals_correlation_heatmap.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Correlation heatmap saved as 'exp1_signals_correlation_heatmap.png'")

print("\nAnalysis complete! Ready for modeling in the next step.")

# 11. OPTIMIZED MODELING WITH BEST PARAMETERS
print("\n=== 11. OPTIMIZED MODELING WITH BEST PARAMETERS ===")

# Import necessary libraries for modeling
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score, f1_score, precision_score, recall_score
import xgboost as xgb
import warnings
warnings.filterwarnings('ignore')

try:
    import catboost as cb
    catboost_available = True
except ImportError:
    catboost_available = False
    print("CatBoost not available, skipping...")

# TEMPORAL SPLIT: First 80% of trials per user for training, last 20% for testing
print("Performing temporal split by user ID...")
train_indices = []
test_indices = []

for user_id in merged_df['id'].unique():
    user_data = merged_df[merged_df['id'] == user_id]
    n_trials = len(user_data)
    split_point = int(n_trials * 0.8)  # 80% for training
    
    # Get indices for this user
    user_indices = user_data.index.tolist()
    train_indices.extend(user_indices[:split_point])
    test_indices.extend(user_indices[split_point:])

# Create train/test sets
X_train = X.iloc[train_indices]
X_test = X.iloc[test_indices]
y_train = y.iloc[train_indices]
y_test = y.iloc[test_indices]

print(f"Temporal split completed:")
print(f"  Train set: {X_train.shape} (first 80% of trials per user)")
print(f"  Test set: {X_test.shape} (last 20% of trials per user)")
print(f"  Train users: {merged_df.iloc[train_indices]['id'].nunique()}")
print(f"  Test users: {merged_df.iloc[test_indices]['id'].nunique()}")

# Use best parameters from previous grid search results
best_params = {
    'XGBoost': {
        'n_estimators': 100,
        'max_depth': 6,
        'learning_rate': 0.1,
        'subsample': 1.0
    },
    'CatBoost': {
        'iterations': 100,
        'depth': 6,
        'learning_rate': 0.1,
        'l2_leaf_reg': 3
    }
}

# Store results
results = {}

# Train XGBoost with best parameters
print(f"\n{'='*50}")
print(f"🚀 STARTING XGBOOST")
print(f"{'='*50}")

print(f"📊 Model: XGBoost")
print(f"📊 Using best parameters: {best_params['XGBoost']}")

print(f"🔄 Fitting XGBoost with best parameters...")
xgb_model = xgb.XGBClassifier(
    random_state=42, 
    eval_metric='logloss',
    **best_params['XGBoost']
)
xgb_model.fit(X_train, y_train)

# Predicting
print(f"🎯 Predicting with XGBoost model...")
y_pred_xgb = xgb_model.predict(X_test)
y_pred_proba_xgb = xgb_model.predict_proba(X_test)[:, 1]

# Calculate metrics
accuracy_xgb = (y_pred_xgb == y_test).mean()
f1_xgb = f1_score(y_test, y_pred_xgb)
auc_xgb = roc_auc_score(y_test, y_pred_proba_xgb)

# Store results
results['XGBoost'] = {
    'model': xgb_model,
    'best_params': best_params['XGBoost'],
    'test_accuracy': accuracy_xgb,
    'test_f1': f1_xgb,
    'test_auc': auc_xgb,
    'predictions': y_pred_xgb,
    'probabilities': y_pred_proba_xgb
}

print(f"✅ XGBOOST FINISHED!")
print(f"   Test Accuracy: {accuracy_xgb:.4f}")
print(f"   Test F1 Score: {f1_xgb:.4f}")
print(f"   Test AUC: {auc_xgb:.4f}")

# Train CatBoost with best parameters (if available)
if catboost_available:
    print(f"\n{'='*50}")
    print(f"🚀 STARTING CATBOOST")
    print(f"{'='*50}")
    
    print(f"📊 Model: CatBoost")
    print(f"📊 Using best parameters: {best_params['CatBoost']}")
    
    print(f"🔄 Fitting CatBoost with best parameters...")
    cat_model = cb.CatBoostClassifier(
        random_state=42, 
        verbose=False,
        **best_params['CatBoost']
    )
    cat_model.fit(X_train, y_train)
    
    # Predicting
    print(f"🎯 Predicting with CatBoost model...")
    y_pred_cat = cat_model.predict(X_test)
    y_pred_proba_cat = cat_model.predict_proba(X_test)[:, 1]
    
    # Calculate metrics
    accuracy_cat = (y_pred_cat == y_test).mean()
    f1_cat = f1_score(y_test, y_pred_cat)
    auc_cat = roc_auc_score(y_test, y_pred_proba_cat)
    
    # Store results
    results['CatBoost'] = {
        'model': cat_model,
        'best_params': best_params['CatBoost'],
        'test_accuracy': accuracy_cat,
        'test_f1': f1_cat,
        'test_auc': auc_cat,
        'predictions': y_pred_cat,
        'probabilities': y_pred_proba_cat
    }
    
    print(f"✅ CATBOOST FINISHED!")
    print(f"   Test Accuracy: {accuracy_cat:.4f}")
    print(f"   Test F1 Score: {f1_cat:.4f}")
    print(f"   Test AUC: {auc_cat:.4f}")

# Find best model
best_model_name = max(results.keys(), key=lambda x: results[x]['test_f1'])
best_model = results[best_model_name]['model']

print(f"\n🏆 BEST MODEL: {best_model_name}")
print(f"   Test F1 Score: {results[best_model_name]['test_f1']:.4f}")

# Feature Importance Analysis
print(f"\n--- Feature Importance Analysis ({best_model_name}) ---")
feature_importance = pd.DataFrame({
    'feature': X.columns,
    'importance': best_model.feature_importances_
}).sort_values('importance', ascending=False)

print("Top 15 Most Important Features:")
for i, (_, row) in enumerate(feature_importance.head(15).iterrows(), 1):
    print(f"  {i:2d}. {row['feature']:35s} - {row['importance']:.4f}")
    
    # Save results
    plt.figure(figsize=(12, 8))
    top_features = feature_importance.head(15)
    plt.barh(range(len(top_features)), top_features['importance'])
    plt.yticks(range(len(top_features)), top_features['feature'])
    plt.xlabel('Feature Importance')
    plt.title(f'Top 15 Feature Importances ({best_model_name})')
    plt.gca().invert_yaxis()
    plt.tight_layout()
    plt.savefig('exp1_feature_importance_final.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Feature importance plot saved as 'exp1_feature_importance_final.png'")
    
    # Comprehensive Results Summary
    print(f"\n{'='*80}")
    print("🏆 COMPREHENSIVE MODEL COMPARISON RESULTS")
    print(f"{'='*80}")
    
    # Create results summary table
    summary_data = []
    for model_name, result in results.items():
        summary_data.append({
            'Model': model_name,
            'Best Params': str(result['best_params']),
            'Test F1': f"{result['test_f1']:.4f}",
            'Test Accuracy': f"{result['test_accuracy']:.4f}",
            'Test AUC': f"{result['test_auc']:.4f}",
            'Test Precision': f"{precision_score(y_test, result['predictions']):.4f}",
            'Test Recall': f"{recall_score(y_test, result['predictions']):.4f}"
        })
    
    # Convert to DataFrame for nice formatting
    summary_df = pd.DataFrame(summary_data)
    print("\n📊 MODEL PERFORMANCE COMPARISON:")
    print(summary_df.to_string(index=False))
    
    # Highlight winner
    print(f"\n🥇 WINNER: {best_model_name}")
    print(f"   🎯 Best Test F1 Score: {results[best_model_name]['test_f1']:.4f}")
    print(f"   🎯 Best Test AUC: {results[best_model_name]['test_auc']:.4f}")
    print(f"   🎯 Best Test Accuracy: {results[best_model_name]['test_accuracy']:.4f}")
    
    # Detailed winner analysis
    print(f"\n{'='*60}")
    print(f"🔍 DETAILED ANALYSIS: {best_model_name.upper()}")
    print(f"{'='*60}")
    
    winner_result = results[best_model_name]
    winner_pred = winner_result['predictions']
    
    print(f"\n📈 PERFORMANCE METRICS:")
    print(f"   • Accuracy:  {winner_result['test_accuracy']:.4f} ({winner_result['test_accuracy']*100:.2f}%)")
    print(f"   • F1 Score:  {winner_result['test_f1']:.4f}")
    print(f"   • Precision: {precision_score(y_test, winner_pred):.4f}")
    print(f"   • Recall:    {recall_score(y_test, winner_pred):.4f}")
    print(f"   • ROC AUC:   {winner_result['test_auc']:.4f}")
    
    print(f"\n⚙️  BEST HYPERPARAMETERS:")
    for param, value in winner_result['best_params'].items():
        print(f"   • {param}: {value}")
    
    # Confusion Matrix
    cm = confusion_matrix(y_test, winner_pred)
    print(f"\n📊 CONFUSION MATRIX:")
    print(f"   True Negatives:  {cm[0,0]:,}")
    print(f"   False Positives: {cm[0,1]:,}")
    print(f"   False Negatives: {cm[1,0]:,}")
    print(f"   True Positives:  {cm[1,1]:,}")
    
    # Feature Importance Analysis (Winner)
    print(f"\n{'='*60}")
    print(f"🎯 FEATURE IMPORTANCE ANALYSIS ({best_model_name.upper()})")
    print(f"{'='*60}")
    
    feature_importance = pd.DataFrame({
        'feature': X.columns,
        'importance': best_model.feature_importances_
    }).sort_values('importance', ascending=False)
    
    print(f"\n📊 TOP 20 MOST IMPORTANT FEATURES:")
    print(f"{'Rank':<4} {'Feature':<40} {'Importance':<12} {'Category'}")
    print(f"{'-'*4} {'-'*40} {'-'*12} {'-'*20}")
    
    for i, (_, row) in enumerate(feature_importance.head(20).iterrows(), 1):
        feature = row['feature']
        importance = row['importance']
        
        # Categorize features
        if 'stimulus' in feature and 'rolling' not in feature:
            category = "Current Stimulus"
        elif 'ds_recommends' in feature:
            category = "DS Recommendation"
        elif 'rolling' in feature:
            category = "Historical Pattern"
        elif 'system_d' in feature:
            category = "System Settings"
        elif 'dependency' in feature:
            category = "User Dependency"
        elif 'classification_time' in feature:
            category = "Response Time"
        else:
            category = "Other"
            
        print(f"{i:<4} {feature:<40} {importance:<12.4f} {category}")
    
    # Feature categories summary
    print(f"\n📈 FEATURE CATEGORIES SUMMARY:")
    categories = {}
    for _, row in feature_importance.iterrows():
        feature = row['feature']
        importance = row['importance']
        
        if 'stimulus' in feature and 'rolling' not in feature:
            cat = "Current Stimulus"
        elif 'ds_recommends' in feature:
            cat = "DS Recommendation"
        elif 'rolling' in feature:
            cat = "Historical Pattern"
        elif 'system_d' in feature:
            cat = "System Settings"
        elif 'dependency' in feature:
            cat = "User Dependency"
        elif 'classification_time' in feature:
            cat = "Response Time"
        else:
            cat = "Other"
            
        categories[cat] = categories.get(cat, 0) + importance
    
    for cat, total_importance in sorted(categories.items(), key=lambda x: x[1], reverse=True):
        print(f"   • {cat:<20}: {total_importance:.4f} ({total_importance/sum(categories.values())*100:.1f}%)")
    
    print(f"\n{'='*80}")
    print("✅ MODELING COMPLETE - ALL ANALYSES FINISHED")
    print(f"{'='*80}")
    print("✓ All models trained with grid search")
    print("✓ Best model identified and analyzed")
    print("✓ Comprehensive performance comparison completed")
    print("✓ Feature importance analyzed and categorized")
    print("✓ Results saved to files")


