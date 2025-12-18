# 🔧 Deploy Fix: Auto-Generate Unique Test AIDs

## 📋 What Was Fixed

**Problem:** When accessing https://omribouch.pythonanywhere.com/ without an `aid` parameter, the system used `aid="test"` as default. But a user with `aid="test"` already exists and is complete, causing an immediate redirect to CloudResearch's "Thank You" page.

**Solution:** Modified `views.py` to auto-generate unique test AIDs in format `test_YYYYMMDD_HHMMSS_XXXXXX` instead of reusing "test".

---

## 🚀 Deployment Steps on PythonAnywhere

### Step 1: Navigate to Project Directory
```bash
cd ~/ds-experiment-omri
```

### Step 2: Check Current Git Status
```bash
git status
```

### Step 3: Pull Latest Changes
```bash
git pull origin main
```

**Expected output:**
```
Updating a1dde69..4ae3e45
Fast-forward
 Experiment_Code/experiment/views.py | 19 ++++++++++++-------
 1 file changed, 12 insertions(+), 7 deletions(-)
```

### Step 4: Verify Changes Were Applied
```bash
grep -A 10 "Get aid - generate unique test aid" Experiment_Code/experiment/views.py
```

**Expected output:** Should show the new code with unique aid generation.

### Step 5: Reload Web App
1. Go to PythonAnywhere Web tab: https://www.pythonanywhere.com/user/Omribouch/webapps/
2. Click the green **"Reload omribouch.pythonanywhere.com"** button
3. Wait for confirmation message

### Step 6: Test the Fix
Open a **new incognito window** and go to:
- https://omribouch.pythonanywhere.com/

**Expected result:** You should see the "Welcome to the Study" page, **NOT** the "Thank You" page.

---

## 📊 Verification Script

Run this to check if user with `aid="test"` exists:

```bash
bash "QA Codes - PythonAnywhere/check_test_user.sh"
```

---

## ✅ What Changed in the Code

### Before:
```python
def landing_page(request):
    aid = request.GET.get("aid", "test")  # Always used "test" as default
    
    try:
        experiment_data = ExperimentData.objects.get(aid=aid)
        if experiment_data.complete:
            return redirect('/end/')  # → This caused Thank You redirect
```

### After:
```python
def landing_page(request):
    aid = request.GET.get("aid", None)
    
    # If no aid, generate unique test aid
    if not aid:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = uuid.uuid4().hex[:6]
        aid = f"test_{timestamp}_{unique_id}"  # e.g., test_20251218_140530_a1b2c3
    
    try:
        experiment_data = ExperimentData.objects.get(aid=aid)
        if experiment_data.complete:
            # If test user already complete, generate NEW unique aid
            if aid.startswith("test"):
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                unique_id = uuid.uuid4().hex[:6]
                aid = f"test_{timestamp}_{unique_id}"
                raise ExperimentData.DoesNotExist  # Create new user
```

---

## 🎯 Impact

- ✅ Direct access to https://omribouch.pythonanywhere.com/ now works
- ✅ Each test session gets a unique AID automatically
- ✅ Real CloudResearch users (with proper AIDs) are unaffected
- ✅ No data loss or corruption
- ✅ Easy to identify test users in analysis (aid starts with "test_")

---

## ⚠️ If `git pull` Has Conflicts

If you see conflicts, especially in `views.py`:

```bash
# Stash local changes
git stash

# Pull again
git pull origin main

# Check if views.py has the fix
grep -A 5 "generate unique test aid" Experiment_Code/experiment/views.py
```

If the fix is there, you're good! If not, contact Omri.

---

## 📧 Questions?

Contact Omri if:
- The page still shows "Thank You" after deployment
- Git pull fails with errors
- Any other issues arise

**System is now ready for testing and continuing the pilot!** 🎉

