# Pull Instructions for PythonAnywhere

## Recent Commits to Pull

1. **41883bb** - Set end_time when resetting abandoned rows (30-minute timeout)
2. **9644e34** - Add manual edit instructions for views.py on PythonAnywhere
3. **39cb485** - Fix backfill script to work from any directory
4. **3db093e** - Update end_time for incomplete users to use last action time
5. **3a4b692** - Fix timeout to check since last action, not start_time

## Files That May Have Conflicts

### 1. `experiment/views.py` (MOST LIKELY)
**Why:** You manually edited this file to fix the duplicate code.

**Changes in remote:**
- `end()` function: Added end_time calculation for incomplete users (lines ~471-493)
- `_reset_abandoned_rows()` function: Added end_time setting when resetting abandoned rows (lines ~240-263)

**What to do:**
1. Check your current `end()` function - make sure it doesn't have duplicate code
2. Check your current `_reset_abandoned_rows()` function - see if it sets end_time
3. If conflicts occur, you'll need to merge manually

### 2. `QA Codes - PythonAnywhere/backfill_end_time_for_incomplete.sh`
**Why:** We updated this script.

**Changes in remote:**
- Updated to work from any directory
- Updated to show what changed (old vs new end_time)

**What to do:**
- No conflicts expected (you probably didn't edit this)

## Step-by-Step Pull Process

### Step 1: Check for Conflicts
```bash
cd ~/ds-experiment-omri
bash "QA Codes - PythonAnywhere/check_git_conflicts.sh"
```

This will show:
- Uncommitted changes
- Files that differ from remote
- What commits would be pulled

### Step 2: Backup Your Current views.py (IMPORTANT!)
```bash
cp Experiment_Code/experiment/views.py Experiment_Code/experiment/views.py.backup_$(date +%Y%m%d_%H%M%S)
```

### Step 3: Stash Local Changes (if any)
```bash
git stash save "Local changes before pull $(date +%Y%m%d_%H%M%S)"
```

### Step 4: Pull
```bash
git pull origin main
```

### Step 5: If Conflicts Occur

**Option A: Keep Remote Version (Recommended if you want the latest code)**
```bash
git checkout --theirs Experiment_Code/experiment/views.py
git add Experiment_Code/experiment/views.py
git commit -m "Resolve conflict: use remote version of views.py"
```

**Option B: Merge Manually**
1. Open `Experiment_Code/experiment/views.py`
2. Look for conflict markers: `<<<<<<<`, `=======`, `>>>>>>>`
3. Manually merge the changes
4. Save and commit

### Step 6: Verify the Changes
```bash
# Check that end_time logic is in _reset_abandoned_rows()
grep -A 5 "Set end_time to last action time" Experiment_Code/experiment/views.py

# Check that end_time logic is in end() function
grep -A 10 "Set end_time to last action time" Experiment_Code/experiment/views.py | head -15
```

## Expected Result

After pulling, your `views.py` should have:
1. ✅ `end()` function with end_time calculation for incomplete users (no duplicate code)
2. ✅ `_reset_abandoned_rows()` function that sets end_time when resetting abandoned rows

## If You Need Help

If conflicts are too complex, you can:
1. Keep your current version
2. Manually add the end_time setting in `_reset_abandoned_rows()` (see the code in commit 41883bb)

