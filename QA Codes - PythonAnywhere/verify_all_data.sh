#!/bin/bash
# Comprehensive data verification script
# Verifies: DS decisions, stimulus values, event types, CSV row matching, used flags
# Usage: bash verify_all_data.sh [user_id]  (if no user_id, checks all users)

USER_ID=${1:-""}

cd ~/ds-experiment-omri && python3 << EOF
import sqlite3
import pandas as pd
import numpy as np

conn = sqlite3.connect('db.sqlite3')

print("=" * 100)
print("🔍 COMPREHENSIVE DATA VERIFICATION")
print("=" * 100)

# Load CSV
csv_df = pd.read_csv('DATA/conditions_experiment_3ps_11x11_120_A.csv')
print(f"✅ CSV loaded: {len(csv_df)} rows")

# Show available column patterns
cols = csv_df.columns.tolist()
print(f"   Trial columns: s_t*, event_t*, h_t* (120 trials each)")

# The stimulus threshold is 6.5 - h_t values are centered around 0, stimulus_seen is centered around 6.5
STIMULUS_THRESHOLD = 6.5

# Get users
user_id = "$USER_ID"
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
        ORDER BY user_id
    """, conn)

print(f"📊 Checking {len(users)} users")

# Track issues
all_issues = []
summary = {
    'users_checked': 0,
    'users_ok': 0,
    'users_with_issues': 0,
    'total_trials': 0,
    'ds_correct': 0,
    'ds_wrong': 0,
    'stimulus_correct': 0,
    'stimulus_wrong': 0,
    'event_correct': 0,
    'event_wrong': 0,
    'csv_used_correct': 0,
    'csv_used_wrong': 0,
    'param_match': 0,
    'param_mismatch': 0
}

for _, u in users.iterrows():
    user_issues = []
    user_id = u['user_id']
    csv_row_id = u['csv_row_id']
    
    # Get CSV row
    csv_match = csv_df[csv_df['id'] == csv_row_id]
    if len(csv_match) == 0:
        user_issues.append(f"CSV row {csv_row_id} not found!")
        all_issues.append((user_id, user_issues))
        continue
    
    csv_row = csv_match.iloc[0]
    summary['users_checked'] += 1
    
    # Check parameter matching
    param_ok = True
    if float(u['ps']) != float(csv_row['ps']):
        user_issues.append(f"PS mismatch: DB={u['ps']}, CSV={csv_row['ps']}")
        param_ok = False
    if float(u['human_sensitivity']) != float(csv_row['dprime_h']):
        user_issues.append(f"d'_human mismatch: DB={u['human_sensitivity']}, CSV={csv_row['dprime_h']}")
        param_ok = False
    if float(u['ds_sensitivity']) != float(csv_row['dprime_s']):
        user_issues.append(f"d'_DS mismatch: DB={u['ds_sensitivity']}, CSV={csv_row['dprime_s']}")
        param_ok = False
    
    if param_ok:
        summary['param_match'] += 1
    else:
        summary['param_mismatch'] += 1
    
    # Check CSV used flag
    if u['complete']:
        if csv_row['used'] != 1:
            user_issues.append(f"CSV used flag wrong: complete=True but used={csv_row['used']}")
            summary['csv_used_wrong'] += 1
        else:
            summary['csv_used_correct'] += 1
    else:
        if csv_row['used'] == 1:
            user_issues.append(f"CSV used flag wrong: complete=False but used=1")
            summary['csv_used_wrong'] += 1
        else:
            summary['csv_used_correct'] += 1
    
    # Get actions
    actions = pd.read_sql_query(f"""
        SELECT block_number, trial_number, stimulus_seen, dss_judgment, 
               classification_decision, correct_classification
        FROM experiment_experimentaction
        WHERE user_id_id = {user_id}
        ORDER BY block_number, trial_number
    """, conn)
    
    if len(actions) == 0:
        if len(user_issues) > 0:
            all_issues.append((user_id, user_issues))
        continue
    
    summary['total_trials'] += len(actions)
    
    # Verify each trial
    trial_issues = []
    for _, a in actions.iterrows():
        block = int(a['block_number'])
        trial = int(a['trial_number'])
        
        # Calculate CSV trial index (1-10 for B1, 11-20 for B2, 21-120 for B3)
        if block == 1:
            csv_trial = trial
        elif block == 2:
            csv_trial = trial + 10
        else:  # block 3
            csv_trial = trial + 20
        
        # Get expected values from CSV
        csv_s_t = csv_row[f's_t{csv_trial:02d}']  # transformed stimulus (for DS decision)
        csv_h_t = csv_row[f'h_t{csv_trial:02d}']  # stimulus value (centered around 0)
        csv_event = csv_row[f'event_t{csv_trial:02d}']  # event (could be 0/1 or string)
        
        # === DS DECISION CHECK ===
        # DS decides signal if s_t > 0
        expected_ds = 'signal' if csv_s_t > 0 else 'noise'
        actual_ds = a['dss_judgment']
        
        if actual_ds == expected_ds:
            summary['ds_correct'] += 1
        else:
            summary['ds_wrong'] += 1
            trial_issues.append(f"B{block}T{trial}: DS wrong! s_t={csv_s_t:.2f}, expected={expected_ds}, got={actual_ds}")
        
        # === STIMULUS CHECK ===
        # h_t is centered around 0, stimulus_seen is centered around 6.5
        # So stimulus_seen should equal h_t + 6.5
        expected_stimulus = csv_h_t + STIMULUS_THRESHOLD
        actual_stimulus = a['stimulus_seen']
        
        if abs(actual_stimulus - expected_stimulus) < 0.01:
            summary['stimulus_correct'] += 1
        else:
            summary['stimulus_wrong'] += 1
            trial_issues.append(f"B{block}T{trial}: Stimulus mismatch! h_t={csv_h_t:.2f}, expected={expected_stimulus:.2f}, got={actual_stimulus:.2f}")
        
        # === EVENT/CORRECT ANSWER CHECK ===
        # Handle both integer (0/1) and string ('signal'/'noise') formats
        if isinstance(csv_event, str):
            expected_event = csv_event.lower()
        else:
            expected_event = 'signal' if csv_event == 1 else 'noise'
        actual_event = a['correct_classification']
        
        if actual_event == expected_event:
            summary['event_correct'] += 1
        else:
            summary['event_wrong'] += 1
            trial_issues.append(f"B{block}T{trial}: Event wrong! expected={expected_event}, got={actual_event}")
    
    # Only show first 5 trial issues per user
    if trial_issues:
        user_issues.extend(trial_issues[:5])
        if len(trial_issues) > 5:
            user_issues.append(f"... and {len(trial_issues) - 5} more trial issues")
    
    if user_issues:
        summary['users_with_issues'] += 1
        all_issues.append((user_id, user_issues))
    else:
        summary['users_ok'] += 1

# Print results
print("\n" + "=" * 100)
print("📊 VERIFICATION SUMMARY")
print("=" * 100)

print(f"\n👥 USERS:")
print(f"   Checked:      {summary['users_checked']}")
print(f"   All OK:       {summary['users_ok']} ✅")
print(f"   With issues:  {summary['users_with_issues']} {'❌' if summary['users_with_issues'] > 0 else ''}")

print(f"\n📋 PARAMETERS (ps, d'_human, d'_DS):")
print(f"   Match:        {summary['param_match']} ✅")
print(f"   Mismatch:     {summary['param_mismatch']} {'❌' if summary['param_mismatch'] > 0 else ''}")

print(f"\n🎯 DS DECISIONS (s_t > 0 → signal):")
print(f"   Correct:      {summary['ds_correct']} ✅")
print(f"   Wrong:        {summary['ds_wrong']} {'❌' if summary['ds_wrong'] > 0 else ''}")

print(f"\n📈 STIMULUS VALUES (h_t + 6.5 = stimulus_seen):")
print(f"   Correct:      {summary['stimulus_correct']} ✅")
print(f"   Mismatch:     {summary['stimulus_wrong']} {'❌' if summary['stimulus_wrong'] > 0 else ''}")

print(f"\n🎪 EVENT/CORRECT ANSWER (event_t from CSV):")
print(f"   Correct:      {summary['event_correct']} ✅")
print(f"   Wrong:        {summary['event_wrong']} {'❌' if summary['event_wrong'] > 0 else ''}")

print(f"\n📁 CSV 'used' FLAG:")
print(f"   Correct:      {summary['csv_used_correct']} ✅")
print(f"   Wrong:        {summary['csv_used_wrong']} {'❌' if summary['csv_used_wrong'] > 0 else ''}")

# Print issues
if all_issues:
    print("\n" + "=" * 100)
    print("⚠️  ISSUES FOUND:")
    print("=" * 100)
    for user_id, issues in all_issues:
        print(f"\n   User {user_id}:")
        for issue in issues:
            print(f"      - {issue}")
else:
    print("\n" + "=" * 100)
    print("✅ ALL VERIFICATIONS PASSED!")
    print("=" * 100)

# Final verdict
print("\n" + "=" * 100)
if summary['ds_wrong'] == 0 and summary['stimulus_wrong'] == 0 and summary['event_wrong'] == 0 and summary['param_mismatch'] == 0:
    print("🎉 DATA INTEGRITY: VERIFIED ✅")
else:
    print("⚠️  DATA INTEGRITY: ISSUES FOUND ❌")
print("=" * 100)

conn.close()
EOF
