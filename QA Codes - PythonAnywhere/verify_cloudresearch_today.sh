#!/bin/bash
# CLOUDRESEARCH USERS VALIDATION - Today's pilot users
# Validates: Trials, TOAST, CSV matching, completion status
# Usage: bash verify_cloudresearch_today.sh

cd ~/ds-experiment-omri/Experiment_Code && python3 << 'EOF'
import sqlite3
import pandas as pd
from datetime import datetime, date

conn = sqlite3.connect('DATA/db.sqlite3')
csv_df = pd.read_csv('DATA/conditions_experiment_3ps_11x11_120_A.csv')

print("=" * 100)
print("☁️  CLOUDRESEARCH USERS VALIDATION - TODAY'S PILOT")
print("=" * 100)
print(f"🕒 Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# ============================================================================
# 1. GET TODAY'S CLOUDRESEARCH USERS
# ============================================================================
today = date.today().isoformat()

# Get all users from today that are NOT test users
users = pd.read_sql_query(f"""
    SELECT user_id, aid, csv_row_id, ps, human_sensitivity, ds_sensitivity, 
           complete, start_time, end_time
    FROM experiment_experimentdata
    WHERE DATE(start_time) = '{today}'
      AND aid NOT LIKE 'test%'
      AND aid NOT LIKE '{{%'
    ORDER BY user_id DESC
""", conn)

print(f"\n📊 Found {len(users)} CloudResearch users today ({today})")

if len(users) == 0:
    print("\n⚠️  No CloudResearch users found today!")
    print("   Checking for any recent CloudResearch users...")
    
    # Get last 10 CloudResearch users regardless of date
    users = pd.read_sql_query("""
        SELECT user_id, aid, csv_row_id, ps, human_sensitivity, ds_sensitivity, 
               complete, start_time, end_time
        FROM experiment_experimentdata
        WHERE aid NOT LIKE 'test%'
          AND aid NOT LIKE '{{%'
        ORDER BY user_id DESC
        LIMIT 10
    """, conn)
    print(f"   Found {len(users)} recent CloudResearch users")

# ============================================================================
# 2. DETAILED USER ANALYSIS
# ============================================================================
print("\n" + "=" * 100)
print("📋 DETAILED USER ANALYSIS")
print("=" * 100)

all_valid = True
results = []

for _, u in users.iterrows():
    user_id = u['user_id']
    aid = u['aid']
    csv_row_id = u['csv_row_id']
    
    print(f"\n{'─' * 100}")
    print(f"👤 User {user_id}: {aid[:50]}{'...' if len(aid) > 50 else ''}")
    print(f"{'─' * 100}")
    
    # Basic info
    print(f"   📅 Started: {u['start_time']}")
    print(f"   📅 Ended:   {u['end_time'] if u['end_time'] else 'Not yet'}")
    print(f"   ✅ Complete: {'YES' if u['complete'] else 'NO'}")
    
    # CSV Row info
    print(f"\n   📊 Experiment Parameters:")
    print(f"      CSV Row: {int(csv_row_id) if csv_row_id else 'N/A'}")
    print(f"      ps: {u['ps']}, d'_human: {u['human_sensitivity']}, d'_DS: {u['ds_sensitivity']}")
    
    # Check CSV matching
    if csv_row_id:
        csv_row = csv_df[csv_df['id'] == csv_row_id]
        if len(csv_row) > 0:
            csv_row = csv_row.iloc[0]
            ps_match = u['ps'] == csv_row['ps']
            dh_match = u['human_sensitivity'] == csv_row['dprime_h']
            dds_match = u['ds_sensitivity'] == csv_row['dprime_s']
            used_val = csv_row['used']
            
            print(f"\n   🔍 CSV Validation:")
            print(f"      ps:       DB={u['ps']}, CSV={csv_row['ps']} {'✅' if ps_match else '❌'}")
            print(f"      d'_human: DB={u['human_sensitivity']}, CSV={csv_row['dprime_h']} {'✅' if dh_match else '❌'}")
            print(f"      d'_DS:    DB={u['ds_sensitivity']}, CSV={csv_row['dprime_s']} {'✅' if dds_match else '❌'}")
            print(f"      used:     {used_val} ({'Available' if used_val == 0 else 'In-progress' if used_val == 0.5 else 'Completed'})")
            
            if not (ps_match and dh_match and dds_match):
                all_valid = False
        else:
            print(f"   ❌ CSV row {csv_row_id} not found!")
            all_valid = False
    
    # Get trials
    trials = pd.read_sql_query(f"""
        SELECT COUNT(*) as cnt, 
               MAX(block_number) as max_block, 
               MAX(trial_number) as max_trial
        FROM experiment_experimentaction 
        WHERE user_id_id = {user_id}
    """, conn).iloc[0]
    
    trial_count = int(trials['cnt'])
    max_block = int(trials['max_block']) if trials['max_block'] else 0
    max_trial = int(trials['max_trial']) if trials['max_trial'] else 0
    
    print(f"\n   📈 Progress:")
    print(f"      Trials: {trial_count}/120")
    print(f"      Current: Block {max_block}, Trial {max_trial}")
    
    if trial_count > 0:
        # Get accuracy
        actions = pd.read_sql_query(f"""
            SELECT classification_decision, correct_classification, dss_judgment
            FROM experiment_experimentaction 
            WHERE user_id_id = {user_id}
        """, conn)
        
        correct = (actions['classification_decision'] == actions['correct_classification']).sum()
        agreed = (actions['classification_decision'] == actions['dss_judgment']).sum()
        
        print(f"      Accuracy: {100*correct/trial_count:.1f}% ({correct}/{trial_count})")
        print(f"      DS Agreement: {100*agreed/trial_count:.1f}% ({agreed}/{trial_count})")
    
    # Check TOAST
    toast = pd.read_sql_query(f"""
        SELECT * FROM experiment_toast_toastresponse WHERE user_id_id = {user_id}
    """, conn)
    
    print(f"\n   📝 TOAST Questionnaire:")
    if len(toast) > 0:
        t = toast.iloc[0]
        print(f"      ✅ Completed!")
        print(f"      Usefulness: {t['usefulness']}, Reliability: {t['reliability']}, Trust: {t['trust']}")
        print(f"      Confidence: {t['confidence']}, Satisfaction: {t['satisfaction']}")
        print(f"      Age: {t['age']}, Gender: {t['gender']}, Education: {t['education']}")
    else:
        print(f"      ❌ Not completed")
        if u['complete']:
            print(f"      ⚠️  WARNING: User marked complete but no TOAST!")
            all_valid = False
    
    # Summary for this user
    status = "✅ VALID" if (trial_count == 120 and len(toast) > 0 and u['complete']) else \
             "🔄 IN PROGRESS" if trial_count > 0 else \
             "⏳ NOT STARTED"
    
    results.append({
        'ID': user_id,
        'AID': aid[:30],
        'Trials': trial_count,
        'TOAST': '✅' if len(toast) > 0 else '❌',
        'Complete': '✅' if u['complete'] else '❌',
        'Status': status
    })

# ============================================================================
# 3. SUMMARY TABLE
# ============================================================================
print("\n" + "=" * 100)
print("📊 SUMMARY TABLE")
print("=" * 100)

results_df = pd.DataFrame(results)
print(f"\n{'ID':<6} {'AID':<32} {'Trials':<10} {'TOAST':<7} {'Complete':<10} {'Status'}")
print("-" * 100)
for _, r in results_df.iterrows():
    print(f"{r['ID']:<6} {r['AID']:<32} {r['Trials']:<10} {r['TOAST']:<7} {r['Complete']:<10} {r['Status']}")

# ============================================================================
# 4. STATISTICS
# ============================================================================
print("\n" + "=" * 100)
print("📈 STATISTICS")
print("=" * 100)

completed = len([r for r in results if r['Status'] == "✅ VALID"])
in_progress = len([r for r in results if r['Status'] == "🔄 IN PROGRESS"])
not_started = len([r for r in results if r['Status'] == "⏳ NOT STARTED"])

print(f"\n   ✅ Completed:    {completed}")
print(f"   🔄 In Progress:  {in_progress}")
print(f"   ⏳ Not Started:  {not_started}")
print(f"   📊 Total:        {len(results)}")

if completed > 0:
    completed_trials = [r['Trials'] for r in results if r['Status'] == "✅ VALID"]
    print(f"\n   Average trials (completed): {sum(completed_trials)/len(completed_trials):.0f}")

# ============================================================================
# 5. FINAL VERDICT
# ============================================================================
print("\n" + "=" * 100)
if all_valid and completed > 0:
    print("🎉 ALL CLOUDRESEARCH USERS DATA IS VALID!")
elif completed == 0 and in_progress > 0:
    print("🔄 USERS STILL IN PROGRESS - CHECK BACK LATER")
elif not all_valid:
    print("⚠️  SOME VALIDATION ISSUES FOUND - REVIEW ABOVE")
else:
    print("⏳ NO COMPLETED USERS YET")
print("=" * 100)

conn.close()
EOF


