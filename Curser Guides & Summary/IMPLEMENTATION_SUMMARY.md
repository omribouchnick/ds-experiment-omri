# Implementation Summary: CSV Row Assignment Fix

## ✅ Changes Implemented

### 1. Model Update (`experiment/models.py`)
- ✅ Added `csv_row_id` field to `ExperimentData` model
- ✅ Field is nullable to support existing records

### 2. Migration Created
- ✅ Migration file: `experiment/migrations/0007_add_csv_row_id.py`
- ✅ Run migration: `python manage.py migrate`

### 3. `load_block_trials()` Function (`experiment/views.py`)
- ✅ Now accepts optional `csv_row_id` parameter
- ✅ If `csv_row_id` provided: loads that specific row
- ✅ If not provided: selects unused row, or cycles through if all used
- ✅ **Row cycling**: If all rows are `used=1`, randomly selects any row

### 4. `landing_page()` Function (`experiment/views.py`)
- ✅ **Checks database by `aid`** (not just session)
- ✅ If user exists:
  - If completed → redirect to end
  - If incomplete → restore their assigned row
- ✅ If new user:
  - Selects new CSV row
  - Creates `ExperimentData` with `csv_row_id`
  - Uses `get_or_create()` to prevent race conditions
- ✅ **Local testing**: Keeps `aid="test"` as-is (can exclude in analysis)

### 5. `mark_row_as_used()` Function (`experiment/views.py`)
- ✅ Now accepts `user_id` instead of `row_id`
- ✅ Gets `csv_row_id` from database (not session)
- ✅ Marks row as `used=1` and `used_type='reg'`
- ✅ **Only called when user completes** (from `toast_4()`)

### 6. `toast_4()` Function (`experiment/views.py`)
- ✅ Calls `mark_row_as_used(experiment_data.user_id)` after questionnaire
- ✅ Row marked as used only when user completes

## 🎯 How It Works Now

### New User Flow:
1. User arrives with `aid="ABC123"`
2. `landing_page()` checks database → no record found
3. Selects unused CSV row (or cycles if all used)
4. Creates `ExperimentData` with `csv_row_id=42`, `aid="ABC123"`
5. Row stays `used=0` (not marked yet)
6. User completes experiment → `toast_4()` marks row as `used=1`

### Existing User Flow (Refresh):
1. User refreshes page with `aid="ABC123"`
2. `landing_page()` checks database → finds existing record
3. Loads `csv_row_id=42` from database
4. Loads same trials from row 42
5. Restores session with same data
6. **Result**: Same row, no change ✅

### Incomplete User Flow:
1. User quits before completing
2. Row stays `used=0` in CSV
3. Another user can get the same row
4. **Result**: Row is reusable ✅

### Row Cycling:
1. All CSV rows are `used=1`
2. New user arrives
3. `load_block_trials()` cycles through (selects any row randomly)
4. **Result**: Experiment can continue even if all rows used ✅

## 📊 Tracking

- **Database**: `ExperimentData` table has `aid` and `csv_row_id`
- **CSV**: `conditions_experiment_3ps_11x11_120_A.csv` has `used` and `used_type`
- **Query example**: 
  ```python
  # Find all users with their CSV rows
  ExperimentData.objects.values('user_id', 'aid', 'csv_row_id', 'complete')
  ```

## ⚠️ Next Steps

1. **Run migration** on production:
   ```bash
   python manage.py migrate
   ```

2. **Test locally**:
   - Test with `aid="test"` (local testing)
   - Test refresh (should keep same row)
   - Test incomplete user (row should stay unused)

3. **Verify**:
   - Check that `csv_row_id` is saved correctly
   - Check that rows are only marked as used when complete
   - Check that row cycling works when all rows used

## 🔒 Safety Features

- ✅ `get_or_create()` prevents race conditions
- ✅ Database check by `aid` (not just session)
- ✅ Row only marked as used when complete
- ✅ Row cycling if all rows used
- ✅ Handles session expiration correctly

