#!/bin/bash
# Diagnostic script for accuracy calculation and duplicate CSV rows
# Usage: bash "QA Codes - PythonAnywhere/diagnose_accuracy_and_duplicates.sh"

# Get script directory and navigate to Experiment_Code
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
EXPERIMENT_CODE_DIR="$(dirname "$SCRIPT_DIR")/Experiment_Code"

if [ ! -d "$EXPERIMENT_CODE_DIR" ]; then
    EXPERIMENT_CODE_DIR="$HOME/ds-experiment-omri/Experiment_Code"
fi

cd "$EXPERIMENT_CODE_DIR" && python3 << 'EOF'
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime

conn = sqlite3.connect('DATA/db.sqlite3')
csv_df = pd.read_csv('DATA/conditions_experiment_3ps_11x11_120_A.csv')

print("=" * 100)
print("🔍 DIAGNOSTIC: ACCURACY CALCULATION & DUPLICATE CSV ROWS")
print("=" * 100)
print()

################################################################################
# ISSUE 1: DUPLICATE CSV ROWS FOR USERS 300+
################################################################################
print("=" * 100)
print("ISSUE 1: INVESTIGATING DUPLICATE CSV ROWS")
print("=" * 100)
print()

users = pd.read_sql_query("""
    SELECT user_id, aid, csv_row_id, complete, start_time
    FROM experiment_experimentdata
    WHERE complete = 1
""", conn)

# Find duplicates
duplicate_rows = users.groupby('csv_row_id').size()
duplicate_rows = duplicate_rows[duplicate_rows > 1]

print(f"Found {len(duplicate_rows)} duplicate CSV rows among complete users")
print()

for row_id, count in duplicate_rows.items():
    print(f"CSV Row {int(row_id)}: {count} users")
    dup_users = users[users['csv_row_id'] == row_id].sort_values('user_id')
    
    for _, u in dup_users.iterrows():
        print(f"   User {u['user_id']}: aid={u['aid'][:40]}, started={u['start_time']}")
    
    # Check CSV flag
    csv_row = csv_df[csv_df['id'] == row_id].iloc[0]
    print(f"   CSV Row Status: used={csv_row['used']}, isDemo={csv_row['isDemo']}")
    print()

################################################################################
# ISSUE 2: ACCURACY CALCULATION
################################################################################
print("=" * 100)
print("ISSUE 2: INVESTIGATING ACCURACY CALCULATION")
print("=" * 100)
print()

# Get complete users
complete_users = users[users['complete'] == 1]

# Get all actions
actions = pd.read_sql_query("""
    SELECT user_id_id as user_id, block_number, trial_number, 
           classification_decision, correct_classification
    FROM experiment_experimentaction
""", conn)

# Filter to complete users only
complete_actions = actions[actions['user_id'].isin(complete_users['user_id'])].copy()

print(f"Total complete users: {len(complete_users)}")
print(f"Total actions for complete users: {len(complete_actions)}")
print()

# Check data types and values
print("📊 Data Quality Check:")
print(f"   classification_decision unique values: {complete_actions['classification_decision'].unique()}")
print(f"   correct_classification unique values: {complete_actions['correct_classification'].unique()}")
print()

# Check for any null values
print(f"   Null classification_decision: {complete_actions['classification_decision'].isna().sum()}")
print(f"   Null correct_classification: {complete_actions['correct_classification'].isna().sum()}")
print()

# Sample some raw data
print("📋 Sample Raw Data (first 10 actions):")
sample = complete_actions.head(10)[['user_id', 'block_number', 'trial_number', 'classification_decision', 'correct_classification']]
print(sample.to_string(index=False))
print()

# Calculate accuracy properly
print("📈 Accuracy Calculation:")
print()

# Direct string comparison (no normalization issues)
complete_actions['is_correct'] = (
    complete_actions['classification_decision'] == complete_actions['correct_classification']
).astype(int)

print("Overall:")
overall_correct = complete_actions['is_correct'].sum()
overall_total = len(complete_actions)
print(f"   Correct: {overall_correct}/{overall_total} = {100*overall_correct/overall_total:.1f}%")
print()

print("By Block:")
for block in [1, 2, 3]:
    block_actions = complete_actions[complete_actions['block_number'] == block]
    correct = block_actions['is_correct'].sum()
    total = len(block_actions)
    acc = 100 * correct / total if total > 0 else 0
    print(f"   Block {block}: {correct}/{total} = {acc:.1f}%")
print()

# Per-user accuracy distribution
print("📊 Per-User Accuracy Distribution:")
user_accuracies = []
for user_id in complete_users['user_id'].head(20):  # First 20 users
    user_actions = complete_actions[complete_actions['user_id'] == user_id]
    if len(user_actions) > 0:
        acc = 100 * user_actions['is_correct'].sum() / len(user_actions)
        user_accuracies.append(acc)
        if len(user_accuracies) <= 10:
            print(f"   User {user_id}: {acc:.1f}% ({user_actions['is_correct'].sum()}/{len(user_actions)})")

if len(user_accuracies) > 0:
    print(f"\n   Mean user accuracy (first 20): {np.mean(user_accuracies):.1f}%")
    print(f"   Std dev: {np.std(user_accuracies):.1f}%")
    print(f"   Range: {np.min(user_accuracies):.1f}% - {np.max(user_accuracies):.1f}%")
print()

# Check users with very low accuracy (< 30%)
print("⚠️  Users with accuracy < 30%:")
low_acc_users = []
for user_id in complete_users['user_id']:
    user_actions = complete_actions[complete_actions['user_id'] == user_id]
    if len(user_actions) == 120:  # Only complete users
        acc = 100 * user_actions['is_correct'].sum() / len(user_actions)
        if acc < 30:
            low_acc_users.append((user_id, acc, len(user_actions)))

if len(low_acc_users) > 0:
    print(f"   Found {len(low_acc_users)} users with < 30% accuracy")
    for user_id, acc, total in low_acc_users[:10]:
        user_info = users[users['user_id'] == user_id].iloc[0]
        print(f"   User {user_id}: {acc:.1f}% (aid: {user_info['aid'][:30]}...)")
else:
    print(f"   ✅ No users with < 30% accuracy")
print()

# Check if there's a pattern with user_id ranges
print("📊 Accuracy by User ID Range:")
for start in [1, 100, 200, 300]:
    end = start + 99
    range_users = complete_users[(complete_users['user_id'] >= start) & (complete_users['user_id'] <= end)]
    if len(range_users) > 0:
        range_actions = complete_actions[complete_actions['user_id'].isin(range_users['user_id'])]
        if len(range_actions) > 0:
            acc = 100 * range_actions['is_correct'].sum() / len(range_actions)
            print(f"   Users {start}-{end}: {acc:.1f}% ({len(range_users)} users, {len(range_actions)} actions)")

print()
print("=" * 100)
print("✅ DIAGNOSTIC COMPLETE")
print("=" * 100)

conn.close()
EOF

