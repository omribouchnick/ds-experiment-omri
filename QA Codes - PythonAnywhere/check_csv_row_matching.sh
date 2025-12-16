#!/bin/bash
# Check specific user's CSV row matching - verify all trial data matches
# Usage: bash check_csv_row_matching.sh [user_id]
# If no user_id provided, checks the newest user

USER_ID=${1:-""}

cd ~/ds-experiment-omri && python3 << EOF
import sqlite3
import pandas as pd

conn = sqlite3.connect('db.sqlite3')
user_id = "$USER_ID"

# Get user
if user_id:
    users = pd.read_sql_query(f"""
        SELECT user_id, aid, csv_row_id, ps, human_sensitivity, ds_sensitivity, complete
        FROM experiment_experimentdata
        WHERE user_id = {user_id}
    """, conn)
else:
    users = pd.read_sql_query("""
        SELECT user_id, aid, csv_row_id, ps, human_sensitivity, ds_sensitivity, complete
        FROM experiment_experimentdata
        ORDER BY user_id DESC LIMIT 1
    """, conn)

if len(users) == 0:
    print("❌ User not found")
    conn.close()
    exit()

u = users.iloc[0]
print("=" * 80)
print(f"📋 CSV ROW MATCHING - USER {u['user_id']}")
print("=" * 80)
print(f"AID:         {u['aid']}")
print(f"CSV Row ID:  {u['csv_row_id']}")
print(f"Complete:    {'✅' if u['complete'] else '❌'}")

# Load CSV
csv_df = pd.read_csv('DATA/conditions_experiment_3ps_11x11_120_A.csv')
csv_row = csv_df[csv_df['id'] == u['csv_row_id']].iloc[0]

print(f"\n{'='*80}")
print("🔍 PARAMETER MATCHING")
print("=" * 80)
print(f"{'Parameter':<20} {'DB Value':<15} {'CSV Value':<15} {'Match'}")
print("-" * 60)

ps_match = "✅" if float(u['ps']) == float(csv_row['ps']) else "❌"
dh_match = "✅" if float(u['human_sensitivity']) == float(csv_row['dprime_h']) else "❌"
ds_match = "✅" if float(u['ds_sensitivity']) == float(csv_row['dprime_s']) else "❌"

print(f"{'ps':<20} {u['ps']:<15} {csv_row['ps']:<15} {ps_match}")
print(f"{'d_prime_human':<20} {u['human_sensitivity']:<15} {csv_row['dprime_h']:<15} {dh_match}")
print(f"{'d_prime_DS':<20} {u['ds_sensitivity']:<15} {csv_row['dprime_s']:<15} {ds_match}")

# Get all actions - correct column names
actions = pd.read_sql_query(f"""
    SELECT block_number, trial_number, stimulus_seen, dss_judgment, 
           classification_decision, correct_classification
    FROM experiment_experimentaction
    WHERE user_id_id = {u['user_id']}
    ORDER BY block_number, trial_number
""", conn)

print(f"\n{'='*80}")
print(f"🔍 ALL TRIALS DS VERIFICATION ({len(actions)} trials)")
print("=" * 80)
print(f"{'Trial':<8} {'s_t':<10} {'Expected':<10} {'DS':<10} {'User':<10} {'Correct':<8} {'DS OK'}")
print("-" * 70)

all_ds_ok = True
for _, a in actions.iterrows():
    block = int(a['block_number'])
    trial = int(a['trial_number'])
    csv_trial = trial if block == 1 else (trial + 10 if block == 2 else trial + 20)
    
    s_t = csv_row[f's_t{csv_trial:02d}']
    expected_ds = 'signal' if s_t > 0 else 'noise'
    actual_ds = a['dss_judgment']
    user = a['classification_decision']
    user_correct = "✅" if user == a['correct_classification'] else "❌"
    ds_match = '✅' if actual_ds == expected_ds else '❌'
    
    if actual_ds != expected_ds:
        all_ds_ok = False
    
    print(f"B{block}T{trial:<4} {s_t:>8.2f}  {expected_ds:<10} {actual_ds:<10} {user:<10} {user_correct:<8} {ds_match}")

print("-" * 70)
print(f"{'✅ ALL DS DECISIONS CORRECT!' if all_ds_ok else '❌ DS MISMATCHES FOUND!'}")

# Summary stats
print(f"\n{'='*80}")
print("📊 SUMMARY STATISTICS")
print("=" * 80)

for block in [1, 2, 3]:
    ba = actions[actions['block_number'] == block]
    if len(ba) > 0:
        correct = (ba['classification_decision'] == ba['correct_classification']).sum()
        agreed = (ba['classification_decision'] == ba['dss_judgment']).sum()
        print(f"Block {block}: {len(ba)} trials | Accuracy: {correct}/{len(ba)} ({100*correct/len(ba):.0f}%) | DS Agreement: {agreed}/{len(ba)} ({100*agreed/len(ba):.0f}%)")

# Overall
if len(actions) > 0:
    total_correct = (actions['classification_decision'] == actions['correct_classification']).sum()
    total_agreed = (actions['classification_decision'] == actions['dss_judgment']).sum()
    print(f"\nOverall: {len(actions)} trials | Accuracy: {total_correct}/{len(actions)} ({100*total_correct/len(actions):.0f}%) | DS Agreement: {total_agreed}/{len(actions)} ({100*total_agreed/len(actions):.0f}%)")

# CSV row final status
print(f"\n{'='*80}")
print("📋 CSV ROW STATUS")
print("=" * 80)
print(f"used:    {csv_row['used']} {'✅' if (u['complete'] and csv_row['used'] == 1) or (not u['complete'] and csv_row['used'] == 0) else '❌'}")
print(f"isDemo:  {csv_row.get('isDemo', 'N/A')}")

conn.close()
print("\n" + "=" * 80)
EOF
