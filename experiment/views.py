from django.contrib.sessions.models import Session
from django.shortcuts import render, redirect
from django.http import HttpResponseForbidden
from django.conf import settings
import pandas as pd
import random
import datetime
import os
from .models import *


def load_block_trials() -> tuple:
    """
    Load trial data from CSV for a user.
    Randomly selects ANY row where used=0, then uses that row's ps/dprimes.
    Returns: (data_dict, row_id, ps, dprime_h, dprime_s) where:
        - data_dict: all trial data organized by blocks
        - row_id: CSV row ID for marking as used later
        - ps, dprime_h, dprime_s: values from the selected row
    """
    # Scalar to add to all stimuli values (makes task harder without changing probabilities)
    STIMULI_SCALAR = 6.5
    
    # Load CSV and filter for ANY unused row
    csv_path = os.path.join(settings.BASE_DIR, "data", "conditions_experiment_3ps_11x11_120_A.csv")
    event_data = pd.read_csv(csv_path)
    available_rows = event_data[event_data['used'] == 0].copy()
    
    if len(available_rows) == 0:
        raise ValueError("No available rows with used=0. All conditions have been used!")
    
    # Randomly select one row
    selected_row = available_rows.sample(n=1).iloc[0]
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
    for trial_num in range(1, 101):
        t_str = format_trial_num(trial_num)
        data_dict[3][trial_num] = {
            'event': selected_row[f'event_t{t_str}'],
            'stimuli': float(selected_row[f'h_t{t_str}']) + STIMULI_SCALAR,  # Human evidence from CSV + scalar
            'ds_stimuli': float(selected_row[f's_t{t_str}']) + STIMULI_SCALAR,  # System evidence from CSV + scalar
            'ds_judgment': int(selected_row[f'ds_dec_t{t_str}'])  # DS decision from CSV
        }
    
    return data_dict, row_id, ps, dprime_h, dprime_s


def mark_row_as_used(row_id: int):
    """Mark a CSV row as used=1 after experiment completion."""
    csv_path = os.path.join(settings.BASE_DIR, "data", "conditions_experiment_3ps_11x11_120_A.csv")
    event_data = pd.read_csv(csv_path)
    event_data.loc[event_data['id'] == row_id, 'used'] = 1
    event_data.to_csv(csv_path, index=False)


def landing_page(request):
    # Load data: randomly select ANY unused row, then use its ps/dprimes
    events_data, csv_row_id, ps, dprime_h, dprime_s = load_block_trials()
    
    # Store values from the selected CSV row
    request.session["ps"] = ps
    request.session["human_sensitivity"] = dprime_h
    request.session["ds_sensitivity"] = dprime_s
    request.session["block_scores"] = {}
    request.session["events_data"] = events_data
    request.session["csv_row_id"] = csv_row_id  # Store row ID for marking as used later
    request.session["aid"] = request.GET.get("aid", "test")
    request.session["experiment_start_time"] = datetime.datetime.now().isoformat()

    # Create an ExperimentData entry for the participant
    # Note: complete=False by default (only set to True after questionnaire)
    # If user quits, row stays as used=0 and can be reused
    if 'user_id' not in request.session:  # Ensure we don't create a new entry every time
        experiment_data = ExperimentData.objects.create(
            aid=request.session["aid"],
            ps=request.session["ps"],
            human_sensitivity=request.session["human_sensitivity"],
            ds_sensitivity=request.session["ds_sensitivity"],
            complete=False  # Explicitly set to False (default, but making it clear)
        )
        request.session["user_id"] = experiment_data.user_id
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
    current_screen = request.session.get("current_screen", "1")
    
    # Prevent access to Block 2 instructions (screen 4) before completing Block 1
    if current_screen == 4:
        # Check if Block 1 was completed
        if 'block_scores' not in request.session or 1 not in request.session.get("block_scores", {}):
            # Block 1 not completed, redirect to screen 3 (Scoring System)
            current_screen = 3
            request.session["current_screen"] = 3
    
    context = {
        "screen": current_screen, 'ds_sensitivity': request.session["ds_sensitivity"],
        "v_tp": 1, "v_fp": 1, "v_tn": 1, "v_fn": 2,
    }
    if request.method == "POST":
        if request.POST['Continue'] == 'continue':
            # Prevent going to screen 4 (Block 2) before completing Block 1
            current_screen = request.session.get("current_screen", 1)
            if current_screen == 3:
                # Screen 3 should go to Block 1 game, not screen 4
                # This should not happen as screen 3 has "Start the Experiment" button
                pass
            else:
                request.session["current_screen"] += 1
        elif request.POST['Continue'] == 'back':
            current_screen = request.session.get("current_screen", 1)
            # Prevent going back to screen 4 if Block 1 not completed
            if current_screen == 4 and 'block_scores' in request.session and 1 not in request.session.get("block_scores", {}):
                # Block 1 not completed, can't access Block 2 instructions
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
            block_scores[1] = [request.session["score"], False]
            request.session["current_screen"] = 4  # Go to Block 2 instructions after Block 1
        if request.session["block"] == 2:
            block_scores[2] = [request.session["score"], True]
            request.session["current_screen"] = 6  # Go to Block 3 instructions after Block 2
        else:
            block_scores[2] = [request.session["score"], True]
        request.session["block_scores"] = block_scores
        return redirect('/instructions/')
    elif request.session["block"] == 3 and request.session["trial"] > 100:  # Block 3 has 100 trials
        block_scores = request.session.get("block_scores", {})
        block_scores[3] = [request.session["score"], request.session["pd"]]
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
    experiment_data = ExperimentData.objects.get(user_id=request.session["user_id"])

    if request.method == 'POST':
        request.session["q5"] = request.POST.get('satisfaction')
        request.session["q6"] = request.POST.get('accuracy')
        request.session["q7"] = request.POST.get('consistency')
        request.session["q8"] = request.POST.get('surprised')
        request.session["q9"] = request.POST.get('comfortable')

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
            comfortable=request.session["q9"]
        )
        
        # Mark CSV row as used only after questionnaire completion
        # This ensures incomplete sessions keep the row available (used=0)
        if 'csv_row_id' in request.session:
            mark_row_as_used(request.session['csv_row_id'])
            print(f"DEBUG: Marked CSV row {request.session['csv_row_id']} as used=1 (session completed)")

        return redirect('/end/')

    return render(request, 'toast_2.html')


def save_db(request):
    if request.session['authenticated']:
        users_dict = {}
        for idx, user in enumerate(ExperimentData.objects.all()):
            users_dict[idx] = [user.user_id, user.aid, user.ps, user.human_sensitivity, user.ds_sensitivity, user.start_time,
                               user.complete, user.end_time]

        users_df = pd.DataFrame.from_dict(users_dict, orient='index',
                                          columns=['user_id', 'aid', 'ps', 'human_sensitivity', 'ds_sensitivity',
                                                   'start_time', 'complete', 'end_time'])
        users_df.to_csv(os.path.join(settings.BASE_DIR, 'data', 'experiment_data.csv'), index=False)

        # ---- ExperimentAction ----
        actions_dict = {}
        for idx, action in enumerate(ExperimentAction.objects.all()):
            actions_dict[idx] = [
                action.user_id.user_id,
                action.block_number,
                action.trial_number,
                action.classification_decision,
                action.stimulus_seen,
                action.dss_judgment,
                action.decision_time,
                action.correct_classification
            ]

        actions_df = pd.DataFrame.from_dict(actions_dict, orient='index',
                                            columns=['user_id', 'block_number', 'trial_number',
                                                     'classification_decision',
                                                     'stimulus_seen', 'dss_judgment',
                                                     'decision_time', 'correct_classification'])
        actions_df.to_csv(os.path.join(settings.BASE_DIR, 'data', 'experiment_actions.csv'), index=False)

        # ---- TOAST ----
        actions_dict = {}
        for idx, action in enumerate(TOASTResponse.objects.all()):
            actions_dict[idx] = [
                action.user_id.user_id,
                action.usefulness,
                action.reliability,
                action.trust,
                action.confidence,
                action.satisfaction,
                action.predictability,
                action.predictability,
                action.surprised,
                action.comfortable
            ]

        actions_df = pd.DataFrame.from_dict(actions_dict, orient='index',
                                            columns=['user_id', 'q1', 'q2', 'q3', 'q4',
                                                     'q5', 'q6', 'q7', 'q8', 'q9'])
        actions_df.to_csv(os.path.join(settings.BASE_DIR, 'data', 'TOAST.csv'), index=False)

        return redirect('/login/')
    else:
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
