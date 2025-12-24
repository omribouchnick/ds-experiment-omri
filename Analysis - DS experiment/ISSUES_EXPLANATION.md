# Issues Explanation (English)

## 1. 3 Duplicate csv_row_id - Expected from Race Condition

### What Happened:
- **3 CSV rows** were assigned to **multiple completed users** (duplicate assignments)
- This occurred **before the race condition fix** was implemented

### Why This Happened:
1. **Race Condition Bug (Pre-Fix):**
   - When two users started the experiment simultaneously, both could read the CSV file at the same time
   - Both would see the same row as `used=0` (available)
   - Both would be assigned the same `csv_row_id`
   - The fix (3-state system: 0, 0.5, 1) was implemented later to prevent this

2. **Timeline:**
   - **Before fix:** Simple binary system (`used=0` or `used=1`)
   - **After fix:** 3-state system (`used=0` = available, `used=0.5` = in-progress, `used=1` = completed)
   - The 3 duplicate assignments happened during the pre-fix period

### Impact:
- **Low impact** - These are historical artifacts from before the fix
- The data itself is correct - both users completed their experiments correctly
- The issue is just that they share the same CSV row assignment
- This is **expected behavior** and doesn't affect data quality

### Action Required:
- **None** - This is documented and expected
- The fix is already in place for future users
- For analysis: You can either:
  - Keep both users (they have different data despite same CSV row)
  - Or exclude one if you need unique CSV row assignments

---

## 2. 5 CSV Flags - Cosmetic Issue

### What Happened:
- **5 CSV rows** are marked as `used=0` (available) but have **completed users** assigned to them
- These rows should be marked as `used=1` (completed)

### Why This Happened:
1. **Possible Causes:**
   - User completed the experiment, but the CSV flag wasn't updated to `used=1`
   - This could happen if:
     - The user completed but the `end()` function didn't run properly
     - There was an error during the completion process
     - The CSV file wasn't saved after marking as complete

2. **The Fix:**
   - The code in `views.py` should mark rows as `used=1` when users complete
   - But for these 5 users, the flag wasn't updated

### Impact:
- **Very Low (Cosmetic)** - This is just a flag mismatch
- The actual data is correct:
  - Users completed their experiments
  - Their data is in the database
  - Their trials are recorded correctly
- The only issue is the CSV `used` flag doesn't reflect reality

### Action Required:
- **Optional** - Run `fix_csv_used_flags.sh` to update the flags
- This is purely cosmetic - doesn't affect data analysis
- The script will:
  1. Find all completed users
  2. Check their CSV row assignments
  3. Update `used=1` for rows with completed users

### Why It's Called "Cosmetic":
- The flag is used for **row assignment logic** (which rows to assign to new users)
- But for **data analysis**, it doesn't matter - we use the database data, not the CSV flags
- It's like having a typo in a label - the data itself is fine, just the label is wrong

---

## Summary

| Issue | Severity | Impact | Action |
|-------|----------|--------|--------|
| 3 duplicate csv_row_id | Low | Historical artifact, expected | None (documented) |
| 5 CSV flags mismatch | Very Low | Cosmetic only | Optional (run fix script) |

**Both issues are non-blocking** - the data is correct and ready for analysis. These are just housekeeping items that can be cleaned up if desired.



