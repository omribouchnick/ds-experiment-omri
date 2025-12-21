# Manual Fix: Set end_time in _reset_abandoned_rows()

## File to Edit
`Experiment_Code/experiment/views.py`

## Find This Code (around line 240-242)

Look for the `_reset_abandoned_rows()` function. Find this section:

```python
        # If >30 minutes since last activity, reset to 0
        # User can still come back and complete - it will change to 1 when they finish
        if time_diff > timeout_minutes:
            event_data.loc[event_data['id'] == csv_row_id, 'used'] = 0
            reset_count += 1
```

## Replace With This

```python
        # If >30 minutes since last activity, reset to 0 and set end_time
        # User can still come back and complete - it will change to 1 when they finish
        if time_diff > timeout_minutes:
            event_data.loc[event_data['id'] == csv_row_id, 'used'] = 0
            reset_count += 1
            
            # Set end_time to last action time (if actions exist)
            if not user.end_time:  # Only set if not already set
                if last_action:
                    # Calculate last action time: start_time + sum of all decision_times
                    all_actions = ExperimentAction.objects.filter(user_id=user.user_id).order_by('id')
                    total_decision_time = sum(a.decision_time for a in all_actions)  # seconds
                    
                    start_time = user.start_time
                    if isinstance(start_time, str):
                        start_time = datetime.datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                    if start_time.tzinfo:
                        start_time = start_time.replace(tzinfo=None)
                    
                    last_action_time = start_time + datetime.timedelta(seconds=total_decision_time)
                    user.end_time = last_action_time.isoformat()
                    user.save()
                else:
                    # No actions - set to start_time
                    user.end_time = user.start_time.isoformat() if isinstance(user.start_time, str) else str(user.start_time)
                    user.save()
```

## What Changed

**BEFORE:** Only reset CSV row from `used=0.5` → `used=0`

**AFTER:** Reset CSV row AND set `end_time` to last action time

## Verification

After making the change, verify it's correct:

```bash
grep -A 20 "Set end_time to last action time" Experiment_Code/experiment/views.py
```

You should see the code block above.

## That's It!

This is the ONLY change needed. No paths, no other files, just this one addition to set `end_time` when abandoned users timeout.


