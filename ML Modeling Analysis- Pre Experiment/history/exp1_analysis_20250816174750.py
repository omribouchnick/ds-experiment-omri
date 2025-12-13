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
agg_df = agg_df.rename(columns={
    'How much did the automation help you in the task?': 'help_task_score',
    'How good was the automation in distinguishing between blue and orange Vibranium strains?': 'distinguishing_score'
})
agg_df['avg_score'] = agg_df[['help_task_score', 'distinguishing_score']].mean(axis=1)
agg_df = agg_df.rename(columns={'id': 'ID', 'block': 'Block'})
print(f"agg_df columns after renaming: {list(agg_df.columns)}")

raw_df = raw_df.sort_values(['ID', 'Block'])
raw_df = raw_df.drop(columns=[c for c in ['counterbalance_block', 'dependency', 'system_d'] if c in raw_df.columns])
raw_df = raw_df.query('Alert_System == 1')
raw_df.columns = raw_df.columns.str.lower().str.replace(' ', '_')
print(f"raw_df columns after cleaning: {list(raw_df.columns)}")

# 3. AGGREGATING RAW & FEATURE ENGINEERING (per-row and per-block)
print("\n=== 3. AGGREGATING RAW & FEATURE ENGINEERING ===")
raw_df = raw_df.assign(
    correct=(raw_df.user_action == raw_df.event_type).astype(int),
    tp=((raw_df.user_action == 'S') & (raw_df.event_type == 'S')).astype(int),
    fp=((raw_df.user_action == 'S') & (raw_df.event_type == 'N')).astype(int),
    tn=((raw_df.user_action == 'N') & (raw_df.event_type == 'N')).astype(int),
    fn=((raw_df.user_action == 'N') & (raw_df.event_type == 'S')).astype(int)
)
block_funcs = {
    'score': ['mean', 'max'],
    'stimulus': ['median'],
    'classification_time': ['median'],
    'correct': 'sum',
    'tp': 'sum',
    'fp': 'sum',
    'tn': 'sum',
    'fn': 'sum'
}
raw_agg = (
    raw_df
    .groupby(['id', 'block'])
    .agg(block_funcs)
    .reset_index()
)
raw_agg.columns = ['_'.join(x).strip('_') if isinstance(x, tuple) else x for x in raw_agg.columns.to_flat_index()]
raw_agg = raw_agg.sort_values(['id', 'block'])
print(f"raw_agg shape: {raw_agg.shape}")
print(f"raw_agg columns: {list(raw_agg.columns)}")

# 4. FEATURE ENGINEERING AGG (dependency_num, remove dependency/help/distinguishing, keep avg_score)
print("\n=== 4. FEATURE ENGINEERING AGG ===")
agg_df = agg_df.sort_values(['ID', 'Block', 'help_task_score', 'distinguishing_score', 'avg_score'])
agg_df.columns = agg_df.columns.str.lower().str.replace(' ', '_')
dep_map_num = {
    'Independent': 1,
    'Low': 2,
    'Medium': 3,
    'High': 4,
    'Full': 5
}
agg_df['dependency_num'] = agg_df['dependency'].map(dep_map_num)
# Remove dependency, help_task_score, distinguishing_score, keep avg_score
agg_df = agg_df.drop(columns=[c for c in ['dependency', 'help_task_score', 'distinguishing_score'] if c in agg_df.columns])
print(f"agg_df columns after feature engineering: {list(agg_df.columns)}")

# 5. EXTRA FEATURES (isfirstds_block, avg_score_prev_block)
print("\n=== 5. EXTRA FEATURES ===")
agg_df['isfirstds_block'] = (agg_df.groupby('id')['block'].rank(method='first') == 1).astype(int)
agg_df['avg_score_prev_block'] = (
    agg_df
    .sort_values(['id', 'block'])
    .groupby('id')['avg_score']
    .shift(1)
)
print("Sample of isfirstds_block and avg_score_prev_block:")
print(agg_df[['id', 'block', 'isfirstds_block', 'avg_score_prev_block']].head())

# 6. INNER JOIN
print("\n=== 6. INNER JOIN ===")
df_model = pd.merge(
    raw_agg,
    agg_df,
    left_on=['id', 'block'],
    right_on=['id', 'block'],
    how='inner'
)
print(f"After INNER JOIN: {len(df_model)} rows")
print(f"df_model columns after merge: {list(df_model.columns)}")

# 7. LOWER COL NAMES, CLEANING, INTERACTION FEATURES (not using avg_score as feature)
print("\n=== 7. CLEANING & INTERACTION FEATURES ===")
df_model.columns = df_model.columns.str.lower().str.replace(' ', '_')
# Remove columns not needed as features (keep avg_score only as target)
cols_to_remove = [
    'avg_score'  # Only keep as target, not as feature
]
# Remove only from features, not from the dataframe (so we can use as target)
feature_cols = [col for col in df_model.columns if col not in cols_to_remove]
# One-hot encoding for dependency_num
dep_dummies = pd.get_dummies(df_model['dependency_num'], prefix='depnum')
df_model = pd.concat([df_model, dep_dummies], axis=1)
print(f"Added dependency_num one-hot columns: {list(dep_dummies.columns)}")

# Calculate precision, recall, F1
df_model['precision_rate'] = df_model['tp_sum'] / (df_model['tp_sum'] + df_model['fp_sum'] + 0.001)
df_model['recall_rate'] = df_model['tp_sum'] / (df_model['tp_sum'] + df_model['fn_sum'] + 0.001)
df_model['f1_score'] = 2 * (df_model['precision_rate'] * df_model['recall_rate']) / (df_model['precision_rate'] + df_model['recall_rate'] + 0.001)
print("Sample precision, recall, f1:")
print(df_model[['precision_rate', 'recall_rate', 'f1_score']].head())

# Interaction features (do not use avg_score as input)
df_model['difficulty_time_interaction'] = df_model['stimulus_median'] * df_model['classification_time_median']
df_model['system_performance_interaction'] = df_model['system_d'] * df_model['precision_rate']
df_model['dependency_performance_interaction'] = df_model['dependency_num'] * df_model['f1_score']
df_model['system_dependency_interaction'] = df_model['system_d'] * df_model['dependency_num']
print("Sample interaction features:")
print(df_model[['difficulty_time_interaction', 'system_performance_interaction', 'dependency_performance_interaction', 'system_dependency_interaction']].head())

# 8. VIZ
print("\n=== 8. VIZ ===")
# Correlation heatmap
plt.figure(figsize=(16, 12))
corr = df_model.corr()
mask = np.triu(np.ones_like(corr, dtype=bool))
sns.heatmap(corr, mask=mask, annot=True, cmap='coolwarm', center=0, 
            square=True, linewidths=0.5, cbar_kws={"shrink": .8}, fmt='.2f')
plt.title('Feature Correlation Heatmap')
plt.tight_layout()
plt.savefig('correlation_heatmap.png', dpi=300, bbox_inches='tight')
plt.close()
print("✓ Correlation heatmap saved as 'correlation_heatmap.png'")

# Distribution plots for key features
features_to_plot = [
    'system_d', 'stimulus_median', 'classification_time_median', 'dependency_num',
    'precision_rate', 'recall_rate', 'f1_score',
    'tp_sum', 'fp_sum', 'tn_sum', 'fn_sum',
    'score_mean', 'score_max', 'correct_sum',
    'difficulty_time_interaction', 'system_performance_interaction',
    'dependency_performance_interaction', 'system_dependency_interaction'
]
ncols = 4
nrows = int(np.ceil(len(features_to_plot) / ncols))
fig, axes = plt.subplots(nrows, ncols, figsize=(20, 5 * nrows))
axes = axes.flatten()
for i, feat in enumerate(features_to_plot):
    axes[i].hist(df_model[feat], bins=30, alpha=0.7, edgecolor='black')
    axes[i].set_title(f'{feat} Distribution')
    axes[i].set_xlabel(feat)
    axes[i].set_ylabel('Frequency')
for j in range(i+1, len(axes)):
    axes[j].axis('off')
plt.tight_layout()
plt.savefig('feature_distributions.png', dpi=300, bbox_inches='tight')
plt.close()
print("✓ Feature distributions saved as 'feature_distributions.png'")

# Plot interaction features against avg_score
interaction_features = [
    'difficulty_time_interaction',
    'system_performance_interaction',
    'dependency_performance_interaction',
    'system_dependency_interaction'
]
plt.figure(figsize=(16, 10))
for idx, feat in enumerate(interaction_features):
    plt.subplot(2, 2, idx+1)
    plt.scatter(df_model[feat], df_model['avg_score'], alpha=0.6)
    plt.xlabel(feat)
    plt.ylabel('avg_score')
    plt.title(f'{feat} vs avg_score')
plt.tight_layout()
plt.savefig('interaction_vs_avg_score.png', dpi=300, bbox_inches='tight')
plt.close()
print("✓ Interaction feature scatter plots saved as 'interaction_vs_avg_score.png'")

# 9. SPLIT
print("\n=== 9. SPLIT ===")
# Prepare features and target
feature_columns = [
    'system_d', 'stimulus_median', 'classification_time_median', 'dependency_num',
    'precision_rate', 'recall_rate', 'f1_score',
    'tp_sum', 'fp_sum', 'tn_sum', 'fn_sum',
    'score_mean', 'score_max', 'correct_sum',
    'difficulty_time_interaction', 'system_performance_interaction',
    'dependency_performance_interaction', 'system_dependency_interaction',
    'isfirstds_block', 'avg_score_prev_block'
]
# Add one-hot dependency columns
dep_columns = [col for col in df_model.columns if col.startswith('depnum_')]
feature_columns.extend(dep_columns)
print(f"Feature columns for modeling: {feature_columns}")

# For target, get avg_score from df_model
y = df_model['avg_score']
X = df_model[feature_columns]

# Remove rows with missing values
X_clean = X.dropna()
y_clean = y[X_clean.index]
print(f"Shape after dropping missing: X={X_clean.shape}, y={y_clean.shape}")
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
    # For regression, "accuracy" is not standard, but we can use R^2 as a proxy for accuracy.
    # Alternatively, we can define accuracy as the percentage of predictions within a certain tolerance.
    # Here, let's define accuracy as % of predictions within 0.5 of the true value.
    accuracy = np.mean(np.abs(y_pred - y_test) <= 0.5)
    cv_scores = cross_val_score(model, X_train, y_train, cv=5, scoring='r2')
    results[name] = {
        'model': model,
        'rmse': rmse,
        'r2': r2,
        'cv_r2': cv_scores.mean(),
        'accuracy': accuracy
    }
    print(f"{name}: Test RMSE={rmse:.3f}, Test R²={r2:.3f}, CV R²={cv_scores.mean():.3f}, Accuracy (|pred-true|<=0.5)={accuracy:.3f}")

best_model_name = max(results.keys(), key=lambda x: results[x]['cv_r2'])
print(f"\nBest model: {best_model_name}")

# Feature importance (Random Forest)
print("\nRandom Forest Feature Importances:")
rf_model = results['RandomForest']['model']
feature_importance = pd.DataFrame({
    'feature': feature_columns,
    'importance': rf_model.feature_importances_
}).sort_values('importance', ascending=False)
for i, (_, row) in enumerate(feature_importance.head(10).iterrows(), 1):
    print(f"  {i:2d}. {row['feature']:35s} - {row['importance']:.4f}")

plt.figure(figsize=(12, 8))
sns.barplot(data=feature_importance.head(15), x='importance', y='feature', palette='plasma')
plt.title('Top 15 Feature Importances (Random Forest)')
plt.tight_layout()
plt.savefig('feature_importance_RF.png', dpi=300, bbox_inches='tight')
plt.close()
print("✓ Feature importance plot saved as 'feature_importance_RF.png'")

# 11. SHAP
print("\n=== 11. SHAP ===")
try:
    import shap
    explainer = shap.TreeExplainer(rf_model)
    shap_values = explainer.shap_values(X_test)
    plt.figure(figsize=(14, 10))
    shap.summary_plot(shap_values, X_test, feature_names=feature_columns, show=False)
    plt.title('SHAP Summary Plot')
    plt.tight_layout()
    plt.savefig('shap_summary.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ SHAP summary plot saved as 'shap_summary.png'")
    shap_importance = np.abs(shap_values).mean(0)
    shap_feature_importance = pd.DataFrame({
        'feature': feature_columns,
        'shap_importance': shap_importance
    }).sort_values('shap_importance', ascending=False)
    print("\nTop 10 Most Important Features (SHAP):")
    for i, (_, row) in enumerate(shap_feature_importance.head(10).iterrows(), 1):
        print(f"{i:2d}. {row['feature']:35s} - {row['shap_importance']:.4f}")

    # Plot SHAP values for interaction features
    plt.figure(figsize=(12, 8))
    for idx, feat in enumerate(interaction_features):
        if feat in feature_columns:
            plt.subplot(2, 2, idx+1)
            shap.dependence_plot(feat, shap_values, X_test, feature_names=feature_columns, show=False)
            plt.title(f"SHAP Dependence: {feat}")
    plt.tight_layout()
    plt.savefig('shap_interaction_features.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ SHAP interaction feature plots saved as 'shap_interaction_features.png'")

except ImportError:
    print("SHAP not available. Skipping SHAP analysis.")

print("\nAnalysis complete!")