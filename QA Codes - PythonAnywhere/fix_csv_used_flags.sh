#!/bin/bash
# Fix CSV used flags for incomplete users
# Resets used=1 to used=0 for incomplete users
# Usage: bash fix_csv_used_flags.sh

cd ~/ds-experiment-omri/Experiment_Code && python3 << 'EOF'
import sqlite3
import pandas as pd

conn = sqlite3.connect('DATA/db.sqlite3')
csv_path = 'DATA/conditions_experiment_3ps_11x11_120_A.csv'
csv_df = pd.read_csv(csv_path)

print("=" * 100)
print("🔧 FIXING CSV USED FLAGS")
print("=" * 100)

# Get all users
users = pd.read_sql_query("""
    SELECT user_id, aid, csv_row_id, complete
    FROM experiment_experimentdata
    WHERE csv_row_id IS NOT NULL
    ORDER BY user_id
""", conn)

print(f"\n📊 Checking {len(users)} users with CSV rows...")

fixes_needed = []

# Only fix abandoned rows (used=0.5 for >30 minutes) - don't touch rows completed by other users
for _, u in users.iterrows():
    if u['complete']:
        continue  # Skip complete users
    
    csv_row_id = int(u['csv_row_id'])
    csv_row = csv_df[csv_df['id'] == csv_row_id]
    
    if len(csv_row) == 0:
        continue
    
    current_used = csv_row.iloc[0]['used']
    
    # Only reset if used=0.5 (abandoned in-progress rows)
    # Don't reset if used=1 (completed by another user - that's correct!)
    if current_used == 0.5:
        # Check if user has been inactive for >30 minutes
        start_time = pd.to_datetime(u['start_time'])
        now = pd.Timestamp.now()
        time_diff_minutes = (now - start_time).total_seconds() / 60
        
        if time_diff_minutes > 30:
            fixes_needed.append((csv_row_id, u['user_id'], current_used, 0, 
                f"User {u['user_id']} abandoned (inactive {time_diff_minutes:.1f} min), resetting used=0.5 → 0"))

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
            csv_df.loc[csv_df['id'] == csv_row_id, 'used'] = new_val
            fixed_rows.add(csv_row_id)
    
    # Save CSV
    csv_df.to_csv(csv_path, index=False)
    print(f"✅ Fixed {len(fixes_needed)} CSV rows")
    
    # Verify fixes
    print(f"\n📊 Verification:")
    for csv_row_id, user_id, old_val, new_val, reason in fixes_needed:
        fixed_row = csv_df[csv_df['id'] == csv_row_id].iloc[0]
        print(f"   Row {csv_row_id}: {old_val} → {fixed_row['used']} ✅")

# Show final status
print(f"\n{'='*100}")
print("📊 FINAL CSV USED FLAGS STATUS")
print("=" * 100)
used_0 = len(csv_df[csv_df['used'] == 0])
used_05 = len(csv_df[csv_df['used'] == 0.5])
used_1 = len(csv_df[csv_df['used'] == 1])
print(f"Used = 0 (Available):     {used_0:>4} rows ({100*used_0/len(csv_df):.1f}%)")
print(f"Used = 0.5 (In-progress): {used_05:>4} rows ({100*used_05/len(csv_df):.1f}%)")
print(f"Used = 1 (Completed):     {used_1:>4} rows ({100*used_1/len(csv_df):.1f}%)")

conn.close()
print("\n✅ Fix complete!")
EOF

