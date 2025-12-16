#!/bin/bash
# Quick summary of all users in the experiment
# Usage: bash check_all_users_summary.sh

cd ~/ds-experiment-omri && python3 << 'EOF'
import sqlite3
import pandas as pd

conn = sqlite3.connect('db.sqlite3')

print("=" * 90)
print("📊 ALL USERS SUMMARY")
print("=" * 90)

# Get all users
users = pd.read_sql_query("""
    SELECT user_id, aid, csv_row_id, ps, human_sensitivity, ds_sensitivity, complete, start_time
    FROM experiment_experimentdata
    ORDER BY user_id
""", conn)

if len(users) == 0:
    print("❌ No users found")
    conn.close()
    exit()

# Count stats
total = len(users)
complete = users['complete'].sum()
incomplete = total - complete
demo_users = users[users['aid'].isin(['test']) | users['aid'].str.startswith('local_', na=False)]
real_users = users[~users['aid'].isin(['test']) & ~users['aid'].str.startswith('local_', na=False)]

print(f"\n📈 STATISTICS:")
print(f"   Total Users:     {total}")
print(f"   Complete:        {complete} ✅")
print(f"   Incomplete:      {incomplete} ❌")
print(f"   Demo/Test Users: {len(demo_users)}")
print(f"   Real Users:      {len(real_users)}")

# Show table
print(f"\n{'='*90}")
print(f"{'ID':<5} {'AID':<20} {'CSV':<5} {'PS':<5} {'d_h':<5} {'d_DS':<5} {'Status':<10} {'Start'}")
print("-" * 90)

for _, u in users.iterrows():
    status = "✅ Done" if u['complete'] else "❌ Inc."
    start = str(u['start_time'])[:16] if u['start_time'] else "N/A"
    aid = str(u['aid'])[:18] if len(str(u['aid'])) > 18 else u['aid']
    print(f"{u['user_id']:<5} {aid:<20} {u['csv_row_id']:<5} {u['ps']:<5} {u['human_sensitivity']:<5} {u['ds_sensitivity']:<5} {status:<10} {start}")

# Check for issues
print(f"\n{'='*90}")
print("🔍 DATA QUALITY CHECKS")
print("=" * 90)

# Check for duplicate CSV rows
csv_counts = users['csv_row_id'].value_counts()
duplicates = csv_counts[csv_counts > 1]
if len(duplicates) > 0:
    print(f"⚠️  DUPLICATE CSV ROWS:")
    for row_id, count in duplicates.items():
        dupe_users = users[users['csv_row_id'] == row_id]['user_id'].tolist()
        print(f"   Row {row_id} used by users: {dupe_users}")
else:
    print("✅ No duplicate CSV rows")

# Check CSV used status
try:
    csv_df = pd.read_csv('DATA/conditions_experiment_3ps_11x11_120_A.csv')
    used_rows = csv_df[csv_df['used'] == 1]['id'].tolist()
    complete_user_rows = users[users['complete'] == 1]['csv_row_id'].tolist()
    
    # Rows marked used but user not complete
    mismatched = set(used_rows) - set(complete_user_rows)
    if mismatched:
        print(f"⚠️  CSV rows marked 'used=1' but user not complete: {list(mismatched)}")
    else:
        print("✅ All 'used' CSV rows match complete users")
    
    # isDemo checks
    demo_rows = csv_df[csv_df['isDemo'] == 1]['id'].tolist()
    print(f"✅ Total CSV rows: {len(csv_df)}, Used: {len(used_rows)}, Demo: {len(demo_rows)}")
    
except Exception as e:
    print(f"⚠️  Could not check CSV: {e}")

conn.close()
print("\n" + "=" * 90)
EOF
