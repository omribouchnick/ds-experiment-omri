# 🔬 Comprehensive Validation Guide

## Overview

This folder contains validation scripts to check your experiment's data integrity and performance on PythonAnywhere.

---

## 📊 Available Validation Scripts

### 1. **`comprehensive_pilot_validation.sh`** - FULL ANALYSIS ⭐
**Replicates all checks from the Jupyter notebook**

**What it checks:**
- ✅ Basic data integrity (CSV flags, duplicates, assignments)
- ✅ Learning curve analysis (Block 1→2→3 improvement)
- ✅ Statistical balancing (ps, d'_human, d'_DS distributions)
- ✅ DS decision verification (samples 5 random users)
- ✅ TOAST questionnaire coverage
- ✅ Timeout mechanism (30-minute reset logic)
- ✅ End time coverage

**Use this when:**
- You want a complete health check
- Before/after major pilot batches
- To verify experimental design
- To check learning effects

**Run on PythonAnywhere:**
```bash
cd ~/ds-experiment-omri
bash "QA Codes - PythonAnywhere/comprehensive_pilot_validation.sh"
```

**Expected output:** Detailed report covering all 6 validation sections + final summary

---

### 2. **`validate_complete_user_and_timeout.sh`** - QUICK CHECK
**Focuses on the most recent complete user + timeout logic**

**What it checks:**
- ✅ Most recent complete user (actions, TOAST, CSV flag, end_time)
- ✅ 30-minute timeout for incomplete users
- ✅ CSV flag distribution
- ✅ Basic statistics

**Use this when:**
- You want a quick sanity check
- After a batch completes
- To verify the last user

**Run on PythonAnywhere:**
```bash
cd ~/ds-experiment-omri/Experiment_Code
bash "../QA Codes - PythonAnywhere/validate_complete_user_and_timeout.sh"
```

---

### 3. **`check_last_3_users_status.sh`** - USER DETAILS
**Shows detailed info for the last 3 users**

**What it shows:**
- User ID, AID, CSV row, completion status
- Start/end times, duration
- CSV row matching (ps, d'_human, d'_DS)
- CSV flag status (used, isDemo)
- Progress (actions per block)
- TOAST responses
- DS decision verification (first 6 trials)

**Use this when:**
- You want to inspect specific users
- Debugging user issues
- Verifying CSV row assignments

**Run on PythonAnywhere:**
```bash
cd ~/ds-experiment-omri/Experiment_Code
bash "../QA Codes - PythonAnywhere/check_last_3_users_status.sh"
```

---

### 4. **`validate_last_user_detailed.sh`** - DEEP DIVE ⭐
**Complete forensic analysis of the most recent complete user**

**What it checks:**
- All 120 actions (saved correctly?)
- Accuracy by block (Block 1, 2, 3)
- Reaction times (mean, range)
- DS agreement rates
- CSV row matching (ps, d'_human, d'_DS)
- First 5 trials: DB vs CSV columns verification
  - Event matches
  - Human stimulus (h_t + 6.5)
  - DS stimulus (s_t)
  - DS decision correctness
- TOAST responses
- CSV flag status

**Use this when:**
- You want complete verification of one user
- Before/after major changes
- Investigating data quality issues
- Confirming everything works end-to-end

**Run on PythonAnywhere:**
```bash
cd ~/ds-experiment-omri
bash "QA Codes - PythonAnywhere/validate_last_user_detailed.sh"
```

**Expected output:** Detailed report with action counts, accuracy stats, CSV verification for first 5 trials

---

## 🎯 Recommended Validation Workflow

### During Pilot:
1. **After each batch completes:**
   ```bash
   # Quick check
   cd ~/ds-experiment-omri/Experiment_Code
   bash "../QA Codes - PythonAnywhere/validate_complete_user_and_timeout.sh"
   ```

2. **If you see issues:**
   ```bash
   # Check last users
   bash "../QA Codes - PythonAnywhere/check_last_3_users_status.sh"
   ```

3. **Every 20-30 completions:**
   ```bash
   # Full validation
   cd ~/ds-experiment-omri
   bash "QA Codes - PythonAnywhere/comprehensive_pilot_validation.sh"
   ```

### Before Full Launch:
```bash
# Run comprehensive validation
cd ~/ds-experiment-omri
bash "QA Codes - PythonAnywhere/comprehensive_pilot_validation.sh"
```

**Look for:**
- ✅ "ALL VALIDATIONS PASSED" at the end
- ✅ No ⚠️ warnings in critical sections
- ✅ Learning effects (Block 1→2→3 improvement)
- ✅ Balanced condition distributions

---

## 📝 Interpreting Results

### ✅ Good Signs:
- All CSV flags match completion status
- No duplicate CSV rows for completed users
- Learning curve shows improvement (Block 1→2→3)
- Timeout mechanism working (0.5 → 0 after 30 min)
- 100% TOAST coverage for complete users
- DS decisions match expected values

### ⚠️ Warning Signs:
- CSV flag mismatches > 5%
- No learning improvement (flat accuracy)
- Missing end_time for complete users
- Timeout errors (flags not resetting)
- DS decision errors > 10%

### ❌ Critical Issues:
- Duplicate CSV rows for completed users (indicates race condition)
- Missing TOAST for complete users
- Complete users with 0 actions
- CSV rows stuck at used=0.5 after 30+ min

---

## 🔄 If You Download Database Locally

If you prefer to run the Jupyter notebook locally:

1. **Download from PythonAnywhere:**
   ```bash
   # On PythonAnywhere
   cd ~/ds-experiment-omri/Experiment_Code/DATA
   cp db.sqlite3 ~/
   cp conditions_experiment_3ps_11x11_120_A.csv ~/
   ```

2. **Download via Web Console:**
   - Go to: Files → Home → Download both files

3. **On your local machine:**
   - Place files in: `DATA/pilot_YYYYMMDD/`
   - Run: `comprehensive_validation_analysis.ipynb`

**Pros:** 
- Full Jupyter environment
- Can modify and explore data
- Visual plots and charts

**Cons:**
- Need to download/upload files
- Version sync issues
- Extra steps

**Recommendation:** Use bash scripts on PythonAnywhere for routine checks, download for deep analysis if needed.

---

## 🆘 Troubleshooting

### Script not found:
```bash
# Pull latest changes first
cd ~/ds-experiment-omri
git pull origin main
```

### Permission denied:
```bash
chmod +x "QA Codes - PythonAnywhere/comprehensive_pilot_validation.sh"
```

### Database locked:
```bash
# Wait 10 seconds and try again
# Someone might be accessing the database
```

### Python errors:
```bash
# Make sure you're in the right directory
cd ~/ds-experiment-omri/Experiment_Code
# Or for comprehensive validation:
cd ~/ds-experiment-omri
```

---

## 📊 Sample Output

### Comprehensive Validation (excerpt):
```
================================================================================
🔬 COMPREHENSIVE PILOT VALIDATION - DEEP ANALYSIS
================================================================================
Report generated: 2025-12-18 13:30:00

📊 Data loaded:
   Users: 146 (Complete: 83, Incomplete: 63)
   Actions: 9960 trials
   TOAST responses: 83

================================================================================
✅ SECTION 1: BASIC DATA INTEGRITY CHECKS
================================================================================

1. CSV Row Assignment:
   ✅ Users with csv_row_id: 146/146

2. Duplicate csv_row_id (completed users):
   ✅ No duplicates found!

3. CSV Used Flags Distribution:
   used=0.0 (Available): 274
   used=0.5 (In-progress): 9
   used=1.0 (Completed): 80

4. CSV Flag Validation (completed users):
   ✅ All CSV flags correct!

5. End Time Coverage:
   Complete users: 83
   With end_time: 83 (100.0%)
   ✅ All complete users have end_time!

================================================================================
📈 SECTION 2: LEARNING CURVE ANALYSIS
================================================================================

Performance by Block (Complete Users Only):

   Block 1:
      Accuracy: 65.2% (541/830)
      Mean RT: 2.34s

   Block 2:
      Accuracy: 71.8% (596/830)
      Mean RT: 2.12s

   Block 3:
      Accuracy: 75.8% (6287/8300)
      Mean RT: 1.89s

📊 Learning Effect Analysis:
   Block 1 → Block 2: +6.6% ✅ Improvement
   Block 2 → Block 3: +4.0% ✅ Improvement
   Block 1 → Block 3: +10.6% ✅ Overall improvement

[... more sections ...]

================================================================================
🏁 FINAL VALIDATION SUMMARY
================================================================================

📊 Overall Statistics:
   Total users: 146
   Complete: 83 (56.8%)
   Incomplete: 63 (43.2%)
   CSV rows used: 89 / 363

🎉 ALL VALIDATIONS PASSED!
   ✅ No issues found
   ✅ Data integrity: EXCELLENT
   ✅ Experimental design: VALID
   ✅ System functionality: OPERATIONAL
```

---

## 📌 Quick Reference Card

| Need | Command |
|------|---------|
| Full health check | `bash "QA Codes - PythonAnywhere/comprehensive_pilot_validation.sh"` |
| Last complete user | `bash "../QA Codes - PythonAnywhere/validate_complete_user_and_timeout.sh"` |
| Last 3 users detail | `bash "../QA Codes - PythonAnywhere/check_last_3_users_status.sh"` |
| Deep dive last user | `bash "QA Codes - PythonAnywhere/validate_last_user_detailed.sh"` |
| Download database | Files → `Experiment_Code/DATA/db.sqlite3` |
| Pull latest scripts | `cd ~/ds-experiment-omri && git pull` |

---

**💡 Tip:** Bookmark this file or keep it open in a browser tab while monitoring your pilot!

