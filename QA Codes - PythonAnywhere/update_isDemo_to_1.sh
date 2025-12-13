#!/bin/bash
# Update isDemo=1 for all used rows in CSV
# Usage: bash update_isDemo_to_1.sh

cd ~/ds-experiment-omri
source venv/bin/activate

python3 << 'PYEOF'
import pandas as pd
import os

# Load conditions CSV
conditions_file = 'data/conditions_experiment_3ps_11x11_120_A.csv'
if not os.path.exists(conditions_file):
    conditions_file = 'data/old_data_0912/conditions_experiment_3ps_11x11_120_A.csv'

if not os.path.exists(conditions_file):
    print(f"❌ CSV file not found: {conditions_file}")
    exit(1)

print("=" * 80)
print("UPDATING isDemo=1 FOR ALL USED ROWS")
print("=" * 80)

# Load CSV
df = pd.read_csv(conditions_file)

# Check if isDemo column exists, if not create it
if 'isDemo' not in df.columns:
    df['isDemo'] = None
    print("✅ Created isDemo column")

# Count rows that will be updated
used_rows = df[df['used'] == 1]
rows_to_update = used_rows[used_rows['isDemo'] != 1]

print(f"\n📊 Current status:")
print(f"   Total rows: {len(df)}")
print(f"   Used rows (used=1): {len(used_rows)}")
print(f"   Rows with isDemo=1: {len(used_rows[used_rows['isDemo'] == 1])}")
print(f"   Rows to update: {len(rows_to_update)}")

if len(rows_to_update) > 0:
    # Update all used rows to isDemo=1
    df.loc[df['used'] == 1, 'isDemo'] = 1
    
    # Save CSV
    df.to_csv(conditions_file, index=False)
    print(f"\n✅ Updated {len(rows_to_update)} rows to isDemo=1")
    print(f"✅ Saved to: {conditions_file}")
    
    # Show summary
    print(f"\n📊 Updated status:")
    print(f"   Used rows with isDemo=1: {len(df[(df['used'] == 1) & (df['isDemo'] == 1)])}")
else:
    print(f"\n✅ All used rows already have isDemo=1, no updates needed")

print("\n" + "=" * 80)

PYEOF

