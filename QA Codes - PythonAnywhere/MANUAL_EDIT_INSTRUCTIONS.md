# Manual Edit Instructions for views.py on PythonAnywhere

## Step-by-Step Instructions

1. **Open the file on PythonAnywhere:**
   ```bash
   nano ~/ds-experiment-omri/Experiment_Code/experiment/views.py
   ```
   Or use the PythonAnywhere file editor in the web interface.

2. **Find the `end()` function** - search for `def end(request):` (around line 452)

3. **Find this OLD code block** (around lines 471-476):
   ```python
    else:
        # Incomplete user - mark as incomplete and reset CSV row to available
        participant.complete = False
        request.session["complete"] = False
        participant.end_time = datetime.datetime.now().isoformat()
        participant.save()
   ```

4. **Replace it with this NEW code:**
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

5. **Save the file** (Ctrl+X, then Y, then Enter if using nano)

6. **Reload the web app** in PythonAnywhere's Web tab (click the green reload button)

## What Changed?

**BEFORE:** Incomplete users got `end_time = current time` (when they visited end page)

**AFTER:** Incomplete users get `end_time = start_time + sum(decision_times)` (their actual last action time)

## Verification

After making the change, test with a new incomplete user - their `end_time` should match their last action time, not the time they visited the end page.

