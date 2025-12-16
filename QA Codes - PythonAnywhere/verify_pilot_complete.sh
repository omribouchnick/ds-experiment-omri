#!/bin/bash
# COMPREHENSIVE PILOT COMPLETION VERIFICATION
# Run this before concluding the pilot to ensure all data is valid
# Usage: bash verify_pilot_complete.sh

cd ~/ds-experiment-omri && python3 << 'EOF'
import sqlite3
import pandas as pd
import numpy as np

conn = sqlite3.connect('db.sqlite3')

print("=" * 100)
print("🔍 COMPREHENSIVE PILOT COMPLETION VERIFICATION")
print("=" * 100)

# Load CSV
csv_df = pd.read_csv('DATA/conditions_experiment_3ps_11x11_120_A.csv')

# Get all users
users = pd.read_sql_query("""
    SELECT user_id, aid, csv_row_id, ps, human_sensitivity, ds_sensitivity, 
           complete, start_time, end_time
    FROM experiment_experimentdata
    ORDER BY user_id
""", conn)

print(f"📊 Total users: {len(users)}")
print(f"📊 Complete users: {users['complete'].sum()}")

STIMULUS_THRESHOLD = 6.5
all_checks_passed = True
issues = []

# ============================================================================
# CHECK 1: Data Integrity (already verified, quick recheck)
# ============================================================================
print("\n" + "=" * 100)
print("✅ CHECK 1: DATA INTEGRITY")
print("=" * 100)

ds_wrong = 0
stim_wrong = 0
event_wrong = 0

for _, u in users.iterrows():
    if u['csv_row_id'] is None:
        continue
    csv_match = csv_df[csv_df['id'] == u['csv_row_id']]
    if len(csv_match) == 0:
        continue
    csv_row = csv_match.iloc[0]
    
    actions = pd.read_sql_query(f"""
        SELECT block_number, trial_number, stimulus_seen, dss_judgment, correct_classification
        FROM experiment_experimentaction
        WHERE user_id_id = {u['user_id']}
    """, conn)
    
    for _, a in actions.iterrows():
        block = int(a['block_number'])
        trial = int(a['trial_number'])
        csv_trial = trial if block == 1 else (trial + 10 if block == 2 else trial + 20)
        
        csv_s_t = csv_row[f's_t{csv_trial:02d}']
        csv_h_t = csv_row[f'h_t{csv_trial:02d}']
        csv_event = csv_row[f'event_t{csv_trial:02d}']
        
        expected_ds = 'signal' if csv_s_t > 0 else 'noise'
        expected_stim = csv_h_t + STIMULUS_THRESHOLD
        expected_event = 'signal' if (isinstance(csv_event, str) and csv_event == 'signal') or csv_event == 1 else 'noise'
        
        if a['dss_judgment'] != expected_ds:
            ds_wrong += 1
        if abs(a['stimulus_seen'] - expected_stim) > 0.01:
            stim_wrong += 1
        if a['correct_classification'] != expected_event:
            event_wrong += 1

if ds_wrong == 0 and stim_wrong == 0 and event_wrong == 0:
    print("   DS decisions: ✅ All correct")
    print("   Stimulus values: ✅ All correct")
    print("   Event/correct answer: ✅ All correct")
else:
    print(f"   DS decisions: {'✅' if ds_wrong == 0 else '❌'} {ds_wrong} errors")
    print(f"   Stimulus values: {'✅' if stim_wrong == 0 else '❌'} {stim_wrong} errors")
    print(f"   Event/correct answer: {'✅' if event_wrong == 0 else '❌'} {event_wrong} errors")
    all_checks_passed = False
    issues.append(f"Data integrity issues: DS={ds_wrong}, Stim={stim_wrong}, Event={event_wrong}")

# ============================================================================
# CHECK 2: Complete users have TOAST
# ============================================================================
print("\n" + "=" * 100)
print("✅ CHECK 2: TOAST QUESTIONNAIRE")
print("=" * 100)

complete_users = users[users['complete'] == True]
toast_missing = []

for _, u in complete_users.iterrows():
    toast = pd.read_sql_query(f"""
        SELECT COUNT(*) as cnt FROM experiment_toastresponse WHERE user_id_id = {u['user_id']}
    """, conn)
    if toast.iloc[0]['cnt'] == 0:
        toast_missing.append(u['user_id'])

if len(toast_missing) == 0:
    print(f"   All {len(complete_users)} complete users have TOAST: ✅")
else:
    print(f"   Missing TOAST for users: {toast_missing} ❌")
    all_checks_passed = False
    issues.append(f"Missing TOAST for users: {toast_missing}")

# ============================================================================
# CHECK 3: Trial counts (10 + 10 + 100 = 120)
# ============================================================================
print("\n" + "=" * 100)
print("✅ CHECK 3: TRIAL COUNTS")
print("=" * 100)

trial_issues = []
for _, u in complete_users.iterrows():
    actions = pd.read_sql_query(f"""
        SELECT block_number, COUNT(*) as cnt
        FROM experiment_experimentaction
        WHERE user_id_id = {u['user_id']}
        GROUP BY block_number
    """, conn)
    
    block_counts = {int(r['block_number']): int(r['cnt']) for _, r in actions.iterrows()}
    expected = {1: 10, 2: 10, 3: 100}
    
    for block, expected_cnt in expected.items():
        actual_cnt = block_counts.get(block, 0)
        if actual_cnt != expected_cnt:
            trial_issues.append(f"User {u['user_id']}: Block {block} has {actual_cnt} trials (expected {expected_cnt})")

if len(trial_issues) == 0:
    print(f"   All complete users have correct trial counts (10+10+100): ✅")
else:
    print(f"   Trial count issues: ❌")
    for issue in trial_issues[:5]:
        print(f"      - {issue}")
    if len(trial_issues) > 5:
        print(f"      ... and {len(trial_issues) - 5} more")
    all_checks_passed = False
    issues.append(f"{len(trial_issues)} trial count issues")

# ============================================================================
# CHECK 4: Duplicate AIDs (CloudResearch users should be unique)
# ============================================================================
print("\n" + "=" * 100)
print("✅ CHECK 4: DUPLICATE AIDS")
print("=" * 100)

# Exclude test/demo AIDs
real_users = users[~users['aid'].isin(['test', 'testWorker', 'test123', 'pilot_test1']) & ~users['aid'].str.startswith('local_', na=False)]
aid_counts = real_users['aid'].value_counts()
duplicates = aid_counts[aid_counts > 1]

if len(duplicates) == 0:
    print(f"   No duplicate AIDs among {len(real_users)} real users: ✅")
else:
    print(f"   Duplicate AIDs found: ❌")
    for aid, count in duplicates.items():
        print(f"      - '{aid}' appears {count} times")
    all_checks_passed = False
    issues.append(f"Duplicate AIDs: {list(duplicates.index)}")

# ============================================================================
# CHECK 5: CSV used flag consistency
# ============================================================================
print("\n" + "=" * 100)
print("✅ CHECK 5: CSV 'used' FLAG")
print("=" * 100)

used_issues = []
for _, u in users.iterrows():
    if u['csv_row_id'] is None:
        continue
    csv_match = csv_df[csv_df['id'] == u['csv_row_id']]
    if len(csv_match) == 0:
        continue
    csv_row = csv_match.iloc[0]
    
    if u['complete'] and csv_row['used'] != 1:
        used_issues.append(f"User {u['user_id']}: complete=True but used={csv_row['used']}")
    elif not u['complete'] and csv_row['used'] == 1:
        used_issues.append(f"User {u['user_id']}: complete=False but used=1")

if len(used_issues) == 0:
    print(f"   CSV 'used' flags are consistent: ✅")
else:
    print(f"   CSV 'used' flag issues: ❌")
    for issue in used_issues:
        print(f"      - {issue}")
    all_checks_passed = False
    issues.append(f"{len(used_issues)} CSV used flag issues")

# ============================================================================
# CHECK 6: isDemo flag for test users
# ============================================================================
print("\n" + "=" * 100)
print("✅ CHECK 6: isDemo FLAG")
print("=" * 100)

demo_issues = []
for _, u in complete_users.iterrows():
    if u['csv_row_id'] is None:
        continue
    csv_match = csv_df[csv_df['id'] == u['csv_row_id']]
    if len(csv_match) == 0:
        continue
    csv_row = csv_match.iloc[0]
    
    is_test = u['aid'] == 'test' or str(u['aid']).startswith('local_')
    expected_demo = 1 if is_test else 0
    actual_demo = csv_row.get('isDemo', None)
    
    if pd.isna(actual_demo):
        demo_issues.append(f"User {u['user_id']}: isDemo not set (aid='{u['aid']}')")
    elif int(actual_demo) != expected_demo:
        demo_issues.append(f"User {u['user_id']}: isDemo={int(actual_demo)}, expected={expected_demo} (aid='{u['aid']}')")

if len(demo_issues) == 0:
    print(f"   isDemo flags are correct: ✅")
else:
    print(f"   isDemo flag issues: ❌")
    for issue in demo_issues:
        print(f"      - {issue}")
    # Don't fail for this - just a warning
    print(f"   ⚠️  This is a warning, not a failure")

# ============================================================================
# CHECK 7: Reaction times (sanity check)
# ============================================================================
print("\n" + "=" * 100)
print("✅ CHECK 7: REACTION TIMES")
print("=" * 100)

all_actions = pd.read_sql_query("""
    SELECT user_id_id, block_number, trial_number, decision_time
    FROM experiment_experimentaction
""", conn)

if len(all_actions) > 0:
    avg_rt = all_actions['decision_time'].mean()
    min_rt = all_actions['decision_time'].min()
    max_rt = all_actions['decision_time'].max()
    
    # Check for suspiciously fast responses (< 0.2 seconds)
    fast_responses = all_actions[all_actions['decision_time'] < 0.2]
    # Check for suspiciously slow responses (> 60 seconds)
    slow_responses = all_actions[all_actions['decision_time'] > 60]
    
    print(f"   Average RT: {avg_rt:.2f}s, Min: {min_rt:.2f}s, Max: {max_rt:.2f}s")
    print(f"   Very fast responses (<0.2s): {len(fast_responses)} ({100*len(fast_responses)/len(all_actions):.1f}%)")
    print(f"   Very slow responses (>60s): {len(slow_responses)} ({100*len(slow_responses)/len(all_actions):.1f}%)")
    
    if len(fast_responses) > len(all_actions) * 0.1:  # More than 10% suspiciously fast
        print(f"   ⚠️  Warning: High proportion of very fast responses")
    else:
        print(f"   RT distribution looks reasonable: ✅")

# ============================================================================
# CHECK 8: Duplicate CSV rows
# ============================================================================
print("\n" + "=" * 100)
print("✅ CHECK 8: DUPLICATE CSV ROWS")
print("=" * 100)

csv_row_counts = users['csv_row_id'].value_counts()
csv_duplicates = csv_row_counts[csv_row_counts > 1]

if len(csv_duplicates) == 0:
    print(f"   No duplicate CSV row assignments: ✅")
else:
    print(f"   Duplicate CSV rows found: ❌")
    for row_id, count in csv_duplicates.items():
        dup_users = users[users['csv_row_id'] == row_id]['user_id'].tolist()
        print(f"      - Row {row_id} used by users: {dup_users}")
    all_checks_passed = False
    issues.append(f"Duplicate CSV rows: {list(csv_duplicates.index)}")

# ============================================================================
# CHECK 9: Block 3 column mapping (21-120)
# ============================================================================
print("\n" + "=" * 100)
print("✅ CHECK 9: BLOCK 3 COLUMN MAPPING")
print("=" * 100)

b3_issues = []
for _, u in complete_users.iterrows():
    if u['csv_row_id'] is None:
        continue
    csv_match = csv_df[csv_df['id'] == u['csv_row_id']]
    if len(csv_match) == 0:
        continue
    csv_row = csv_match.iloc[0]
    
    actions = pd.read_sql_query(f"""
        SELECT block_number, trial_number, stimulus_seen
        FROM experiment_experimentaction
        WHERE user_id_id = {u['user_id']} AND block_number = 3
        ORDER BY trial_number
        LIMIT 3
    """, conn)
    
    for _, a in actions.iterrows():
        trial = int(a['trial_number'])
        csv_trial = trial + 20  # Block 3 uses columns 21-120
        csv_h_t = csv_row[f'h_t{csv_trial:02d}']
        expected_stim = csv_h_t + STIMULUS_THRESHOLD
        
        if abs(a['stimulus_seen'] - expected_stim) > 0.01:
            b3_issues.append(f"User {u['user_id']} B3T{trial}: expected {expected_stim:.2f}, got {a['stimulus_seen']:.2f}")
            break  # One issue per user is enough

if len(b3_issues) == 0:
    print(f"   Block 3 uses columns 21-120 correctly: ✅")
else:
    print(f"   Block 3 column mapping issues: ❌")
    for issue in b3_issues[:5]:
        print(f"      - {issue}")
    all_checks_passed = False
    issues.append("Block 3 column mapping issues")

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "=" * 100)
print("📊 PILOT VERIFICATION SUMMARY")
print("=" * 100)

print(f"\n   Total users: {len(users)}")
print(f"   Complete users: {users['complete'].sum()}")
print(f"   Demo/test users: {len(users) - len(real_users)}")
print(f"   Real users: {len(real_users)}")
print(f"   Real complete users: {len(real_users[real_users['complete'] == True])}")

print("\n" + "=" * 100)
if all_checks_passed:
    print("🎉 ALL CHECKS PASSED - PILOT DATA IS VALID! ✅")
else:
    print("⚠️  ISSUES FOUND:")
    for issue in issues:
        print(f"   - {issue}")
print("=" * 100)

conn.close()
EOF





