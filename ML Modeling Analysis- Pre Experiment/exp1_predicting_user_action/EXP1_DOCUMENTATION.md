# Experiment 1: Predicting User Decisions - Documentation

## Table of Contents
1. [Overview](#1-overview)
2. [Folder Structure](#2-folder-structure)
3. [Python Files Summary](#3-python-files-summary)
4. [Experimental Framework](#4-experimental-framework)
5. [Feature Engineering](#5-feature-engineering)
6. [Model Training Pipeline](#6-model-training-pipeline)
7. [Split Strategies](#7-split-strategies)
8. [Ablation Studies](#8-ablation-studies)
9. [Key Decisions and Changes](#9-key-decisions-and-changes)
10. [Expected Results and Hypotheses](#10-expected-results-and-hypotheses)

---

# 1. Overview

## 1.1 Research Goal
**Primary Question:** Can we predict whether a user will decide "Signal" or "Noise" on a given trial based on:
- Current trial information (stimulus, DSS recommendation)
- Historical behavior patterns (rolling features)
- User and system characteristics (d', dependency level)

## 1.2 Data Source
- **exp1_raw.csv**: Trial-level data from Experiment 1 (existing dataset)
- **exp1_agg.csv**: Aggregated user-level and block-level data
- **Note:** This is different from the new experiment we're building - this is analysis of existing data

## 1.3 Two Block Types Analyzed
| Block Type | Description | Key Features |
|------------|-------------|--------------|
| **DS** | Trials WITH Decision Support System | Includes `ds_recommends_signal` |
| **NONDS** | Trials WITHOUT Decision Support System | No DSS features |

---

# 2. Folder Structure

```
exp1_predicting_user_action/
├── data/
│   ├── exp1_raw.csv                    # Raw trial-level data
│   └── exp1_agg.csv                    # Aggregated user/block data
│
├── Python Scripts (Active)
│   ├── exp1_predicting_user_decision.py         # Main: 70/30 splits, XGBoost
│   ├── exp1_predicting_user_decision_with_new_features.py  # + trend analysis
│   ├── exp1_predicting_user_decision_30_20.py   # 30/20 split variant
│   ├── exp1_comprehensive_experiments.py        # Multiple split strategies
│   └── pred_user_decision_1809                  # Advanced: EB smoothing, drift
│
├── Python Scripts (Legacy - to delete)
│   ├── exp1_predict_signals_old.py              # Original version
│   ├── generate_conditions-delete?.py           # CSV generator (100 trials)
│   ├── generate_conditions_B1-delete.py         # B1 variant
│   ├── generate_conditions_B2-delete.py         # B2 variant
│   └── generate_B1_B2-delete.py                 # Combined B1+B2
│
├── Generated CSVs
│   ├── conditions_experiment_3ps_11x11_100.csv
│   ├── conditions_experiment_3ps_11x11_100_B1.csv
│   └── conditions_experiment_3ps_11x11_100_B2.csv
│
├── Output Folders (Generated)
│   ├── exp1_outputs/                   # From basic scripts
│   ├── exp1_experiment_outputs/        # From main experiments
│   └── exp1_comprehensive_outputs/     # From comprehensive experiments
│
└── Generated Plots
    ├── exp1_feature_importance_final.png
    ├── exp1_signals_correlation_heatmap.png
    └── exp1_modeling_analysis.png
```

---

# 3. Python Files Summary

## 3.1 Main Production Scripts

### `exp1_predicting_user_decision.py` (Main Script)
**Purpose:** Core prediction pipeline with two split modes

**Key Features:**
- Split modes: `pooled_chrono_70_30` and `holdout_ids_70_30`
- XGBoost with grid search
- Isotonic calibration
- Feature ablation studies
- Leakage checks

**Parameters:**
```python
CENTER_M = 6.0           # SDT neutral point
ROLLING_WINDOWS = [1, 3, 7, 14, 21, 40]
XGB_PARAMS = {
    'n_estimators': [100, 200],
    'max_depth': [3, 6],
    'learning_rate': [0.1, 0.2],
    'subsample': [0.8, 1.0]
}
CALIBRATE = True
CAL_METHOD = 'isotonic'
CAL_RATIO = 0.10
```

**Ablations Run:**
- `full`: All features
- `no_stim`: Without current p_signal
- `no_ds`: Without DSS recommendation
- `no_stim_and_ds`: Without both stimulus and DSS
- `no_stim_hard`: Without stimulus history features
- `no_historical`: Only current trial features

---

### `exp1_predicting_user_decision_with_new_features.py`
**Purpose:** Enhanced version with additional features and analysis

**Additions over main script:**
- New rolling features: `user_ds_agreement_rate`, `ds_tp_rate`, `ds_fp_rate`
- Conditional features: `user_tp_given_ds_alarm`, `user_tp_given_ds_no_alarm`
- Trend analysis: Performance by test-trial rank bins
- Per-user metrics output

**New Feature Categories:**
```python
# DS-specific rolling features
'ds_tp_rate_rolling_{w}'
'ds_fp_rate_rolling_{w}'
'user_ds_agreement_rate_rolling_{w}'
'user_tp_given_ds_alarm_rate_rolling_{w}'
'user_tp_given_ds_no_alarm_rate_rolling_{w}'
```

---

### `exp1_predicting_user_decision_30_20.py`
**Purpose:** Alternative split for users with 50+ trials

**Split Logic:**
- First 30 trials: Training
- Last 20 trials: Testing
- Only users with ≥50 trials included

**Use Case:** Test generalization to later trials after learning phase

---

### `exp1_comprehensive_experiments.py`
**Purpose:** Compare multiple split strategies and models

**Split Strategies Tested:**
1. **80/20 Temporal**: Last 20% of each user's trials
2. **30/20 Fixed**: First 30 → Last 20 trials
3. **User-based**: 70% users train, 30% users test

**Models Compared:**
- XGBoost with grid search
- CatBoost with grid search

**Feature Sets:**
- Full features (with rolling)
- No historical (current trial only)

---

### `pred_user_decision_1809` (Advanced Version)
**Purpose:** Most advanced pipeline with additional techniques

**Key Innovations:**
1. **Exact Gaussian Posterior (p_signal):**
   ```python
   def compute_p_signal_paper(df, train_prior_pi):
       # Equal-variance SDT
       mu_s = center + 0.5 * dprime * sigma
       mu_n = center - 0.5 * dprime * sigma
       ps = pi * normal_pdf(x, mu_s, sigma)
       pn = (1-pi) * normal_pdf(x, mu_n, sigma)
       return ps / (ps + pn)
   ```

2. **Empirical Bayes Smoothing:**
   ```python
   # Beta prior (1,1) for rate smoothing
   EB_ALPHA, EB_BETA = 1.0, 1.0
   rate = (successes + alpha) / (trials + alpha + beta)
   ```

3. **Three Split Modes:**
   - `pooled_chrono_70_30` (strict)
   - `pooled_chrono_70_30_online` (warm start)
   - `holdout_ids_70_30`

4. **Prior-Shift Reports:**
   ```
   user S-rate: train=0.XXX, test=0.XXX
   event_type S-rate: train=0.XXX, test=0.XXX
   ```

5. **Drift Analysis:**
   - Per-user early vs. late decision patterns
   - Histogram of decision drift

---

## 3.2 Legacy Scripts (To Delete)

### `exp1_predict_signals_old.py`
**Original version** with:
- Basic temporal split
- XGBoost + CatBoost
- Simpler feature engineering
- No leakage checks

### `generate_conditions*.py`
**CSV generators** for the new experiment:
- Create 363 conditions (3 × 11 × 11)
- Sample evidence from Gaussians
- Compute DS decisions

**Note:** These belong in the `ds-experiment-omri` project, not here.

---

# 4. Experimental Framework

## 4.1 Target Variable
```python
target = (user_action == 'S').astype(int)
# 1 = User decided "Signal"
# 0 = User decided "Noise"
```

## 4.2 Theoretical Model: Signal Detection Theory
Users observe evidence from overlapping Gaussian distributions:

```
If event = "Signal": x ~ N(+d'/2, 1)
If event = "Noise":  x ~ N(-d'/2, 1)
```

**Posterior Probability:**
```python
P(Signal|x) = P(x|Signal) * P(Signal) / P(x)
            = f_s * π / (f_s * π + f_n * (1-π))
```

Where:
- `f_s = N(x | +d'/2, 1)` - likelihood under signal
- `f_n = N(x | -d'/2, 1)` - likelihood under noise
- `π` = prior probability of signal (estimated from training data)

> 📚 **Deep Dive:** Reference SDT formulations (Green & Swets, 1966; Macmillan & Creelman, 2005)

---

# 5. Feature Engineering

## 5.1 Current Trial Features

| Feature | Description | Type |
|---------|-------------|------|
| `p_signal` | Bayesian posterior P(Signal\|stimulus) | Continuous |
| `ds_recommends_signal` | DSS says "Alarm" (1) or not (0) | Binary |
| `trial` | Trial number within block | Integer |
| `block` | Block number | Integer |
| `is_first_trial` | Is this trial 1? | Binary |
| `is_first_block` | Is this block 1? | Binary |
| `purchase_ds_block_num` | DS block count for user | Integer |
| `system_d` | d' parameter for this user | Continuous |
| `dependency_num` | Dependency level (1-5) | Ordinal |

## 5.2 Rolling Historical Features

### Rolling Windows
```python
ROLLING_WINDOWS = [1, 3, 7, 14, 21, 40]
```

### User Behavior History
| Feature Pattern | Description |
|-----------------|-------------|
| `signal_rate_rolling_{w}` | Rate of "Signal" decisions |
| `tp_rate_rolling_{w}` | True Positive rate |
| `fp_rate_rolling_{w}` | False Positive rate |
| `user_ds_agreement_rate_rolling_{w}` | Agreement with DSS |

### System Performance History
| Feature Pattern | Description |
|-----------------|-------------|
| `system_tp_rate_rolling_{w}` | System TP rate |
| `system_fp_rate_rolling_{w}` | System FP rate |
| `ds_tp_rate_rolling_{w}` | DSS TP rate (when present) |
| `ds_fp_rate_rolling_{w}` | DSS FP rate |

### Conditional Features
| Feature Pattern | Description |
|-----------------|-------------|
| `user_tp_given_system_signal_rate_rolling_{w}` | User TP when system says signal |
| `user_tp_given_system_noise_rate_rolling_{w}` | User TP when system says noise |
| `user_tp_given_ds_alarm_rate_rolling_{w}` | User TP when DSS alarms |

### Stimulus History
| Feature Pattern | Description |
|-----------------|-------------|
| `p_signal_mean_rolling_{w}` | Mean posterior over window |
| `stimulus_mean_rolling_{w}` | Mean raw stimulus |

## 5.3 Leakage Prevention

**Critical:** All rolling features use `shift(1)` to prevent information leakage:

```python
# CORRECT: Uses only past information
df['feature'] = df['column'].rolling(w).mean().shift(1)

# WRONG: Would include current trial
df['feature'] = df['column'].rolling(w).mean()  # DO NOT USE
```

**Banned Current-Trial Columns:**
```python
ban = ['tp', 'fp', 'system_tp', 'system_fp', 
       'user_tp_given_system_signal', 'user_tp_given_system_noise',
       'ds_tp', 'ds_fp', 'user_ds_agreement']
```

These can only be used in their `_rolling_{w}` versions.

---

# 6. Model Training Pipeline

## 6.1 Overall Flow

```
1. Load Data
   ↓
2. Filter Block Type (DS or NONDS)
   ↓
3. Compute p_signal (using TRAIN prior only)
   ↓
4. Add Rolling Features (per split, with shift(1))
   ↓
5. Split Train/Test
   ↓
6. Carve Calibration Set (10% of train)
   ↓
7. Grid Search CV on Train Core
   ↓
8. Train Best Model
   ↓
9. Isotonic Calibration
   ↓
10. Find Optimal Threshold (F1)
    ↓
11. Evaluate on Test
    ↓
12. Save Results & Plots
```

## 6.2 XGBoost Configuration

```python
XGB_PARAM_GRID = {
    'n_estimators': [100, 200],
    'max_depth': [3, 6],
    'learning_rate': [0.1, 0.2],
    'subsample': [0.8, 1.0],
}

XGB_FIXED = {
    'random_state': 42,
    'eval_metric': 'logloss',
    'n_jobs': -1,
    'tree_method': 'hist'
}
```

## 6.3 Calibration

**Method:** Isotonic Regression (non-parametric)

```python
CALIBRATE = True
CAL_METHOD = 'isotonic'
CAL_RATIO = 0.10  # 10% of train for calibration
```

**Process:**
1. Carve last 10% of each user's training trials
2. Train base model on remaining 90%
3. Fit isotonic calibrator on carved set
4. Apply calibrator to all predictions

## 6.4 Threshold Tuning

```python
def best_threshold_f1(y_true, y_prob):
    ts = np.linspace(0, 1, 101)
    for t in ts:
        f1 = f1_score(y_true, (y_prob >= t))
        # Track best F1 and threshold
    return best_t, best_f1
```

**Applied on:** Calibration holdout set

---

# 7. Split Strategies

## 7.1 Pooled Chronological (70/30)

```python
def per_user_chrono_split(df, test_ratio=0.3):
    # Per user: first 70% train, last 30% test
    for user in df['id'].unique():
        user_trials = df[df['id'] == user]
        split_point = int(len(user_trials) * 0.7)
        train += user_trials[:split_point]
        test += user_trials[split_point:]
```

**Properties:**
- Respects temporal order
- All users appear in both train and test
- Tests on later trials (after learning)

## 7.2 Holdout IDs (70/30)

```python
def holdout_ids_split(df, train_ratio=0.7):
    # 70% of users for train, 30% for test
    users = df['id'].unique()
    shuffle(users)
    train_users = users[:int(len(users)*0.7)]
    test_users = users[int(len(users)*0.7):]
```

**Properties:**
- Tests generalization to new users
- No overlap between train and test users
- Harder task (no user history available)

## 7.3 30/20 Fixed Split

```python
def per_user_30_20_split(df):
    # First 30 trials: train
    # Last 20 trials: test
    # Only users with 50+ trials
```

**Properties:**
- Fixed number of trials per user
- Consistent learning period
- Tests only on trials 31-50

## 7.4 Online Mode (Warm Start)

```python
# Compute rolling features on FULL data (train + test)
# Then split
# Test rows have "warm" history from their own train portion
```

**Properties:**
- Simulates deployment scenario
- Allows feature leakage (intentional)
- Higher performance, less generalizable

---

# 8. Ablation Studies

## 8.1 Feature Set Definitions

| Ablation | Description | Purpose |
|----------|-------------|---------|
| `full` | All features | Baseline |
| `no_stim` | Remove `p_signal` | Test DSS + history only |
| `no_ds` | Remove `ds_recommends_signal` | Test stimulus + history only |
| `no_stim_and_ds` | Remove both current indicators | Test history only |
| `no_stim_hard` | Remove all stimulus-derived | No stimulus info at all |
| `no_ds_hard` | Remove all DSS-derived | No DSS info at all |
| `no_historical` | Only current trial | No history features |

## 8.2 Expected Ablation Results

| Ablation | Expected AUC | Reasoning |
|----------|--------------|-----------|
| `full` | ~0.75-0.80 | All information available |
| `no_stim` | ~0.70-0.75 | DSS partially encodes stimulus |
| `no_ds` | ~0.65-0.70 | Stimulus is primary driver |
| `no_stim_and_ds` | ~0.60-0.65 | Only behavioral patterns |
| `no_historical` | ~0.70-0.75 | Current trial very predictive |

## 8.3 Key Questions Answered

1. **How much does DSS recommendation add beyond stimulus?**
   - Compare `full` vs `no_ds`

2. **How much does user history add?**
   - Compare `no_historical` vs `full`

3. **Can we predict without current trial info?**
   - Look at `no_stim_and_ds` performance

4. **Is stimulus or DSS more predictive?**
   - Compare `no_stim` vs `no_ds`

---

# 9. Key Decisions and Changes

## 9.1 Posterior Calculation (p_signal)

### Original Approach
```python
# Simple logistic transformation
logit = log(ps/(1-ps)) + dprime * (x - CENTER_M)
p_signal = 1 / (1 + exp(-logit))
```

### Current Approach (Exact Gaussian)
```python
# Full Bayesian posterior with Gaussian likelihoods
mu_s = CENTER_M + 0.5 * dprime * sigma
mu_n = CENTER_M - 0.5 * dprime * sigma
f_s = gaussian_pdf(x, mu_s, sigma)
f_n = gaussian_pdf(x, mu_n, sigma)
p_signal = (pi * f_s) / (pi * f_s + (1-pi) * f_n)
```

**Why changed:** More theoretically correct; matches SDT literature

## 9.2 Empirical Bayes Smoothing

### Problem
Early trials have high variance in rolling rates (e.g., 1 TP in 3 trials = 0.33 rate)

### Solution
```python
# Beta(1,1) prior → smoothed rate
EB_ALPHA, EB_BETA = 1.0, 1.0
smoothed_rate = (successes + alpha) / (total + alpha + beta)
```

**Effect:** Shrinks extreme rates toward 0.5; most impactful for small windows

## 9.3 Prior Estimation

**Critical Decision:** Prior π is estimated from TRAIN data only, then applied to both train and test.

```python
# CORRECT
train_prior = df_train['target'].mean()
df_train['p_signal'] = compute_posterior(df_train, train_prior)
df_test['p_signal'] = compute_posterior(df_test, train_prior)

# WRONG - leakage!
full_prior = df['target'].mean()  # Uses test data
```

## 9.4 Removing Redundant Features

**Removed:**
- `stimulus` (raw) - replaced by `p_signal`
- `ds_confidence` - redundant with stimulus
- `user_correct_rate` - same as `tp_rate` for binary target
- `avg_score_prev_blocks` - redundant with confusion matrix rates

**Kept:**
- `system_d` - per-user sensitivity parameter
- `dependency_num` - user's dependency level

---

# 10. Expected Results and Hypotheses

## 10.1 Main Hypotheses

### H1: Current Stimulus is Primary Predictor
**Hypothesis:** `p_signal` (current trial posterior) will be the most important feature.

**Expected:** Feature importance > 0.3 for `p_signal`

### H2: DSS Recommendation Adds Unique Value
**Hypothesis:** Removing `ds_recommends_signal` will decrease AUC beyond what's explained by removing `p_signal`.

**Expected:** AUC(no_ds) < AUC(no_stim) when d'_s > d'_h

### H3: Historical Features Improve Prediction
**Hypothesis:** Rolling features capture stable user tendencies not explained by current trial.

**Expected:** AUC(full) > AUC(no_historical) by at least 0.03

### H4: Generalization to New Users is Harder
**Hypothesis:** `holdout_ids` split will show lower performance than `pooled_chrono`.

**Expected:** AUC(holdout) < AUC(pooled) by 0.05-0.10

### H5: Performance Improves Over Trials
**Hypothesis:** Later trials (higher test_rank) will have better predictions due to richer history.

**Expected:** Trend analysis shows increasing AUC with trial number

## 10.2 Expected Performance Ranges

| Metric | DS Blocks | NONDS Blocks |
|--------|-----------|--------------|
| AUC | 0.75-0.85 | 0.65-0.75 |
| F1 | 0.65-0.75 | 0.55-0.65 |
| Accuracy | 0.70-0.80 | 0.60-0.70 |

**Rationale:** DS blocks have additional predictor (`ds_recommends_signal`) that encodes both stimulus and system judgment.

## 10.3 Key Comparisons

1. **DS vs NONDS:**
   - DS should outperform due to DSS signal
   - Difference indicates DSS informativeness

2. **Pooled vs Holdout:**
   - Difference indicates user-specific learning
   - Large gap → model learns user-specific patterns

3. **Ablation Hierarchy:**
   - `full` > `no_ds` > `no_stim` > `no_stim_and_ds` > `no_historical`

## 10.4 Feature Importance Expectations

| Rank | Expected Feature | Category |
|------|-----------------|----------|
| 1 | `p_signal` | Current Stimulus |
| 2 | `ds_recommends_signal` | DSS Recommendation |
| 3-5 | `signal_rate_rolling_{w}` | User History |
| 6-10 | `tp_rate_rolling_{w}` | Performance History |
| 11+ | Meta features | Trial/Block position |

---

# Appendix A: Output Files Reference

## Per Experiment Run

| File Pattern | Description |
|--------------|-------------|
| `summary_{BLOCK}_{SPLIT}.csv` | Metrics for all ablations |
| `fi_top15_{BLOCK}_{SPLIT}_{ABLATION}.csv` | Feature importance |
| `leak_reports_{BLOCK}_{SPLIT}.txt` | Leakage warnings |
| `preds_{TAG}.csv` | Per-row predictions |
| `cm_norm_{TAG}.png` | Confusion matrix |
| `pr_{TAG}.png` | Precision-Recall curve |
| `cal_{TAG}.png` | Calibration plot |
| `preds_{TAG}.trend.csv` | Performance by trial bin |
| `drift_users_{TAG}.csv` | Per-user drift |

## Metrics Tracked

| Metric | Description |
|--------|-------------|
| `acc` | Accuracy @ threshold 0.5 |
| `f1` | F1 score @ 0.5 |
| `prec` | Precision @ 0.5 |
| `rec` | Recall @ 0.5 |
| `auc` | ROC AUC |
| `ap` | Average Precision |
| `brier` | Brier Score |
| `ece` | Expected Calibration Error |
| `acc_tuned` | Accuracy @ tuned threshold |
| `f1_tuned` | F1 @ tuned threshold |
| `thresh` | Optimal threshold from calibration |

---

# Appendix B: Quick Reference - Running Scripts

```bash
# Basic experiment
python exp1_predicting_user_decision.py

# With new features and trends
python exp1_predicting_user_decision_with_new_features.py

# 30/20 split variant
python exp1_predicting_user_decision_30_20.py

# Comprehensive comparison
python exp1_comprehensive_experiments.py

# Advanced with EB smoothing
python pred_user_decision_1809
```

---

*Document created: December 2024*
*For: MSc Thesis - Human-AI Decision Making*

