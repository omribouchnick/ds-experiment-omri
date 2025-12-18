#!/bin/bash
# Diagnostic script to check CSV flag status vs database
# Usage: bash diagnose_csv_flags.sh

cd ~/ds-experiment-omri/Experiment_Code && python3 << 'EOF'
import sqlite3
import pandas as pd
import os

print("=" * 80)
print("🔍 CSV FLAGS DIAGNOSTIC - BEFORE ANY FIXES")
print("=" * 80)

# Connect to database
db_path = 'DATA/db.sqlite3'
if not os.path.exists(db_path):
    db_path = 'DATA/pilot_20251215/db.sqlite3'

if not os.path.exists(db_path):
    print(f"❌ Database not found at: {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)

# Get all users with their completion status
users_df = pd.read_sql_query("""
    SELECT user_id, csv_row_id, complete, start_time
    FROM experiment_experimentdata
    ORDER BY user_id DESC
""", conn)

# Get completed users
completed_users = users_df[users_df['complete'] == 1]
incomplete_users = users_df[users_df['complete'] == 0]

print(f"\n📊 DATABASE STATUS:")
print(f"   Total users: {len(users_df)}")
print(f"   Completed users: {len(completed_users)}")
print(f"   Incomplete users: {len(incomplete_users)}")
print(f"   Users with csv_row_id: {users_df['csv_row_id'].notna().sum()}")

# Load CSV
csv_path = 'DATA/conditions_experiment_3ps_11x11_120_A.csv'
if not os.path.exists(csv_path):
    print(f"❌ CSV not found at: {csv_path}")
    conn.close()
    exit(1)

conditions_df = pd.read_csv(csv_path)

print(f"\n📊 CSV FILE STATUS:")
print(f"   Total CSV rows: {len(conditions_df)}")
print(f"   Rows with used=0: {len(conditions_df[conditions_df['used'] == 0])}")
print(f"   Rows with used=0.5: {len(conditions_df[conditions_df['used'] == 0.5])}")
print(f"   Rows with used=1: {len(conditions_df[conditions_df['used'] == 1])}")

# Get unique CSV rows assigned to completed users
completed_csv_rows = completed_users['csv_row_id'].dropna().unique()
print(f"\n📊 COMPLETED USERS vs CSV:")
print(f"   Unique CSV rows assigned to completed users: {len(completed_csv_rows)}")

# Check mismatches: rows with completed users but CSV says used != 1
print(f"\n" + "=" * 80)
print("🔍 MISMATCH ANALYSIS")
print("=" * 80)

mismatches_completed_not_1 = []
for row_id in completed_csv_rows:
    csv_row = conditions_df[conditions_df['id'] == row_id]
    if len(csv_row) > 0:
        csv_used = csv_row.iloc[0]['used']
        if csv_used != 1:
            users_on_row = completed_users[completed_users['csv_row_id'] == row_id]
            mismatches_completed_not_1.append({
                'csv_row_id': row_id,
                'csv_used': csv_used,
                'completed_users': len(users_on_row),
                'user_ids': users_on_row['user_id'].tolist()
            })

print(f"\n1. Rows with COMPLETED users but CSV used != 1:")
print(f"   Total: {len(mismatches_completed_not_1)}")
if len(mismatches_completed_not_1) > 0:
    print(f"\n   Breakdown by CSV used value:")
    for used_val in [0, 0.5]:
        count = sum(1 for m in mismatches_completed_not_1 if m['csv_used'] == used_val)
        if count > 0:
            print(f"     used={used_val}: {count} rows")
    
    print(f"\n   First 10 examples:")
    for m in mismatches_completed_not_1[:10]:
        print(f"     Row {m['csv_row_id']}: CSV used={m['csv_used']}, {m['completed_users']} completed user(s) {m['user_ids']}")

# Check rows marked used=1 but have no completed users
csv_used_1_rows = set(conditions_df[conditions_df['used'] == 1]['id'].tolist())
rows_with_completed = set(completed_csv_rows)
rows_marked_1_but_no_completed = csv_used_1_rows - rows_with_completed

print(f"\n2. Rows marked used=1 but have NO completed users:")
print(f"   Total: {len(rows_marked_1_but_no_completed)}")
if len(rows_marked_1_but_no_completed) > 0:
    print(f"   Examples: {sorted(list(rows_marked_1_but_no_completed))[:10]}")
    
    # Check if these rows have incomplete users
    incomplete_on_these_rows = []
    for row_id in list(rows_marked_1_but_no_completed)[:10]:
        users_on_row = users_df[users_df['csv_row_id'] == row_id]
        if len(users_on_row) > 0:
            incomplete_on_these_rows.append({
                'row_id': row_id,
                'users': users_on_row[['user_id', 'complete']].to_dict('records')
            })
    
    if len(incomplete_on_these_rows) > 0:
        print(f"\n   Checking if these rows have incomplete users:")
        for item in incomplete_on_these_rows[:5]:
            print(f"     Row {item['row_id']}: {item['users']}")

# Check for duplicate rows (race condition cases)
print(f"\n3. Duplicate CSV rows (race condition - shared rows):")
duplicate_rows = []
for row_id in completed_csv_rows:
    users_on_row = users_df[users_df['csv_row_id'] == row_id]
    completed_count = users_on_row['complete'].sum()
    incomplete_count = len(users_on_row) - completed_count
    
    if len(users_on_row) > 1:  # Multiple users on same row
        duplicate_rows.append({
            'row_id': row_id,
            'total_users': len(users_on_row),
            'completed': completed_count,
            'incomplete': incomplete_count,
            'csv_used': conditions_df[conditions_df['id'] == row_id].iloc[0]['used'] if len(conditions_df[conditions_df['id'] == row_id]) > 0 else None,
            'user_ids': users_on_row[['user_id', 'complete']].to_dict('records')
        })

if len(duplicate_rows) > 0:
    print(f"   Found {len(duplicate_rows)} rows with multiple users (race condition)")
    print(f"\n   Rows with BOTH completed and incomplete users (expected - ignore in checks):")
    mixed_rows = [r for r in duplicate_rows if r['completed'] > 0 and r['incomplete'] > 0]
    print(f"   Total: {len(mixed_rows)}")
    for r in mixed_rows:
        print(f"     Row {r['row_id']}: CSV used={r['csv_used']}, {r['completed']} completed, {r['incomplete']} incomplete")
        print(f"       Users: {r['user_ids']}")
else:
    print(f"   No duplicate rows found")

# Check incomplete users and their CSV flags
print(f"\n4. Incomplete users and their CSV row status:")
incomplete_with_row = incomplete_users[incomplete_users['csv_row_id'].notna()]
if len(incomplete_with_row) > 0:
    print(f"   Incomplete users with csv_row_id: {len(incomplete_with_row)}")
    
    incomplete_csv_rows = incomplete_with_row['csv_row_id'].unique()
    print(f"   Unique CSV rows assigned to incomplete users: {len(incomplete_csv_rows)}")
    
    incomplete_flag_status = {'0': 0, '0.5': 0, '1': 0}
    incomplete_on_shared_rows = []  # Incomplete users on rows that also have completed users
    
    for row_id in incomplete_csv_rows:
        csv_row = conditions_df[conditions_df['id'] == row_id]
        if len(csv_row) > 0:
            csv_used = csv_row.iloc[0]['used']
            incomplete_flag_status[str(csv_used)] = incomplete_flag_status.get(str(csv_used), 0) + 1
            
            # Check if this row also has completed users (shared row from race condition)
            users_on_row = users_df[users_df['csv_row_id'] == row_id]
            has_completed = users_on_row['complete'].sum() > 0
            if has_completed and csv_used == 1:
                incomplete_on_shared_rows.append(row_id)
    
    print(f"   CSV flag distribution for incomplete users:")
    for flag, count in incomplete_flag_status.items():
        if count > 0:
            print(f"     used={flag}: {count} rows")
    
    if len(incomplete_on_shared_rows) > 0:
        print(f"\n   ⚠️  {len(incomplete_on_shared_rows)} incomplete users on rows shared with completed users:")
        print(f"      These rows are correctly marked used=1 (because completed user exists)")
        print(f"      Rows: {incomplete_on_shared_rows}")
        print(f"      ✅ IGNORE in mismatch checks - this is expected from race condition")

# Check last user status
print(f"\n" + "=" * 80)
print("👤 LAST USER STATUS")
print("=" * 80)

if len(users_df) > 0:
    last_user = users_df.iloc[0]  # Already sorted DESC by user_id
    print(f"\nLast user (most recent):")
    print(f"   User ID: {last_user['user_id']}")
    print(f"   CSV Row ID: {last_user['csv_row_id']}")
    print(f"   Complete: {last_user['complete']}")
    print(f"   Start time: {last_user['start_time']}")
    
    if pd.notna(last_user['csv_row_id']):
        csv_row_id = int(last_user['csv_row_id'])
        csv_row = conditions_df[conditions_df['id'] == csv_row_id]
        if len(csv_row) > 0:
            csv_used = csv_row.iloc[0]['used']
            print(f"\n   CSV Row {csv_row_id} status:")
            print(f"     CSV used flag: {csv_used}")
            print(f"     Expected: {'1' if last_user['complete'] else '0.5' if not last_user['complete'] else '0'}")
            
            if last_user['complete'] and csv_used != 1:
                print(f"     ⚠️  MISMATCH: User completed but CSV used={csv_used}")
            elif not last_user['complete'] and csv_used == 1:
                print(f"     ⚠️  MISMATCH: User incomplete but CSV used=1")
            elif not last_user['complete'] and csv_used == 0:
                print(f"     ⚠️  MISMATCH: User incomplete but CSV used=0 (should be 0.5 if in progress)")
            else:
                print(f"     ✅ Status matches")
        else:
            print(f"   ⚠️  CSV row {csv_row_id} not found!")
    else:
        print(f"   ⚠️  User has no csv_row_id assigned")

print(f"\n" + "=" * 80)
print("📋 SUMMARY")
print("=" * 80)
print(f"   Completed users: {len(completed_users)}")
print(f"   CSV rows with used=1: {len(csv_used_1_rows)}")
print(f"   Rows with completed users but not marked used=1: {len(mismatches_completed_not_1)}")
print(f"   Rows marked used=1 but no completed users: {len(rows_marked_1_but_no_completed)}")

# Count incomplete users on shared rows (should be ignored)
incomplete_on_shared = []
for row_id in incomplete_with_row['csv_row_id'].unique():
    users_on_row = users_df[users_df['csv_row_id'] == row_id]
    if users_on_row['complete'].sum() > 0:  # Row has completed user
        incomplete_on_shared.append(row_id)

if len(incomplete_on_shared) > 0:
    print(f"   Incomplete users on shared rows (ignore - expected): {len(incomplete_on_shared)}")

real_mismatches = len(mismatches_completed_not_1) + len(rows_marked_1_but_no_completed)
print(f"\n   ⚠️  Total real mismatches (excluding shared rows): {real_mismatches}")
if real_mismatches == 0:
    print(f"   ✅ All CSV flags are correct!")
print("=" * 80)

conn.close()
EOF

