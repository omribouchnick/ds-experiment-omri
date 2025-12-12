# Bug Analysis and Fix Plan

## 1. ROOT CAUSE ANALYSIS

### The Bug:
**Problem:** Users have wrong `ps` and `dprime_s` values in database, but their actual trial data matches different CSV rows.

**Root Cause:**
1. `landing_page()` is called **EVERY TIME** the page loads
2. `load_block_trials()` is called **EVERY TIME**, selecting a new random row
3. `ExperimentData` is only created **ONCE** (when `user_id` not in session)
4. If user refreshes page or session expires:
   - New CSV row is selected
   - `events_data` in session is updated
   - But `ExperimentData` in database is NOT updated (already exists)
   - Result: Database has old ps, user sees new trials

### Code Flow Issue:
```python
def landing_page(request):
    # This is called EVERY TIME
    events_data, csv_row_id, ps, dprime_h, dprime_s = load_block_trials()  # NEW row selected
    
    # Session is updated with new values
    request.session["ps"] = ps
    request.session["events_data"] = events_data
    request.session["csv_row_id"] = csv_row_id
    
    # But this only runs ONCE
    if 'user_id' not in request.session:  # Only creates if doesn't exist
        experiment_data = ExperimentData.objects.create(
            ps=request.session["ps"],  # Uses OLD ps from first call
            ...
        )
```

### Why is_used is Wrong:
- `mark_row_as_used()` is only called after questionnaire completion
- It uses `request.session['csv_row_id']` which might be from a DIFFERENT call
- If user refreshed, `csv_row_id` in session is from the LAST call, not the original
- Result: Wrong row gets marked as used, or no row gets marked

## 2. FIX FOR FUTURE

### Solution 1: Store csv_row_id in Database
```python
# Add csv_row_id column to ExperimentData model
# Store it when creating ExperimentData
# Use it when marking as used (not from session)
```

### Solution 2: Don't Re-select Row if User Exists
```python
def landing_page(request):
    if 'user_id' in request.session:
        # User already exists, don't select new row
        # Load existing data from database
        experiment_data = ExperimentData.objects.get(user_id=request.session['user_id'])
        # Use existing csv_row_id and events_data
    else:
        # New user, select row
        events_data, csv_row_id, ps, dprime_h, dprime_s = load_block_trials()
        experiment_data = ExperimentData.objects.create(
            csv_row_id=csv_row_id,  # Store in database
            ...
        )
```

### Solution 3: Mark Row as Used Immediately
```python
# Mark row as used when ExperimentData is created
# If user quits, mark as unused when they're deleted
```

## 3. CURRENT STATUS

- **52 completed users**
- **51 unique CSV rows used** (1 row used by 2 users - needs investigation)
- **Only 1 row marked as used=1** in CSV (should be 51)
- **38 users have wrong ps in database** (73%)

## 4. WHAT NEEDS TO BE DONE

### Step 1: Verify All Mappings ✅
- Match all 52 users to their CSV rows
- Verify 100% match on events, DS decisions, stimulus values
- Identify the duplicate row usage

### Step 2: Update Database
- Update `ps` values for all users
- Update `dprime_s` values for all users
- Verify `dprime_h` is correct (should be, but verify)

### Step 3: Update CSV is_used
- Mark all 51 unique rows as used=1
- Handle the duplicate row case

### Step 4: Verify Everything
- Re-run analysis with corrected data
- Verify ps distribution is correct
- Verify statistical analysis is valid

## 5. QUESTIONS TO ANSWER BEFORE CONTINUING

1. **Why does 1 row appear to be used by 2 users?**
   - Is this a real duplicate or a matching error?
   - Should we investigate this specific case?

2. **Should we update the database directly or create a migration?**
   - Direct update is faster
   - Migration is safer for production

3. **Do we need to update the CSV file?**
   - Yes, to mark rows as used
   - This prevents future reuse

4. **Should we fix the code before continuing?**
   - Recommended: Fix code first
   - Then update data
   - Then verify


