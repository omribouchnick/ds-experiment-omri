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
from .models import *


def load_block_trials(csv_row_id=None) -> tuple:
    """
    Load trial data from CSV for a user.
    - If csv_row_id provided: load that specific row
    - If not: select unused row, or cycle through if all used
    
    Returns: (data_dict, row_id, ps, dprime_h, dprime_s) where:
        - data_dict: all trial data organized by blocks
        - row_id: CSV row ID for tracking
        - ps, dprime_h, dprime_s: values from the selected row
    """
    # Scalar to add to all stimuli values (makes task harder without changing probabilities)
    STIMULI_SCALAR = 6.5
    
    # Load CSV
    csv_path = os.path.join(settings.BASE_DIR, "DATA", "conditions_experiment_3ps_11x11_120_A.csv")
    event_data = pd.read_csv(csv_path)
    
    if csv_row_id:
        # Load specific row
        selected_row = event_data[event_data['id'] == csv_row_id].iloc[0]
        row_id = int(selected_row['id'])
    else:
        # Select new row
        available_rows = event_data[event_data['used'] == 0].copy()
        
        if len(available_rows) > 0:
            # Has unused rows - select randomly
            selected_row = available_rows.sample(n=1).iloc[0]
            row_id = int(selected_row['id'])
        else:
            # All rows used - cycle through (select any row randomly)
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


def mark_row_as_used(user_id: int):
    """
    Mark CSV row as used=1 ONLY when user completes experiment.
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


def landing_page(request):
    # Get aid (keep "test" as-is for local testing - can exclude in analysis)
    aid = request.GET.get("aid", "test")
    
    # Check if user already exists (by aid, not just session!)
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
        request.session["block_scores"] = request.session.get("block_scores", {})
        if "experiment_start_time" not in request.session:
            request.session["experiment_start_time"] = datetime.datetime.now().isoformat()
        
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
        # Incomplete user - mark as incomplete and redirect directly to ThankYouTerm
        participant.complete = False
        request.session["complete"] = False
        participant.end_time = datetime.datetime.now().isoformat()
        participant.save()
        
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
            csv_path = os.path.join(settings.BASE_DIR, 'data', 'devtools_log.csv')
            file_exists = os.path.exists(csv_path)
            with open(csv_path, 'a', newline='') as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(['user_id', 'details', 'timestamp'])
                writer.writerow([user_id, request.body.decode('utf-8'), datetime.datetime.now().isoformat()])
    return JsonResponse({'status': 'ok'})
