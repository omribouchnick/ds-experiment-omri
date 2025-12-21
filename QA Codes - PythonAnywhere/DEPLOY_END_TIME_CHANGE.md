# Deploy end_time Change to PythonAnywhere

## Summary
This change updates incomplete users' `end_time` to be their **last action time** (start_time + sum of decision_times) instead of the time they visited the end page.

## 1. Where is end_time stored?
- **Table**: `experiment_experimentdata`
- **Column**: `end_time` (DateTimeField, nullable)
- **Data source for backfill**: 
  - `start_time` from `experiment_experimentdata`
  - `decision_time` from `experiment_experimentaction` (sum all actions)

## 2. Backfill Existing Data

Run this script on PythonAnywhere to update all existing incomplete users:

```bash
cd ~/ds-experiment-omri/Experiment_Code
bash "QA Codes - PythonAnywhere/backfill_end_time_for_incomplete.sh"
```

This will:
- Find all incomplete users (`complete = 0`)
- Calculate their last action time: `start_time + sum(decision_times)`
- Update the `end_time` column in the database

## 3. Deploy Code Change (views.py)

**IMPORTANT**: This change does NOT affect any paths. It only changes the `end_time` calculation logic.

### What Changed:
In `experiment/views.py`, function `end()`, lines **471-493**:

**OLD CODE:**
```python
else:
    # Incomplete user - mark as incomplete and reset CSV row to available
    participant.complete = False
    request.session["complete"] = False
    participant.end_time = datetime.datetime.now().isoformat()
    participant.save()
```

**NEW CODE:**
```python
else:
    # Incomplete user - mark as incomplete and reset CSV row to available
    participant.complete = False
    request.session["complete"] = False
    
    # Set end_time to last action time (if actions exist), otherwise use current time
    last_action = ExperimentAction.objects.filter(user_id=request.session["user_id"]).order_by('-id').first()
    if last_action:
        # Calculate last action time: start_time + sum of all decision_times up to last action
        all_actions = ExperimentAction.objects.filter(user_id=request.session["user_id"]).order_by('id')
        total_decision_time = sum(a.decision_time for a in all_actions)  # seconds
        
        start_time = participant.start_time
        if isinstance(start_time, str):
            start_time = datetime.datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        if start_time.tzinfo:
            start_time = start_time.replace(tzinfo=None)
        
        last_action_time = start_time + datetime.timedelta(seconds=total_decision_time)
        participant.end_time = last_action_time.isoformat()
    else:
        # No actions - use current time
        participant.end_time = datetime.datetime.now().isoformat()
    
    participant.save()
```

### Deployment Steps:
1. On PythonAnywhere, edit `experiment/views.py`
2. Find the `end()` function (around line 452)
3. Replace lines 471-493 with the NEW CODE above
4. Save and reload the web app

### Verification:
After deployment, test with an incomplete user - their `end_time` should be their last action time, not the time they visited the end page.


