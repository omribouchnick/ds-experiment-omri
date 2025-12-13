# Updated Fix Plan: CSV Row Assignment

## Requirements

1. **Local testing (`aid="test"`)**: Just mark it for exclusion, no unique ID needed
2. **Row reuse**: If user quits (incomplete), row should be reusable
3. **Mark as used**: Only when user completes (not when assigned)
4. **Row cycling**: If all rows are used, start reusing them
5. **Tracking**: Store `csv_row_id` and `aid` in database for tracking

## Implementation

### Step 1: Add `csv_row_id` to Model

```python
class ExperimentData(models.Model):
    user_id = models.AutoField(primary_key=True)
    aid = models.CharField(max_length=255)
    csv_row_id = models.IntegerField(null=True, blank=True)  # NEW: Track which CSV row
    ps = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    human_sensitivity = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    ds_sensitivity = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    start_time = models.DateTimeField(auto_now_add=True)
    complete = models.BooleanField(default=False)
    end_time = models.DateTimeField(null=True, blank=True)
```

### Step 2: Modify `load_block_trials()` to Support Row Cycling

```python
def load_block_trials(csv_row_id=None):
    """
    Load trial data from CSV.
    - If csv_row_id provided: load that specific row
    - If not: select unused row, or cycle through if all used
    """
    STIMULI_SCALAR = 6.5
    csv_path = os.path.join(settings.BASE_DIR, "data", "conditions_experiment_3ps_11x11_120_A.csv")
    event_data = pd.read_csv(csv_path)
    
    if csv_row_id:
        # Load specific row
        selected_row = event_data[event_data['id'] == csv_row_id].iloc[0]
        row_id = int(selected_row['id'])
    else:
        # Select new row
        available_rows = event_data[event_data['used'] == 0]
        
        if len(available_rows) > 0:
            # Has unused rows - select randomly
            selected_row = available_rows.sample(n=1).iloc[0]
            row_id = int(selected_row['id'])
        else:
            # All rows used - cycle through (select any row)
            selected_row = event_data.sample(n=1).iloc[0]
            row_id = int(selected_row['id'])
    
    # Extract ps and dprimes
    ps = float(selected_row['ps'])
    dprime_h = float(selected_row['dprime_h'])
    dprime_s = float(selected_row['dprime_s'])
    
    # Load trials (same as before)
    data_dict = {1: {}, 2: {}, 3: {}}
    # ... (Block 1, 2, 3 logic)
    
    return data_dict, row_id, ps, dprime_h, dprime_s
```

### Step 3: Update `landing_page()` Logic

```python
def landing_page(request):
    # Get aid (keep "test" as-is for local testing)
    aid = request.GET.get("aid", "test")
    
    # Check if user already exists (by aid)
    try:
        experiment_data = ExperimentData.objects.get(aid=aid)
        
        # User exists - check if completed
        if experiment_data.complete:
            return redirect('/end/')
        
        # Incomplete user - restore their data
        csv_row_id = experiment_data.csv_row_id
        if csv_row_id:
            # Load trials from their assigned row
            events_data, _, ps, dprime_h, dprime_s = load_block_trials(csv_row_id=csv_row_id)
        else:
            # Old record without csv_row_id - assign new row
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
        
        # Store in session
        request.session["user_id"] = experiment_data.user_id
        request.session["aid"] = aid
        request.session["ps"] = float(ps)
        request.session["human_sensitivity"] = float(dprime_h)
        request.session["ds_sensitivity"] = float(dprime_s)
        request.session["events_data"] = events_data
        request.session["csv_row_id"] = csv_row_id
    
    # Continue with rest...
```

### Step 4: Update `mark_row_as_used()` - Only When Complete

```python
def mark_row_as_used(user_id):
    """
    Mark CSV row as used ONLY when user completes experiment.
    Called from toast_4 (after questionnaire completion).
    """
    experiment_data = ExperimentData.objects.get(user_id=user_id)
    csv_row_id = experiment_data.csv_row_id
    
    if csv_row_id:
        csv_path = os.path.join(settings.BASE_DIR, "data", "conditions_experiment_3ps_11x11_120_A.csv")
        event_data = pd.read_csv(csv_path)
        event_data.loc[event_data['id'] == csv_row_id, 'used'] = 1
        
        # Set used_type based on when user started
        # Old users (before Block 3 fix): 'learning'
        # New users (after Block 3 fix): 'reg'
        if 'used_type' not in event_data.columns:
            event_data['used_type'] = None
        event_data.loc[event_data['id'] == csv_row_id, 'used_type'] = 'reg'
        
        event_data.to_csv(csv_path, index=False)
```

### Step 5: Update `toast_4()` to Mark Row as Used

```python
def toast_4(request):
    experiment_data = ExperimentData.objects.get(user_id=request.session["user_id"])

    if request.method == 'POST':
        TOASTResponse.objects.create(
            # ... (existing code)
        )
        
        # Mark CSV row as used ONLY when user completes
        mark_row_as_used(experiment_data.user_id)

        return redirect('/end/')

    return render(request, 'toast_4.html')
```

## Key Changes

1. ✅ **Local testing**: Keep `aid="test"` as-is, can exclude in analysis
2. ✅ **Row reuse**: Rows only marked as used when user completes
3. ✅ **Row cycling**: If all rows used, cycle through them
4. ✅ **Tracking**: `csv_row_id` and `aid` stored in database
5. ✅ **Consistency**: Same row assigned to same `aid` (even after refresh)

## Benefits

- ✅ Incomplete users don't "waste" CSV rows
- ✅ All rows can eventually be used
- ✅ Row cycling if needed
- ✅ Easy tracking: `aid` + `csv_row_id` in database
- ✅ Refresh-safe: same `aid` → same row

