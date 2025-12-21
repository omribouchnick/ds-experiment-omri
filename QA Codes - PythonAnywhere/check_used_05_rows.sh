#!/bin/bash
# Quick check for rows with used=0.5 that shouldn't be there
# Usage: bash check_used_05_rows.sh

cd ~/ds-experiment-omri/Experiment_Code && python3 << 'EOF'
import sqlite3
import csv

conn = sqlite3.connect('DATA/db.sqlite3')
cursor = conn.cursor()
csv_path = 'DATA/conditions_experiment_3ps_11x11_120_A.csv'

# Read CSV
with open(csv_path, 'r') as f:
    reader = csv.DictReader(f)
    csv_rows = list(reader)

print("=" * 80)
print("🔍 CHECKING FOR used=0.5 ROWS")
print("=" * 80)

used_05_rows = [row for row in csv_rows if float(row['used']) == 0.5]

if len(used_05_rows) == 0:
    print("✅ No rows with used=0.5 found - all good!")
else:
    print(f"⚠️  Found {len(used_05_rows)} rows with used=0.5:\n")
    
    for row in used_05_rows:
        csv_row_id = int(row['id'])
        
        # Check if any user is using this row
        cursor.execute("""
            SELECT user_id, aid, complete, start_time
            FROM experiment_experimentdata
            WHERE csv_row_id = ?
        """, (csv_row_id,))
        users = cursor.fetchall()
        
        print(f"Row ID {csv_row_id}:")
        print(f"   CSV used: {row['used']}")
        if users:
            for user_id, aid, complete, start_time in users:
                status = "✅ COMPLETE" if complete else "❌ INCOMPLETE"
                print(f"   User {user_id} ({aid[:20]}...): {status}, started: {start_time}")
        else:
            print(f"   ⚠️  No user found in DB for this row!")
        print()

conn.close()
EOF


