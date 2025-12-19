#!/bin/bash
# Comprehensive Pilot Validation - Replicates Jupyter Notebook Checks
# Runs all deep validation checks from comprehensive_validation_analysis.ipynb
# Usage: bash "QA Codes - PythonAnywhere/comprehensive_pilot_validation.sh"

# Get script directory and navigate to Experiment_Code
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
EXPERIMENT_CODE_DIR="$(dirname "$SCRIPT_DIR")/Experiment_Code"

if [ ! -d "$EXPERIMENT_CODE_DIR" ]; then
    # Fallback to hardcoded path (for PythonAnywhere)
    EXPERIMENT_CODE_DIR="$HOME/ds-experiment-omri/Experiment_Code"
fi

cd "$EXPERIMENT_CODE_DIR" && python3 << 'EOF'
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict

# Load data
conn = sqlite3.connect('DATA/db.sqlite3')
csv_df = pd.read_csv('DATA/conditions_experiment_3ps_11x11_120_A.csv')

print("=" * 100)
print("🔬 COMPREHENSIVE PILOT VALIDATION - DEEP ANALYSIS")
print("=" * 100)
print(f"Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

# Load all data
users = pd.read_sql_query("""
    SELECT user_id, aid, csv_row_id, ps, human_sensitivity, ds_sensitivity, 
           complete, start_time, end_time
    FROM experiment_experimentdata
""", conn)

actions = pd.read_sql_query("""
    SELECT user_id_id as user_id, block_number, trial_number, 
           classification_decision, dss_judgment, stimulus_seen, decision_time,
           correct_classification
    FROM experiment_experimentaction
""", conn)

toast = pd.read_sql_query("""
    SELECT user_id_id as user_id, usefulness, reliability, 
           trust, confidence, satisfaction
    FROM experiment_toastresponse
""", conn)

print(f"📊 Data loaded:")
print(f"   Users: {len(users)} (Complete: {users['complete'].sum()}, Incomplete: {len(users) - users['complete'].sum()})")
print(f"   Actions: {len(actions)} trials")
print(f"   TOAST responses: {len(toast)}")
print()

################################################################################
# SECTION 1: BASIC DATA INTEGRITY
################################################################################
print("=" * 100)
print("✅ SECTION 1: BASIC DATA INTEGRITY CHECKS")
print("=" * 100)
print()

issues = []

# 1. csv_row_id assignment
users_with_row = users[users['csv_row_id'].notna()]
print(f"1. CSV Row Assignment:")
print(f"   ✅ Users with csv_row_id: {len(users_with_row)}/{len(users)}")
print()

# 2. Duplicate csv_row_id (only for completed users)
complete_users = users[users['complete'] == 1]
duplicate_rows = complete_users.groupby('csv_row_id').size()
duplicate_rows = duplicate_rows[duplicate_rows > 1]

if len(duplicate_rows) > 0:
    print(f"2. Duplicate csv_row_id (completed users):")
    print(f"   ⚠️  {len(duplicate_rows)} CSV rows assigned to multiple completed users")
    for row_id, count in duplicate_rows.items():
        user_ids = complete_users[complete_users['csv_row_id'] == row_id]['user_id'].tolist()
        print(f"      Row {int(row_id)}: {count} users {user_ids}")
    issues.append(f"Duplicate CSV rows: {len(duplicate_rows)} rows")
else:
    print(f"2. Duplicate csv_row_id (completed users):")
    print(f"   ✅ No duplicates found!")
print()

# 3. CSV used flags
flag_counts = csv_df['used'].value_counts().sort_index()
print(f"3. CSV Used Flags Distribution:")
for flag, count in flag_counts.items():
    status = {0: "Available", 0.5: "In-progress", 1: "Completed"}.get(flag, "Unknown")
    print(f"   used={flag} ({status}): {count}")
print()

# 4. CSV flag mismatches (completed users should have used=1)
print(f"4. CSV Flag Validation (completed users):")
mismatch_count = 0
complete_user_rows = complete_users['csv_row_id'].dropna().unique()

for row_id in complete_user_rows:
    csv_row = csv_df[csv_df['id'] == row_id]
    if len(csv_row) > 0:
        used_flag = csv_row.iloc[0]['used']
        # Check if there are incomplete users sharing this row (race condition)
        incomplete_on_row = users[(users['csv_row_id'] == row_id) & (users['complete'] == 0)]
        
        if used_flag != 1.0 and len(incomplete_on_row) == 0:
            # Real mismatch - completed user but flag not 1
            mismatch_count += 1
            if mismatch_count <= 5:
                user_id = complete_users[complete_users['csv_row_id'] == row_id]['user_id'].iloc[0]
                print(f"   ⚠️  Row {int(row_id)} (User {user_id}): used={used_flag} (expected 1.0)")

if mismatch_count > 0:
    print(f"   Total mismatches: {mismatch_count}")
    issues.append(f"CSV flag mismatches: {mismatch_count} rows")
else:
    print(f"   ✅ All CSV flags correct!")
print()

# 5. end_time coverage
complete_with_end = complete_users[complete_users['end_time'].notna()]
print(f"5. End Time Coverage:")
print(f"   Complete users: {len(complete_users)}")
print(f"   With end_time: {len(complete_with_end)} ({100*len(complete_with_end)/len(complete_users):.1f}%)")
if len(complete_with_end) < len(complete_users):
    missing = len(complete_users) - len(complete_with_end)
    print(f"   ⚠️  {missing} complete users missing end_time")
    issues.append(f"Missing end_time: {missing} users")
else:
    print(f"   ✅ All complete users have end_time!")
print()

################################################################################
# SECTION 2: LEARNING CURVE ANALYSIS
################################################################################
print("=" * 100)
print("📈 SECTION 2: LEARNING CURVE ANALYSIS")
print("=" * 100)
print()

# Merge actions with users to get complete users only
complete_user_ids = complete_users['user_id'].tolist()
complete_actions = actions[actions['user_id'].isin(complete_user_ids)].copy()

# Calculate correct trials (where human judgment matches ground truth from DB)
# Simply compare classification_decision with correct_classification (both are 'signal' or 'noise')
complete_actions['human_correct'] = (
    complete_actions['classification_decision'] == complete_actions['correct_classification']
).astype(int)

# Group by block
if len(complete_actions) > 0:
    block_stats = complete_actions.groupby('block_number').agg({
        'human_correct': ['sum', 'count'],
        'decision_time': 'mean'
    }).round(2)
    
    print("Performance by Block (Complete Users Only):")
    print()
    
    block_accuracies = {}
    for block in sorted(complete_actions['block_number'].unique()):
        block_data = complete_actions[complete_actions['block_number'] == block]
        correct = block_data['human_correct'].sum()
        total = len(block_data)
        accuracy = 100 * correct / total if total > 0 else 0
        mean_rt = block_data['decision_time'].mean()
        block_accuracies[block] = accuracy
        
        print(f"   Block {int(block)}:")
        print(f"      Accuracy: {accuracy:.1f}% ({correct}/{total})")
        print(f"      Mean RT: {mean_rt:.2f}s")
        print()
    
    # Calculate improvements
    if 1 in block_accuracies and 2 in block_accuracies:
        improvement_1_2 = block_accuracies[2] - block_accuracies[1]
        print(f"📊 Learning Effect Analysis:")
        print(f"   Block 1 → Block 2: {improvement_1_2:+.1f}% {'✅ Improvement' if improvement_1_2 > 0 else '⚠️  No improvement'}")
    
    if 2 in block_accuracies and 3 in block_accuracies:
        improvement_2_3 = block_accuracies[3] - block_accuracies[2]
        print(f"   Block 2 → Block 3: {improvement_2_3:+.1f}% {'✅ Improvement' if improvement_2_3 > 0 else '⚠️  No improvement'}")
    
    if 1 in block_accuracies and 3 in block_accuracies:
        improvement_1_3 = block_accuracies[3] - block_accuracies[1]
        print(f"   Block 1 → Block 3: {improvement_1_3:+.1f}% {'✅ Overall improvement' if improvement_1_3 > 0 else '⚠️  No overall improvement'}")
    print()
else:
    print("   ⚠️  No complete user data available for learning curve analysis")
    print()

################################################################################
# SECTION 3: STATISTICAL BALANCING
################################################################################
print("=" * 100)
print("📊 SECTION 3: STATISTICAL BALANCING (Experimental Design)")
print("=" * 100)
print()

# Check ps, d'_human, d'_DS distributions
print("Condition Distribution (Complete Users):")
print()

print("1. ps (Signal Probability):")
ps_counts = complete_users['ps'].value_counts().sort_index()
for ps_val, count in ps_counts.items():
    pct = 100 * count / len(complete_users)
    print(f"   ps={ps_val}: {count} users ({pct:.1f}%)")
print()

print("2. d'_human (Human Sensitivity):")
dprime_h_counts = complete_users['human_sensitivity'].value_counts().sort_index()
for dh, count in dprime_h_counts.items():
    pct = 100 * count / len(complete_users)
    print(f"   d'_h={dh}: {count} users ({pct:.1f}%)")
print()

print("3. d'_DS (DS Sensitivity):")
dprime_s_counts = complete_users['ds_sensitivity'].value_counts().sort_index()
for ds, count in dprime_s_counts.items():
    pct = 100 * count / len(complete_users)
    print(f"   d'_DS={ds}: {count} users ({pct:.1f}%)")
print()

# Check for balance (chi-square test would go here in full analysis)
ps_min = ps_counts.min()
ps_max = ps_counts.max()
ps_imbalance = (ps_max - ps_min) / len(complete_users) * 100

if ps_imbalance > 20:
    print(f"⚠️  ps distribution imbalance: {ps_imbalance:.1f}% difference")
    issues.append(f"ps imbalance: {ps_imbalance:.1f}%")
else:
    print(f"✅ ps distribution balanced (max difference: {ps_imbalance:.1f}%)")
print()

################################################################################
# SECTION 4: DS DECISION VERIFICATION (CSV vs Database)
################################################################################
print("=" * 100)
print("🤖 SECTION 4: DS DECISION VERIFICATION (CSV vs Database)")
print("=" * 100)
print()

# Helper function to get CSV column name for trial
def get_trial_col(trial_num, block_num):
    """Map block+trial to CSV column number (1-120)"""
    if block_num == 1:
        return trial_num  # Block 1: trials 1-10 → columns 1-10
    elif block_num == 2:
        return trial_num + 10  # Block 2: trials 1-10 → columns 11-20
    else:  # block_num == 3
        return trial_num + 20  # Block 3: trials 1-100 → columns 21-120

# Sample 3 random complete users for detailed verification
print(f"Detailed Verification: Checking 3 random complete users")
print()

sample_users = complete_users.sample(n=min(3, len(complete_users)))
ds_verification_errors = 0

for idx, user in sample_users.iterrows():
    user_id = user['user_id']
    csv_row_id = user['csv_row_id']
    
    print(f"User {user_id} (CSV Row {int(csv_row_id) if pd.notna(csv_row_id) else 'N/A'}):")
    
    if pd.isna(csv_row_id):
        print(f"   ⚠️  No CSV row assigned")
        ds_verification_errors += 1
        continue
    
    # Get CSV row
    csv_row = csv_df[csv_df['id'] == csv_row_id]
    if len(csv_row) == 0:
        print(f"   ⚠️  CSV row not found")
        ds_verification_errors += 1
        continue
    
    csv_row = csv_row.iloc[0]
    
    # Get user actions (first 3 trials only for display)
    user_actions = actions[actions['user_id'] == user_id].sort_values(['block_number', 'trial_number']).head(3)
    
    errors_this_user = 0
    checked_this_user = 0
    
    for _, action in user_actions.iterrows():
        block = int(action['block_number'])
        trial = int(action['trial_number'])
        
        # Map to CSV column
        csv_trial = get_trial_col(trial, block)
        t_str = f'0{csv_trial}' if csv_trial < 10 else f'{csv_trial}'
        
        # Get CSV values
        try:
            s_t_csv = float(csv_row[f's_t{t_str}'])  # DS's stimulus
            h_t_csv = float(csv_row[f'h_t{t_str}'])  # Human's stimulus
            ds_dec_csv = int(csv_row[f'ds_dec_t{t_str}'])  # DS decision from CSV
        except:
            print(f"   ⚠️  B{block}T{trial}: Could not read CSV columns")
            errors_this_user += 1
            continue
        
        # Get database values
        stimulus_db = action['stimulus_seen']
        dss_judgment_db = action['dss_judgment']
        
        # Convert DB dss_judgment to int
        if dss_judgment_db == 'signal':
            ds_dec_db = 1
        elif dss_judgment_db == 'noise':
            ds_dec_db = 0
        else:
            ds_dec_db = -1
        
        # Verify 3 things:
        # 1. CSV ds_dec is correct based on s_t
        expected_ds_dec = 1 if s_t_csv > 0 else 0
        csv_correct = (ds_dec_csv == expected_ds_dec)
        
        # 2. DB dss_judgment matches CSV ds_dec
        db_csv_match = (ds_dec_db == ds_dec_csv)
        
        # 3. DB stimulus_seen matches CSV h_t + 6.5
        expected_stimulus = h_t_csv + 6.5
        stimulus_match = abs(stimulus_db - expected_stimulus) < 0.01  # Allow small float error
        
        # Display result
        status1 = "✅" if csv_correct else "❌"
        status2 = "✅" if db_csv_match else "❌"
        status3 = "✅" if stimulus_match else "❌"
        
        if not (csv_correct and db_csv_match and stimulus_match):
            errors_this_user += 1
        
        checked_this_user += 1
        
        print(f"   B{block}T{trial}: s_t={s_t_csv:.2f} → CSV_ds={ds_dec_csv} {status1} | DB_ds={ds_dec_db} {status2} | stimulus={stimulus_db:.2f} (exp: {expected_stimulus:.2f}) {status3}")
    
    if errors_this_user > 0:
        print(f"   ⚠️  {errors_this_user}/{checked_this_user} trials with errors")
        ds_verification_errors += 1
    else:
        print(f"   ✅ All {checked_this_user} trials verified correctly")
    print()

if ds_verification_errors > 0:
    issues.append(f"DS verification errors: {ds_verification_errors} users")
    print(f"⚠️  {ds_verification_errors} users had verification errors")
else:
    print(f"✅ All sampled users passed DS verification!")

print()

################################################################################
# SECTION 5: TOAST QUESTIONNAIRE VALIDATION
################################################################################
print("=" * 100)
print("📋 SECTION 5: TOAST QUESTIONNAIRE VALIDATION")
print("=" * 100)
print()

complete_with_toast = complete_users[complete_users['user_id'].isin(toast['user_id'])]
print(f"TOAST Coverage:")
print(f"   Complete users: {len(complete_users)}")
print(f"   With TOAST: {len(complete_with_toast)} ({100*len(complete_with_toast)/len(complete_users):.1f}%)")

if len(complete_with_toast) < len(complete_users):
    missing_toast = len(complete_users) - len(complete_with_toast)
    print(f"   ⚠️  {missing_toast} complete users missing TOAST")
    issues.append(f"Missing TOAST: {missing_toast} users")
else:
    print(f"   ✅ All complete users have TOAST responses!")
print()

if len(toast) > 0:
    print("TOAST Response Statistics (mean ± std):")
    toast_stats = toast[['usefulness', 'reliability', 'trust', 'confidence', 'satisfaction']].describe()
    for col in ['usefulness', 'reliability', 'trust', 'confidence', 'satisfaction']:
        if col in toast_stats.columns:
            mean = toast_stats.loc['mean', col]
            std = toast_stats.loc['std', col]
            min_val = toast_stats.loc['min', col]
            max_val = toast_stats.loc['max', col]
            print(f"   {col}: {mean:.2f} ± {std:.2f} (range: {min_val:.0f}-{max_val:.0f})")
    print()

################################################################################
# SECTION 6: TIMEOUT MECHANISM VALIDATION
################################################################################
print("=" * 100)
print("⏱️  SECTION 6: TIMEOUT MECHANISM (30-minute reset)")
print("=" * 100)
print()

# Get incomplete users from last 2 hours
two_hours_ago = datetime.now() - timedelta(hours=2)
recent_incomplete = users[
    (users['complete'] == 0) & 
    (users['start_time'].notna())
].copy()

recent_incomplete['start_dt'] = pd.to_datetime(recent_incomplete['start_time'])
recent_incomplete = recent_incomplete[recent_incomplete['start_dt'] > two_hours_ago]

print(f"Recent Incomplete Users (last 2 hours): {len(recent_incomplete)}")
print()

timeout_correct = 0
timeout_errors = 0

for _, user in recent_incomplete.iterrows():
    user_id = user['user_id']
    csv_row_id = user['csv_row_id']
    start_time = user['start_dt']
    elapsed = (datetime.now() - start_time).total_seconds() / 60
    
    if pd.isna(csv_row_id):
        continue
    
    # Check CSV flag
    csv_row = csv_df[csv_df['id'] == csv_row_id]
    if len(csv_row) == 0:
        continue
    
    used_flag = csv_row.iloc[0]['used']
    
    # Expected flag
    if elapsed > 30:
        expected_flag = 0.0
    else:
        expected_flag = 0.5
    
    if used_flag == expected_flag:
        timeout_correct += 1
    else:
        timeout_errors += 1
        if timeout_errors <= 3:
            print(f"   ⚠️  User {user_id}: elapsed={elapsed:.1f}min, expected flag={expected_flag}, actual={used_flag}")

print(f"Timeout Logic Check:")
print(f"   Correct: {timeout_correct}")
print(f"   Errors: {timeout_errors}")

if timeout_errors > 0:
    print(f"   ⚠️  {timeout_errors} timeout logic errors")
    issues.append(f"Timeout errors: {timeout_errors} users")
else:
    print(f"   ✅ Timeout mechanism working correctly!")
print()

################################################################################
# FINAL SUMMARY
################################################################################
print("=" * 100)
print("🏁 FINAL VALIDATION SUMMARY")
print("=" * 100)
print()

print(f"📊 Overall Statistics:")
print(f"   Total users: {len(users)}")
print(f"   Complete: {len(complete_users)} ({100*len(complete_users)/len(users):.1f}%)")
print(f"   Incomplete: {len(users) - len(complete_users)} ({100*(len(users)-len(complete_users))/len(users):.1f}%)")
print(f"   CSV rows used: {len(users_with_row['csv_row_id'].unique())} / {len(csv_df)}")
print()

if len(issues) == 0:
    print("🎉 ALL VALIDATIONS PASSED!")
    print("   ✅ No issues found")
    print("   ✅ Data integrity: EXCELLENT")
    print("   ✅ Experimental design: VALID")
    print("   ✅ System functionality: OPERATIONAL")
else:
    print(f"⚠️  FOUND {len(issues)} ISSUE(S):")
    for i, issue in enumerate(issues, 1):
        print(f"   {i}. {issue}")
    print()
    print("   💡 Review issues above for details")

print()
print("=" * 100)
print("✅ COMPREHENSIVE VALIDATION COMPLETE")
print("=" * 100)

conn.close()
EOF

