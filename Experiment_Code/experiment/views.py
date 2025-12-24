from django.contrib.sessions.models import Session
from django.shortcuts import render, redirect
from django.http import HttpResponseForbidden, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import csv
import pandas as pd
import random
import datetime
import os
import uuid
import logging
from .models import *

# FileLock for atomic CSV operations - prevents race conditions
# Install: pip install filelock
from filelock import FileLock, Timeout

# Set up logging
logger = logging.getLogger(__name__)


def log_landing_attempt(request, aid, source):
    """
    Log EVERY landing page attempt to a CSV file for debugging.
    This runs BEFORE any database operations, so we can see all attempts.
    """
    try:
        log_path = os.path.join(settings.BASE_DIR, 'DATA', 'landing_attempts.csv')
        file_exists = os.path.exists(log_path)
        
        # Get all URL parameters for debugging
        all_params = dict(request.GET)
        
        with open(log_path, 'a', newline='') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(['timestamp', 'aid', 'source', 'ip', 'user_agent', 'referer', 'all_params'])
            writer.writerow([
                datetime.datetime.now().isoformat(),
                aid,
                source,
                request.META.get('REMOTE_ADDR', 'unknown'),
                request.META.get('HTTP_USER_AGENT', 'unknown')[:100],
                request.META.get('HTTP_REFERER', 'none')[:100] if request.META.get('HTTP_REFERER') else 'none',
                str(all_params)[:200]
            ])
    except Exception as e:
        logger.error(f"Failed to log landing attempt: {e}")


def load_block_trials(csv_row_id=None) -> tuple:
    """
    Load trial data from CSV for a user.
    FIXED: Uses FileLock for atomic row selection to prevent race conditions.
    
    - If csv_row_id provided: load that specific row (returning user)
    - If not: select unused row atomically with FileLock
    
    Returns: (data_dict, row_id, ps, dprime_h, dprime_s) where:
        - data_dict: all trial data organized by blocks
        - row_id: CSV row ID for tracking
        - ps, dprime_h, dprime_s: values from the selected row
    """
    # Scalar to add to all stimuli values (makes task harder without changing probabilities)
    STIMULI_SCALAR = 6.5
    
    # === SINGLE CSV with corrected 'used' column ===
    # - used=1: Already completed (~294 rows)
    # - used=0: Never completed (69 rows) - these will be assigned to new users
    # - used=0.5: Currently in progress
    csv_path = os.path.join(settings.BASE_DIR, "DATA", "conditions_experiment_3ps_11x11_120_A.csv")
    lock_path = csv_path + ".lock"  # Lock file for atomic operations
    
    # Verify path exists
    if not os.path.exists(csv_path):
        logger.error(f"CRITICAL: CSV file not found at {csv_path}")
        raise FileNotFoundError(f"CSV file not found: {csv_path}")
    
    if csv_row_id:
        # RETURNING USER - load their specific row
        event_data = pd.read_csv(csv_path)
        logger.debug(f"Loaded CSV with {len(event_data)} rows")
        
        matching_rows = event_data[event_data['id'] == csv_row_id]
        if len(matching_rows) == 0:
            logger.error(f"CRITICAL: CSV row {csv_row_id} not found in CSV!")
            raise ValueError(f"CSV row {csv_row_id} not found")
        selected_row = matching_rows.iloc[0]
        row_id = int(selected_row['id'])
        logger.debug(f"Loaded specific row {row_id} for returning user")
    else:
        # NEW USER - ATOMIC selection with FileLock to prevent race conditions
        # =====================================================================
        # csv_path already defined above - use the same CSV for all users
        try:
            with FileLock(lock_path, timeout=30):  # Wait up to 30 seconds for lock
                event_data = pd.read_csv(csv_path)
                
                fresh_rows = event_data[event_data['used'] == 0].copy()
                in_progress_rows = event_data[event_data['used'] == 0.5].copy()
                completed_rows = event_data[event_data['used'] == 1].copy()
                
                logger.info(f"Row availability: fresh={len(fresh_rows)}, in_progress={len(in_progress_rows)}, completed={len(completed_rows)}")
                
                if len(fresh_rows) > 0:
                    # Fresh rows available - select one
                    selected_row = fresh_rows.sample(n=1).iloc[0]
                    row_id = int(selected_row['id'])
                    
                    # Mark as in-progress IMMEDIATELY (still inside lock!)
                    event_data.loc[event_data['id'] == row_id, 'used'] = 0.5
                    event_data.to_csv(csv_path, index=False)
                    
                    logger.info(f"Selected fresh row {row_id} and marked as 0.5 (ATOMIC)")
                elif len(in_progress_rows) > 0:
                    # No fresh rows - use in-progress (someone might have abandoned)
                    selected_row = in_progress_rows.sample(n=1).iloc[0]
                    row_id = int(selected_row['id'])
                    logger.warning(f"Selected in-progress row {row_id} (no fresh rows!)")
                else:
                    # All rows completed (used=1) - recycle any row
                    if len(event_data) == 0:
                        logger.error("CRITICAL: CSV has no rows!")
                        raise ValueError("CSV file is empty")
                    selected_row = event_data.sample(n=1).iloc[0]
                    row_id = int(selected_row['id'])
                    logger.warning(f"RECYCLING completed row {row_id} (all rows used!)")
                    
        except Timeout:
            # Lock timeout - log error and use fallback (rare edge case)
            logger.error("FileLock timeout after 30 seconds - selecting random row without lock")
            event_data = pd.read_csv(csv_path)
            selected_row = event_data.sample(n=1).iloc[0]
            row_id = int(selected_row['id'])
    
    # Extract ps and dprimes from the selected row
    ps = float(selected_row['ps'])
    dprime_h = float(selected_row['dprime_h'])
    dprime_s = float(selected_row['dprime_s'])
    
    # Load all 120 trials at once from this row
    data_dict = {1: {}, 2: {}, 3: {}}
    
    # Helper function to format trial number
    def format_trial_num(n):
        return f'0{n}' if n < 10 else f'{n}'
    
    # Block 1: Trials 1-10 (no DS shown)
    for trial_num in range(1, 11):
        t_str = format_trial_num(trial_num)
        data_dict[1][trial_num] = {
            'event': selected_row[f'event_t{t_str}'],
            'stimuli': float(selected_row[f'h_t{t_str}']) + STIMULI_SCALAR,  # Human evidence from CSV + scalar
            'ds_stimuli': float(selected_row[f's_t{t_str}']) + STIMULI_SCALAR,  # System evidence from CSV + scalar
            'ds_judgment': int(selected_row[f'ds_dec_t{t_str}'])  # DS decision from CSV
        }
    
    # Block 2: Trials 11-20 (with DS shown)
    for trial_num in range(11, 21):
        block_trial_num = trial_num - 10  # Block 2 trial numbers: 1-10
        t_str = format_trial_num(trial_num)
        data_dict[2][block_trial_num] = {
            'event': selected_row[f'event_t{t_str}'],
            'stimuli': float(selected_row[f'h_t{t_str}']) + STIMULI_SCALAR,  # Human evidence from CSV + scalar
            'ds_stimuli': float(selected_row[f's_t{t_str}']) + STIMULI_SCALAR,  # System evidence from CSV + scalar
            'ds_judgment': int(selected_row[f'ds_dec_t{t_str}'])  # DS decision from CSV
        }
    
    # Block 3: Trials 1-100 (with DS shown)
    # IMPORTANT: Use CSV columns event_t21 to event_t120 (NOT event_t01 to event_t100)
    # This ensures no overlap with Block 1 (event_t01-10) and Block 2 (event_t11-20)
    # Mapping: Block 3 trial 1 → CSV column 21, Block 3 trial 100 → CSV column 120
    for trial_num in range(1, 101):
        csv_trial_num = trial_num + 20  # Map Block 3 trial 1-100 to CSV columns 21-120
        t_str = format_trial_num(csv_trial_num)
        data_dict[3][trial_num] = {
            'event': selected_row[f'event_t{t_str}'],
            'stimuli': float(selected_row[f'h_t{t_str}']) + STIMULI_SCALAR,  # Human evidence from CSV + scalar
            'ds_stimuli': float(selected_row[f's_t{t_str}']) + STIMULI_SCALAR,  # System evidence from CSV + scalar
            'ds_judgment': int(selected_row[f'ds_dec_t{t_str}'])  # DS decision from CSV
        }
    
    return data_dict, row_id, ps, dprime_h, dprime_s


def mark_row_in_progress(csv_row_id: int):
    """
    Mark CSV row as used=0.5 when user STARTS experiment.
    NOTE: This is now handled atomically inside load_block_trials() with FileLock.
    This function is kept for backwards compatibility but should not be called for new users.
    """
    if csv_row_id:
        csv_path = os.path.join(settings.BASE_DIR, "DATA", "conditions_experiment_3ps_11x11_120_A.csv")
        
        if not os.path.exists(csv_path):
            logger.error(f"CRITICAL: CSV not found at {csv_path} in mark_row_in_progress")
            raise FileNotFoundError(f"CSV not found: {csv_path}")
        
        try:
            event_data = pd.read_csv(csv_path)
            old_value = event_data.loc[event_data['id'] == csv_row_id, 'used'].values
            old_value = old_value[0] if len(old_value) > 0 else 'NOT_FOUND'
            
            event_data.loc[event_data['id'] == csv_row_id, 'used'] = 0.5
            event_data.to_csv(csv_path, index=False)
            
            logger.info(f"Marked row {csv_row_id} as in-progress: {old_value} -> 0.5")
        except Exception as e:
            logger.error(f"Failed to mark row {csv_row_id} as in-progress: {e}")
            raise


def mark_row_as_used(user_id: int):
    """
    Mark CSV row as used=1 when user COMPLETES experiment.
    Called from toast_4 (after questionnaire completion).
    """
    experiment_data = ExperimentData.objects.get(user_id=user_id)
    csv_row_id = experiment_data.csv_row_id
    
    if csv_row_id:
        csv_path = os.path.join(settings.BASE_DIR, "DATA", "conditions_experiment_3ps_11x11_120_A.csv")
        event_data = pd.read_csv(csv_path)
        event_data.loc[event_data['id'] == csv_row_id, 'used'] = 1
        
        # Set isDemo: 1 for old users (demo/pilot), 0 for new users (CloudResearch only)
        # Check if aid is from CloudResearch (not 'test' or local)
        aid = experiment_data.aid
        is_demo = 1 if (aid == 'test' or aid.startswith('local_')) else 0
        
        if 'isDemo' not in event_data.columns:
            event_data['isDemo'] = None
        event_data.loc[event_data['id'] == csv_row_id, 'isDemo'] = is_demo
        
        event_data.to_csv(csv_path, index=False)


def mark_row_as_available(csv_row_id: int):
    """
    Mark CSV row as used=0 when user QUITS/ABANDONS experiment.
    This makes the row available for future users.
    Called when incomplete user is detected.
    """
    if csv_row_id:
        csv_path = os.path.join(settings.BASE_DIR, "DATA", "conditions_experiment_3ps_11x11_120_A.csv")
        event_data = pd.read_csv(csv_path)
        # Only reset if it's in_progress (0.5), not if already completed (1)
        current_value = event_data.loc[event_data['id'] == csv_row_id, 'used'].values[0]
        if current_value == 0.5:
            event_data.loc[event_data['id'] == csv_row_id, 'used'] = 0
            event_data.to_csv(csv_path, index=False)


def _reset_abandoned_rows():
    """
    Auto-timeout: Reset CSV rows that have been in-progress (used=0.5) for >30 minutes.
    Only checks users with used=0.5 rows (not all incomplete users).
    Called on landing_page() - when user 100 arrives, it checks if user 99's row should be reset.
    """
    csv_path = os.path.join(settings.BASE_DIR, "DATA", "conditions_experiment_3ps_11x11_120_A.csv")
    event_data = pd.read_csv(csv_path)
    
    # Only check rows that are currently 0.5 (in-progress)
    in_progress_rows = event_data[event_data['used'] == 0.5]
    
    if len(in_progress_rows) == 0:
        return  # No in-progress rows to check
    
    # Get users with these CSV rows
    csv_row_ids = in_progress_rows['id'].tolist()
    incomplete_users = ExperimentData.objects.filter(
        complete=False, 
        csv_row_id__in=csv_row_ids
    )
    
    now = datetime.datetime.now()
    timeout_minutes = 30
    reset_count = 0
    
    for user in incomplete_users:
        csv_row_id = user.csv_row_id
        if csv_row_id is None or csv_row_id not in csv_row_ids:
            continue
        
        # Get last action time (most recent action ID = most recent activity)
        last_action = ExperimentAction.objects.filter(user_id=user.user_id).order_by('-id').first()
        
        if last_action:
            # User has actions - estimate last activity time
            # Sum all decision_times to estimate when they last acted
            all_actions = ExperimentAction.objects.filter(user_id=user.user_id)
            total_decision_time = sum(a.decision_time for a in all_actions)  # seconds
            
            start_time = user.start_time
            if isinstance(start_time, str):
                start_time = datetime.datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            
            # Remove timezone
            if start_time.tzinfo:
                start_time = start_time.replace(tzinfo=None)
            if now.tzinfo:
                now_naive = now.replace(tzinfo=None)
            else:
                now_naive = now
            
            # Last activity ≈ start_time + total decision time
            last_activity = start_time + datetime.timedelta(seconds=total_decision_time)
            time_diff = (now_naive - last_activity).total_seconds() / 60  # minutes
        else:
            # No actions yet - use start_time
            start_time = user.start_time
            if isinstance(start_time, str):
                start_time = datetime.datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            
            # Remove timezone
            if start_time.tzinfo:
                start_time = start_time.replace(tzinfo=None)
            if now.tzinfo:
                now_naive = now.replace(tzinfo=None)
            else:
                now_naive = now
            
            time_diff = (now_naive - start_time).total_seconds() / 60  # minutes
        
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
    
    # Save if any changes
    if reset_count > 0:
        event_data.to_csv(csv_path, index=False)


def landing_page(request):
    # ========== STEP 1: GET AID FROM MULTIPLE POSSIBLE PARAMETERS ==========
    # CloudResearch might use different parameter names
    aid = None
    aid_source = "none"
    
    # Check multiple possible parameter names (in priority order)
    aid_param_names = ['aid', 'workerId', 'WORKER_ID', 'worker_id', 'participant_id', 
                       'participantId', 'session_id', 'sessionId', 'prolific_pid', 'PROLIFIC_PID']
    
    for param_name in aid_param_names:
        value = request.GET.get(param_name)
        if value and value != '{{WORKER_ID}}' and not value.startswith('{{'):
            aid = value
            aid_source = param_name
            break
    
    # ========== STEP 2: LOG THIS ATTEMPT IMMEDIATELY (before any DB/CSV ops) ==========
    log_landing_attempt(request, aid if aid else "NO_AID", aid_source)
    
    # ========== STEP 3: CHECK SESSION FOR EXISTING AID (prevents refresh creating new user) ==========
    if not aid and 'aid' in request.session and 'user_id' in request.session:
        # User refreshed the page - restore their AID from session
        aid = request.session['aid']
        aid_source = "session_restore"
        logger.info(f"Restored AID from session: {aid}")
    
    # ========== STEP 4: GENERATE TEST AID IF STILL NONE ==========
    if not aid:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = uuid.uuid4().hex[:6]
        aid = f"test_{timestamp}_{unique_id}"
        logger.info(f"Generated test AID: {aid}")
    else:
        if aid_source != "session_restore":
            logger.info(f"Received AID '{aid}' from parameter '{aid_source}'")
    
    # ========== STEP 4: AUTO-TIMEOUT FOR ABANDONED ROWS ==========
    try:
        _reset_abandoned_rows()
    except Exception as e:
        logger.error(f"Error in _reset_abandoned_rows: {e}")
    # Check if user already exists (by aid, not just session!)
    try:
        experiment_data = ExperimentData.objects.get(aid=aid)
        
        # User exists - check if completed
        if experiment_data.complete:
            # If test user already complete, generate new unique aid
            if aid.startswith("test"):
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                unique_id = uuid.uuid4().hex[:6]
                aid = f"test_{timestamp}_{unique_id}"
                # Raise exception to create new user with new aid
                raise ExperimentData.DoesNotExist
            # Real CloudResearch user who already completed
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
        request.session["block_scores"] = request.session.get("block_scores", {})
        if "experiment_start_time" not in request.session:
            request.session["experiment_start_time"] = datetime.datetime.now().isoformat()
        
    except ExperimentData.DoesNotExist:
        # New user - assign CSV row
        logger.info(f"Creating new user with AID: {aid}")
        
        try:
            events_data, csv_row_id, ps, dprime_h, dprime_s = load_block_trials()
            logger.info(f"Assigned CSV row {csv_row_id} to AID {aid}")
        except Exception as e:
            logger.error(f"CRITICAL: Failed to load_block_trials for AID {aid}: {e}")
            # Log the error to a file for debugging
            error_log_path = os.path.join(settings.BASE_DIR, 'DATA', 'csv_errors.log')
            with open(error_log_path, 'a') as f:
                f.write(f"{datetime.datetime.now().isoformat()} - load_block_trials failed for {aid}: {e}\n")
            raise  # Re-raise so we can see the error
        
        # NOTE: Row marking is now done atomically inside load_block_trials() with FileLock
        # The separate mark_row_in_progress() call is no longer needed and is commented out
        # to prevent the race condition that caused duplicate assignments in the first experiment.
        #
        # OLD CODE (caused race condition):
        # try:
        #     mark_row_in_progress(csv_row_id)
        #     logger.info(f"Marked row {csv_row_id} as in-progress (0.5)")
        # except Exception as e:
        #     logger.error(f"CRITICAL: Failed to mark_row_in_progress for row {csv_row_id}, AID {aid}: {e}")
        #     ...
        logger.info(f"Row {csv_row_id} was marked as 0.5 atomically inside load_block_trials()")
        
        # Create record (use get_or_create to prevent race condition)
        try:
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
            logger.info(f"Created user record: user_id={experiment_data.user_id}, created={created}")
        except Exception as e:
            logger.error(f"CRITICAL: Failed to create ExperimentData for AID {aid}: {e}")
            error_log_path = os.path.join(settings.BASE_DIR, 'DATA', 'csv_errors.log')
            with open(error_log_path, 'a') as f:
                f.write(f"{datetime.datetime.now().isoformat()} - ExperimentData creation failed for {aid}: {e}\n")
            raise
        
        # If not created, someone else created it first - use their data
        if not created:
            # Reset our row back to available since we won't use it
            mark_row_as_available(csv_row_id)
            csv_row_id = experiment_data.csv_row_id
            events_data, _, ps, dprime_h, dprime_s = load_block_trials(csv_row_id=csv_row_id)
            logger.info(f"User already existed, restored from row {csv_row_id}")
        
        # Store in session
        request.session["user_id"] = experiment_data.user_id
        request.session["aid"] = aid
        request.session["ps"] = float(ps)
        request.session["human_sensitivity"] = float(dprime_h)
        request.session["ds_sensitivity"] = float(dprime_s)
        request.session["events_data"] = events_data
        request.session["csv_row_id"] = csv_row_id
        request.session["block_scores"] = {}
        request.session["experiment_start_time"] = datetime.datetime.now().isoformat()
    
    if request.method == "POST":
        if request.POST['Continue'] == 'continue':
            return redirect('/consent_form/')
    return render(request, 'landing_page.html')


# View for the consent form page
# def consent_form(request):
#     if request.method == "POST":
#         if request.POST['Continue'] == 'begin_experiment':
#             request.session["current_screen"] = 1
#             return redirect('/recaptcha/')
#         elif request.POST['Continue'] == 'end_experiment':
#             return redirect('/end/')  # Redirect to the instruction page (replace with actual URL name)

#     return render(request, 'consent_form.html')

def consent_form(request):
    if request.method == "POST":
        if request.POST['Continue'] == 'begin_experiment':
            request.session["current_screen"] = 1
            return redirect('/recaptcha/')
        elif request.POST['Continue'] == 'end_experiment':
            # If user never started (no user_id), redirect directly to CloudResearch
            # without creating a database entry
            if 'user_id' not in request.session:
                aid = request.session.get("aid", "test")
                return redirect(f'https://app.cloudresearch.com/Router/ThankYouTerm?aid={aid}')
            else:
                # If they started but quit, go to end page to mark as incomplete
                return redirect('/end/')

    return render(request, 'consent_form.html')

def recaptcha(request):
    # Skip reCAPTCHA for local testing
    if request.method == 'POST':
        return redirect('/instructions/')
    
    # For local testing, just redirect to instructions
    # Uncomment the verification code below for production
    return redirect('/instructions/')
    
    # PRODUCTION CODE (commented out for local testing):
    # if request.method == 'POST':
    #     response_token = request.POST.get('g-recaptcha-response')
    #     if not response_token:
    #         return render(request, 'form.html', {'error': 'reCAPTCHA not completed.'})
    #
    #     # Verify the token with Google
    #     secret_key = '6LeNJdUrAAAAAFd0vWFtLGbkdxYXQCkM7rfPhnGP'
    #     verify_url = 'https://www.google.com/recaptcha/api/siteverify'
    #     payload = {
    #         'secret': secret_key,
    #         'response': response_token,
    #         'remoteip': request.META.get('REMOTE_ADDR')
    #     }
    #
    #     response = requests.post(verify_url, data=payload)
    #     result = response.json()
    #
    #     if result.get('success'):
    #         return redirect('/instructions/')
    #     else:
    #         return render(request, 'recaptcha.html', {'error': 'Invalid reCAPTCHA. Try again.'})
    # return render(request, 'recaptcha.html')


def instructions(request):
    current_screen = int(request.session.get("current_screen", 1))
    block_scores = request.session.get("block_scores", {})
    
    def _has_block_score(block_number: int) -> bool:
        return block_number in block_scores or str(block_number) in block_scores
    
    # Prevent access to Block 2 instructions (screen 4) before completing Block 1
    if current_screen == 4:
        if not _has_block_score(1):
            current_screen = 3
            request.session["current_screen"] = 3
    
    context = {
        "screen": current_screen,
        'ds_sensitivity': request.session["ds_sensitivity"],
        "v_tp": 1, "v_fp": 1, "v_tn": 1, "v_fn": 2,
    }
    if request.method == "POST":
        if request.POST['Continue'] == 'continue':
            current_screen = int(request.session.get("current_screen", 1))
            if current_screen == 3:
                pass
            else:
                request.session["current_screen"] += 1
        elif request.POST['Continue'] == 'back':
            current_screen = int(request.session.get("current_screen", 1))
            if current_screen == 4 and not _has_block_score(1):
                request.session["current_screen"] = 3
            else:
                request.session["current_screen"] -= 1
        elif request.POST['Continue'] == 'start_block_1':
            request.session["current_screen"] += 1
            request.session["pd"] = False
            request.session["score"] = 30
            request.session["block"] = 1
            request.session["trial"] = 1
            return redirect('/game/')
        elif request.POST['Continue'] == 'start_block_2':
            request.session["current_screen"] += 1
            request.session["pd"] = True
            request.session["score"] = 30
            request.session["block"] = 2
            request.session["trial"] = 1
            return redirect('/game/')
        elif request.POST['Continue'] == 'pd_screen':
            request.session["pd"] = True
            request.session["score"] = 30
            request.session["block"] = 3
            request.session["trial"] = 1
            request.session["default"] = False
            return redirect('/game/')
        return redirect('/instructions/')

    return render(request, "instructions.html", context)


def end(request):
    # If user never started (no user_id), redirect directly to CloudResearch
    if 'user_id' not in request.session:
        aid = request.session.get("aid", "test")
        return redirect(f'https://app.cloudresearch.com/Router/ThankYouTerm?aid={aid}')
    
    # Check if user completed the experiment:
    # 1. Must have 120 actions (all trials completed)
    # 2. Must have completed TOAST questionnaire
    action_count = ExperimentAction.objects.filter(user_id=request.session["user_id"]).count()
    participant = ExperimentData.objects.get(user_id=request.session["user_id"])
    
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

    aid = request.session["aid"]

    context = {
        'aid': aid,
        'finish': request.session["complete"],
    }
    return render(request, 'end.html', context)



def game(request):
    # Debug: Check what's in the session
    print(f"DEBUG: block={request.session.get('block')}, trial={request.session.get('trial')}")
    print(f"DEBUG: events_data keys: {list(request.session.get('events_data', {}).keys())}")
    if str(request.session.get('block')) in request.session.get('events_data', {}):
        print(f"DEBUG: Block {request.session.get('block')} trials: {list(request.session['events_data'][str(request.session['block'])].keys())}")
    
    if request.method == "GET":
        request.session['screen_entry_time'] = datetime.datetime.now().isoformat()

    if request.session["block"] <= 2 and request.session["trial"] > 10:  # Blocks 1 & 2 have 10 trials each
        block_scores = request.session.get("block_scores", {})
        if request.session["block"] == 1:
            block_scores["1"] = [request.session["score"], False]
            request.session["current_screen"] = 4  # Go to Block 2 instructions after Block 1
        if request.session["block"] == 2:
            block_scores["2"] = [request.session["score"], True]
            request.session["current_screen"] = 6  # Go to Block 3 instructions after Block 2
        else:
            block_scores["2"] = [request.session["score"], True]
        request.session["block_scores"] = block_scores
        return redirect('/instructions/')
    elif request.session["block"] == 3 and request.session["trial"] > 100:  # Block 3 has 100 trials
        block_scores = request.session.get("block_scores", {})
        block_scores["3"] = [request.session["score"], request.session["pd"]]
        request.session["block_scores"] = block_scores
        request.session["pd"] = True
        request.session["score"] = 30
        request.session["trial"] = 1
        request.session["default"] = False
        return redirect('/toast_1/')
    elif request.session["block"] == 4 and request.session["trial"] > 120:
        return redirect('/toast_1/')
    event_type = request.session["events_data"][str(request.session["block"])][str(request.session["trial"])]['event']
    ds_judgment = request.session["events_data"][str(request.session["block"])][str(request.session["trial"])][f'ds_judgment']
    stimuli = round(request.session["events_data"][str(request.session["block"])][str(request.session["trial"])]['stimuli'], 2)

    # Block 1: Hide DS (show_ds = False)
    # Block 2 & 3: Show DS (show_ds = True)
    show_ds = request.session["block"] > 1
    
    context = {'pd': request.session["pd"],
               'event_type': event_type,
               'ds_judgment': ds_judgment,
               'stimuli': stimuli,
               'trial': request.session["trial"],
               'score': request.session["score"],
               'block': request.session["block"],
               'show_ds': show_ds}  # Add show_ds flag

    if request.method == "POST":
        entry_time = datetime.datetime.fromisoformat(request.session.get('screen_entry_time'))
        time_spent = (datetime.datetime.now() - entry_time).total_seconds()

        request.session["classification"] = request.POST['Classification']
        # Use correct scoring values: v_tp=1, v_tn=1, v_fn=-2, v_fp=-1
        if request.POST['Classification'] == 'signal' and event_type == 'signal':
            request.session["score"] += 1  # True Positive
        if request.POST['Classification'] == 'noise' and event_type == 'noise':
            request.session["score"] += 1  # True Negative
        if request.POST['Classification'] == 'noise' and event_type == 'signal':
            request.session["score"] -= 2  # False Negative (missed intervention)
        if request.POST['Classification'] == 'signal' and event_type == 'noise':
            request.session["score"] -= 1  # False Positive (unnecessary intervention)

        if 'user_id' in request.session:
            # Get the ExperimentData instance using the user_id
            experiment_data = ExperimentData.objects.get(user_id=request.session["user_id"])
            print(request.session["block"],request.session["trial"])
            # Create or update ExperimentAction (use get_or_create to avoid duplicates)
            ExperimentAction.objects.update_or_create(
                user_id=experiment_data,
                block_number=request.session["block"],
                trial_number=request.session["trial"],
                defaults={
                    'classification_decision': request.session["classification"],
                    'stimulus_seen': stimuli,
                    'dss_judgment': 'signal' if ds_judgment == 1 else 'noise',
                    'decision_time': time_spent,
                    'correct_classification': event_type
                }
            )


            request.session["trial"] += 1
            del request.session['screen_entry_time']

        return redirect('/game/')

    return render(request, 'game.html', context)


def toast_1(request):
    if request.method == 'POST':
        request.session["q1"] = request.POST.get('usefulness')
        request.session["q2"] = request.POST.get('reliability')
        request.session["q3"] = request.POST.get('trust')
        request.session["q4"] = request.POST.get('confidence')

        return redirect('/toast_2/')

    return render(request, 'toast_1.html')

def toast_2(request):
    if request.method == 'POST':
        request.session["q5"] = request.POST.get('satisfaction')
        request.session["q6"] = request.POST.get('accuracy')
        request.session["q7"] = request.POST.get('consistency')
        request.session["q8"] = request.POST.get('surprised')
        request.session["q9"] = request.POST.get('comfortable')
        return redirect('/toast_3/')

    return render(request, 'toast_2.html')

def toast_3(request):
    if request.method == 'POST':
        request.session["numeracy_fractions"] = request.POST.get('numeracy_fractions')
        request.session["numeracy_shirt"] = request.POST.get('numeracy_shirt')
        request.session["numeracy_useful"] = request.POST.get('numeracy_useful')
        return redirect('/toast_4/')

    return render(request, 'toast_3.html')

def toast_4(request):
    experiment_data = ExperimentData.objects.get(user_id=request.session["user_id"])

    if request.method == 'POST':
        TOASTResponse.objects.create(
            user_id=experiment_data,
            usefulness=request.session["q1"],
            reliability=request.session["q2"],
            trust=request.session["q3"],
            confidence=request.session["q4"],
            satisfaction=request.session["q5"],
            predictability=request.session["q6"],
            understandability=request.session["q7"],
            surprised=request.session["q8"],
            comfortable=request.session["q9"],
            numeracy_fractions=request.session["numeracy_fractions"],
            numeracy_shirt=request.session["numeracy_shirt"],
            numeracy_useful=request.session["numeracy_useful"],
            age_group=request.POST.get('age_group'),
            gender=request.POST.get('gender'),
            education=request.POST.get('education')
        )
        
        # Mark CSV row as used ONLY when user completes experiment
        mark_row_as_used(experiment_data.user_id)

        return redirect('/end/')

    return render(request, 'toast_4.html')


def save_db(request):
    if request.session.get('authenticated'):
        data_dir = os.path.join(settings.BASE_DIR, 'data')
        os.makedirs(data_dir, exist_ok=True)

        # ExperimentData export
        users_path = os.path.join(data_dir, 'experiment_data.csv')
        with open(users_path, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['user_id', 'aid', 'ps', 'human_sensitivity', 'ds_sensitivity',
                             'start_time', 'complete', 'end_time'])
            for user in ExperimentData.objects.order_by('user_id'):
                writer.writerow([
                    user.user_id,
                    user.aid,
                    user.ps,
                    user.human_sensitivity,
                    user.ds_sensitivity,
                    user.start_time.isoformat() if user.start_time else '',
                    user.complete,
                    user.end_time if user.end_time else ''
                ])

        # ExperimentAction export
        actions_path = os.path.join(data_dir, 'experiment_actions.csv')
        with open(actions_path, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['user_id', 'block_number', 'trial_number', 'classification_decision',
                             'stimulus_seen', 'dss_judgment', 'decision_time', 'correct_classification'])
            for action in ExperimentAction.objects.order_by('user_id', 'block_number', 'trial_number'):
                writer.writerow([
                    action.user_id.user_id,
                    action.block_number,
                    action.trial_number,
                    action.classification_decision,
                    action.stimulus_seen,
                    action.dss_judgment,
                    action.decision_time,
                    action.correct_classification
                ])

        # TOAST export
        toast_path = os.path.join(data_dir, 'TOAST.csv')
        with open(toast_path, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['user_id', 'usefulness', 'reliability', 'trust', 'confidence',
                             'satisfaction', 'predictability', 'understandability',
                             'surprised', 'comfortable', 'numeracy_fractions', 'numeracy_shirt',
                             'numeracy_useful', 'age_group', 'gender', 'education'])
            for response in TOASTResponse.objects.order_by('user_id'):
                writer.writerow([
                    response.user_id.user_id,
                    response.usefulness,
                    response.reliability,
                    response.trust,
                    response.confidence,
                    response.satisfaction,
                    response.predictability,
                    response.understandability,
                    response.surprised,
                    response.comfortable,
                    response.numeracy_fractions,
                    response.numeracy_shirt,
                    response.numeracy_useful,
                    response.age_group,
                    response.gender,
                    response.education
                ])

        return redirect('/login/')
    return redirect('/login/')

def login(request):
    if request.method == 'POST':
        if request.POST.get('password') == ADMIN_PASSWORD:
            request.session['authenticated'] = True
            return redirect('progress')
        else:
            return render(request, 'password_prompt.html')
    return render(request, 'password_prompt.html')


def progress(request):
    if request.session['authenticated']:

        users_dict = {}
        for idx, user in enumerate(ExperimentData.objects.all()):
            users_dict[idx] = [user.user_id, user.aid, user.ps, user.human_sensitivity, user.ds_sensitivity, user.start_time,
                               user.complete, user.end_time]

        users_df = pd.DataFrame.from_dict(users_dict, orient='index',
                                          columns=['user_id', 'aid', 'ps', 'human_sensitivity', 'ds_sensitivity', 'start_time',
                                                   'complete', 'end_time'])

        users_df = users_df[users_df['complete'] == True]

        return render(request, 'user_progress.html', {
            'total': users_df.shape[0]
        })
    else:
        return redirect('/login/')

def fresh_restart(request):
    if request.session['authenticated']:
        # Step 1: Clear all Experiment-related data
        ExperimentAction.objects.all().delete()
        ExperimentData.objects.all().delete()

        # Step 2: Clear current user's session
        request.session.flush()

        # Step 3: (Optional) Delete all session records in DB (for all users)
        Session.objects.all().delete()
        return redirect('/login/')
    else:
        return redirect('/login/')


@csrf_exempt
def log_devtools(request):
    """Log when user opens DevTools - writes directly to CSV"""
    if request.method == 'POST':
        user_id = request.session.get('user_id')
        if user_id:
            csv_path = os.path.join(settings.BASE_DIR, 'DATA', 'devtools_log.csv')
            file_exists = os.path.exists(csv_path)
            with open(csv_path, 'a', newline='') as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(['user_id', 'details', 'timestamp'])
                writer.writerow([user_id, request.body.decode('utf-8'), datetime.datetime.now().isoformat()])
    return JsonResponse({'status': 'ok'})

