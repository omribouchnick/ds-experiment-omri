#!/bin/bash
# Delete test users 96, 97, 98 before rerunning
# Usage: bash delete_test_users.sh

cd ~/ds-experiment-omri/Experiment_Code && python3 << 'EOF'
import sqlite3
import pandas as pd

conn = sqlite3.connect('DATA/db.sqlite3')

print("=" * 100)
print("🗑️  DELETING TEST USERS 96, 97, 98")
print("=" * 100)

test_user_ids = [96, 97, 98]

for user_id in test_user_ids:
    # Check if user exists
    user = pd.read_sql_query(f"""
        SELECT user_id, aid, csv_row_id, complete
        FROM experiment_experimentdata
        WHERE user_id = {user_id}
    """, conn)
    
    if len(user) == 0:
        print(f"User {user_id}: Not found, skipping")
        continue
    
    u = user.iloc[0]
    print(f"\nUser {user_id}:")
    print(f"   AID: {u['aid']}")
    print(f"   CSV Row: {u['csv_row_id']}")
    print(f"   Complete: {u['complete']}")
    
    # Delete actions
    actions_count = pd.read_sql_query(f"""
        SELECT COUNT(*) as c FROM experiment_experimentaction WHERE user_id_id = {user_id}
    """, conn).iloc[0]['c']
    
    conn.execute(f"DELETE FROM experiment_experimentaction WHERE user_id_id = {user_id}")
    print(f"   Deleted {actions_count} actions")
    
    # Delete TOAST responses
    toast_count = pd.read_sql_query(f"""
        SELECT COUNT(*) as c FROM experiment_toastresponse WHERE user_id_id = {user_id}
    """, conn).iloc[0]['c']
    
    conn.execute(f"DELETE FROM experiment_toastresponse WHERE user_id_id = {user_id}")
    print(f"   Deleted {toast_count} TOAST responses")
    
    # Delete user
    conn.execute(f"DELETE FROM experiment_experimentdata WHERE user_id = {user_id}")
    print(f"   ✅ Deleted user {user_id}")

conn.commit()
conn.close()

print("\n" + "=" * 100)
print("✅ Test users deleted!")
print("=" * 100)
EOF

