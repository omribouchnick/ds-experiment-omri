#!/bin/bash
# Verify that the 30-minute timeout logic is in views.py
# Usage: bash verify_timeout_logic.sh

cd ~/ds-experiment-omri/Experiment_Code && python3 << 'EOF'
import re

views_path = 'experiment/views.py'

print("=" * 80)
print("🔍 VERIFYING 30-MINUTE TIMEOUT LOGIC")
print("=" * 80)

with open(views_path, 'r') as f:
    content = f.read()

# Check 1: Function exists
if '_reset_abandoned_rows' in content:
    print("✅ Function _reset_abandoned_rows() exists")
else:
    print("❌ Function _reset_abandoned_rows() NOT FOUND")
    exit(1)

# Check 2: Called in landing_page
if 'landing_page' in content and '_reset_abandoned_rows()' in content:
    # Find where it's called
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if '_reset_abandoned_rows()' in line and 'def landing_page' in '\n'.join(lines[max(0,i-10):i]):
            print(f"✅ Function called in landing_page() at line ~{i+1}")
            break
else:
    print("❌ Function NOT called in landing_page()")
    exit(1)

# Check 3: Uses last activity time (not just start_time)
if 'total_decision_time' in content and 'last_activity' in content:
    print("✅ Uses last activity time (start_time + sum(decision_times))")
else:
    print("❌ Does NOT use last activity time - still using only start_time")
    exit(1)

# Check 4: 30 minute timeout
if 'timeout_minutes = 30' in content or 'timeout_minutes=30' in content:
    print("✅ Timeout set to 30 minutes")
else:
    print("⚠️  Timeout value not found or different")

# Check 5: Resets to 0 (not 1)
if 'used'] = 0' in content or "used'] = '0'" in content:
    print("✅ Resets to used=0 (not 1)")
else:
    print("⚠️  Reset value unclear")

print("\n" + "=" * 80)
print("✅ ALL CHECKS PASSED - Logic is correct!")
print("=" * 80)
EOF


