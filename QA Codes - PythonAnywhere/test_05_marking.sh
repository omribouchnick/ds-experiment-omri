#!/bin/bash
# Test that CSV rows are marked as 0.5 when user starts
# Created: 2025-12-20

cd ~/ds-experiment-omri/Experiment_Code

DB_PATH="DATA/db.sqlite3"
CSV_PATH="DATA/conditions_experiment_3ps_11x11_120_A.csv"

echo "================================================================================"
echo "🧪 TESTING 0.5 MARKING MECHANISM"
echo "================================================================================"
echo ""

# Step 1: Find a fresh row before the test
echo "Step 1: Finding a fresh row (used=0)..."
python3 << 'EOF'
import pandas as pd
csv_df = pd.read_csv('DATA/conditions_experiment_3ps_11x11_120_A.csv')
fresh = csv_df[csv_df['used'] == 0].head(1)
if len(fresh) > 0:
    row_id = fresh.iloc[0]['id']
    print(f"   Found fresh row: {int(row_id)} with used={fresh.iloc[0]['used']}")
else:
    print("   ❌ No fresh rows available!")
EOF

echo ""

# Step 2: Check the most recent user
echo "Step 2: Checking most recent user..."
python3 << 'EOF'
import sqlite3
import pandas as pd

conn = sqlite3.connect('DATA/db.sqlite3')
query = "SELECT user_id, aid, csv_row_id, start_time FROM experiment_experimentdata ORDER BY user_id DESC LIMIT 1"
user = pd.read_sql_query(query, conn).iloc[0]
conn.close()

print(f"   Latest User: {user['user_id']}")
print(f"   AID: {user['aid']}")
print(f"   CSV Row: {int(user['csv_row_id'])}")
print(f"   Start Time: {user['start_time']}")

# Check if this row is marked as 0.5
csv_df = pd.read_csv('DATA/conditions_experiment_3ps_11x11_120_A.csv')
row = csv_df[csv_df['id'] == user['csv_row_id']]

if len(row) > 0:
    used_val = row.iloc[0]['used']
    print(f"   CSV Status: used={used_val}")
    if used_val == 0.5:
        print(f"   ✅ SUCCESS: Row was marked as 0.5 when user was created!")
    elif used_val == 0:
        print(f"   ❌ FAIL: Row is still 0 - mark_row_in_progress() was NOT called")
    else:
        print(f"   ⚠️  Row is {used_val} (unexpected)")
EOF

echo ""

# Step 3: Summary
echo "================================================================================"
echo "📊 CURRENT CSV STATUS"
echo "================================================================================"

python3 << 'EOF'
import pandas as pd
csv_df = pd.read_csv('DATA/conditions_experiment_3ps_11x11_120_A.csv')

fresh = len(csv_df[csv_df['used'] == 0])
in_progress = len(csv_df[csv_df['used'] == 0.5])
completed = len(csv_df[csv_df['used'] == 1])

print(f"Fresh (used=0):        {fresh}")
print(f"In-progress (used=0.5): {in_progress}")
print(f"Completed (used=1):     {completed}")
print(f"Total:                  {len(csv_df)}")
print()

if in_progress > 0:
    print(f"✅ There are {in_progress} rows marked as in-progress")
    print("   This proves mark_row_in_progress() is working!")
else:
    print("⚠️  No rows marked as in-progress")
    print("   Either all users completed or there's a bug")
EOF

echo ""
echo "================================================================================"
echo "✅ TEST COMPLETE"
echo "================================================================================"
echo ""
echo "💡 TO VERIFY MANUALLY:"
echo "   1. Start a new test with a unique AID"
echo "   2. Run this script immediately"
echo "   3. Confirm the row changed from 0 → 0.5"
echo ""



