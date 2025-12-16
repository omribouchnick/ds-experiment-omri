#!/bin/bash
# Check the newest user - quick verification that experiment is working
# Usage: bash check_new_user.sh

cd ~/ds-experiment-omri && python3 << 'EOF'
import sqlite3
import pandas as pd

conn = sqlite3.connect('db.sqlite3')

# Get newest user
users = pd.read_sql_query("""
    SELECT user_id, aid, csv_row_id, ps, human_sensitivity, ds_sensitivity, 
           complete, start_time, end_time
    FROM experiment_experimentdata
    ORDER BY user_id DESC LIMIT 1
""", conn)

if len(users) == 0:
    print("❌ No users found in database")
    conn.close()
    exit()

u = users.iloc[0]
status = "✅ COMPLETE" if u['complete'] else "❌ INCOMPLETE"

print("=" * 70)
print(f"🆕 NEWEST USER CHECK")
print("=" * 70)
print(f"User ID:    {u['user_id']}")
print(f"AID:        {u['aid']}")
print(f"CSV Row:    {u['csv_row_id']}")
print(f"Status:     {status}")
print(f"Start:      {u['start_time']}")
print(f"End:        {u['end_time'] if u['end_time'] else 'N/A'}")
print(f"PS:         {u['ps']}, d'_human: {u['human_sensitivity']}, d'_DS: {u['ds_sensitivity']}")

# Get actions - correct column names
actions = pd.read_sql_query(f"""
    SELECT block_number, trial_number, stimulus_seen, dss_judgment, 
           classification_decision, correct_classification
    FROM experiment_experimentaction
    WHERE user_id_id = {u['user_id']}
    ORDER BY block_number, trial_number
""", conn)
print(f"\n📊 ACTIONS: {len(actions)} trials recorded")

# Block breakdown
if len(actions) > 0:
    for block in [1, 2, 3]:
        block_actions = actions[actions['block_number'] == block]
        if len(block_actions) > 0:
            # correct_classification contains the correct answer, compare with classification_decision
            correct = (block_actions['classification_decision'] == block_actions['correct_classification']).sum()
            total = len(block_actions)
            agreed = (block_actions['classification_decision'] == block_actions['dss_judgment']).sum()
            print(f"   Block {block}: {total} trials, {correct}/{total} correct ({100*correct/total:.0f}%), agreed with DS: {agreed}/{total}")

# Check TOAST
toast = pd.read_sql_query(f"""
    SELECT * FROM experiment_toastresponse WHERE user_id_id = {u['user_id']}
""", conn)
print(f"\n📋 TOAST: {'✅ Completed' if len(toast) > 0 else '❌ Not completed'}")

# Load CSV and verify DS decisions
print("\n" + "=" * 70)
print("🔍 DS DECISION VERIFICATION (first 6 trials)")
print("=" * 70)

try:
    csv_df = pd.read_csv('DATA/conditions_experiment_3ps_11x11_120_A.csv')
    row = csv_df[csv_df['id'] == u['csv_row_id']].iloc[0]
    
    all_ok = True
    for _, a in actions.head(6).iterrows():
        block = int(a['block_number'])
        trial = int(a['trial_number'])
        csv_trial = trial if block == 1 else (trial + 10 if block == 2 else trial + 20)
        s_t = row[f's_t{csv_trial:02d}']
        expected_ds = 'signal' if s_t > 0 else 'noise'
        db_ds = a['dss_judgment']
        match = '✅' if db_ds == expected_ds else '❌'
        if db_ds != expected_ds:
            all_ok = False
        print(f"  B{block}T{trial}: s_t={s_t:.2f}, DS={db_ds}, should={expected_ds} {match}")
    
    print(f"\n{'✅ ALL DS DECISIONS CORRECT!' if all_ok else '❌ DS MISMATCHES FOUND!'}")
    
    # Check CSV row status
    print("\n" + "=" * 70)
    print("📋 CSV ROW STATUS")
print("=" * 70)
    print(f"  Row ID:   {u['csv_row_id']}")
    print(f"  used:     {row['used']}")
    print(f"  isDemo:   {row.get('isDemo', 'N/A')}")
    
except Exception as e:
    print(f"⚠️  Could not verify: {e}")

conn.close()
print("\n" + "=" * 70)
EOF
