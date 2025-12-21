# Fix Duplicate Code in views.py

## Problem
The `end_time` calculation code is duplicated in the `else` block. You have it twice - once right after setting `complete = False`, and again after the first `participant.save()`.

## Solution
Remove the duplicate. Keep only ONE copy of the end_time calculation.

## Correct Code (remove the duplicate section):

```python
    # Check if TOAST questionnaire was completed
    has_toast_response = TOASTResponse.objects.filter(user_id=request.session["user_id"]).exists()
    
    # User is complete ONLY if both conditions are met
    if action_count >= 120 and has_toast_response:
        participant.complete = True
        request.session["complete"] = True
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
        
        # Reset CSV row from 0.5 back to 0 so it can be reused
        if participant.csv_row_id:
            mark_row_as_available(participant.csv_row_id)
        
        aid = request.session.get("aid", "test")
        return redirect(f'https://app.cloudresearch.com/Router/ThankYouTerm?aid={aid}')
    
    # Only complete users reach here - update end_time and show completion page
    exp_start_time = datetime.datetime.fromisoformat(request.session["experiment_start_time"])
    exp_end_time = datetime.datetime.now().isoformat()
    participant.end_time = exp_end_time
    participant.save()
```

## What to Remove
Delete this entire duplicate section (it appears after the first `participant.save()`):

```python
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

Keep only the FIRST occurrence (right after `request.session["complete"] = False`).


