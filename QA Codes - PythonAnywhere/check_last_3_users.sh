#!/bin/bash
# Comprehensive check for last 3 users

cd ~/ds-experiment-omri && source venv/bin/activate && python3 << 'PYEOF'
import sqlite3
import pandas as pd
import os
import numpy as np

# Connect to database
db_path = 'data/old_data_0912/db_old.sqlite3' if os.path.exists('data/old_data_0912/db_old.sqlite3') else 'db.sqlite3'
conn = sqlite3.connect(db_path)

# Get last 3 users with csv_row_id
print("=" * 70)
print("COMPREHENSIVE CHECK: LAST 3 USERS")
print("=" * 70)

users_df = pd.read_sql_query("""
    SELECT user_id, aid, csv_row_id, ps, human_sensitivity, ds_sensitivity, 
           start_time, complete, end_time
    FROM experiment_experimentdata
    WHERE csv_row_id IS NOT NULL
    ORDER BY user_id DESC
    LIMIT 3
""", conn)

if len(users_df) == 0:
    print("❌ No users with csv_row_id found")
    exit()

print(f"\nFound {len(users_df)} users to check\n")

# Load conditions CSV
conditions_file = 'data/conditions_experiment_3ps_11x11_120_A.csv'
conditions_df = pd.read_csv(conditions_file)
STIMULI_SCALAR = 6.5

# Check each user
for idx, user_row in users_df.iterrows():
    user_id = int(user_row['user_id'])
    csv_row_id = int(user_row['csv_row_id'])
    aid = user_row['aid']
    
    print("=" * 70)
    print(f"USER {user_id}")
    print("=" * 70)
    
    # Get CSV row
    csv_row = conditions_df[conditions_df['id'] == csv_row_id].iloc[0]
    
    # Get user's actions
    actions_df = pd.read_sql_query("""
        SELECT block_number, trial_number, correct_classification, 
               stimulus_seen, dss_judgment, classification_decision
        FROM experiment_experimentaction
        WHERE user_id_id = ?
        ORDER BY block_number, trial_number
    """, conn, params=(user_id,))
    
    print(f"\n📋 Basic Info:")
    print(f"   User ID: {user_id}")
    print(f"   AID: {aid}")
    print(f"   CSV Row ID: {csv_row_id}")
    print(f"   Complete: {user_row['complete']}")
    print(f"   Start Time: {user_row['start_time']}")
    print(f"   End Time: {user_row['end_time'] if user_row['end_time'] else 'N/A'}")
    print(f"   Total Actions: {len(actions_df)}")
    
    print(f"\n📋 CSV Row Info:")
    print(f"   ps: {csv_row['ps']}")
    print(f"   dprime_h: {csv_row['dprime_h']}")
    print(f"   dprime_s: {csv_row['dprime_s']}")
    print(f"   used: {csv_row['used']}")
    print(f"   isDemo: {csv_row.get('isDemo', 'NOT SET')}")
    
    # Check ps and dprimes match
    print(f"\n🔍 Database vs CSV Comparison:")
    ps_match = "✅" if float(user_row['ps']) == float(csv_row['ps']) else "❌"
    dprime_h_match = "✅" if float(user_row['human_sensitivity']) == float(csv_row['dprime_h']) else "❌"
    dprime_s_match = "✅" if float(user_row['ds_sensitivity']) == float(csv_row['dprime_s']) else "❌"
    
    print(f"   ps: DB={user_row['ps']}, CSV={csv_row['ps']} {ps_match}")
    print(f"   dprime_h: DB={user_row['human_sensitivity']}, CSV={csv_row['dprime_h']} {dprime_h_match}")
    print(f"   dprime_s: DB={user_row['ds_sensitivity']}, CSV={csv_row['dprime_s']} {dprime_s_match}")
    
    # Check used and isDemo status
    print(f"\n🔍 CSV Row Status:")
    if user_row['complete']:
        used_ok = "✅" if csv_row['used'] == 1 else "❌"
        print(f"   used: {csv_row['used']} {used_ok} (should be 1 when complete)")
        
        # Check isDemo logic
        expected_is_demo = 1 if (aid == 'test' or str(aid).startswith('test_') or str(aid).startswith('local_')) else 0
        actual_is_demo = csv_row.get('isDemo')
        if pd.isna(actual_is_demo):
            is_demo_ok = "❌ NOT SET"
        else:
            is_demo_ok = "✅" if actual_is_demo == expected_is_demo else f"❌ (expected {expected_is_demo}, got {actual_is_demo})"
        print(f"   isDemo: {actual_is_demo} {is_demo_ok} (expected {expected_is_demo} for aid='{aid}')")
    else:
        print(f"   used: {csv_row['used']} (should be 0 if not complete)")
        print(f"   isDemo: {csv_row.get('isDemo', 'NOT SET')} (will be set when user completes)")
    
    # Check Block 1 (trials 1-10, CSV columns 1-10)
    print(f"\n📋 BLOCK 1 Verification (trials 1-10 vs CSV columns 1-10):")
    block1 = actions_df[actions_df['block_number'] == 1]
    if len(block1) > 0:
        matches = 0
        for idx_action, action in block1.iterrows():
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
            
            if csv_event == user_event and abs(csv_stim - user_stim) < 0.01 and csv_ds == user_ds:
                matches += 1
        
        match_rate = matches / len(block1) * 100
        match_ok = "✅" if matches == len(block1) else f"⚠️ {matches}/{len(block1)}"
        print(f"   Matches: {match_ok} ({match_rate:.1f}%)")
    else:
        print(f"   ⚠️  No Block 1 actions")
    
    # Check Block 2 (trials 11-20, CSV columns 11-20)
    print(f"\n📋 BLOCK 2 Verification (trials 1-10 vs CSV columns 11-20):")
    block2 = actions_df[actions_df['block_number'] == 2]
    if len(block2) > 0:
        matches = 0
        for idx_action, action in block2.iterrows():
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
            
            if csv_event == user_event and abs(csv_stim - user_stim) < 0.01 and csv_ds == user_ds:
                matches += 1
        
        match_rate = matches / len(block2) * 100
        match_ok = "✅" if matches == len(block2) else f"⚠️ {matches}/{len(block2)}"
        print(f"   Matches: {match_ok} ({match_rate:.1f}%)")
    else:
        print(f"   ⚠️  No Block 2 actions")
    
    # Check Block 3 (trials 1-100, CSV columns 21-120) - IMPORTANT!
    print(f"\n📋 BLOCK 3 Verification (trials 1-100 vs CSV columns 21-120 - FIXED!):")
    block3 = actions_df[actions_df['block_number'] == 3]
    if len(block3) > 0:
        matches = 0
        sample_mismatches = []
        for idx_action, action in block3.head(20).iterrows():  # Check first 20
            trial_num = int(action['trial_number'])
            csv_trial = trial_num + 20  # Block 3 trial 1 = CSV column 21
            csv_col = f'event_t{str(csv_trial).zfill(2)}'
            csv_h_col = f'h_t{str(csv_trial).zfill(2)}'
            csv_ds_col = f'ds_dec_t{str(csv_trial).zfill(2)}'
            
            csv_event = csv_row[csv_col]
            csv_stim = float(csv_row[csv_h_col]) + STIMULI_SCALAR
            csv_ds = 'signal' if int(csv_row[csv_ds_col]) == 1 else 'noise'
            
            user_event = action['correct_classification']
            user_stim = action['stimulus_seen']
            user_ds = action['dss_judgment']
            
            if csv_event == user_event and abs(csv_stim - user_stim) < 0.01 and csv_ds == user_ds:
                matches += 1
            elif len(sample_mismatches) < 3:
                sample_mismatches.append(f"Trial {trial_num}: Event {'✅' if csv_event == user_event else '❌'}, Stim {'✅' if abs(csv_stim - user_stim) < 0.01 else '❌'}, DS {'✅' if csv_ds == user_ds else '❌'}")
        
        match_rate = matches / min(20, len(block3)) * 100
        match_ok = "✅" if matches == min(20, len(block3)) else f"⚠️ {matches}/{min(20, len(block3))}"
        print(f"   Matches (first 20): {match_ok} ({match_rate:.1f}%)")
        if sample_mismatches:
            print(f"   Sample mismatches:")
            for mm in sample_mismatches:
                print(f"      {mm}")
        print(f"   Total Block 3 actions: {len(block3)}")
    else:
        print(f"   ⚏️  No Block 3 actions yet")
    
    # Summary for this user
    print(f"\n📊 Summary for User {user_id}:")
    all_ok = (
        float(user_row['ps']) == float(csv_row['ps']) and
        float(user_row['human_sensitivity']) == float(csv_row['dprime_h']) and
        float(user_row['ds_sensitivity']) == float(csv_row['dprime_s'])
    )
    if user_row['complete']:
        all_ok = all_ok and csv_row['used'] == 1
    status = "✅ ALL CHECKS PASSED" if all_ok else "⚠️  SOME ISSUES FOUND"
    print(f"   {status}")
    print()

conn.close()

print("=" * 70)
print("✅ ALL USERS CHECKED")
print("=" * 70)

PYEOF

