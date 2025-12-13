# Bug Explanation - Clear Version

## How It Should Work:

1. **User visits landing page** → `landing_page()` is called
2. **Select ONE CSV row** → `load_block_trials()` randomly selects ONE row
3. **Load ALL 120 trials from that ONE row:**
   - Block 1: trials 1-10 (from CSV event_t01 to event_t10)
   - Block 2: trials 11-20 (from CSV event_t11 to event_t20)  
   - Block 3: trials 1-100 (from CSV event_t01 to event_t100)
4. **Store in session** → `events_data` contains all trials from that ONE row
5. **Create ExperimentData** → Store ps, dprime_h, dprime_s from that row
6. **User completes experiment** → All trials come from the SAME row

## What Actually Happened:

### Scenario 1: User Refreshes Landing Page

1. **First visit:**
   - `landing_page()` called
   - Selects Row 100 (ps=0.2)
   - Creates ExperimentData with ps=0.2
   - Stores `events_data` in session

2. **User refreshes page (or session expires):**
   - `landing_page()` called AGAIN
   - Selects NEW row: Row 237 (ps=0.35) ← **DIFFERENT ROW!**
   - Updates `events_data` in session with NEW row
   - BUT: `ExperimentData` already exists, so it's NOT updated
   - Result: Database has ps=0.2, but user sees trials from Row 237 (ps=0.35)

### The Code Problem:

```python
def landing_page(request):
    # This runs EVERY TIME the page loads
    events_data, csv_row_id, ps, dprime_h, dprime_s = load_block_trials()  # NEW row selected!
    
    # Session is updated with new values
    request.session["events_data"] = events_data
    request.session["ps"] = ps
    
    # But this only runs ONCE (when user_id doesn't exist)
    if 'user_id' not in request.session:
        ExperimentData.objects.create(
            ps=ps,  # Uses ps from FIRST call
            ...
        )
    # If user_id exists, ExperimentData is NOT updated!
```

## Answer to Your Questions:

### Q1: Does each user get the same row for all 3 blocks?
**YES!** Each user should get ONE row for ALL 3 blocks. The code loads all 120 trials from one row.

### Q2: Did each user get 1 row (but wrong) or 3 different rows?
**Each user got 1 row**, but:
- Database has ps from the FIRST row selected
- User actually saw trials from a DIFFERENT row (if they refreshed)

### Q3: Why exactly did it happen?
**Because `landing_page()` is called every time the page loads:**
- If user refreshes → new row selected
- If session expires → new row selected  
- If user navigates back → new row selected
- But `ExperimentData` is only created once, so it has old values

## How to Fix:

### Solution 1: Don't Re-select Row if User Exists

```python
def landing_page(request):
    if 'user_id' in request.session:
        # User already exists - don't select new row!
        # Load existing data from database
        experiment_data = ExperimentData.objects.get(user_id=request.session['user_id'])
        # Use existing events_data from session (don't reload)
        if 'events_data' not in request.session:
            # Only reload if session was lost
            # But use the SAME csv_row_id from database
            pass
    else:
        # New user - select row
        events_data, csv_row_id, ps, dprime_h, dprime_s = load_block_trials()
        experiment_data = ExperimentData.objects.create(
            csv_row_id=csv_row_id,  # Store in database!
            ps=ps,
            ...
        )
```

### Solution 2: Store csv_row_id in Database

Add `csv_row_id` column to `ExperimentData` model, then:
- Store it when creating ExperimentData
- Use it to reload same row if session expires
- Use it when marking row as used (not from session)

### Solution 3: Mark Row as Used Immediately

```python
# Mark row as used when ExperimentData is created
# If user quits, mark as unused when they're deleted
```

## Current Status:

- ✅ Each user got ONE row for all blocks (verified)
- ❌ But database has wrong ps for 73% of users
- ❌ CSV is_used is wrong (only 1 row marked, should be 51)


