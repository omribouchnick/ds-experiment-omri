# Thesis Documentation: Human-AI Decision Making Experiment

## Table of Contents
1. [Introduction and Research Overview](#1-introduction-and-research-overview)
2. [Theoretical Background](#2-theoretical-background)
3. [Signal Detection Theory Framework](#3-signal-detection-theory-framework)
4. [Experimental Design](#4-experimental-design)
5. [Technical Implementation](#5-technical-implementation)
6. [Project Structure and Deployment](#6-project-structure-and-deployment)
7. [Data Collection and Management](#7-data-collection-and-management)
8. [Development Decisions and Changes](#8-development-decisions-and-changes)
9. [Statistical Analysis Plan](#9-statistical-analysis-plan)
10. [Machine Learning Models](#10-machine-learning-models)
11. [Hypotheses and Expected Results](#11-hypotheses-and-expected-results)
12. [Limitations and Future Work](#12-limitations-and-future-work)

---

# 1. Introduction and Research Overview

## 1.1 Research Question
This thesis investigates how humans integrate advice from a Decision Support System (DSS) when making perceptual decisions under uncertainty. Specifically, we examine:

1. **How does DSS reliability affect human reliance on the system?**
2. **How does prior probability (base rate) influence human-DSS collaboration?**
3. **What factors predict whether a human will follow or override DSS recommendations?**

> 📚 **Deep Dive:** Add references to literature on human-AI collaboration, automation reliance, and trust in AI systems (e.g., Lee & See, 2004; Parasuraman & Riley, 1997).

## 1.2 Research Significance
Understanding human-DSS interaction is critical as AI systems become more prevalent in high-stakes domains (medical diagnosis, autonomous vehicles, financial decisions). This research contributes to:

- Understanding optimal DSS design parameters
- Predicting human behavior in human-AI teams
- Developing better calibration between human and machine decision-making

> 📚 **Deep Dive:** Cite studies on automation bias, algorithm aversion, and appropriate reliance on AI (Dietvorst et al., 2015; Logg et al., 2019).

## 1.3 Experimental Overview
The experiment presents participants with a signal detection task where they must classify stimuli as "signal" or "noise" while receiving advice from a DSS. Key manipulations include:

- **Prior probability (ps):** 0.2, 0.35, 0.5 (between-subjects)
- **Human sensitivity (d'_h):** 0.5 to 2.5 (11 levels, between-subjects)
- **DSS sensitivity (d'_s):** 0.5 to 2.5 (11 levels, between-subjects)

Total conditions: 3 × 11 × 11 = 363 unique experimental conditions

---

# 2. Theoretical Background

## 2.1 Signal Detection Theory (SDT)
Signal Detection Theory provides a mathematical framework for understanding perceptual decisions under uncertainty.

### Core Concepts:
- **Signal and Noise distributions:** Evidence is drawn from one of two overlapping Gaussian distributions
- **Sensitivity (d'):** The separation between signal and noise distributions
- **Criterion (c):** The decision threshold for classifying stimuli

> 📚 **Deep Dive:** Reference foundational SDT work (Green & Swets, 1966; Macmillan & Creelman, 2005).

## 2.2 Decision Support Systems
DSS are computational systems designed to aid human decision-making by providing recommendations or relevant information.

### Key Considerations:
- **Transparency:** How much of the DSS reasoning is visible to users?
- **Reliability:** How accurate is the DSS across different conditions?
- **Autonomy:** Does the user maintain control over final decisions?

> 📚 **Deep Dive:** Add references on DSS design and human-computer interaction (Benbasat & Nault, 1990; Arnott & Pervan, 2005).

## 2.3 Human-AI Collaboration
The interaction between humans and AI systems can be characterized by:

- **Complementarity:** When human and AI strengths compensate for each other's weaknesses
- **Reliance patterns:** Under-reliance (ignoring good advice) vs. over-reliance (following bad advice)
- **Trust calibration:** Matching trust level to actual system reliability

> 📚 **Deep Dive:** Cite work on human-AI teaming (Bansal et al., 2019; Zhang et al., 2020).

---

# 3. Signal Detection Theory Framework

## 3.1 Mathematical Formulation

### 3.1.1 Evidence Distributions
For each trial, evidence is sampled from one of two Gaussian distributions:

```
If event = "signal":
    x ~ N(μ = +d'/2, σ = 1.0)

If event = "noise":
    x ~ N(μ = -d'/2, σ = 1.0)
```

Where:
- `d'` is the sensitivity parameter (higher = easier to discriminate)
- The distributions have equal variance (σ = 1.0)
- The midpoint between distributions is at 0

### 3.1.2 Human Evidence (h_t)
Human evidence is sampled using the human sensitivity parameter `d'_h`:
```
h_t ~ N(±d'_h/2, 1.0)  depending on event type
```

In the experiment, a scalar of 6.5 is added to shift values to a positive range:
```
displayed_stimulus = h_t + 6.5
```

### 3.1.3 DSS Evidence (s_t)
DSS evidence is sampled independently using the DSS sensitivity parameter `d'_s`:
```
s_t ~ N(±d'_s/2, 1.0)  depending on event type
```

## 3.2 DSS Decision Rule

### 3.2.1 Symmetric Threshold (Current Implementation)
The DSS uses a simple symmetric threshold:
```
If s_t > 0 → DSS says "signal"
If s_t ≤ 0 → DSS says "noise"
```

This is equivalent to using the midpoint between the signal and noise distributions as the decision criterion (c = 0).

### 3.2.2 Why Symmetric Threshold?
**Rationale:**
- Simple and consistent across all conditions
- Does not depend on prior probability (ps)
- Provides a neutral baseline for studying human-DSS interaction

**Trade-offs:**
- Higher False Positive Rate when ps is low (0.2)
- Not optimal in Bayesian sense
- May affect perceived DSS reliability differently across ps conditions

### 3.2.3 Alternative: Bayesian Optimal Threshold
The Bayesian optimal threshold would incorporate prior probability:
```
logit P(Signal|s_t) = ln(ps / (1-ps)) + d'_s · s_t
P(Signal|s_t) = 1 / (1 + exp(-logit))
Decision: "signal" if P(Signal|s_t) > 0.5
```

**Why not used:**
- With low ps (0.2) and low d'_s (0.5), the DSS almost never says "signal"
- This makes the DSS appear unreliable to participants
- Limits the ability to study human-DSS interaction when DSS rarely provides recommendations

> 📚 **Deep Dive:** Discuss optimal observer models and Bayesian decision theory (Green & Swets, 1966; Wickens, 2002).

## 3.3 Performance Metrics

### 3.3.1 Hit Rate and False Alarm Rate
```
Hit Rate (H) = TP / (TP + FN)
False Alarm Rate (FA) = FP / (FP + TN)
```

### 3.3.2 Sensitivity (d')
Empirical d' is calculated from hit rate and false alarm rate:
```
d' = z(H) - z(FA)
```
Where z() is the inverse of the standard normal CDF.

### 3.3.3 Criterion (c)
The response bias or criterion:
```
c = -0.5 * (z(H) + z(FA))
```

### 3.3.4 Accuracy
```
Accuracy = (TP + TN) / (TP + TN + FP + FN)
```

---

# 4. Experimental Design

## 4.1 Participants
- **Target sample:** 400 participants via CloudResearch
- **Pilot sample:** ~50 participants for validation
- **Inclusion criteria:** [To be specified]
- **Compensation:** [To be specified]

> 📚 **Deep Dive:** Justify sample size with power analysis. Reference crowdsourcing best practices (Peer et al., 2017).

## 4.2 Independent Variables

### 4.2.1 Prior Probability (ps)
- **Levels:** 0.2, 0.35, 0.5
- **Manipulation:** Between-subjects
- **Rationale:** Represents different base rates of signals in real-world scenarios

### 4.2.2 Human Sensitivity (d'_h)
- **Levels:** 0.5, 0.7, 0.9, 1.1, 1.3, 1.5, 1.7, 1.9, 2.1, 2.3, 2.5 (11 levels)
- **Manipulation:** Between-subjects (determined by stimulus generation)
- **Rationale:** Represents task difficulty from human perspective

### 4.2.3 DSS Sensitivity (d'_s)
- **Levels:** 0.5, 0.7, 0.9, 1.1, 1.3, 1.5, 1.7, 1.9, 2.1, 2.3, 2.5 (11 levels)
- **Manipulation:** Between-subjects
- **Rationale:** Represents DSS reliability/accuracy

## 4.3 Dependent Variables

### 4.3.1 Primary Outcomes
1. **Accuracy:** Proportion of correct classifications
2. **DSS Reliance:** Proportion of trials where participant follows DSS recommendation
3. **d' (human):** Calculated sensitivity after experiment
4. **Criterion (c):** Response bias

### 4.3.2 Secondary Outcomes
1. **Decision time:** Reaction time per trial
2. **Trust ratings:** Subjective trust in DSS (TOAST questionnaire)
3. **Agreement patterns:** When do participants agree/disagree with DSS?

## 4.4 Experimental Blocks

### Block Structure:
| Block | Trials | DSS Shown | CSV Columns |
|-------|--------|-----------|-------------|
| Block 1 | 10 | No | event_t01 - event_t10 |
| Block 2 | 10 | Yes | event_t11 - event_t20 |
| Block 3 | 100 | Yes | event_t21 - event_t120 |

**Total:** 120 trials per participant

### Block Purposes:
- **Block 1:** Baseline human performance without DSS
- **Block 2:** Learning phase with DSS
- **Block 3:** Main experimental phase with DSS

## 4.5 Condition Assignment
Each participant is assigned to one of 363 unique conditions (ps × d'_h × d'_s) via a pre-generated CSV file. The assignment ensures:
- All 120 trials come from the same CSV row
- Event sequences match the assigned ps (exact base rate)
- Stimulus values match the assigned d' parameters

## 4.6 TOAST Questionnaire
Post-experiment questionnaire measuring:
- Trust in DSS (usefulness, reliability, trust, confidence)
- Satisfaction and predictability
- Numeracy (3 items)
- Demographics (age, gender, education)

> 📚 **Deep Dive:** Reference TOAST validation studies and trust measurement literature.

---

# 5. Technical Implementation

## 5.1 Technology Stack

### Backend:
- **Framework:** Django (Python)
- **Database:** SQLite
- **Hosting:** PythonAnywhere

### Frontend:
- **Templates:** Django HTML templates
- **Styling:** CSS
- **JavaScript:** For interactive game interface

### Data Analysis:
- **Python:** pandas, numpy, scipy, scikit-learn
- **Jupyter Notebooks:** For analysis and visualization

## 5.2 Key Code Components

### 5.2.1 Models (`experiment/models.py`)
```python
class ExperimentData:
    - user_id: Unique participant identifier
    - aid: CloudResearch assignment ID
    - csv_row_id: Reference to conditions CSV row
    - ps, human_sensitivity, ds_sensitivity: Experimental parameters
    - start_time, end_time, complete: Session tracking

class ExperimentAction:
    - user_id: Foreign key to ExperimentData
    - block_number, trial_number: Trial identification
    - correct_classification: Ground truth event type
    - stimulus_seen: Displayed stimulus value
    - dss_judgment: DSS recommendation
    - classification_decision: Participant's response
    - decision_time: Reaction time

class ToastResponse:
    - Trust and satisfaction ratings
    - Numeracy responses
    - Demographics
```

### 5.2.2 Views (`experiment/views.py`)
Key functions:
- `load_block_trials()`: Loads trial data from CSV
- `landing_page()`: Handles participant entry and condition assignment
- `game()`: Runs the main experimental task
- `record_action()`: Saves trial-by-trial responses
- `toast_1-4()`: Handles questionnaire pages
- `mark_row_as_used()`: Updates CSV after completion

### 5.2.3 Stimulus Generation
The conditions CSV contains pre-generated stimuli:
- 363 rows (one per condition)
- 120 trials per row
- Columns: events, human evidence (h_t), DSS evidence (s_t), DSS decisions

Stimulus scalar: +6.5 added to all evidence values for display

## 5.3 Data Validation
Implemented checks:
1. CSV row assignment verification
2. Block trial matching (no overlap)
3. ps/dprime consistency between DB and CSV
4. Used row tracking

---

# 6. Project Structure and Deployment

## 6.1 Directory Structure

```
ds-experiment-omri/
├── data/
│   ├── conditions_experiment_3ps_11x11_120_A.csv  # Main stimulus file
│   ├── conditions_experiment_3ps_11x11_120_A-old_baysian_ds.csv  # Backup
│   ├── old_data_0912/  # Backup folder with old experiment exports
│   │   ├── db.sqlite3
│   │   ├── experiment_data.csv
│   │   ├── experiment_actions.csv
│   │   ├── TOAST.csv
│   │   └── devtools_log.csv
│   └── old_data/  # Previous data backups
│
├── experiment/
│   ├── models.py      # Database models
│   ├── views.py       # Request handlers
│   ├── urls.py        # URL routing
│   └── migrations/    # Database migrations
│
├── templates/
│   ├── landing_page.html
│   ├── instructions.html
│   ├── game.html
│   ├── BlockSummary.html
│   ├── toast_1.html - toast_4.html
│   └── end.html
│
├── static/
│   ├── images/
│   └── fonts/
│
├── experiment_analysis.ipynb  # Main analysis notebook
├── export_db_to_csv.py        # Data export script
└── manage.py                  # Django management
```

## 6.2 Deployment Pipeline

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Local Dev     │────▶│      Git        │────▶│ PythonAnywhere  │
│  (VS Code/      │     │   (GitHub)      │     │  (Production)   │
│   Cursor)       │     │                 │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                        │
                                                        ▼
                                                ┌─────────────────┐
                                                │ CloudResearch   │
                                                │  (Recruitment)  │
                                                └─────────────────┘
                                                        │
                                                        ▼
                                                ┌─────────────────┐
                                                │  Participants   │
                                                └─────────────────┘
```

### 6.2.1 Local Development
- Code editing in VS Code/Cursor
- Local testing with Django development server
- Jupyter notebooks for analysis

### 6.2.2 Version Control (Git/GitHub)
- All code changes tracked
- Branches for features/fixes
- History for debugging

### 6.2.3 PythonAnywhere (Production)
- Hosts the Django application
- Runs SQLite database
- Accessible via public URL
- Pull from GitHub to update

### 6.2.4 CloudResearch (Recruitment)
- Participant recruitment platform
- Provides unique assignment IDs (aid)
- Handles compensation
- Redirects to PythonAnywhere experiment URL

## 6.3 Data Flow

```
1. Participant clicks CloudResearch link
2. Redirected to PythonAnywhere with aid parameter
3. Django assigns CSV row and creates ExperimentData
4. Participant completes experiment
5. Data saved to SQLite database
6. Export script extracts to CSV files
7. Analysis in Jupyter notebooks
```

---

# 7. Data Collection and Management

## 7.1 Database Tables

### ExperimentData (1 row per participant)
| Column | Description |
|--------|-------------|
| user_id | Auto-increment primary key |
| aid | CloudResearch assignment ID |
| csv_row_id | Reference to conditions CSV row |
| ps | Prior probability (0.2, 0.35, 0.5) |
| human_sensitivity | d'_h parameter |
| ds_sensitivity | d'_s parameter |
| start_time | Session start timestamp |
| end_time | Session end timestamp |
| complete | Boolean: completed experiment |

### ExperimentAction (120 rows per participant)
| Column | Description |
|--------|-------------|
| user_id | Foreign key to ExperimentData |
| block_number | 1, 2, or 3 |
| trial_number | Within-block trial number |
| correct_classification | Ground truth: "signal" or "noise" |
| stimulus_seen | Displayed stimulus value |
| dss_judgment | DSS recommendation |
| classification_decision | Participant response |
| decision_time | Reaction time (seconds) |

### ToastResponse (1 row per participant)
| Column | Description |
|--------|-------------|
| Trust items | 1-7 Likert scale |
| Numeracy items | Correct/incorrect responses |
| Demographics | Age, gender, education |

## 7.2 Conditions CSV Structure

| Column Group | Columns | Description |
|--------------|---------|-------------|
| Metadata | id, used, ps, dprime_h, dprime_s | Row identification and parameters |
| Events | event_t01 - event_t120 | Ground truth: "signal" or "noise" |
| Human Evidence | h_t01 - h_t120 | Raw stimulus values for human |
| DSS Evidence | s_t01 - s_t120 | Raw stimulus values for DSS |
| DSS Decisions | ds_dec_t01 - ds_dec_t120 | DSS recommendation: 1 or 0 |
| Tracking | isDemo | 1=pilot, 0=production |

## 7.3 Data Export Process

```bash
# On PythonAnywhere
cd ~/ds-experiment-omri
source venv/bin/activate
python export_db_to_csv.py
```

Exports:
- `experiment_data.csv`: Participant metadata
- `experiment_actions.csv`: Trial-by-trial responses
- `TOAST.csv`: Questionnaire responses
- `devtools_log.csv`: DevTools detection events

---

# 8. Development Decisions and Changes

## 8.1 DSS Decision Rule Change

### Original Implementation (Bayesian)
```python
logit = log(ps/(1-ps)) + dprime_s * s_t
p_signal = 1 / (1 + exp(-logit))
decision = 1 if p_signal > 0.5 else 0
```

### Problem Identified
With low ps (0.2) and low d'_s (0.5):
- DSS almost never says "signal" (0 out of 120 trials)
- Cannot calculate meaningful d' for DSS
- DSS appears non-functional to participants

### New Implementation (Symmetric)
```python
decision = 1 if s_t > 0 else 0
```

### Rationale
- Simple and interpretable
- Provides balanced signal/noise recommendations
- Allows studying human-DSS interaction across all conditions
- Trade-off: Higher FPR when ps is low

## 8.2 Block 3 Trial Assignment Fix

### Bug (Original)
Block 3 used CSV columns event_t01 to event_t100, overlapping with Block 1 and 2.

### Fix
Block 3 now uses event_t21 to event_t120:
- Block 1: t01-t10 (10 trials)
- Block 2: t11-t20 (10 trials)
- Block 3: t21-t120 (100 trials)

### Impact on Pilot Data
Pilot participants (52 users) have 20 repeated trials in Block 3. For analysis:
- Option A: Use all trials (repeated trials show learning effect)
- Option B: Use only trials 21-100 (unique trials only)

## 8.3 CSV Row Assignment Fix

### Bug (Original)
- Page refresh caused new CSV row selection
- DB stored old ps, user saw new trials
- 73% of users had mismatched data

### Fix
- Added `csv_row_id` field to ExperimentData
- Row selected once at session start
- Row persists across page refreshes
- Row marked as `used=1` only on completion

## 8.4 DevTools Detection

### Implementation
JavaScript detection of browser developer tools:
- Window size changes
- Console access attempts

### Purpose
- Identify potential cheating
- Filter suspicious participants in analysis

---

# 9. Statistical Analysis Plan

## 9.1 Primary Analyses

### 9.1.1 Effect of ps on Accuracy
- **Analysis:** One-way ANOVA or Kruskal-Wallis
- **IV:** ps (0.2, 0.35, 0.5)
- **DV:** Accuracy
- **Expected:** Accuracy increases with ps (more signals = easier task)

### 9.1.2 Effect of d'_s on DSS Reliance
- **Analysis:** Regression
- **IV:** d'_s (continuous)
- **DV:** Proportion of trials following DSS
- **Expected:** Higher d'_s → more reliance on DSS

### 9.1.3 Interaction of ps × d'_s on Accuracy
- **Analysis:** Two-way ANOVA
- **IVs:** ps, d'_s (may need to bin d'_s)
- **DV:** Accuracy
- **Expected:** Interaction effect where high d'_s compensates for low ps

## 9.2 Secondary Analyses

### 9.2.1 Trust Ratings and DSS Reliance
- **Analysis:** Correlation/Regression
- **Variables:** TOAST scores, reliance proportion
- **Expected:** Positive correlation between trust and reliance

### 9.2.2 Learning Effects
- **Analysis:** Repeated measures (early vs. late Block 3)
- **DV:** Accuracy, decision time
- **Expected:** Improvement over trials

### 9.2.3 Numeracy and Performance
- **Analysis:** Moderation analysis
- **Moderator:** Numeracy score
- **Expected:** High numeracy → better calibration with DSS

## 9.3 Confusion Matrix Analysis

### 9.3.1 Human × DSS Agreement Matrix
```
                    DSS: Signal    DSS: Noise
Human: Signal        Agree-S        Disagree
Human: Noise         Disagree       Agree-N
```

### 9.3.2 Metrics to Calculate
- Agreement rate overall
- Conditional agreement (given event type)
- Complementarity index

## 9.4 Sample Size Justification

Target N = 400 participants
- 363 conditions → ~1.1 participants per condition
- For group-level analysis: ~133 per ps level
- Power analysis: [To be calculated based on expected effect sizes]

> 📚 **Deep Dive:** Add formal power analysis with references.

---

# 10. Machine Learning Models

## 10.1 Prediction Task
**Goal:** Predict whether a participant will follow the DSS recommendation on a given trial.

### Target Variable
```
follow_dss = 1 if classification_decision == dss_judgment else 0
```

## 10.2 Feature Categories

### 10.2.1 Trial-Level Features
- `stimulus_seen`: Evidence strength
- `dss_judgment`: DSS recommendation (1/0)
- `correct_classification`: Ground truth
- `trial_number`: Position in block
- `block_number`: 1, 2, or 3

### 10.2.2 History Features
- Recent accuracy (rolling window)
- Recent DSS accuracy (rolling window)
- Consecutive agreements/disagreements
- Cumulative DSS reliability

### 10.2.3 Condition Features
- `ps`: Prior probability
- `dprime_h`: Human sensitivity
- `dprime_s`: DSS sensitivity

### 10.2.4 Individual Difference Features
- Numeracy score
- Trust ratings (TOAST)
- Demographics

## 10.3 Model Candidates

### 10.3.1 Logistic Regression
- Baseline model
- Interpretable coefficients
- Feature importance via odds ratios

### 10.3.2 Random Forest
- Handles non-linear relationships
- Feature importance ranking
- Robust to multicollinearity

### 10.3.3 Gradient Boosting (XGBoost/LightGBM)
- High predictive accuracy
- Handles interactions automatically
- Feature importance and SHAP values

### 10.3.4 Neural Network
- Complex pattern learning
- May capture temporal dependencies
- Requires more data

## 10.4 Evaluation Metrics
- **AUC-ROC:** Discrimination ability
- **Accuracy:** Overall correctness
- **F1-Score:** Balance of precision/recall
- **Confusion Matrix:** Detailed error analysis

## 10.5 Cross-Validation Strategy
- **Within-subject split:** Random trials within participants
- **Between-subject split:** Held-out participants
- **k-fold:** 5 or 10 folds

> 📚 **Deep Dive:** Reference ML in psychology/behavioral science (Yarkoni & Westfall, 2017).

---

# 11. Hypotheses and Expected Results

## 11.1 Primary Hypotheses

### H1: DSS Reliance and Accuracy
**Hypothesis:** Participants who rely more on a reliable DSS (high d'_s) will achieve higher accuracy.

**Expected:** Positive correlation between DSS reliance and accuracy when d'_s > d'_h.

### H2: ps Effect on Criterion
**Hypothesis:** Participants in low ps conditions will adopt a more conservative criterion.

**Expected:** Higher criterion (c) for ps=0.2 compared to ps=0.5.

### H3: DSS Reliability and Trust
**Hypothesis:** Participants exposed to more reliable DSS (higher d'_s) will report higher trust.

**Expected:** Positive correlation between d'_s and TOAST scores.

## 11.2 Secondary Hypotheses

### H4: Complementarity
**Hypothesis:** Human-DSS teams will outperform either alone when their sensitivities are complementary.

**Expected:** Highest accuracy when both d'_h and d'_s are moderate.

### H5: Numeracy Moderation
**Hypothesis:** High numeracy participants will better calibrate their reliance to DSS reliability.

**Expected:** Stronger d'_s × reliance correlation for high numeracy participants.

### H6: Learning Effects
**Hypothesis:** Participants will learn to calibrate their reliance over trials.

**Expected:** Reliance patterns in late Block 3 better match optimal strategies than early Block 3.

## 11.3 Exploratory Questions

1. What features best predict trial-level follow/override decisions?
2. Are there distinct behavioral profiles (e.g., always-follow, always-override, calibrated)?
3. How does decision time relate to agreement/disagreement?
4. Do trust ratings predict actual reliance behavior?

## 11.4 Expected Results Summary

| Variable | Expected Direction | Rationale |
|----------|-------------------|-----------|
| ps → Accuracy | + | More signals = easier detection |
| d'_s → Reliance | + | Better DSS = more trust |
| d'_h → Accuracy | + | Better human = better performance |
| ps × d'_s → Accuracy | Interaction | Complementary effects |
| Trust → Reliance | + | Trust enables reliance |
| Numeracy → Calibration | + | Better understanding = better use |

---

# 12. Limitations and Future Work

## 12.1 Current Limitations

### 12.1.1 Design Limitations
- Between-subjects design limits within-subject comparisons
- Symmetric DSS threshold may not reflect real-world AI systems
- Abstract task may not generalize to domain-specific decisions

### 12.1.2 Sample Limitations
- Crowdsourced sample (CloudResearch) may differ from target populations
- Online administration limits control over environment
- Self-selection bias in participation

### 12.1.3 Technical Limitations
- Pilot data has 20 repeated trials in Block 3
- DevTools detection may miss sophisticated cheating
- Reaction time precision limited by web platform

## 12.2 Future Directions

### 12.2.1 Extended Research
- Manipulate DSS decision rule (symmetric vs. Bayesian vs. utility-based)
- Add feedback manipulation (immediate vs. delayed vs. none)
- Compare different DSS presentation formats

### 12.2.2 Applied Extensions
- Domain-specific tasks (medical, financial, security)
- Compare AI types (rule-based vs. ML-based)
- Longitudinal study of trust development

### 12.2.3 Methodological Improvements
- Within-subjects design for d'_s manipulation
- Eye-tracking for attention analysis
- Process tracing (mouse tracking, verbal protocols)

---

# Appendices

## A. Key Files Reference

| File | Purpose |
|------|---------|
| `experiment/views.py` | Main experiment logic |
| `experiment/models.py` | Database schema |
| `data/conditions_experiment_3ps_11x11_120_A.csv` | Stimulus generation |
| `experiment_analysis.ipynb` | Analysis code |
| `export_db_to_csv.py` | Data export script |

## B. Key Parameters

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| STIMULI_SCALAR | 6.5 | Shift values to positive range |
| d' range | 0.5-2.5 | From difficult to easy discrimination |
| ps values | 0.2, 0.35, 0.5 | Low, medium, high base rates |
| Trials per block | 10, 10, 100 | Baseline, learning, main |

## C. TOAST Scale Items

1. Usefulness
2. Reliability
3. Trust
4. Confidence
5. Satisfaction
6. Predictability
7. Understandability
8. Surprised
9. Comfortable

## D. Numeracy Items

1. Fractions question
2. Percentage/discount question
3. Statistical reasoning question

---

*Document created: December 2024*
*Last updated: [Auto-update on changes]*

