#!/bin/bash
# Show last 3 users with all relevant columns and status
# Usage: bash check_last_3_users_status.sh

cd ~/ds-experiment-omri
source venv/bin/activate

python manage.py shell << 'PYEOF'
from experiment.models import ExperimentData, ExperimentAction, TOASTResponse
from django.db.models import Count
import pandas as pd
import os

print("=" * 80)
print("LAST 3 USERS - COMPLETE STATUS AND ALL COLUMNS")
print("=" * 80)

# Load conditions CSV
conditions_file = 'data/conditions_experiment_3ps_11x11_120_A.csv'
if not os.path.exists(conditions_file):
    conditions_file = 'data/old_data_0912/conditions_experiment_3ps_11x11_120_A.csv'

try:
    conditions_df = pd.read_csv(conditions_file)
except Exception as e:
    print(f"⚠️  Warning: Could not load CSV file: {e}")
    conditions_df = None

# Get last 3 users ordered by user_id (most recent first)
last_3_users = ExperimentData.objects.order_by('-user_id')[:3]

if not last_3_users:
    print("❌ No users found in database")
    exit()

print(f"\nFound {len(last_3_users)} users\n")

for user in last_3_users:
    # Get related data counts
    action_count = ExperimentAction.objects.filter(user_id=user.user_id).count()
    has_toast = TOASTResponse.objects.filter(user_id=user.user_id).exists()
    
    # Status indicator
    status_icon = "✅ COMPLETE" if user.complete else "❌ INCOMPLETE"
    
    print("=" * 80)
    print(f"USER ID: {user.user_id} - {status_icon}")
    print("=" * 80)
    
    # All relevant columns from ExperimentData
    print(f"\n📋 Basic Information:")
    print(f"   user_id:           {user.user_id}")
    print(f"   aid:               {user.aid}")
    print(f"   csv_row_id:        {user.csv_row_id if user.csv_row_id is not None else 'N/A'}")
    print(f"   complete:          {user.complete}")
    print(f"   start_time:        {user.start_time}")
    print(f"   end_time:          {user.end_time if user.end_time else 'N/A'}")
    
    print(f"\n📊 Experiment Parameters:")
    print(f"   ps:                {user.ps if user.ps is not None else 'N/A'}")
    print(f"   human_sensitivity: {user.human_sensitivity if user.human_sensitivity is not None else 'N/A'}")
    print(f"   ds_sensitivity:    {user.ds_sensitivity if user.ds_sensitivity is not None else 'N/A'}")
    
    # Check CSV row data if available
    if conditions_df is not None and user.csv_row_id is not None:
        try:
            csv_row = conditions_df[conditions_df['id'] == user.csv_row_id]
            if len(csv_row) > 0:
                csv_row = csv_row.iloc[0]
                
                print(f"\n📋 CSV Row Information (row_id={user.csv_row_id}):")
                print(f"   ps:                {csv_row['ps']}")
                print(f"   dprime_h:          {csv_row['dprime_h']}")
                print(f"   dprime_s:          {csv_row['dprime_s']}")
                print(f"   used:              {csv_row['used']}")
                print(f"   isDemo:            {csv_row.get('isDemo', 'N/A')}")
                
                # Database vs CSV comparison
                print(f"\n🔍 Database vs CSV Comparison:")
                ps_match = "✅" if user.ps is not None and float(user.ps) == float(csv_row['ps']) else "❌"
                dprime_h_match = "✅" if user.human_sensitivity is not None and float(user.human_sensitivity) == float(csv_row['dprime_h']) else "❌"
                dprime_s_match = "✅" if user.ds_sensitivity is not None and float(user.ds_sensitivity) == float(csv_row['dprime_s']) else "❌"
                
                print(f"   ps:                DB={user.ps}, CSV={csv_row['ps']} {ps_match}")
                print(f"   dprime_h:          DB={user.human_sensitivity}, CSV={csv_row['dprime_h']} {dprime_h_match}")
                print(f"   dprime_s:          DB={user.ds_sensitivity}, CSV={csv_row['dprime_s']} {dprime_s_match}")
                
                # Check used and isDemo status
                print(f"\n🔍 CSV Row Status Checks:")
                if user.complete:
                    used_ok = "✅" if csv_row['used'] == 1 else "❌"
                    print(f"   used:              {csv_row['used']} {used_ok} (should be 1 when complete)")
                    
                    # Check isDemo logic (matches views.py: only 'test' or 'local_' prefix, not 'test_')
                    expected_is_demo = 1 if (user.aid == 'test' or str(user.aid).startswith('local_')) else 0
                    actual_is_demo = csv_row.get('isDemo')
                    if pd.isna(actual_is_demo):
                        is_demo_ok = "❌ NOT SET"
                    else:
                        is_demo_ok = "✅" if actual_is_demo == expected_is_demo else f"❌ (expected {expected_is_demo}, got {actual_is_demo})"
                    print(f"   isDemo:            {actual_is_demo} {is_demo_ok} (expected {expected_is_demo} for aid='{user.aid}')")
                else:
                    used_ok = "✅" if csv_row['used'] == 0 else "⚠️"
                    print(f"   used:              {csv_row['used']} {used_ok} (should be 0 if not complete)")
                    print(f"   isDemo:            {csv_row.get('isDemo', 'N/A')} (will be set when user completes)")
        except Exception as e:
            print(f"\n⚠️  Warning: Could not check CSV row data: {e}")
    
    print(f"\n📈 Progress:")
    print(f"   Total Actions:     {action_count}")
    print(f"   TOAST Response:    {'✅ Yes' if has_toast else '❌ No'}")
    
    # Calculate duration if end_time exists
    if user.end_time and user.start_time:
        duration = user.end_time - user.start_time
        hours = duration.total_seconds() / 3600
        minutes = (duration.total_seconds() % 3600) / 60
        print(f"   Duration:          {int(hours)}h {int(minutes)}m")
    
    # Show TOAST details if exists
    if has_toast:
        toast = TOASTResponse.objects.get(user_id=user.user_id)
        print(f"\n📋 TOAST Questionnaire:")
        print(f"   Usefulness:        {toast.usefulness if toast.usefulness is not None else 'N/A'}")
        print(f"   Reliability:       {toast.reliability if toast.reliability is not None else 'N/A'}")
        print(f"   Trust:             {toast.trust if toast.trust is not None else 'N/A'}")
        print(f"   Confidence:        {toast.confidence if toast.confidence is not None else 'N/A'}")
        print(f"   Satisfaction:      {toast.satisfaction if toast.satisfaction is not None else 'N/A'}")
        print(f"   Predictability:    {toast.predictability if toast.predictability is not None else 'N/A'}")
        print(f"   Understandability: {toast.understandability if toast.understandability is not None else 'N/A'}")
        print(f"   Surprised:         {toast.surprised if toast.surprised is not None else 'N/A'}")
        print(f"   Comfortable:       {toast.comfortable if toast.comfortable is not None else 'N/A'}")
        print(f"   Age Group:         {toast.age_group if toast.age_group else 'N/A'}")
        print(f"   Gender:            {toast.gender if toast.gender else 'N/A'}")
        print(f"   Education:         {toast.education if toast.education else 'N/A'}")
    
    # Action breakdown by block
    if action_count > 0:
        block_counts = ExperimentAction.objects.filter(user_id=user.user_id).values('block_number').annotate(
            count=Count('block_number')
        ).order_by('block_number')
        
        print(f"\n📊 Actions by Block:")
        for block_info in block_counts:
            print(f"   Block {block_info['block_number']}: {block_info['count']} actions")
    
    print()

print("=" * 80)
print("✅ SUMMARY COMPLETE")
print("=" * 80)

exit()
PYEOF

