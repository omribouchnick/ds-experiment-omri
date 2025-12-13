from django.contrib.sessions.models import Session
from django.shortcuts import render, redirect
from django.http import HttpResponseForbidden
import requests
import pandas as pd
import random
import datetime
from .models import *


def load_block_trials(ps: float, human_sensitivity: float, system_sensitivity: float) -> dict:
    # Updated to use new CSV format with 120 trials
    event_data = pd.read_csv("data/conditions_experiment_3ps_11x11_120_A.csv")
    generated_data = event_data[(event_data['ps'] == ps) &
                                (event_data['dprime_h'] == human_sensitivity) &
                                (event_data['dprime_s'] == system_sensitivity)].copy()
    data_dict = {1: {}, 2: {}, 3: {}}
    
    # Load all blocks from CSV
    for index, row in generated_data.iterrows():
         # Block 1: Use first 10 trials from CSV (no DS shown, but data loaded)
         for event_number in range(1, 11):
             if event_number < 10:
                 event_number_str = f'0{event_number}'
             else:
                 event_number_str = f'{event_number}'
             event_type = row[f'event_t{event_number_str}']
             human_stimulus = row[f'h_t{event_number_str}']
             system_stimulus = row[f's_t{event_number_str}']
             system_judgment = int(row[f'ds_dec_t{event_number_str}'])
             data_dict[1][int(event_number)] = {'event': event_type,
                                                'stimuli': human_stimulus,
                                                'ds_stimuli': system_stimulus,
                                                'ds_judgment': system_judgment}
         
         # Block 2: Use first 10 trials from CSV (with DS)
         for event_number in range(1, 11):
             if event_number < 10:
                 event_number_str = f'0{event_number}'
             else:
                 event_number_str = f'{event_number}'
             event_type = row[f'event_t{event_number_str}']
             human_stimulus = row[f'h_t{event_number_str}']
             system_stimulus = row[f's_t{event_number_str}']
             system_judgment = int(row[f'ds_dec_t{event_number_str}'])
             data_dict[2][int(event_number)] = {'event': event_type,
                                                'stimuli': human_stimulus,
                                                'ds_stimuli': system_stimulus,
                                                'ds_judgment': system_judgment}
         
         # Block 3: Use first 100 trials from CSV (with DS)
         for event_number in range(1, 101):
             if event_number < 10:
                 event_number_str = f'0{event_number}'
             else:
                 event_number_str = f'{event_number}'
             event_type = row[f'event_t{event_number_str}']
             human_stimulus = row[f'h_t{event_number_str}']
             system_stimulus = row[f's_t{event_number_str}']
             system_judgment = int(row[f'ds_dec_t{event_number_str}'])
             data_dict[3][int(event_number)] = {'event': event_type,
                                                'stimuli': human_stimulus,
                                                'ds_stimuli': system_stimulus,
                                                'ds_judgment': system_judgment}
         break  # Only process first matching row
    return data_dict


def landing_page(request):
    request.session["ps"] = random.choice([0.2, 0.35, 0.5])
    request.session["human_sensitivity"] = random.choice([0.5, 0.7, 0.9, 1.1, 1.3, 1.5, 1.7, 1.9, 2.1, 2.3, 2.5])
    request.session["ds_sensitivity"] = random.choice([0.5, 0.7, 0.9, 1.1, 1.3, 1.5, 1.7, 1.9, 2.1, 2.3, 2.5])
    request.session["block_scores"] = {}
    request.session["events_data"] = load_block_trials(request.session["ps"],
                                                       request.session["human_sensitivity"],
                                                       request.session["ds_sensitivity"])
    request.session["aid"] = request.GET.get("aid", "test")
    request.session["experiment_start_time"] = datetime.datetime.now().isoformat()

    # Create an ExperimentData entry for the participant
    if 'user_id' not in request.session:  # Ensure we don't create a new entry every time
        experiment_data = ExperimentData.objects.create(
            aid=request.session["aid"],
            ps=request.session["ps"],
            human_sensitivity=request.session["human_sensitivity"],
            ds_sensitivity=request.session["ds_sensitivity"]
        )
        request.session["user_id"] = experiment_data.user_id
    if request.method == "POST":
        if request.POST['Continue'] == 'continue':
            return redirect('/consent_form/')
    return render(request, 'landing_page.html')


# View for the consent form page
def consent_form(request):
    if request.method == "POST":
        if request.POST['Continue'] == 'begin_experiment':
            request.session["current_screen"] = 1
            return redirect('/recaptcha/')
        elif request.POST['Continue'] == 'end_experiment':
            return redirect('/end/')  # Redirect to the instruction page (replace with actual URL name)

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
    context = {
        "screen": current_screen, 'ds_sensitivity': request.session["ds_sensitivity"],
        "v_tp": 1, "v_fp": 1, "v_tn": 1, "v_fn": 2,
    }
    if request.method == "POST":
        if request.POST['Continue'] == 'continue':
            request.session["current_screen"] += 1
        elif request.POST['Continue'] == 'back':
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
    action_count = ExperimentAction.objects.filter(user_id=request.session["user_id"]).count()
    if action_count >= 120:
        participant = ExperimentData.objects.get(user_id=request.session["user_id"])
        participant.complete = True
        request.session["complete"] = True
    else:
        participant = ExperimentData.objects.get(user_id=request.session["user_id"])
        participant.complete = False
        request.session["complete"] = False
    exp_start_time = datetime.datetime.fromisoformat(request.session["experiment_start_time"])
    exp_end_time = datetime.datetime.now().isoformat()
    exp_time = (datetime.datetime.now() - exp_start_time).total_seconds()
    participant.end_time = exp_end_time

    # Save changes to DB
    participant.save()

    aid = request.session["aid"]

    context = {
        'aid': aid,
        'finish': request.session["complete"],
    }
    return render(request, 'end.html', context)



# Debug: Check what's in the session
print(f"DEBUG: block={request.session.get('block')}, trial={request.session.get('trial')}")
print(f"DEBUG: events_data keys: {list(request.session.get('events_data', {}).keys())}")
if str(request.session.get('block')) in request.session.get('events_data', {}):
    print(f"DEBUG: Block {request.session.get('block')} trials: {list(request.session['events_data'][str(request.session['block'])].keys())}")

def game(request):
    if request.method == "GET":
        request.session['screen_entry_time'] = datetime.datetime.now().isoformat()

    if request.session["block"] <= 2 and request.session["trial"] > 10:  # Blocks 1 & 2 have 10 trials each
        if request.session["block"] == 1:
            request.session["block_scores"][1] = [request.session["score"], False]
        if request.session["block"] == 2:
            request.session["block_scores"][2] = [request.session["score"], True]
        else:
            request.session["block_scores"][2] = [request.session["score"], True]
        return redirect('/instructions/')
    elif request.session["block"] == 3 and request.session["trial"] > 100:  # Block 3 has 100 trials
        request.session["block_scores"][3] = [request.session["score"], request.session["pd"]]
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
        if request.POST['Classification'] == 'signal' and event_type == 'signal':
            request.session["score"] += 3
        if request.POST['Classification'] == 'noise' and event_type == 'noise':
            request.session["score"] += 3
        if request.POST['Classification'] == 'noise' and event_type == 'signal':
            request.session["score"] -= 6
        if request.POST['Classification'] == 'signal' and event_type == 'noise':
            request.session["score"] -= 3

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
        users_df.to_csv('data/experiment_data.csv', index=False)

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
        actions_df.to_csv('data/experiment_actions.csv', index=False)

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
        actions_df.to_csv('data/TOAST.csv', index=False)

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
