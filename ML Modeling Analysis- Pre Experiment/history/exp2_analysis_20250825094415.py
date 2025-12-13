import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import LinearRegression, Ridge, Lasso, ElasticNet
from sklearn.metrics import mean_squared_error, r2_score
import warnings
warnings.filterwarnings('ignore')
plt.switch_backend('Agg')

print("=== EXPERIMENT 2 ANALYSIS ===")

# 1. LOAD DATA
print("\n=== 1. LOAD DATA ===")
raw_df = pd.read_csv('exp2_raw.csv')
agg_df = pd.read_csv('exp2_agg.csv')
print(f"Raw data shape: {raw_df.shape}")
print(f"Aggregated data shape: {agg_df.shape}")

# 2. DATA CLEANING AND PREPARATION
print("\n=== 2. DATA CLEANING AND PREPARATION ===")
# Clean aggregated data
agg_df['high_sensitivity'] = agg_df['system_sensitivity'] == 'high'
agg_df = agg_df.rename(columns={
    'How much did the automation help you in the task?': 'help_task_score',
    'How good was the automation in distinguishing between blue and orange Vibranium strains?': 'distinguishing_score'
})
agg_df['avg_score'] = agg_df[['help_task_score', 'distinguishing_score']].mean(axis=1)
print(f"agg_df columns after cleaning: {list(agg_df.columns)}")

# 3. FEATURE ENGINEERING ON TRIAL LEVEL
print("\n=== 3. FEATURE ENGINEERING ON TRIAL LEVEL ===")
def safe_eq(a, b):
    return (a == b) & ~(pd.isna(a) | pd.isna(b))

# Confusion matrix elements
raw_df['tp'] = safe_eq(raw_df['classification'], 'Blue') & safe_eq(raw_df['event'], 'Blue')
raw_df['fp'] = safe_eq(raw_df['classification'], 'Blue') & safe_eq(raw_df['event'], 'Orange')
raw_df['tn'] = safe_eq(raw_df['classification'], 'Orange') & safe_eq(raw_df['event'], 'Orange')
raw_df['fn'] = safe_eq(raw_df['classification'], 'Orange') & safe_eq(raw_df['event'], 'Blue')

# DS label and confidence
raw_df['auto_label'] = np.where(
    pd.notna(raw_df['system_p']),
    np.where(raw_df['system_p'] > 0.5, 'Blue', 'Orange'),
    raw_df['system_output']
)
raw_df['ds_conf'] = np.where(pd.notna(raw_df['system_p']), np.abs(raw_df['system_p'] - 0.5), np.nan)

# Human confidence (for integrated systems)
raw_df['human_conf'] = np.where(pd.notna(raw_df['human_p']), np.abs(raw_df['human_p'] - 0.5), np.nan)

# Agreement features
raw_df['agree_all'] = safe_eq(raw_df['classification'], raw_df['auto_label']).astype(float)
raw_df['agree_prob'] = np.where(
    pd.notna(raw_df['system_p']),
    ((safe_eq(raw_df['classification'], 'Blue') & (raw_df['system_p'] > 0.5)) |
     (safe_eq(raw_df['classification'], 'Orange') & (raw_df['system_p'] <= 0.5))).astype(float),
    np.nan
)
raw_df['agree_when_pd'] = np.where(
    raw_df['pd'],
    safe_eq(raw_df['classification'], raw_df['auto_label']).astype(float),
    np.nan
)

# Evidence difficulty
raw_df['difficulty'] = np.abs(raw_df['stimulus_s'])

# 4. USER-LEVEL AGGREGATION (ALL TRIALS + CONDITIONAL KPIs)
print("\n=== 4. USER-LEVEL AGGREGATION (ALL TRIALS + CONDITIONAL KPIs) ===")

# First, calculate purchase rate from ALL trials per user
purchase_rates = raw_df.groupby('id')['pd'].agg(['sum', 'count', 'mean']).reset_index()
purchase_rates['pd_rate'] = purchase_rates['sum'] / purchase_rates['count']
print(f"Purchase rate range: {purchase_rates['pd_rate'].min():.2f} to {purchase_rates['pd_rate'].max():.2f}")
print(f"Purchase rate mean: {purchase_rates['pd_rate'].mean():.2f}")

# Filter out users with 0% purchase rate (they won't have DS features anyway)
users_with_purchases = purchase_rates[purchase_rates['pd_rate'] > 0]['id'].tolist()
print(f"Users with at least one DS purchase: {len(users_with_purchases)} out of {len(purchase_rates)} total users")

# Aggregate ALL trials per user first (but only for users with purchases)
all_trials_agg = raw_df[raw_df['id'].isin(users_with_purchases)].groupby('id').agg({
    # From ALL trials
    'pd': ['sum', 'count', 'mean'],  # Purchase counts and rate
    'binary': 'first',
    'integrated': 'first', 
    'system_type': 'first',
    'system_sensitivity': 'first',
    'id': 'first'
}).reset_index()

# Flatten column names
all_trials_agg.columns = ['_'.join([str(i) for i in c if i]) for c in all_trials_agg.columns.to_flat_index()]

# Now aggregate only purchased trials (pd=1) for DS-specific features
ds_purchased_df = raw_df[raw_df['pd'] == True].copy()
print(f"Trials where DS was purchased: {len(ds_purchased_df)} out of {len(raw_df)} total trials")

ds_features_agg = ds_purchased_df.groupby('id').agg({
    # Only from purchased trials (pd=1)
    'tp': 'sum', 'fp': 'sum', 'tn': 'sum', 'fn': 'sum',
    'agree_when_pd': 'mean',  # Agreement when DS purchased
    'ds_conf': 'mean',  # DS confidence (only when purchased)
    'human_conf': 'mean',  # Human confidence (only when purchased)
    'difficulty': 'median',  # Difficulty (only when purchased)
    'score': ['mean', 'max'],  # Scores (only when purchased)
    'time': 'mean',  # Time (only when purchased)
}).reset_index()

# Flatten column names
ds_features_agg.columns = ['_'.join([str(i) for i in c if i]) for c in ds_features_agg.columns.to_flat_index()]

# Merge the two aggregations
user_agg = all_trials_agg.merge(ds_features_agg, on='id', how='left')

# Rename columns for clarity
user_agg = user_agg.rename(columns={
    'pd_mean': 'pd_mean',
    'binary_first': 'isBinary',
    'integrated_first': 'isIntegrated',
    'system_type_first': 'system_type',
    'system_sensitivity_first': 'system_sensitivity'
})

print(f"user_agg shape: {user_agg.shape}")
print(f"user_agg columns: {list(user_agg.columns)}")

# 5. MERGE AGGREGATED DATA
print("\n=== 5. MERGE AGGREGATED DATA ===")
# Only keep relevant columns from agg_df
agg_df_clean = agg_df[['id', 'help_task_score', 'distinguishing_score', 'avg_score']]
df = pd.merge(user_agg, agg_df_clean, left_on='id_first', right_on='id', how='inner')  # Changed to inner join
print(f"After INNER JOIN (only users with DS purchases): {df.shape}")
print(f"df columns: {list(df.columns)}")

# 6. DERIVED FEATURES AND CLEANUP
print("\n=== 6. DERIVED FEATURES AND CLEANUP ===")
# Calculate precision, recall, F1
df['precision'] = df['tp_sum'] / (df['tp_sum'] + df['fp_sum'] + 1e-6)
df['recall'] = df['tp_sum'] / (df['tp_sum'] + df['fn_sum'] + 1e-6)
df['f1'] = 2 * (df['precision'] * df['recall']) / (df['precision'] + df['recall'] + 1e-6)

# Log transform time_mean
if 'time_mean' in df.columns:
    df['log_time_mean'] = np.log1p(df['time_mean'])

# High sensitivity as binary
df['high_sensitivity'] = (df['system_sensitivity'] == 'high').astype(int)

# System type one-hot
df['system_type_binary'] = (df['system_type'] == 'binary').astype(int)
df['system_type_integrated'] = (df['system_type'] == 'integrated').astype(int)

# Interaction features
if 'difficulty_median' in df.columns and 'time_mean' in df.columns:
    df['difficulty_x_time'] = df['difficulty_median'] * df['time_mean']
if 'ds_conf_mean' in df.columns and 'pd_mean' in df.columns:
    df['conf_x_purchase'] = df['ds_conf_mean'] * df['pd_mean']

# Remove columns not needed for modeling
drop_cols = [
    'id_first', 'id_x', 'id_y', 'system_type', 'system_sensitivity',
    'tp_sum', 'fp_sum', 'tn_sum', 'fn_sum'
]
df = df.drop(columns=[c for c in drop_cols if c in df.columns])

# Remove rows with missing target
df = df[~df['avg_score'].isna()]
print(f"Final shape after cleanup: {df.shape}")

# 7. FEATURE SELECTION AND TARGET
print("\n=== 7. FEATURE SELECTION AND TARGET ===")
target = 'avg_score'
feature_columns = [
    # System characteristics
    'isBinary', 'isIntegrated', 'high_sensitivity',
    'system_type_binary', 'system_type_integrated',
    # DS usage and confidence
    'pd_mean', 'ds_conf_mean', 'human_conf_mean',
    # Agreement (only when DS purchased)
    'agree_when_pd_mean',
    # Performance metrics
    'precision', 'recall', 'f1',
    # Difficulty and timing
    'difficulty_median', 'time_mean', 'log_time_mean',
    # Scores (only mean and max)
    'score_mean', 'score_max',
    # Interactions
    'difficulty_x_time', 'conf_x_purchase'
]
feature_columns = [c for c in feature_columns if c in df.columns]
X = df[feature_columns]
y = df[target]

print(f"Feature columns for modeling: {feature_columns}")
print(f"Target shape: {y.shape}, Features shape: {X.shape}")
print(f"Target variable: {target}")
print(f"Target range: {y.min():.2f} to {y.max():.2f}")
print(f"Target mean: {y.mean():.2f}")

# Show purchase rate distribution
print(f"\nDS Purchase Rate Distribution:")
print(f"pd_mean range: {df['pd_mean'].min():.2f} to {df['pd_mean'].max():.2f}")
print(f"pd_mean mean: {df['pd_mean'].mean():.2f}")
print(f"pd_mean std: {df['pd_mean'].std():.2f}")

# Check for NaN values and remove them
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

# 8. VISUALIZATIONS
print("\n=== 8. VISUALIZATIONS ===")
plt.figure(figsize=(16, 12))
corr = X_clean.corr()
mask = np.triu(np.ones_like(corr, dtype=bool))
sns.heatmap(corr, mask=mask, annot=True, cmap='coolwarm', center=0, 
            square=True, linewidths=0.5, cbar_kws={"shrink": .8}, fmt='.2f')
plt.title('Feature Correlation Heatmap - Exp2 (DS Purchased Trials Only) - CLEANED')
plt.tight_layout()
plt.savefig('exp2_correlation_heatmap_cleaned.png', dpi=300, bbox_inches='tight')
plt.close()
print("✓ Correlation heatmap saved as 'exp2_correlation_heatmap_cleaned.png'")

# Distribution plots for key features
features_to_plot = [
    'isBinary', 'isIntegrated', 'high_sensitivity', 'pd_mean',
    'ds_conf_mean', 'human_conf_mean', 'difficulty_median', 'score_max', 'time_mean',
    'agree_when_pd_mean', 'precision', 'recall', 'f1', 'difficulty_x_time', 'conf_x_purchase'
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
plt.savefig('exp2_feature_distributions_cleaned.png', dpi=300, bbox_inches='tight')
plt.close()
print("✓ Feature distributions saved as 'exp2_feature_distributions_cleaned.png'")

# 9. DATA SPLIT
print("\n=== 9. DATA SPLIT ===")
X_train, X_test, y_train, y_test = train_test_split(X_clean, y_clean, test_size=0.2, random_state=42)
print(f"Train: {X_train.shape}, Test: {X_test.shape}")

# 10. MODELING
print("\n=== 10. MODELING ===")
models = {
    'Linear': LinearRegression(),
    'Ridge': Ridge(alpha=1.0),
    'Lasso': Lasso(alpha=0.1),
    'ElasticNet': ElasticNet(alpha=0.1, l1_ratio=0.5),
    'RandomForest': RandomForestRegressor(n_estimators=100, random_state=42),
    'GradientBoosting': GradientBoostingRegressor(n_estimators=100, random_state=42)
}

results = {}
for name, model in models.items():
    print(f"\nTraining {name}...")
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    mse = mean_squared_error(y_test, y_pred)
    rmse = np.sqrt(mse)
    r2 = r2_score(y_test, y_pred)
    cv_scores = cross_val_score(model, X_train, y_train, cv=5, scoring='r2')
    results[name] = {
        'model': model,
        'rmse': rmse,
        'r2': r2,
        'cv_r2': cv_scores.mean()
    }
    print(f"{name}: Test RMSE={rmse:.3f}, Test R²={r2:.3f}, CV R²={cv_scores.mean():.3f}")

best_model_name = max(results.keys(), key=lambda x: results[x]['cv_r2'])
print(f"\nBest model: {best_model_name}")

# 11. FEATURE IMPORTANCE
print("\n=== 11. FEATURE IMPORTANCE ===")
rf_model = results['RandomForest']['model']
feature_importance = pd.DataFrame({
    'feature': X_clean.columns,
    'importance': rf_model.feature_importances_
}).sort_values('importance', ascending=False)

print("Random Forest Feature Importances (CLEANED):")
for i, (_, row) in enumerate(feature_importance.head(15).iterrows(), 1):
    print(f"  {i:2d}. {row['feature']:35s} - {row['importance']:.4f}")

plt.figure(figsize=(12, 8))
sns.barplot(data=feature_importance.head(15), x='importance', y='feature', palette='plasma')
plt.title('Top 15 Feature Importances (Random Forest) - Exp2 CLEANED')
plt.tight_layout()
plt.savefig('exp2_feature_importance_RF_cleaned.png', dpi=300, bbox_inches='tight')
plt.close()
print("✓ Feature importance plot saved as 'exp2_feature_importance_RF_cleaned.png'")

# 12. SHAP ANALYSIS
print("\n=== 12. SHAP ANALYSIS ===")
try:
    import shap
    explainer = shap.TreeExplainer(rf_model)
    shap_values = explainer.shap_values(X_test)
    plt.figure(figsize=(14, 10))
    shap.summary_plot(shap_values, X_test, feature_names=X_clean.columns, show=False)
    plt.title('SHAP Summary Plot - Exp2 CLEANED')
    plt.tight_layout()
    plt.savefig('exp2_shap_summary_cleaned.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ SHAP summary plot saved as 'exp2_shap_summary_cleaned.png'")
    
    shap_importance = np.abs(shap_values).mean(0)
    shap_feature_importance = pd.DataFrame({
        'feature': X_clean.columns,
        'shap_importance': shap_importance
    }).sort_values('shap_importance', ascending=False)
    
    print("\nTop 10 Most Important Features (SHAP) - CLEANED:")
    for i, (_, row) in enumerate(shap_feature_importance.head(10).iterrows(), 1):
        print(f"{i:2d}. {row['feature']:35s} - {row['shap_importance']:.4f}")
        
except ImportError:
    print("SHAP not available. Skipping SHAP analysis.")

# 13. ADDITIONAL INSIGHTS
print("\n=== 13. ADDITIONAL INSIGHTS ===")
print("Key improvements made:")
print("- Added human confidence (human_conf_mean) from stimulus_h")
print("- Removed redundant features (conf_median, conf_max, difficulty_mean)")
print("- Kept only agree_when_pd_mean (removed agree_all_mean)")
print("- Kept only score_mean and score_max (removed score_median, score_min)")
print("- Removed irrelevant features (direction_human, event base rate)")
print("- Fixed _first suffix (these are consistent per user)")

print(f"\nDataset Summary:")
print(f"- Total users with DS purchases: {len(df)}")
print(f"- Target variable: {target}")
print(f"- Target range: {y.min():.2f} to {y.max():.2f}")
print(f"- Target mean: {y.mean():.2f}")
print(f"- Number of features: {len(feature_columns)}")
print(f"- DS purchase rate varies between users (not always 1.0)")

print("\nAnalysis complete!")