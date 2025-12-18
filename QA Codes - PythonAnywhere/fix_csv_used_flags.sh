#!/bin/bash
# Fix CSV used flags for incomplete users
# Resets used=1 to used=0 for incomplete users
# Usage: bash fix_csv_used_flags.sh

cd ~/ds-experiment-omri/Experiment_Code && python3 << 'EOF'
import sqlite3
import csv
from datetime import datetime

conn = sqlite3.connect('DATA/db.sqlite3')
cursor = conn.cursor()
csv_path = 'DATA/conditions_experiment_3ps_11x11_120_A.csv'

# Read CSV
with open(csv_path, 'r') as f:
    reader = csv.DictReader(f)
    csv_rows = list(reader)

# Create lookup dict for CSV rows by id
csv_lookup = {int(row['id']): row for row in csv_rows}

print("=" * 100)
print("🔧 FIXING CSV USED FLAGS")
print("=" * 100)

# Get all users
cursor.execute("""
    SELECT user_id, aid, csv_row_id, complete, start_time
    FROM experiment_experimentdata
    WHERE csv_row_id IS NOT NULL
    ORDER BY user_id
""")
users = cursor.fetchall()

print(f"\n📊 Checking {len(users)} users with CSV rows...")

fixes_needed = []
now = datetime.now()

# Only fix abandoned rows (used=0.5 for >30 minutes) - don't touch rows completed by other users
for user_id, aid, csv_row_id, complete, start_time_str in users:
    if complete:
        continue  # Skip complete users
    
    csv_row_id_int = int(csv_row_id)
    csv_row = csv_lookup.get(csv_row_id_int)
    
    if csv_row is None:
        continue
    
    current_used = float(csv_row['used'])
    
    # Only reset if used=0.5 (abandoned in-progress rows)
    # Don't reset if used=1 (completed by another user - that's correct!)
    if current_used == 0.5:
        # Check if user has been inactive for >30 minutes
        start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00').replace('+00:00', ''))
        if start_time.tzinfo:
            start_time = start_time.replace(tzinfo=None)
        time_diff_minutes = (now - start_time).total_seconds() / 60
        
        if time_diff_minutes > 30:
            fixes_needed.append((csv_row_id_int, user_id, current_used, 0, 
                f"User {user_id} abandoned (inactive {time_diff_minutes:.1f} min), resetting used=0.5 → 0"))

if len(fixes_needed) == 0:
    print("✅ No fixes needed - all CSV used flags are correct!")
else:
    print(f"\n⚠️  Found {len(fixes_needed)} fixes needed:")
    for csv_row_id, user_id, old_val, new_val, reason in fixes_needed:
        print(f"   {reason} → Setting to {new_val}")
    
    # Apply fixes (only fix each row once, even if multiple users share it)
    print(f"\n🔧 Applying fixes...")
    fixed_rows = set()
    for csv_row_id, user_id, old_val, new_val, reason in fixes_needed:
        if csv_row_id not in fixed_rows:
            csv_lookup[csv_row_id]['used'] = str(new_val)
            fixed_rows.add(csv_row_id)
    
    # Write CSV back
    with open(csv_path, 'w', newline='') as f:
        fieldnames = csv_rows[0].keys()
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_rows)
    
    print(f"✅ Fixed {len(fixed_rows)} CSV rows")
    
    # Verify fixes
    print(f"\n📊 Verification:")
    for csv_row_id, user_id, old_val, new_val, reason in fixes_needed:
        if csv_row_id in fixed_rows:
            fixed_val = csv_lookup[csv_row_id]['used']
            print(f"   Row {csv_row_id}: {old_val} → {fixed_val} ✅")

# Show final status
print(f"\n{'='*100}")
print("📊 FINAL CSV USED FLAGS STATUS")
print("=" * 100)
used_0 = sum(1 for row in csv_rows if float(row['used']) == 0)
used_05 = sum(1 for row in csv_rows if float(row['used']) == 0.5)
used_1 = sum(1 for row in csv_rows if float(row['used']) == 1)
total = len(csv_rows)
print(f"Used = 0 (Available):     {used_0:>4} rows ({100*used_0/total:.1f}%)")
print(f"Used = 0.5 (In-progress): {used_05:>4} rows ({100*used_05/total:.1f}%)")
print(f"Used = 1 (Completed):     {used_1:>4} rows ({100*used_1/total:.1f}%)")

conn.close()
print("\n✅ Fix complete!")
EOF

