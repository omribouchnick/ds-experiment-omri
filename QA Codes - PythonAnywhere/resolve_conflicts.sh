#!/bin/bash
# Resolve git conflicts for views.py
# Usage: bash resolve_conflicts.sh

cd ~/ds-experiment-omri

echo "=================================================================================="
echo "🔧 RESOLVING GIT CONFLICTS"
echo "=================================================================================="

# Backup current views.py
echo -e "\n📋 Step 1: Backing up current views.py..."
cp Experiment_Code/experiment/views.py Experiment_Code/experiment/views.py.backup_$(date +%Y%m%d_%H%M%S)
echo "✅ Backup created"

# Stash local changes (whitespace only, so safe to stash)
echo -e "\n📋 Step 2: Stashing local changes..."
git stash save "Local whitespace changes before pull $(date +%Y%m%d_%H%M%S)"
echo "✅ Changes stashed"

# Pull latest changes
echo -e "\n📋 Step 3: Pulling latest changes..."
git pull origin main

if [ $? -eq 0 ]; then
    echo "✅ Pull successful!"
    
    # Verify the end_time logic is present
    echo -e "\n📋 Step 4: Verifying end_time logic..."
    
    if grep -q "Set end_time to last action time" Experiment_Code/experiment/views.py; then
        echo "✅ end_time logic found in _reset_abandoned_rows()"
    else
        echo "⚠️  end_time logic NOT found - may need manual merge"
    fi
    
    if grep -A 5 "Set end_time to last action time" Experiment_Code/experiment/views.py | grep -q "if last_action:"; then
        echo "✅ end_time logic found in end() function"
    else
        echo "⚠️  end_time logic in end() function may be missing"
    fi
    
    echo -e "\n=================================================================================="
    echo "✅ RESOLUTION COMPLETE"
    echo "=================================================================================="
    echo ""
    echo "Your backup is saved as: Experiment_Code/experiment/views.py.backup_*"
    echo "If you need to restore: cp Experiment_Code/experiment/views.py.backup_* Experiment_Code/experiment/views.py"
else
    echo "❌ Pull failed - conflicts need manual resolution"
    echo ""
    echo "To resolve manually:"
    echo "1. Check conflicts: git status"
    echo "2. Edit Experiment_Code/experiment/views.py to resolve conflicts"
    echo "3. git add Experiment_Code/experiment/views.py"
    echo "4. git commit -m 'Resolve conflicts in views.py'"
fi


