#!/bin/bash
# Delete test users 96, 97, 98 before rerunning
# Usage: bash delete_test_users.sh

cd ~/ds-experiment-omri/Experiment_Code && python3 << 'EOF'
import sqlite3
import csv

conn = sqlite3.connect('DATA/db.sqlite3')
cursor = conn.cursor()

print("=" * 100)
print("🗑️  DELETING TEST USERS 96, 97, 98")
print("=" * 100)

test_user_ids = [96, 97, 98]
csv_path = 'DATA/conditions_experiment_3ps_11x11_120_A.csv'

# Read CSV
with open(csv_path, 'r') as f:
    reader = csv.DictReader(f)
    csv_rows = list(reader)

for user_id in test_user_ids:
    # Check if user exists
    cursor.execute("""
        SELECT user_id, aid, csv_row_id, complete
        FROM experiment_experimentdata
        WHERE user_id = ?
    """, (user_id,))
    user_row = cursor.fetchone()
    
    if user_row is None:
        print(f"User {user_id}: Not found, skipping")
        continue
    
    user_id_db, aid, csv_row_id, complete = user_row
    print(f"\nUser {user_id}:")
    print(f"   AID: {aid}")
    print(f"   CSV Row: {csv_row_id}")
    print(f"   Complete: {complete}")
    
    # Delete actions
    cursor.execute("SELECT COUNT(*) FROM experiment_experimentaction WHERE user_id_id = ?", (user_id,))
    actions_count = cursor.fetchone()[0]
    cursor.execute("DELETE FROM experiment_experimentaction WHERE user_id_id = ?", (user_id,))
    print(f"   Deleted {actions_count} actions")
    
    # Delete TOAST responses
    cursor.execute("SELECT COUNT(*) FROM experiment_toastresponse WHERE user_id_id = ?", (user_id,))
    toast_count = cursor.fetchone()[0]
    cursor.execute("DELETE FROM experiment_toastresponse WHERE user_id_id = ?", (user_id,))
    print(f"   Deleted {toast_count} TOAST responses")
    
    # Delete user
    cursor.execute("DELETE FROM experiment_experimentdata WHERE user_id = ?", (user_id,))
    print(f"   Deleted user {user_id}")
    
    # Reset CSV row to 0 (since user is deleted)
    if csv_row_id is not None:
        csv_row_id_int = int(csv_row_id)
        for row in csv_rows:
            if int(row['id']) == csv_row_id_int:
                row['used'] = '0'
                print(f"   ✅ Reset CSV row {csv_row_id_int} to used=0")
                break

# Write CSV back
if csv_rows:
    with open(csv_path, 'w', newline='') as f:
        fieldnames = csv_rows[0].keys()
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_rows)

conn.commit()
conn.close()

print("\n" + "=" * 100)
print("✅ Test users deleted and CSV rows reset!")
print("=" * 100)
EOF

