# Validation Checks Added to Notebook

## ✅ What Was Added

A comprehensive validation cell was added to `experiment_analysis.ipynb` (after data loading) that checks:

### CHECK 1: Each user has exactly 1 csv_row_id
- Verifies all users have a `csv_row_id` assigned
- Checks for duplicate `csv_row_id` assignments (should be 0 for completed users)
- Reports users without `csv_row_id` (likely from before the fix)

### CHECK 2: CSV rows with used=0 are NOT assigned to users
- Verifies that unused CSV rows (`used=0`) are not assigned to any user
- This ensures rows can be reused if user quits

### CHECK 3: CSV rows with used=1 are assigned to exactly 1 user
- Verifies that used CSV rows (`used=1`) are assigned to exactly 1 user
- Checks for rows marked as used but not assigned (shouldn't happen)
- Checks for rows assigned to multiple users (error condition)

### CHECK 4: Sample verification - User trials vs CSV row
- Samples 3 users and compares their actual trials to their assigned CSV row
- Verifies Block 1 (columns 1-10)
- Verifies Block 2 (columns 11-20)
- **Verifies Block 3 (columns 21-120)** - critical check for the fix

### CHECK 5: Block 3 column mapping verification
- Specifically checks if Block 3 trial 1 matches CSV column 21 (correct) or column 1 (wrong)
- This directly validates the Block 3 fix

## 📝 Important Note

**Update the SQL query in cell 3** to include `csv_row_id`:

```python
# Change from:
SELECT user_id, aid, ps, human_sensitivity, ds_sensitivity, 
       start_time, complete, end_time
FROM experiment_experimentdata

# To:
SELECT user_id, aid, csv_row_id, ps, human_sensitivity, ds_sensitivity, 
       start_time, complete, end_time
FROM experiment_experimentdata
```

The validation cell will work even without this update (it handles missing `csv_row_id` gracefully), but it's better to include it for full validation.

## 🔍 What the Validation Prevents

These checks ensure:
1. ✅ No duplicate row assignments
2. ✅ Rows are only marked as used when assigned to users
3. ✅ Each user gets exactly one CSV row
4. ✅ Block 3 uses correct columns (21-120, not 1-100)
5. ✅ Data integrity between database and CSV file

## 🚨 Error Detection

The validation will catch:
- ❌ Multiple users assigned to same CSV row
- ❌ Unused rows assigned to users
- ❌ Used rows not assigned to any user
- ❌ Block 3 using wrong columns (1-100 instead of 21-120)
- ❌ Users without `csv_row_id` (from before migration)

## 📊 Running the Validation

The validation cell runs automatically when you execute the notebook. It will:
1. Check all conditions
2. Report any issues found
3. Provide a summary at the end

Run this cell after loading data to verify everything is correct!

