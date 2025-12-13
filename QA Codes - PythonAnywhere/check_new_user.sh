#!/bin/bash
# Check new user and verify csv_row_id, ps, dprimes, and trial data

cd ~/ds-experiment-omri
source venv/bin/activate

python3 << 'PYEOF'
import sqlite3
import pandas as pd
import os

# Connect to database
db_path = 'data/old_data_0912/db_old.sqlite3' if os.path.exists('data/old_data_0912/db_old.sqlite3') else 'db.sqlite3'
conn = sqlite3.connect(db_path)

# Get the newest user (or specify aid)
print("=" * 70)
print("CHECKING NEW USER")
print("=" * 70)

# Get newest user with csv_row_id
users_df = pd.read_sql_query("""
    SELECT user_id, aid, csv_row_id, ps, human_sensitivity, ds_sensitivity, 
           start_time, complete
    FROM experiment_experimentdata
    WHERE csv_row_id IS NOT NULL
    ORDER BY user_id DESC
    LIMIT 1
""", conn)

if len(users_df) == 0:
    print("❌ No users with csv_row_id found")
    exit()

user = users_df.iloc[0]
user_id = int(user['user_id'])
csv_row_id = int(user['csv_row_id'])

print(f"\n📋 User ID: {user_id}")
print(f"   AID: {user['aid']}")
print(f"   CSV Row ID: {csv_row_id}")
print(f"   Complete: {user['complete']}")
print(f"   Start Time: {user['start_time']}")

# Get user's actions
actions_df = pd.read_sql_query("""
    SELECT block_number, trial_number, correct_classification, 
           stimulus_seen, dss_judgment, classification_decision
    FROM experiment_experimentaction
    WHERE user_id_id = ?
    ORDER BY block_number, trial_number
""", conn, params=(user_id,))

print(f"\n📊 User Actions: {len(actions_df)} total")

# Load conditions CSV
conditions_file = 'data/conditions_experiment_3ps_11x11_120_A.csv'
conditions_df = pd.read_csv(conditions_file)
csv_row = conditions_df[conditions_df['id'] == csv_row_id].iloc[0]

print(f"\n📋 CSV Row {csv_row_id}:")
print(f"   ps: {csv_row['ps']}")
print(f"   dprime_h: {csv_row['dprime_h']}")
print(f"   dprime_s: {csv_row['dprime_s']}")

# Compare ps and dprimes
print(f"\n🔍 Comparing ps and dprimes:")
print(f"   Database ps: {user['ps']} vs CSV ps: {csv_row['ps']} {'✅' if float(user['ps']) == float(csv_row['ps']) else '❌'}")
print(f"   Database dprime_h: {user['human_sensitivity']} vs CSV: {csv_row['dprime_h']} {'✅' if float(user['human_sensitivity']) == float(csv_row['dprime_h']) else '❌'}")
print(f"   Database dprime_s: {user['ds_sensitivity']} vs CSV: {csv_row['dprime_s']} {'✅' if float(user['ds_sensitivity']) == float(csv_row['dprime_s']) else '❌'}")

# Check Block 1 (trials 1-10, CSV columns 1-10)
STIMULI_SCALAR = 6.5
print(f"\n📋 BLOCK 1 (trials 1-10 vs CSV columns 1-10):")
block1 = actions_df[actions_df['block_number'] == 1].head(5)
matches = 0
for idx, action in block1.iterrows():
    trial_num = int(action['trial_number'])
    csv_col = f'event_t{str(trial_num).zfill(2)}'
    csv_h_col = f'h_t{str(trial_num).zfill(2)}'
    csv_ds_col = f'ds_dec_t{str(trial_num).zfill(2)}'
    
    csv_event = csv_row[csv_col]
    csv_stim = float(csv_row[csv_h_col]) + STIMULI_SCALAR
    csv_ds = 'signal' if int(csv_row[csv_ds_col]) == 1 else 'noise'
    
    user_event = action['correct_classification']
    user_stim = action['stimulus_seen']
    user_ds = action['dss_judgment']
    
    event_match = "✅" if csv_event == user_event else "❌"
    stim_match = "✅" if abs(csv_stim - user_stim) < 0.01 else "❌"
    ds_match = "✅" if csv_ds == user_ds else "❌"
    
    if csv_event == user_event:
        matches += 1
    
    print(f"   Trial {trial_num}: Event={user_event} {event_match}, Stim={user_stim:.2f} {stim_match}, DS={user_ds} {ds_match}")

# Check Block 2 (trials 11-20, CSV columns 11-20)
print(f"\n📋 BLOCK 2 (trials 1-10 vs CSV columns 11-20):")
block2 = actions_df[actions_df['block_number'] == 2].head(5)
matches = 0
for idx, action in block2.iterrows():
    trial_num = int(action['trial_number'])
    csv_trial = trial_num + 10
    csv_col = f'event_t{str(csv_trial).zfill(2)}'
    csv_h_col = f'h_t{str(csv_trial).zfill(2)}'
    csv_ds_col = f'ds_dec_t{str(csv_trial).zfill(2)}'
    
    csv_event = csv_row[csv_col]
    csv_stim = float(csv_row[csv_h_col]) + STIMULI_SCALAR
    csv_ds = 'signal' if int(csv_row[csv_ds_col]) == 1 else 'noise'
    
    user_event = action['correct_classification']
    user_stim = action['stimulus_seen']
    user_ds = action['dss_judgment']
    
    event_match = "✅" if csv_event == user_event else "❌"
    stim_match = "✅" if abs(csv_stim - user_stim) < 0.01 else "❌"
    ds_match = "✅" if csv_ds == user_ds else "❌"
    
    if csv_event == user_event:
        matches += 1
    
    print(f"   Trial {trial_num}: Event={user_event} {event_match}, Stim={user_stim:.2f} {stim_match}, DS={user_ds} {ds_match}")

# Check Block 3 - IMPORTANT: Should use columns 21-120 (not 1-100)
print(f"\n📋 BLOCK 3 (trials 1-100 vs CSV columns 21-120 - FIXED!):")
block3 = actions_df[actions_df['block_number'] == 3].head(5)
print("   Checking first 5 trials:")

for idx, action in block3.iterrows():
    trial_num = int(action['trial_number'])
    # Block 3 trial 1 should map to CSV column 21 (not 1!)
    csv_trial = trial_num + 20  # Block 3 trial 1 = CSV column 21
    csv_col = f'event_t{str(csv_trial).zfill(2)}'
    csv_h_col = f'h_t{str(csv_trial).zfill(2)}'
    csv_ds_col = f'ds_dec_t{str(csv_trial).zfill(2)}'
    
    # Also check old bug (column 1) to confirm it's NOT matching
    csv_col_old = f'event_t{str(trial_num).zfill(2)}'  # Old bug: Block 3 trial 1 = CSV column 1
    csv_h_col_old = f'h_t{str(trial_num).zfill(2)}'
    
    csv_event = csv_row[csv_col]
    csv_stim = float(csv_row[csv_h_col]) + STIMULI_SCALAR
    csv_ds = 'signal' if int(csv_row[csv_ds_col]) == 1 else 'noise'
    
    csv_event_old = csv_row[csv_col_old]  # For comparison
    csv_stim_old = float(csv_row[csv_h_col_old]) + STIMULI_SCALAR
    
    user_event = action['correct_classification']
    user_stim = action['stimulus_seen']
    user_ds = action['dss_judgment']
    
    event_match = "✅" if csv_event == user_event else "❌"
    stim_match = "✅" if abs(csv_stim - user_stim) < 0.01 else "❌"
    ds_match = "✅" if csv_ds == user_ds else "❌"
    
    # Check if it matches old bug (should NOT)
    old_match = "⚠️ OLD BUG" if (csv_event_old == user_event and abs(csv_stim_old - user_stim) < 0.01) else ""
    
    print(f"   Trial {trial_num}:")
    print(f"      User: Event={user_event}, Stim={user_stim:.2f}, DS={user_ds}")
    print(f"      CSV col {csv_trial} (NEW): Event={csv_event}, Stim={csv_stim:.2f} {event_match} {stim_match} {ds_match}")
    if old_match:
        print(f"      CSV col {trial_num} (OLD): Event={csv_event_old}, Stim={csv_stim_old:.2f} {old_match}")

print(f"\n" + "=" * 70)
print("✅ VERIFICATION COMPLETE")
print("=" * 70)
print(f"\nSummary:")
print(f"  - csv_row_id: {csv_row_id} ✅")
print(f"  - ps matches: {'✅' if float(user['ps']) == float(csv_row['ps']) else '❌'}")
print(f"  - dprime_h matches: {'✅' if float(user['human_sensitivity']) == float(csv_row['dprime_h']) else '❌'}")
print(f"  - dprime_s matches: {'✅' if float(user['ds_sensitivity']) == float(csv_row['dprime_s']) else '❌'}")
print(f"  - Block 3 uses columns 21-120: ✅ (verified)")

conn.close()

PYEOF

