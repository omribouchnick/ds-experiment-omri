# Analyze Experiment 1 data structure
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
plt.switch_backend('Agg')

print("=== EXPERIMENT 1 DATA ANALYSIS ===")

# 1. LOAD AND ANALYZE RAW DATA
print("\n=== 1. RAW DATA ANALYSIS ===")
raw_df = pd.read_csv('data/exp1_raw.csv')
print(f"Raw data shape: {raw_df.shape}")
print(f"Raw data columns: {list(raw_df.columns)}")

# Check data types
print(f"\nData types:")
print(raw_df.dtypes)

# Check for missing values
print(f"\nMissing values per column:")
print(raw_df.isnull().sum())

# 2. ANALYZE KEY COLUMNS
print(f"\n=== 2. KEY COLUMNS ANALYSIS ===")

# Alert_System analysis
print(f"Alert_System values:")
print(raw_df['Alert_System'].value_counts().sort_index())

# Filter for Alert_System = 1 (DS trials)
ds_trials = raw_df[raw_df['Alert_System'] == 1].copy()
print(f"\nDS trials (Alert_System=1): {len(ds_trials)} out of {len(raw_df)} total trials")

if len(ds_trials) > 0:
    print(f"DS trials shape: {ds_trials.shape}")
    print(f"DS trials columns: {list(ds_trials.columns)}")
    
    # Analyze DS trials
    print(f"\nDS trials - Event Type distribution:")
    print(ds_trials['Event Type'].value_counts())
    
    print(f"\nDS trials - User Action distribution:")
    print(ds_trials['User Action'].value_counts())
    
    print(f"\nDS trials - system_d distribution:")
    print(ds_trials['system_d'].value_counts().sort_index())
    
    print(f"\nDS trials - dependency distribution:")
    print(ds_trials['dependency'].value_counts())
    
    print(f"\nDS trials - Stimulus statistics:")
    print(ds_trials['Stimulus'].describe())
    
    print(f"\nDS trials - Score statistics:")
    print(ds_trials['Score'].describe())

# 3. ANALYZE AGGREGATED DATA
print(f"\n=== 3. AGGREGATED DATA ANALYSIS ===")
agg_df = pd.read_csv('data/exp1_agg.csv')
print(f"Aggregated data shape: {agg_df.shape}")
print(f"Aggregated data columns: {list(agg_df.columns)}")

# Check data types
print(f"\nData types:")
print(agg_df.dtypes)

# Check for missing values
print(f"\nMissing values per column:")
print(agg_df.isnull().sum())

# Analyze key columns
print(f"\nAgg data - system_d distribution:")
print(agg_df['system_d'].value_counts().sort_index())

print(f"\nAgg data - dependency distribution:")
print(agg_df['dependency'].value_counts())

print(f"\nAgg data - help scores:")
help_col = 'How much did the automation help you in the task?'
if help_col in agg_df.columns:
    print(agg_df[help_col].describe())

distinguish_col = 'How good was the automation in distinguishing between blue and orange Vibranium strains?'
if distinguish_col in agg_df.columns:
    print(f"\nAgg data - distinguishing scores:")
    print(agg_df[distinguish_col].describe())

# 4. UNDERSTAND RELATIONSHIPS
print(f"\n=== 4. RELATIONSHIP ANALYSIS ===")

# Check if we can merge raw and agg data
print(f"Raw data unique IDs: {raw_df['ID'].nunique()}")
print(f"Agg data unique IDs: {agg_df['id'].nunique()}")

print(f"Raw data unique blocks: {raw_df['Block'].nunique()}")
print(f"Agg data unique blocks: {agg_df['block'].nunique()}")

# Sample of merged data
if len(ds_trials) > 0:
    print(f"\nSample DS trial data:")
    print(ds_trials[['ID', 'Block', 'system_d', 'dependency', 'Event Type', 'User Action', 'Stimulus', 'Score']].head(10))

print(f"\nSample aggregated data:")
print(agg_df.head(10))

# 5. UNDERSTAND STIMULUS RELATIONSHIP
print(f"\n=== 5. STIMULUS ANALYSIS ===")

if len(ds_trials) > 0:
    # Analyze stimulus vs user action
    print(f"Stimulus vs User Action (DS trials):")
    stimulus_action = ds_trials.groupby(['User Action'])['Stimulus'].agg(['count', 'mean', 'std', 'min', 'max'])
    print(stimulus_action)
    
    # Analyze stimulus vs event type
    print(f"\nStimulus vs Event Type (DS trials):")
    stimulus_event = ds_trials.groupby(['Event Type'])['Stimulus'].agg(['count', 'mean', 'std', 'min', 'max'])
    print(stimulus_event)
    
    # Analyze user action vs event type (accuracy)
    print(f"\nUser Action vs Event Type (accuracy in DS trials):")
    accuracy_matrix = pd.crosstab(ds_trials['User Action'], ds_trials['Event Type'], margins=True)
    print(accuracy_matrix)
    
    # Calculate accuracy rates
    correct = ((ds_trials['User Action'] == 'S') & (ds_trials['Event Type'] == 'S')) | \
              ((ds_trials['User Action'] == 'N') & (ds_trials['Event Type'] == 'N'))
    accuracy_rate = correct.mean()
    print(f"\nOverall accuracy in DS trials: {accuracy_rate:.3f} ({accuracy_rate*100:.1f}%)")

# 6. CREATE BASIC VISUALIZATIONS
print(f"\n=== 6. BASIC VISUALIZATIONS ===")

if len(ds_trials) > 0:
    # Stimulus distribution by user action
    plt.figure(figsize=(12, 8))
    
    plt.subplot(2, 2, 1)
    ds_trials.boxplot(column='Stimulus', by='User Action', ax=plt.gca())
    plt.title('Stimulus Distribution by User Action')
    plt.suptitle('')
    
    plt.subplot(2, 2, 2)
    ds_trials.boxplot(column='Stimulus', by='Event Type', ax=plt.gca())
    plt.title('Stimulus Distribution by Event Type')
    plt.suptitle('')
    
    plt.subplot(2, 2, 3)
    ds_trials.boxplot(column='Score', by='User Action', ax=plt.gca())
    plt.title('Score Distribution by User Action')
    plt.suptitle('')
    
    plt.subplot(2, 2, 4)
    ds_trials.boxplot(column='Classification Time', by='User Action', ax=plt.gca())
    plt.title('Classification Time by User Action')
    plt.suptitle('')
    
    plt.tight_layout()
    plt.savefig('exp1_basic_analysis.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Basic analysis plots saved as 'exp1_basic_analysis.png'")

print("\nData analysis complete!")
