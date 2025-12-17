#!/bin/bash
# Check for git conflicts before pulling
# Usage: bash check_git_conflicts.sh

cd ~/ds-experiment-omri

echo "=" * 80
echo "🔍 CHECKING GIT STATUS AND POTENTIAL CONFLICTS"
echo "=" * 80

# Check current branch
echo -e "\n📋 Current branch:"
git branch

# Check if there are uncommitted changes
echo -e "\n📋 Uncommitted changes:"
git status --short

# Check what files differ between local and remote
echo -e "\n📋 Files that differ from remote:"
git fetch origin
git diff --name-only HEAD origin/main

# Check for specific file that we changed
echo -e "\n📋 Checking experiment/views.py:"
if [ -f "Experiment_Code/experiment/views.py" ]; then
    echo "✅ File exists"
    # Check if it has local modifications
    if git diff --quiet Experiment_Code/experiment/views.py; then
        echo "✅ No local modifications to views.py"
    else
        echo "⚠️  views.py has local modifications:"
        git diff Experiment_Code/experiment/views.py | head -50
    fi
else
    echo "❌ File not found"
fi

# Show what would be pulled
echo -e "\n📋 What would be pulled (last 5 commits):"
git log HEAD..origin/main --oneline -5

echo -e "\n" + "=" * 80
echo "✅ CHECK COMPLETE"
echo "=" * 80
echo ""
echo "If there are conflicts, you'll need to:"
echo "1. Stash local changes: git stash"
echo "2. Pull: git pull origin main"
echo "3. Apply stashed changes: git stash pop"
echo "4. Resolve any conflicts manually"

