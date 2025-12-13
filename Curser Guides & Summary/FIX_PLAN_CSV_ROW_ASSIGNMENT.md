# Fix Plan: Consistent CSV Row Assignment per User

## Problem Summary

**Current Issue:**
- `landing_page()` is called every time the page loads
- Each call selects a NEW random CSV row
- If user refreshes, they get a different row
- Database `ExperimentData` is only created once, so it has wrong `ps`/`dprime_s`

**Root Cause:**
- No persistent storage of which CSV row was assigned to which user
- Row selection happens in session (volatile)
- No check if user already exists before selecting new row

## Solution

### Step 1: Add `csv_row_id` to Database Model

Add field to `ExperimentData` model to store which CSV row was assigned:
```python
csv_row_id = models.IntegerField(null=True, blank=True)
```

### Step 2: Modify `load_block_trials()` to Accept Optional `csv_row_id`

Allow loading a specific row instead of always selecting a new one:
```python
def load_block_trials(csv_row_id=None):
    if csv_row_id:
        # Load specific row
        selected_row = event_data[event_data['id'] == csv_row_id].iloc[0]
    else:
        # Select new unused row (existing logic)
        available_rows = event_data[event_data['used'] == 0]
        selected_row = available_rows.sample(n=1).iloc[0]
        csv_row_id = int(selected_row['id'])
    # ... rest of function
```

### Step 3: Fix `landing_page()` Logic

**New Flow:**
1. Get `aid` from request (CloudResearch participant ID)
2. Check if `ExperimentData` exists for this `aid`
3. **If exists:**
   - Load existing `csv_row_id` from database
   - Load trials from that specific row
   - Use existing `ps`/`dprime_s` from database
   - Restore session data
4. **If not exists:**
   - Select new unused CSV row
   - Create `ExperimentData` with `csv_row_id`, `ps`, `dprime_s`
   - Store in session

**Key Change:** Check database by `aid`, not just session!

### Step 4: Fix `mark_row_as_used()` to Use Database

Instead of using `request.session['csv_row_id']`, get it from database:
```python
def mark_row_as_used(user_id):
    experiment_data = ExperimentData.objects.get(user_id=user_id)
    csv_row_id = experiment_data.csv_row_id
    # Mark that row as used
```

## Implementation Steps

1. ✅ Add `csv_row_id` field to model
2. ✅ Create migration
3. ✅ Modify `load_block_trials()` to accept `csv_row_id` parameter
4. ✅ Modify `landing_page()` to check database by `aid`
5. ✅ Modify `mark_row_as_used()` to use database `csv_row_id`
6. ✅ Test: Refresh page should not change row

## Benefits

- ✅ Each `aid` gets ONE CSV row (persistent)
- ✅ Refresh doesn't change row assignment
- ✅ Database `ps`/`dprime_s` matches actual trials
- ✅ CSV `used` column correctly marked
- ✅ Session expiration doesn't break assignment

