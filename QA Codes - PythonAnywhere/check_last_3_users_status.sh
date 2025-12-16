#!/bin/bash
# Show last 3 users with all relevant columns, CSV matching, and status
# Usage: bash check_last_3_users_status.sh

cd ~/ds-experiment-omri && python3 << 'EOF'
import sqlite3
import pandas as pd

conn = sqlite3.connect('db.sqlite3')

print("=" * 80)
print("📊 LAST 3 USERS - COMPLETE STATUS CHECK")
print("=" * 80)

# Load conditions CSV
try:
    csv_df = pd.read_csv('DATA/conditions_experiment_3ps_11x11_120_A.csv')
    print(f"✅ CSV loaded: {len(csv_df)} rows")
except Exception as e:
    print(f"❌ Could not load CSV: {e}")
    csv_df = None

# Get last 3 users
users = pd.read_sql_query("""
    SELECT user_id, aid, csv_row_id, ps, human_sensitivity, ds_sensitivity, 
           complete, start_time, end_time
    FROM experiment_experimentdata
    ORDER BY user_id DESC LIMIT 3
""", conn)

if len(users) == 0:
    print("❌ No users found")
    conn.close()
    exit()

print(f"📊 Total users in DB: {pd.read_sql_query('SELECT COUNT(*) as c FROM experiment_experimentdata', conn).iloc[0]['c']}")
print()

for _, u in users.iterrows():
    status = "✅ COMPLETE" if u['complete'] else "❌ INCOMPLETE"
    
    print("=" * 80)
    print(f"USER ID: {u['user_id']} - {status}")
    print("=" * 80)
    
    # Basic info
    print(f"\n📋 BASIC INFO:")
    print(f"   AID:              {u['aid']}")
    print(f"   CSV Row ID:       {u['csv_row_id']}")
    print(f"   Start:            {u['start_time']}")
    print(f"   End:              {u['end_time'] if u['end_time'] else 'N/A'}")
    
    # Parameters from DB
    print(f"\n📊 EXPERIMENT PARAMETERS (from DB):")
    print(f"   ps:               {u['ps']}")
    print(f"   d'_human:         {u['human_sensitivity']}")
    print(f"   d'_DS:            {u['ds_sensitivity']}")
    
    # Compare with CSV
    if csv_df is not None and u['csv_row_id'] is not None:
        try:
            csv_row = csv_df[csv_df['id'] == u['csv_row_id']].iloc[0]
            
            print(f"\n🔍 CSV MATCHING (Row {u['csv_row_id']}):")
            
            # Parameter matching
            ps_match = "✅" if u['ps'] is not None and float(u['ps']) == float(csv_row['ps']) else "❌"
            dh_match = "✅" if u['human_sensitivity'] is not None and float(u['human_sensitivity']) == float(csv_row['dprime_h']) else "❌"
            ds_match = "✅" if u['ds_sensitivity'] is not None and float(u['ds_sensitivity']) == float(csv_row['dprime_s']) else "❌"
            
            print(f"   ps:       DB={u['ps']}, CSV={csv_row['ps']} {ps_match}")
            print(f"   d'_human: DB={u['human_sensitivity']}, CSV={csv_row['dprime_h']} {dh_match}")
            print(f"   d'_DS:    DB={u['ds_sensitivity']}, CSV={csv_row['dprime_s']} {ds_match}")
            
            # CSV status
            print(f"\n📋 CSV ROW STATUS:")
            print(f"   used:     {csv_row['used']}", end="")
            if u['complete']:
                print(f" {'✅' if csv_row['used'] == 1 else '❌ (should be 1)'}")
            else:
                print(f" {'✅' if csv_row['used'] == 0 else '⚠️ (should be 0)'}")
            
            # isDemo check
            expected_demo = 1 if (u['aid'] == 'test' or str(u['aid']).startswith('local_')) else 0
            actual_demo = csv_row.get('isDemo', None)
            if pd.isna(actual_demo):
                demo_status = "❌ NOT SET"
            elif actual_demo == expected_demo:
                demo_status = "✅"
            else:
                demo_status = f"❌ (expected {expected_demo})"
            print(f"   isDemo:   {actual_demo} {demo_status} (aid='{u['aid']}')")
            
        except Exception as e:
            print(f"   ⚠️ Error checking CSV: {e}")
    
    # Actions - correct column names
    actions = pd.read_sql_query(f"""
        SELECT block_number, trial_number, dss_judgment, classification_decision, correct_classification
        FROM experiment_experimentaction
        WHERE user_id_id = {u['user_id']}
        ORDER BY block_number, trial_number
    """, conn)
    
    print(f"\n📈 PROGRESS:")
    print(f"   Total Actions: {len(actions)}")
    
    if len(actions) > 0:
        for block in [1, 2, 3]:
            ba = actions[actions['block_number'] == block]
            if len(ba) > 0:
                correct = (ba['classification_decision'] == ba['correct_classification']).sum()
                agreed = (ba['classification_decision'] == ba['dss_judgment']).sum()
                print(f"   Block {block}: {len(ba)} trials, {correct}/{len(ba)} correct ({100*correct/len(ba):.0f}%), agreed: {agreed}/{len(ba)}")
    
    # TOAST
    toast = pd.read_sql_query(f"""
        SELECT usefulness, reliability, trust, confidence, satisfaction,
               predictability, understandability, surprised, comfortable,
               age_group, gender, education
        FROM experiment_toastresponse WHERE user_id_id = {u['user_id']}
    """, conn)
    
    if len(toast) > 0:
        t = toast.iloc[0]
        print(f"\n📋 TOAST QUESTIONNAIRE: ✅ Completed")
        print(f"   Usefulness: {t['usefulness']}, Reliability: {t['reliability']}, Trust: {t['trust']}")
        print(f"   Confidence: {t['confidence']}, Satisfaction: {t['satisfaction']}")
        print(f"   Age: {t['age_group']}, Gender: {t['gender']}, Education: {t['education']}")
    else:
        print(f"\n📋 TOAST QUESTIONNAIRE: ❌ Not completed")
    
    # DS verification (first 6 trials)
    if len(actions) > 0 and csv_df is not None and u['csv_row_id'] is not None:
        try:
            csv_row = csv_df[csv_df['id'] == u['csv_row_id']].iloc[0]
            print(f"\n🔍 DS VERIFICATION (first 6):")
            all_ok = True
            for _, a in actions.head(6).iterrows():
                block = int(a['block_number'])
                trial = int(a['trial_number'])
                csv_trial = trial if block == 1 else (trial + 10 if block == 2 else trial + 20)
                s_t = csv_row[f's_t{csv_trial:02d}']
                expected = 'signal' if s_t > 0 else 'noise'
                actual = a['dss_judgment']
                match = '✅' if actual == expected else '❌'
                if actual != expected:
                    all_ok = False
                print(f"   B{block}T{trial}: s_t={s_t:.2f} → DS={actual} {match}")
            print(f"   {'✅ ALL CORRECT' if all_ok else '❌ MISMATCHES!'}")
        except:
            pass
    
    print()

conn.close()
print("=" * 80)
print("✅ CHECK COMPLETE")
print("=" * 80)
EOF
