"""
Export database to CSV files - For use with: python manage.py shell < export_db_to_csv_shell.py
Or copy-paste into Django shell
"""

import csv
import os
from experiment.models import ExperimentData, ExperimentAction, TOASTResponse
from django.conf import settings

data_dir = os.path.join(settings.BASE_DIR, 'data')
os.makedirs(data_dir, exist_ok=True)

print("=" * 60)
print("EXPORTING DATABASE TO CSV")
print("=" * 60)

# Export ExperimentData
print("\n📊 Exporting experiment_data.csv...")
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
            user.end_time.isoformat() if user.end_time else ''
        ])
print(f"   ✅ Exported {ExperimentData.objects.count()} users")

# Export ExperimentAction
print("\n📝 Exporting experiment_actions.csv...")
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
print(f"   ✅ Exported {ExperimentAction.objects.count()} actions")

# Export TOAST
print("\n📋 Exporting TOAST.csv...")
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
print(f"   ✅ Exported {TOASTResponse.objects.count()} TOAST responses")

print("\n" + "=" * 60)
print("✅ EXPORT COMPLETE!")
print(f"📁 Files saved to: {data_dir}")
print("=" * 60)


