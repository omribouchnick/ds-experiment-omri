#!/bin/bash
# Analyze CSV row issues: why users 96,97 still 0.5 and why 2,7,52,59,87 have used=1
# Usage: bash analyze_csv_row_issues.sh

cd ~/ds-experiment-omri/Experiment_Code && python3 << 'EOF'
import sqlite3
import pandas as pd

conn = sqlite3.connect('DATA/db.sqlite3')
csv_df = pd.read_csv('DATA/conditions_experiment_3ps_11x11_120_A.csv')

print("=" * 100)
print("🔍 ANALYZING CSV ROW ISSUES")
print("=" * 100)

# Get all users
users = pd.read_sql_query("""
    SELECT user_id, aid, csv_row_id, complete, start_time, end_time
    FROM experiment_experimentdata
    WHERE csv_row_id IS NOT NULL
    ORDER BY user_id
""", conn)

# ============================================================================
# Issue 1: Users 96, 97 still have used=0.5 (should be reset to 0)
# ============================================================================
print("\n" + "=" * 100)
print("📊 ISSUE 1: Users 96, 97 with used=0.5")
print("=" * 100)

for user_id in [96, 97]:
    u = users[users['user_id'] == user_id]
    if len(u) > 0:
        u = u.iloc[0]
        csv_row = csv_df[csv_df['id'] == u['csv_row_id']].iloc[0]
        print(f"\nUser {user_id}:")
        print(f"   AID: {u['aid']}")
        print(f"   CSV Row: {u['csv_row_id']}")
        print(f"   Complete: {u['complete']}")
        print(f"   Start: {u['start_time']}")
        print(f"   End: {u['end_time'] if u['end_time'] else 'N/A (never reached /end/ view)'}")
        print(f"   CSV used flag: {csv_row['used']}")
        print(f"   ⚠️  Issue: User closed tab without reaching /end/ view, so mark_row_as_available() was never called")

# ============================================================================
# Issue 2: Users 2, 7, 52, 59, 87 have used=1 but are incomplete
# ============================================================================
print("\n" + "=" * 100)
print("📊 ISSUE 2: Incomplete users with used=1 (checking for duplicate rows)")
print("=" * 100)

problem_users = [2, 7, 52, 59, 87]
for user_id in problem_users:
    u = users[users['user_id'] == user_id]
    if len(u) > 0:
        u = u.iloc[0]
        csv_row_id = u['csv_row_id']
        csv_row = csv_df[csv_df['id'] == csv_row_id].iloc[0]
        
        # Find all users using this CSV row
        users_with_same_row = users[users['csv_row_id'] == csv_row_id]
        
        print(f"\nUser {user_id}:")
        print(f"   AID: {u['aid']}")
        print(f"   CSV Row: {csv_row_id}")
        print(f"   Complete: {u['complete']} ❌")
        print(f"   CSV used flag: {csv_row['used']} (should be 0 or 0.5)")
        print(f"   Other users using same CSV row:")
        
        for _, other_user in users_with_same_row.iterrows():
            if other_user['user_id'] != user_id:
                status = "✅ COMPLETE" if other_user['complete'] else "❌ INCOMPLETE"
                print(f"      User {other_user['user_id']}: {status} (AID: {other_user['aid'][:30]}...)")
                if other_user['complete']:
                    print(f"      ⚠️  This complete user marked the CSV row as used=1!")
                    print(f"      💡 Solution: Reset to used=0 since user {user_id} is incomplete")

print("\n" + "=" * 100)
print("💡 EXPLANATION")
print("=" * 100)
print("""
Issue 1 (Users 96, 97):
- These users closed the browser tab without reaching the /end/ view
- The mark_row_as_available() function only runs in the /end/ view
- Solution: Manually reset these to 0, or they'll reset when they visit /end/ again

Issue 2 (Users 2, 7, 52, 59, 87):
- These users share CSV rows with COMPLETE users (duplicate rows from before race condition fix)
- When the complete user finished, they marked the CSV row as used=1
- But the incomplete user still has that row assigned
- Solution: Reset these rows to used=0 since at least one user is incomplete
""")

conn.close()
EOF


