#!/bin/bash
# Detailed validation of the most recent complete user
# Shows all actions, accuracy, CSV matching, and data integrity
# Usage: bash "QA Codes - PythonAnywhere/validate_last_user_detailed.sh"

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
from datetime import datetime

# Load data
conn = sqlite3.connect('DATA/db.sqlite3')
csv_df = pd.read_csv('DATA/conditions_experiment_3ps_11x11_120_A.csv')

print("=" * 100)
print("🔬 DETAILED VALIDATION - MOST RECENT COMPLETE USER")
print("=" * 100)
print(f"Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

# Get most recent complete user
user = pd.read_sql_query("""
    SELECT user_id, aid, csv_row_id, ps, human_sensitivity, ds_sensitivity, 
           complete, start_time, end_time
    FROM experiment_experimentdata
    WHERE complete = 1
    ORDER BY user_id DESC
    LIMIT 1
""", conn).iloc[0]

user_id = user['user_id']
csv_row_id = user['csv_row_id']

print(f"📊 USER INFORMATION")
print("-" * 100)
print(f"User ID:      {user_id}")
print(f"AID:          {user['aid']}")
print(f"CSV Row ID:   {int(csv_row_id)}")
print(f"Start Time:   {user['start_time']}")
print(f"End Time:     {user['end_time']}")
print(f"Complete:     {user['complete'] == 1}")
print()

# Get CSV row
csv_row = csv_df[csv_df['id'] == csv_row_id].iloc[0]

print(f"📋 EXPERIMENTAL CONDITIONS (DB vs CSV)")
print("-" * 100)
print(f"ps (Signal Probability):")
print(f"   DB:  {user['ps']}")
print(f"   CSV: {csv_row['ps']}")
print(f"   {'✅ Match' if user['ps'] == csv_row['ps'] else '❌ MISMATCH'}")
print()

print(f"d'_human (Human Sensitivity):")
print(f"   DB:  {user['human_sensitivity']}")
print(f"   CSV: {csv_row['dprime_h']}")
print(f"   {'✅ Match' if user['human_sensitivity'] == csv_row['dprime_h'] else '❌ MISMATCH'}")
print()

print(f"d'_DS (DS Sensitivity):")
print(f"   DB:  {user['ds_sensitivity']}")
print(f"   CSV: {csv_row['dprime_s']}")
print(f"   {'✅ Match' if user['ds_sensitivity'] == csv_row['dprime_s'] else '❌ MISMATCH'}")
print()

# Get all actions
actions = pd.read_sql_query(f"""
    SELECT block_number, trial_number, classification_decision, 
           stimulus_seen, dss_judgment, decision_time, correct_classification
    FROM experiment_experimentaction
    WHERE user_id_id = {user_id}
    ORDER BY block_number, trial_number
""", conn)

print(f"📊 ACTIONS SUMMARY")
print("-" * 100)
print(f"Total actions recorded: {len(actions)}")
print(f"Expected: 120 (10 + 10 + 100)")
print(f"{'✅ All actions saved' if len(actions) == 120 else f'⚠️  Missing {120 - len(actions)} actions'}")
print()

# Group by block
print(f"Actions by Block:")
for block in [1, 2, 3]:
    block_actions = actions[actions['block_number'] == block]
    expected = 10 if block <= 2 else 100
    print(f"   Block {block}: {len(block_actions)}/{expected} trials {'✅' if len(block_actions) == expected else '❌'}")
print()

# Calculate accuracy per block
print(f"📈 ACCURACY BY BLOCK")
print("-" * 100)

# Normalize columns
actions['classification_norm'] = actions['classification_decision'].replace({
    'signal': 1, 'noise': 0
}).astype(int)
actions['correct_norm'] = actions['correct_classification'].replace({
    'signal': 1, 'noise': 0
}).astype(int)
actions['is_correct'] = (actions['classification_norm'] == actions['correct_norm']).astype(int)

for block in [1, 2, 3]:
    block_actions = actions[actions['block_number'] == block]
    if len(block_actions) > 0:
        correct = block_actions['is_correct'].sum()
        total = len(block_actions)
        accuracy = 100 * correct / total
        mean_rt = block_actions['decision_time'].mean()
        
        print(f"Block {block}:")
        print(f"   Accuracy:     {accuracy:.1f}% ({correct}/{total})")
        print(f"   Mean RT:      {mean_rt:.2f}s")
        print(f"   RT range:     {block_actions['decision_time'].min():.2f}s - {block_actions['decision_time'].max():.2f}s")
        print()

# Overall accuracy
overall_correct = actions['is_correct'].sum()
overall_total = len(actions)
overall_accuracy = 100 * overall_correct / overall_total
print(f"Overall Accuracy: {overall_accuracy:.1f}% ({overall_correct}/{overall_total})")
print()

# DS agreement (only for Blocks 2 and 3 where DS is shown)
actions['dss_norm'] = actions['dss_judgment'].replace({
    'signal': 1, 'noise': 0
}).astype(int)
actions['agreed_with_ds'] = (actions['classification_norm'] == actions['dss_norm']).astype(int)

print(f"📊 DS AGREEMENT (Blocks 2-3 only, where DS is shown):")
for block in [2, 3]:
    block_actions = actions[actions['block_number'] == block]
    if len(block_actions) > 0:
        agreed = block_actions['agreed_with_ds'].sum()
        total = len(block_actions)
        agreement = 100 * agreed / total
        print(f"   Block {block}: {agreement:.1f}% ({agreed}/{total})")

# For Block 1, show coincidental match (interesting but not "agreement")
block1_actions = actions[actions['block_number'] == 1]
if len(block1_actions) > 0:
    coincidental = block1_actions['agreed_with_ds'].sum()
    total = len(block1_actions)
    rate = 100 * coincidental / total
    print(f"\n   Block 1 (no DS shown): {rate:.1f}% coincidental match with DS ({coincidental}/{total})")
    print(f"   (User made independent decisions, didn't see DS)")

print()

# Helper function to map trial to CSV column
def get_trial_col(trial_num, block_num):
    if block_num == 1:
        return trial_num
    elif block_num == 2:
        return trial_num + 10
    else:
        return trial_num + 20

# Detailed CSV verification for first 5 trials
print(f"🔍 DETAILED CSV VERIFICATION (First 5 Trials)")
print("-" * 100)
print(f"Checking DB values against CSV row {int(csv_row_id)} columns...")
print()

verification_errors = 0
for _, action in actions.head(5).iterrows():
    block = int(action['block_number'])
    trial = int(action['trial_number'])
    csv_trial = get_trial_col(trial, block)
    t_str = f'0{csv_trial}' if csv_trial < 10 else f'{csv_trial}'
    
    # Get CSV values
    try:
        event_csv = csv_row[f'event_t{t_str}']
        h_t_csv = float(csv_row[f'h_t{t_str}'])
        s_t_csv = float(csv_row[f's_t{t_str}'])
        ds_dec_csv = int(csv_row[f'ds_dec_t{t_str}'])
    except Exception as e:
        print(f"❌ B{block}T{trial}: Could not read CSV columns - {e}")
        verification_errors += 1
        continue
    
    # Get DB values
    stimulus_db = action['stimulus_seen']
    dss_judgment_db = action['dss_judgment']
    correct_class_db = action['correct_classification']
    human_decision_db = action['classification_decision']
    
    # Convert to comparable format
    ds_dec_db = 1 if dss_judgment_db == 'signal' else 0
    expected_stimulus = h_t_csv + 6.5
    expected_ds_from_st = 1 if s_t_csv > 0 else 0
    
    # Verify
    stimulus_match = abs(stimulus_db - expected_stimulus) < 0.01
    ds_match = (ds_dec_db == ds_dec_csv)
    ds_correct = (ds_dec_csv == expected_ds_from_st)
    event_match = (correct_class_db == event_csv)
    
    print(f"Block {block}, Trial {trial} (CSV column t{csv_trial:02d}):")
    print(f"   Event:        CSV={event_csv:6s}, DB_correct={correct_class_db:6s} {'✅' if event_match else '❌'}")
    print(f"   h_t:          CSV={h_t_csv:6.2f}, DB_stimulus={stimulus_db:6.2f} (exp: {expected_stimulus:6.2f}) {'✅' if stimulus_match else '❌'}")
    print(f"   s_t:          CSV={s_t_csv:6.2f} → expected_ds={expected_ds_from_st}")
    print(f"   ds_dec:       CSV={ds_dec_csv}, DB={ds_dec_db} {'✅' if ds_match else '❌'}, calc_correct={'✅' if ds_correct else '❌'}")
    print(f"   Human chose:  {human_decision_db}")
    print()
    
    if not (stimulus_match and ds_match and ds_correct and event_match):
        verification_errors += 1

if verification_errors > 0:
    print(f"⚠️  Found {verification_errors} verification errors in first 5 trials")
else:
    print(f"✅ All first 5 trials verified correctly!")

print()

# Get TOAST
toast = pd.read_sql_query(f"""
    SELECT usefulness, reliability, trust, confidence, satisfaction
    FROM experiment_toastresponse
    WHERE user_id_id = {user_id}
""", conn)

print(f"📋 TOAST QUESTIONNAIRE")
print("-" * 100)
if len(toast) > 0:
    toast_row = toast.iloc[0]
    print(f"✅ TOAST completed")
    print(f"   Usefulness:    {toast_row['usefulness']}/7")
    print(f"   Reliability:   {toast_row['reliability']}/7")
    print(f"   Trust:         {toast_row['trust']}/7")
    print(f"   Confidence:    {toast_row['confidence']}/7")
    print(f"   Satisfaction:  {toast_row['satisfaction']}/7")
else:
    print(f"❌ No TOAST response found")

print()

# CSV Row Status
print(f"📋 CSV ROW STATUS")
print("-" * 100)
print(f"Row {int(csv_row_id)} in CSV:")
print(f"   used:    {csv_row['used']} {'✅ (completed)' if csv_row['used'] == 1.0 else '⚠️  (should be 1.0)'}")
print(f"   isDemo:  {csv_row['isDemo']} {'✅' if pd.notna(csv_row['isDemo']) else '⚠️  (not set)'}")

print()
print("=" * 100)
print("✅ DETAILED VALIDATION COMPLETE")
print("=" * 100)

conn.close()
EOF

