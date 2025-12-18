#!/bin/bash
# FINAL PILOT VERIFICATION - Complete analysis before finishing pilot
# Shows: Users-CSV mapping, used flags, DS decisions, summary chart
# Usage: bash verify_pilot_final.sh

cd ~/ds-experiment-omri/Experiment_Code && python3 << 'EOF'
import sqlite3
import pandas as pd
from datetime import datetime

conn = sqlite3.connect('DATA/db.sqlite3')
csv_df = pd.read_csv('DATA/conditions_experiment_3ps_11x11_120_A.csv')

print("=" * 120)
print("🔍 FINAL PILOT VERIFICATION - COMPLETE ANALYSIS")
print("=" * 120)

# ============================================================================
# 1. USERS - CSV ROW MAPPING
# ============================================================================
print("\n" + "=" * 120)
print("📊 1. USERS - CSV ROW MAPPING")
print("=" * 120)

users = pd.read_sql_query("""
    SELECT user_id, aid, csv_row_id, ps, human_sensitivity, ds_sensitivity, 
           complete, start_time, end_time
    FROM experiment_experimentdata
    ORDER BY user_id
""", conn)

print(f"\nTotal users: {len(users)}")
print(f"Complete: {users['complete'].sum()} ✅ | Incomplete: {(~users['complete']).sum()} ❌")

# Show mapping table
d_h_label = "d'_h"
d_ds_label = "d'_DS"
print(f"\n{'User ID':<10} {'AID':<40} {'CSV Row':<10} {'PS':<6} {d_h_label:<6} {d_ds_label:<7} {'Status':<12} {'Used Flag':<12}")
print("-" * 120)

csv_row_users = {}  # Track which CSV rows are used by which users
for idx, u in users.iterrows():
    csv_row_id = u['csv_row_id']
    if csv_row_id is not None:
        if csv_row_id not in csv_row_users:
            csv_row_users[csv_row_id] = []
        csv_row_users[csv_row_id].append(int(u['user_id']))
    
    status = "✅ COMPLETE" if u['complete'] else "❌ INCOMPLETE"
    aid_short = u['aid'][:38] + ".." if len(u['aid']) > 40 else u['aid']
    d_h_val = f"{u['human_sensitivity']:.1f}"
    d_ds_val = f"{u['ds_sensitivity']:.1f}"
    print(f"{u['user_id']:<10} {aid_short:<40} {csv_row_id if csv_row_id else 'N/A':<10} {u['ps']:<6} {d_h_val:<6} {d_ds_val:<7} {status:<12} ", end="")
    
    # Get CSV used flag
    if csv_row_id is not None:
        csv_row = csv_df[csv_df['id'] == csv_row_id]
        if len(csv_row) > 0:
            used_val = csv_row.iloc[0]['used']
            used_status = f"{used_val} ({'Available' if used_val == 0 else 'In-progress' if used_val == 0.5 else 'Completed'})"
            print(used_status)
        else:
            print("CSV row not found")
    else:
        print("No CSV row")

# Check for duplicate CSV rows
print(f"\n{'='*120}")
print("🔍 CSV ROW DUPLICATION CHECK")
print("=" * 120)
duplicates = {row_id: user_list for row_id, user_list in csv_row_users.items() if len(user_list) > 1}
if duplicates:
    print(f"⚠️  Found {len(duplicates)} CSV rows used by multiple users:")
    for row_id, user_list in duplicates.items():
        csv_row = csv_df[csv_df['id'] == row_id].iloc[0]
        incomplete_count = sum(1 for uid in user_list if not users[users['user_id']==uid]['complete'].iloc[0])
        print(f"   Row {row_id}: Users {user_list} | Used flag: {csv_row['used']} | Incomplete: {incomplete_count}/{len(user_list)}")
else:
    print("✅ No duplicate CSV rows (all users have unique rows)")

# ============================================================================
# 2. CSV USED FLAGS STATUS
# ============================================================================
print(f"\n{'='*120}")
print("📊 2. CSV USED FLAGS STATUS")
print("=" * 120)

used_0 = len(csv_df[csv_df['used'] == 0])
used_05 = len(csv_df[csv_df['used'] == 0.5])
used_1 = len(csv_df[csv_df['used'] == 1])

print(f"\nTotal CSV rows: {len(csv_df)}")
print(f"Used = 0 (Available):     {used_0:>4} rows ({100*used_0/len(csv_df):.1f}%)")
print(f"Used = 0.5 (In-progress):  {used_05:>4} rows ({100*used_05/len(csv_df):.1f}%)")
print(f"Used = 1 (Completed):      {used_1:>4} rows ({100*used_1/len(csv_df):.1f}%)")

# Show in-progress rows
if used_05 > 0:
    print(f"\n⚠️  In-progress rows (used=0.5):")
    in_progress = csv_df[csv_df['used'] == 0.5]
    for _, row in in_progress.iterrows():
        # Find which user(s) are using this row
        using_users = [int(u['user_id']) for idx, u in users.iterrows() if u['csv_row_id'] == row['id']]
        user_str = ", ".join([str(uid) for uid in using_users]) if using_users else "Unknown"
        print(f"   Row {int(row['id'])}: User(s) {user_str}")

# ============================================================================
# 3. DS DECISION VERIFICATION
# ============================================================================
print(f"\n{'='*120}")
print("🔍 3. DS DECISION VERIFICATION")
print("=" * 120)

STIMULUS_SCALAR = 6.5
ds_errors = []
stim_errors = []
event_errors = []

for _, u in users.iterrows():
    if u['csv_row_id'] is None:
        continue
    
    csv_row = csv_df[csv_df['id'] == u['csv_row_id']].iloc[0]
    actions = pd.read_sql_query(f"""
        SELECT block_number, trial_number, stimulus_seen, dss_judgment, 
               classification_decision, correct_classification
        FROM experiment_experimentaction
        WHERE user_id_id = {u['user_id']}
        ORDER BY block_number, trial_number
    """, conn)
    
    if len(actions) == 0:
        continue
    
    for _, a in actions.iterrows():
        block = int(a['block_number'])
        trial = int(a['trial_number'])
        csv_trial = trial if block == 1 else (trial + 10 if block == 2 else trial + 20)
        
        # DS decision check
        csv_s_t = csv_row[f's_t{csv_trial:02d}']
        expected_ds = 'signal' if csv_s_t > 0 else 'noise'
        if a['dss_judgment'] != expected_ds:
            ds_errors.append(f"User {u['user_id']} B{block}T{trial}: s_t={csv_s_t:.2f}, expected={expected_ds}, got={a['dss_judgment']}")
        
        # Stimulus check
        csv_h_t = csv_row[f'h_t{csv_trial:02d}']
        expected_stim = csv_h_t + STIMULUS_SCALAR
        if abs(a['stimulus_seen'] - expected_stim) > 0.01:
            stim_errors.append(f"User {u['user_id']} B{block}T{trial}: h_t={csv_h_t:.2f}, expected={expected_stim:.2f}, got={a['stimulus_seen']:.2f}")
        
        # Event check
        csv_event = csv_row[f'event_t{csv_trial:02d}']
        expected_event = 'signal' if (isinstance(csv_event, str) and csv_event == 'signal') or csv_event == 1 else 'noise'
        if a['correct_classification'] != expected_event:
            event_errors.append(f"User {u['user_id']} B{block}T{trial}: expected={expected_event}, got={a['correct_classification']}")

total_trials = pd.read_sql_query("SELECT COUNT(*) as c FROM experiment_experimentaction", conn).iloc[0]['c']

print(f"\nTotal trials checked: {total_trials}")
print(f"DS decisions:   {'✅ All correct' if len(ds_errors) == 0 else f'❌ {len(ds_errors)} errors'}")
print(f"Stimulus values: {'✅ All correct' if len(stim_errors) == 0 else f'❌ {len(stim_errors)} errors'}")
print(f"Event types:    {'✅ All correct' if len(event_errors) == 0 else f'❌ {len(event_errors)} errors'}")

if ds_errors:
    print(f"\n⚠️  First 5 DS errors:")
    for err in ds_errors[:5]:
        print(f"   {err}")

# ============================================================================
# 4. SUMMARY CHART
# ============================================================================
print(f"\n{'='*120}")
print("📊 4. SUMMARY CHART - ALL USERS PERFORMANCE")
print("=" * 120)

results = []
for _, u in users.iterrows():
    actions = pd.read_sql_query(f"""
        SELECT block_number, trial_number, classification_decision, 
               dss_judgment, correct_classification, decision_time
        FROM experiment_experimentaction
        WHERE user_id_id = {u['user_id']}
    """, conn)
    
    if len(actions) == 0:
        results.append({
            'ID': u['user_id'],
            'AID': u['aid'][:20] + ".." if len(u['aid']) > 22 else u['aid'],
            'CSV': u['csv_row_id'],
            'PS': u['ps'],
            'Trials': 0,
            'Acc%': 0,
            'DS Ag%': 0,
            'Complete': '❌'
        })
        continue
    
    correct = (actions['classification_decision'] == actions['correct_classification']).sum()
    agreed = (actions['classification_decision'] == actions['dss_judgment']).sum()
    total_time = actions['decision_time'].sum() / 60  # minutes
    
    results.append({
        'ID': u['user_id'],
        'AID': u['aid'][:20] + ".." if len(u['aid']) > 22 else u['aid'],
        'CSV': u['csv_row_id'],
        'PS': u['ps'],
        'Trials': len(actions),
        'Acc%': f"{100*correct/len(actions):.1f}",
        'DS Ag%': f"{100*agreed/len(actions):.1f}",
        'Time(m)': f"{total_time:.1f}",
        'Complete': '✅' if u['complete'] else '❌'
    })

results_df = pd.DataFrame(results)
print(f"\n{'ID':<5} {'AID':<25} {'CSV':<6} {'PS':<5} {'Trials':<8} {'Acc%':<7} {'DS Ag%':<8} {'Time(m)':<9} {'Status'}")
print("-" * 120)
for _, r in results_df.iterrows():
    print(f"{r['ID']:<5} {r['AID']:<25} {r['CSV'] if r['CSV'] else 'N/A':<6} {r['PS']:<5} {r['Trials']:<8} {r['Acc%']:<7} {r['DS Ag%']:<8} {r['Time(m)']:<9} {r['Complete']}")

# Overall stats
complete_users = results_df[results_df['Complete'] == '✅']
if len(complete_users) > 0:
    print(f"\n{'='*120}")
    print("📈 OVERALL STATISTICS (Complete users only)")
    print("=" * 120)
    print(f"Complete users: {len(complete_users)}")
    if len(complete_users) > 0:
        avg_acc = complete_users['Acc%'].astype(float).mean()
        avg_ds_ag = complete_users['DS Ag%'].astype(float).mean()
        print(f"Average Accuracy: {avg_acc:.1f}%")
        print(f"Average DS Agreement: {avg_ds_ag:.1f}%")

# ============================================================================
# 5. FINAL VERIFICATION CHECKLIST
# ============================================================================
print(f"\n{'='*120}")
print("✅ 5. FINAL VERIFICATION CHECKLIST")
print("=" * 120)

all_ok = True
checks = []

# Check 1: All complete users have used=1
complete_with_csv = users[users['complete'] & users['csv_row_id'].notna()]
complete_ok = True
for _, u in complete_with_csv.iterrows():
    csv_row = csv_df[csv_df['id'] == u['csv_row_id']].iloc[0]
    if csv_row['used'] != 1:
        checks.append(f"❌ User {u['user_id']} complete but CSV row {u['csv_row_id']} used={csv_row['used']} (should be 1)")
        complete_ok = False
        all_ok = False
if complete_ok and len(complete_with_csv) > 0:
    checks.append("✅ All complete users have CSV used=1")
elif len(complete_with_csv) == 0:
    checks.append("✅ No complete users to check")

# Check 2: Incomplete users have used=0 or 0.5
incomplete_with_csv = users[~users['complete'] & users['csv_row_id'].notna()]
incomplete_ok = True
for _, u in incomplete_with_csv.iterrows():
    csv_row = csv_df[csv_df['id'] == u['csv_row_id']].iloc[0]
    if csv_row['used'] == 1:
        checks.append(f"❌ User {u['user_id']} incomplete but CSV row {u['csv_row_id']} used=1 (should be 0 or 0.5)")
        incomplete_ok = False
        all_ok = False
if incomplete_ok and len(incomplete_with_csv) > 0:
    checks.append("✅ All incomplete users have CSV used=0 or 0.5")
elif len(incomplete_with_csv) == 0:
    checks.append("✅ No incomplete users to check")

# Check 3: DS decisions correct
if len(ds_errors) == 0:
    checks.append("✅ All DS decisions match CSV")
else:
    checks.append(f"❌ {len(ds_errors)} DS decision errors found")
    all_ok = False

# Check 4: No duplicate CSV rows (unless both incomplete)
if duplicates:
    dup_ok = True
    for row_id, user_list in duplicates.items():
        all_incomplete = all(not users[users['user_id']==uid]['complete'].iloc[0] for uid in user_list)
        if not all_incomplete:
            checks.append(f"❌ CSV row {row_id} used by multiple users, at least one complete")
            dup_ok = False
            all_ok = False
    if dup_ok:
        checks.append("✅ Duplicate CSV rows only for incomplete users")
else:
    checks.append("✅ No duplicate CSV rows")

for check in checks:
    print(f"   {check}")

print(f"\n{'='*120}")
if all_ok:
    print("🎉 ALL CHECKS PASSED - PILOT DATA IS VALID!")
else:
    print("⚠️  SOME ISSUES FOUND - REVIEW ABOVE")
print("=" * 120)

conn.close()
EOF

