# Edge Cases Analysis for CSV Row Assignment Fix

## Critical Questions & Answers

### 1. What if user accesses URL without `aid` from CloudResearch?

**Current behavior:**
- `aid = request.GET.get("aid", "test")` → defaults to `"test"`
- Multiple users without `aid` will all get `aid="test"`
- **Problem:** They'll share the same CSV row!

**Solution:**
- Generate unique `aid` if missing: `aid = request.GET.get("aid") or f"local_{uuid.uuid4()}"`
- OR: Require `aid` and redirect/error if missing
- **Recommendation:** Generate unique ID for local testing, but log warning

---

### 2. What if user refreshes the page?

**With the fix:**
- ✅ Check database by `aid` → finds existing `ExperimentData`
- ✅ Load `csv_row_id` from database
- ✅ Load same trials from same CSV row
- ✅ Session gets restored with same data
- **Result:** Refresh works correctly, no row change

**Without the fix (current):**
- ❌ New row selected every refresh
- ❌ Database has old row, session has new row
- **Result:** Mismatch

---

### 3. Can two users get the same `aid` from CloudResearch?

**CloudResearch behavior:**
- CloudResearch generates **unique** `aid` per participant
- Each participant gets a unique assignment ID
- **However:** Edge cases exist:
  - Manual URL manipulation (someone copies a link)
  - Testing with same `aid`
  - CloudResearch bug (rare but possible)

**Protection needed:**
- Check if `ExperimentData` exists for `aid`
- If exists AND `complete=True` → redirect to completion page
- If exists AND `complete=False` → allow continuation (same user returning)
- If exists AND different session → **PROBLEM!** Need to handle this

**Solution:**
```python
existing = ExperimentData.objects.filter(aid=aid).first()
if existing:
    if existing.complete:
        # Already completed - redirect
        return redirect('/end/')
    else:
        # Incomplete - allow continuation
        # Use existing csv_row_id
        pass
else:
    # New user - assign row
    pass
```

---

### 4. Race Condition: Two simultaneous requests with same `aid`

**Scenario:**
- User A and User B both access with `aid="ABC123"` at exact same time
- Both check database → both see "no existing record"
- Both select a CSV row → could get different rows or same row

**Protection:**
- Use database transaction with `get_or_create()`:
```python
experiment_data, created = ExperimentData.objects.get_or_create(
    aid=aid,
    defaults={
        'csv_row_id': csv_row_id,
        'ps': ps,
        ...
    }
)
```
- If `created=False`, someone else created it first → use their `csv_row_id`
- **Result:** First request wins, second uses same row (correct behavior)

---

### 5. Session expiration vs Database persistence

**Scenario:**
- User starts experiment → `ExperimentData` created with `csv_row_id=42`
- User's session expires (browser closed, timeout, etc.)
- User returns later → new session, but same `aid`

**With the fix:**
- ✅ Check database by `aid` → finds existing record
- ✅ Load `csv_row_id=42` from database
- ✅ Reload trials from row 42
- ✅ Restore session with correct data
- **Result:** Works correctly!

**Without the fix:**
- ❌ New session → no `user_id` in session
- ❌ New row selected
- ❌ Database has old row, user sees new row
- **Result:** Mismatch

---

## Potential Issues & Solutions

### Issue 1: Multiple incomplete records for same `aid`

**How it could happen:**
- Race condition (if not using `get_or_create`)
- Manual database manipulation
- Bug in code

**Protection:**
- Use `get_or_create()` to prevent duplicates
- Add database constraint: `unique_together = ('aid',)` if incomplete
- OR: Check for existing incomplete record first

### Issue 2: CSV row already marked as `used=1` but user incomplete

**How it could happen:**
- User assigned row 42
- Row 42 marked as used
- User quits (incomplete)
- Row 42 can't be reused

**Current behavior:**
- Row stays marked as used (even if user incomplete)
- **Is this OK?** Depends on your policy:
  - **Option A:** Mark as used immediately → prevents reuse (safer)
  - **Option B:** Only mark as used when complete → allows reuse if user quits

**Recommendation:** Mark as used when `ExperimentData` is created (Option A)
- Prevents row reuse even if user quits
- More conservative, safer for data integrity

### Issue 3: Local testing with `aid="test"`

**Problem:**
- Multiple local tests all use `aid="test"`
- They'll share the same CSV row
- Data gets mixed up

**Solution:**
- Generate unique `aid` for local testing:
```python
aid = request.GET.get("aid")
if not aid or aid == "test":
    aid = f"local_{uuid.uuid4()}"
```

---

## Recommended Implementation

### Safe `landing_page()` Logic:

```python
def landing_page(request):
    # Get aid (generate unique if missing)
    aid = request.GET.get("aid")
    if not aid or aid == "test":
        aid = f"local_{uuid.uuid4()}"
    
    # Check if user already exists (by aid, not session!)
    try:
        experiment_data = ExperimentData.objects.get(aid=aid)
        
        # User exists - check if completed
        if experiment_data.complete:
            # Already completed - redirect to end
            return redirect('/end/')
        
        # Incomplete user - restore their data
        csv_row_id = experiment_data.csv_row_id
        if csv_row_id:
            # Load trials from their assigned row
            events_data, _, ps, dprime_h, dprime_s = load_block_trials(csv_row_id=csv_row_id)
        else:
            # Old record without csv_row_id - need to handle
            # (for existing data before migration)
            events_data, csv_row_id, ps, dprime_h, dprime_s = load_block_trials()
            experiment_data.csv_row_id = csv_row_id
            experiment_data.ps = ps
            experiment_data.human_sensitivity = dprime_h
            experiment_data.ds_sensitivity = dprime_s
            experiment_data.save()
        
        # Restore session
        request.session["user_id"] = experiment_data.user_id
        request.session["aid"] = aid
        request.session["ps"] = float(ps)
        request.session["human_sensitivity"] = float(dprime_h)
        request.session["ds_sensitivity"] = float(dprime_s)
        request.session["events_data"] = events_data
        request.session["csv_row_id"] = csv_row_id
        
    except ExperimentData.DoesNotExist:
        # New user - assign CSV row
        events_data, csv_row_id, ps, dprime_h, dprime_s = load_block_trials()
        
        # Create record (use get_or_create to prevent race condition)
        experiment_data, created = ExperimentData.objects.get_or_create(
            aid=aid,
            defaults={
                'ps': ps,
                'human_sensitivity': dprime_h,
                'ds_sensitivity': dprime_s,
                'csv_row_id': csv_row_id,
                'complete': False
            }
        )
        
        # If not created, someone else created it first - use their data
        if not created:
            csv_row_id = experiment_data.csv_row_id
            events_data, _, ps, dprime_h, dprime_s = load_block_trials(csv_row_id=csv_row_id)
        
        # Mark row as used immediately (conservative approach)
        mark_row_as_used(csv_row_id)
        
        # Store in session
        request.session["user_id"] = experiment_data.user_id
        request.session["aid"] = aid
        request.session["ps"] = float(ps)
        request.session["human_sensitivity"] = float(dprime_h)
        request.session["ds_sensitivity"] = float(dprime_s)
        request.session["events_data"] = events_data
        request.session["csv_row_id"] = csv_row_id
    
    # Continue with rest of function...
```

---

## Summary: Is This Safe?

✅ **Yes, with proper implementation:**
- Use `get_or_create()` to prevent race conditions
- Check database by `aid` (not just session)
- Handle existing incomplete users
- Generate unique `aid` for local testing
- Mark row as used when assigned (conservative)

⚠️ **Edge cases handled:**
- No `aid` → generate unique ID
- Refresh → uses existing row
- Session expiration → restores from database
- Same `aid` twice → first wins, second continues
- Race conditions → `get_or_create()` prevents duplicates

