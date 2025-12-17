#!/bin/bash
# Final validation before continuing pilot
# Usage: bash final_validation_before_pilot.sh

cd ~/ds-experiment-omri/Experiment_Code && python3 << 'EOF'
import sqlite3
import pandas as pd
from datetime import datetime

conn = sqlite3.connect('DATA/db.sqlite3')

print("=" * 80)
print("🔍 FINAL VALIDATION BEFORE CONTINUING PILOT")
print("=" * 80)

# 1. Check end_time coverage
users = pd.read_sql_query("""
    SELECT user_id, aid, complete, start_time, end_time
    FROM experiment_experimentdata
    WHERE start_time >= '2025-12-14'
    ORDER BY user_id
""", conn)

incomplete_users = users[users['complete'] == False]
complete_users = users[users['complete'] == True]

incomplete_with_endtime = incomplete_users[incomplete_users['end_time'].notna()]
incomplete_without_endtime = incomplete_users[incomplete_users['end_time'].isna()]

print(f"\n📋 1. END_TIME COVERAGE:")
print(f"   Complete users: {len(complete_users)}")
print(f"   - With end_time: {complete_users['end_time'].notna().sum()} ✅")
print(f"   - Without end_time: {complete_users['end_time'].isna().sum()}")
print(f"   Incomplete users: {len(incomplete_users)}")
print(f"   - With end_time: {len(incomplete_with_endtime)} ✅")
print(f"   - Without end_time: {len(incomplete_without_endtime)}")
if len(incomplete_without_endtime) > 0:
    print(f"     Users without end_time: {incomplete_without_endtime['user_id'].tolist()}")
    print(f"     (These are users still in progress)")

# 2. Check DS decisions for recent users
print(f"\n📋 2. DS DECISION VERIFICATION (Last 10 users):")
csv_df = pd.read_csv('DATA/conditions_experiment_3ps_11x11_120_A.csv')

recent_users = users.tail(10)
all_correct = True

for _, user in recent_users.iterrows():
    if pd.isna(user.get('csv_row_id')):
        continue
    
    csv_row_id = int(user['csv_row_id'])
    csv_row = csv_df[csv_df['id'] == csv_row_id].iloc[0]
    
    actions = pd.read_sql_query(f"""
        SELECT block_number, trial_number, dss_judgment
        FROM experiment_experimentaction
        WHERE user_id_id = {user['user_id']}
        ORDER BY block_number, trial_number
        LIMIT 6
    """, conn)
    
    errors = 0
    for _, a in actions.iterrows():
        block = int(a['block_number'])
        trial = int(a['trial_number'])
        csv_trial = trial if block == 1 else (trial + 10 if block == 2 else trial + 20)
        s_t = csv_row[f's_t{csv_trial:02d}']
        expected = 'signal' if s_t > 0 else 'noise'
        actual = a['dss_judgment']
        if actual != expected:
            errors += 1
            all_correct = False
    
    status = "✅" if errors == 0 else f"❌ {errors} errors"
    print(f"   User {user['user_id']}: {status}")

if all_correct:
    print(f"   ✅ All DS decisions are CORRECT!")

# 3. Check CSV used flags
print(f"\n📋 3. CSV USED FLAGS:")
used_counts = csv_df['used'].value_counts().sort_index()
print(f"   used=0 (available): {used_counts.get(0.0, 0)}")
print(f"   used=0.5 (in-progress): {used_counts.get(0.5, 0)}")
print(f"   used=1 (completed): {used_counts.get(1.0, 0)}")

# Check mismatches
complete_user_rows = users[users['complete'] == True]['csv_row_id'].dropna().astype(int).unique()
rows_marked_1 = csv_df[csv_df['used'] == 1]['id'].tolist()

mismatches = []
for row_id in complete_user_rows:
    if row_id not in rows_marked_1:
        mismatches.append(row_id)

if len(mismatches) == 0:
    print(f"   ✅ All completed users have CSV used=1")
else:
    print(f"   ⚠️  {len(mismatches)} completed users don't have CSV used=1")
    print(f"      Rows: {mismatches[:5]}")

# 4. Check Block 3 column mapping
print(f"\n📋 4. BLOCK 3 COLUMN MAPPING (t21 not t1):")
sample_user = users[users['complete'] == True].iloc[0] if len(complete_users) > 0 else None
if sample_user is not None and pd.notna(sample_user.get('csv_row_id')):
    csv_row_id = int(sample_user['csv_row_id'])
    csv_row = csv_df[csv_df['id'] == csv_row_id].iloc[0]
    
    b3t1 = pd.read_sql_query(f"""
        SELECT correct_classification, stimulus_seen
        FROM experiment_experimentaction
        WHERE user_id_id = {sample_user['user_id']}
        AND block_number = 3 AND trial_number = 1
    """, conn)
    
    if len(b3t1) > 0:
        actual_event = b3t1.iloc[0]['correct_classification']
        actual_stimulus = b3t1.iloc[0]['stimulus_seen']
        csv_event_21 = csv_row['event_t21']
        csv_h_21 = float(csv_row['h_t21']) + 6.5
        
        event_match = actual_event.lower() == (csv_event_21 if isinstance(csv_event_21, str) else ('signal' if csv_event_21 == 1 else 'noise')).lower()
        stim_match = abs(actual_stimulus - csv_h_21) < 0.01
        
        if event_match and stim_match:
            print(f"   ✅ Block 3 trial 1 uses column t21 (User {sample_user['user_id']})")
        else:
            print(f"   ❌ Block 3 mapping incorrect!")
    else:
        print(f"   ⚠️  No Block 3 data to verify")
else:
    print(f"   ⚠️  No complete users to verify")

# 5. Summary
print(f"\n" + "=" * 80)
print(f"📊 SUMMARY")
print(f"=" * 80)
print(f"Total users: {len(users)}")
print(f"Complete: {len(complete_users)}, Incomplete: {len(incomplete_users)}")
print(f"")
issues = []
if len(complete_users[complete_users['end_time'].isna()]) > 0:
    issues.append("❌ Some complete users missing end_time")
if len(incomplete_without_endtime) > 0:
    # Check if they're just in progress (started recently)
    recent_incomplete = []
    for _, u in incomplete_without_endtime.iterrows():
        start = pd.to_datetime(u['start_time'])
        now = pd.Timestamp.now()
        if (now - start).total_seconds() < 3600:  # Less than 1 hour
            recent_incomplete.append(u['user_id'])
    if len(recent_incomplete) < len(incomplete_without_endtime):
        issues.append(f"⚠️  {len(incomplete_without_endtime) - len(recent_incomplete)} old incomplete users without end_time")
if not all_correct:
    issues.append("❌ Some DS decisions are incorrect")
if len(mismatches) > 0:
    issues.append(f"⚠️  {len(mismatches)} CSV flag mismatches")

if len(issues) == 0:
    print("✅ ALL CHECKS PASSED - READY FOR PILOT")
else:
    print("⚠️  ISSUES FOUND:")
    for issue in issues:
        print(f"   {issue}")

conn.close()
print("=" * 80)
EOF

