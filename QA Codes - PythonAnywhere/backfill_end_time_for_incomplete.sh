#!/bin/bash
# Backfill end_time for incomplete users based on their last action time
# Usage: bash backfill_end_time_for_incomplete.sh
# Can be run from any directory - will automatically find the correct path

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
# Navigate to Experiment_Code (one level up from QA Codes - PythonAnywhere)
EXPERIMENT_CODE_DIR="$(dirname "$SCRIPT_DIR")/Experiment_Code"

if [ ! -d "$EXPERIMENT_CODE_DIR" ]; then
    echo "❌ Error: Could not find Experiment_Code directory at: $EXPERIMENT_CODE_DIR"
    exit 1
fi

cd "$EXPERIMENT_CODE_DIR" && python3 << 'EOF'
import sqlite3
import datetime

conn = sqlite3.connect('DATA/db.sqlite3')
cursor = conn.cursor()

# Get all incomplete users (update all, even if they already have end_time)
cursor.execute("""
    SELECT user_id, start_time, end_time 
    FROM experiment_experimentdata 
    WHERE complete = 0
""")

incomplete_users = cursor.fetchall()
print(f"Found {len(incomplete_users)} incomplete users to update")

updated_count = 0

for user_id, start_time_str, current_end_time in incomplete_users:
    # Get all actions for this user
    cursor.execute("""
        SELECT decision_time 
        FROM experiment_experimentaction 
        WHERE user_id_id = ? 
        ORDER BY id
    """, (user_id,))
    
    actions = cursor.fetchall()
    
    if len(actions) > 0:
        # Calculate last action time: start_time + sum of all decision_times
        total_decision_time = sum(row[0] for row in actions)
        
        # Parse start_time
        if isinstance(start_time_str, str):
            start_time = datetime.datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
        else:
            start_time = datetime.datetime.fromisoformat(start_time_str)
        
        if start_time.tzinfo:
            start_time = start_time.replace(tzinfo=None)
        
        last_action_time = start_time + datetime.timedelta(seconds=total_decision_time)
        end_time_str = last_action_time.isoformat()
        
        # Update end_time
        cursor.execute("""
            UPDATE experiment_experimentdata 
            SET end_time = ? 
            WHERE user_id = ?
        """, (end_time_str, user_id))
        
        # Show what changed
        if current_end_time:
            print(f"✅ User {user_id}: Updated end_time from {current_end_time} to {end_time_str} (based on {len(actions)} actions)")
        else:
            print(f"✅ User {user_id}: Set end_time to {end_time_str} (based on {len(actions)} actions)")
        
        updated_count += 1
    else:
        # No actions - set to start_time
        if current_end_time:
            print(f"⚠️  User {user_id}: No actions, updated end_time from {current_end_time} to start_time")
        else:
            print(f"⚠️  User {user_id}: No actions, set end_time = start_time")
        
        cursor.execute("""
            UPDATE experiment_experimentdata 
            SET end_time = ? 
            WHERE user_id = ?
        """, (start_time_str, user_id))
        
        updated_count += 1

conn.commit()
conn.close()

print(f"\n✅ Updated {updated_count} users")
EOF

