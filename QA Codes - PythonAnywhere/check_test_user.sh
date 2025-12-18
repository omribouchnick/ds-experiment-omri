#!/bin/bash
# Check if user with aid="test" exists and is complete

cd ~/ds-experiment-omri/Experiment_Code && python3 << 'EOF'
import sqlite3
import pandas as pd

conn = sqlite3.connect('DATA/db.sqlite3')

print("=" * 80)
print("🔍 CHECKING USER WITH AID='test'")
print("=" * 80)

# Check user with aid="test"
user = pd.read_sql_query("""
    SELECT user_id, aid, complete, csv_row_id, start_time, end_time
    FROM experiment_experimentdata
    WHERE aid = 'test'
""", conn)

if len(user) > 0:
    u = user.iloc[0]
    status = "✅ COMPLETE" if u['complete'] else "❌ INCOMPLETE"
    print(f"\nUser found:")
    print(f"  User ID: {u['user_id']}")
    print(f"  AID: {u['aid']}")
    print(f"  Status: {status}")
    print(f"  CSV Row: {u['csv_row_id']}")
    print(f"  Start: {u['start_time']}")
    print(f"  End: {u['end_time']}")
    
    # Check actions
    actions = pd.read_sql_query(f"""
        SELECT COUNT(*) as count
        FROM experiment_experimentaction
        WHERE user_id_id = {u['user_id']}
    """, conn)
    print(f"  Actions: {actions.iloc[0]['count']}")
    
    # Check TOAST
    toast = pd.read_sql_query(f"""
        SELECT COUNT(*) as count
        FROM experiment_toastresponse
        WHERE user_id_id = {u['user_id']}
    """, conn)
    print(f"  TOAST responses: {toast.iloc[0]['count']}")
    
    if u['complete']:
        print(f"\n⚠️  PROBLEM: User 'test' is marked as complete!")
        print(f"   This causes redirect to /end/ when accessing without aid parameter")
        print(f"\n✅ SOLUTION: Delete this user or change the default aid logic")
else:
    print("\n✅ User with aid='test' does not exist")

conn.close()
print("=" * 80)
EOF
