#!/bin/bash
# Summary table of all users with performance metrics
# Usage: bash check_all_users_performance.sh

cd ~/ds-experiment-omri && python3 << 'EOF'
import sqlite3
import pandas as pd
from datetime import datetime

conn = sqlite3.connect('db.sqlite3')

print("=" * 175)
print("📊 ALL USERS PERFORMANCE SUMMARY")
print("=" * 175)

# Get all users
users = pd.read_sql_query("""
    SELECT user_id, aid, csv_row_id, ps, human_sensitivity, ds_sensitivity, 
           complete, start_time, end_time
    FROM experiment_experimentdata
    ORDER BY user_id
""", conn)

if len(users) == 0:
    print("❌ No users found")
    conn.close()
    exit()

# Prepare results
results = []

for _, u in users.iterrows():
    # Get actions
    actions = pd.read_sql_query(f"""
        SELECT block_number, trial_number, stimulus_seen, dss_judgment, 
               classification_decision, correct_classification, decision_time
        FROM experiment_experimentaction
        WHERE user_id_id = {u['user_id']}
        ORDER BY block_number, trial_number
    """, conn)
    
    # Get TOAST
    toast = pd.read_sql_query(f"""
        SELECT usefulness, reliability, trust, confidence, satisfaction
        FROM experiment_toastresponse
        WHERE user_id_id = {u['user_id']}
    """, conn)
    
    # Truncate AID for display
    aid_short = str(u['aid'])[:12] + '..' if len(str(u['aid'])) > 14 else str(u['aid'])
    
    row = {
        'ID': u['user_id'],
        'aid': aid_short,
        'csv': u['csv_row_id'],
        'ps': u['ps'],
        'd_h': u['human_sensitivity'],
        'd_DS': u['ds_sensitivity'],
        'trials': len(actions),
        'last': '-',
        'correct': 0,
        'acc': 0,
        'ds_agree': 0,
        'hit_rate': 0,
        'fa_rate': 0,
        'f1': 0,
        'rt_ms': 0,
        'time_min': 0,
        'time_type': '',  # '' = actual, '~' = estimated from RT
        'toast': '-',
        'complete': '✅' if u['complete'] else '❌'
    }
    
    # TOAST status
    if len(toast) > 0:
        t = toast.iloc[0]
        row['toast'] = f"{int(t['usefulness']) if pd.notna(t['usefulness']) else '-'}/{int(t['reliability']) if pd.notna(t['reliability']) else '-'}/{int(t['trust']) if pd.notna(t['trust']) else '-'}/{int(t['confidence']) if pd.notna(t['confidence']) else '-'}/{int(t['satisfaction']) if pd.notna(t['satisfaction']) else '-'}"
    
    # Time calculation - properly check for None/NaN
    has_end_time = pd.notna(u['end_time']) and u['end_time'] is not None and str(u['end_time']) != ''
    has_start_time = pd.notna(u['start_time']) and u['start_time'] is not None
    
    if has_end_time and has_start_time:
        # Complete with end_time: use actual duration
        try:
            start = pd.to_datetime(u['start_time'])
            end = pd.to_datetime(u['end_time'])
            row['time_min'] = (end - start).total_seconds() / 60
            row['time_type'] = ''
        except:
            pass
    elif len(actions) > 0:
        # No end_time but has actions: estimate from cumulative RT
        # decision_time is in SECONDS (based on observed values 2-7 and completion times 5-7 min)
        total_rt_seconds = actions['decision_time'].sum()
        # Add ~1 second per trial for stimulus display, feedback, transitions
        estimated_seconds = total_rt_seconds + (len(actions) * 1.0)
        row['time_min'] = estimated_seconds / 60
        row['time_type'] = '~'  # mark as estimated
    
    if len(actions) > 0:
        last = actions.iloc[-1]
        row['last'] = f"B{int(last['block_number'])}T{int(last['trial_number'])}"
        
        y_true = actions['correct_classification']
        y_pred = actions['classification_decision']
        y_ds = actions['dss_judgment']
        
        # Accuracy
        row['correct'] = (y_pred == y_true).sum()
        row['acc'] = row['correct'] / len(actions) * 100
        
        # DS agreement
        row['ds_agree'] = (y_pred == y_ds).sum() / len(actions) * 100
        
        # Signal detection
        tp = ((y_pred == 'signal') & (y_true == 'signal')).sum()
        tn = ((y_pred == 'noise') & (y_true == 'noise')).sum()
        fp = ((y_pred == 'signal') & (y_true == 'noise')).sum()
        fn = ((y_pred == 'noise') & (y_true == 'signal')).sum()
        
        row['hit_rate'] = tp / (tp + fn) * 100 if (tp + fn) > 0 else 0
        row['fa_rate'] = fp / (fp + tn) * 100 if (fp + tn) > 0 else 0
        
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        row['f1'] = 2 * precision * recall / (precision + recall) * 100 if (precision + recall) > 0 else 0
        
        # RT - average in seconds, show in same unit
        row['rt_ms'] = actions['decision_time'].mean()
    
    results.append(row)

# Print summary stats
complete_count = sum(1 for r in results if r['complete'] == '✅')
toast_count = sum(1 for r in results if r['toast'] != '-')
trials_120 = sum(1 for r in results if r['trials'] == 120)
print(f"\n📈 STATISTICS: {len(results)} users | {complete_count} complete | {trials_120} with 120 trials | {toast_count} with TOAST")

# Print table header
print(f"\n{'='*175}")
print(f"{'ID':<3} {'AID':<14} {'CSV':<4} {'ps':<5} {'d_h':<4} {'d_DS':<4} {'Tri':<4} {'Last':<7} {'Cor':<4} {'Acc%':<6} {'DSAg%':<6} {'Hit%':<6} {'FA%':<5} {'F1%':<5} {'RT(s)':<6} {'Time':<8} {'TOAST (U/R/T/C/S)':<18} {'OK'}")
print("-" * 175)

for r in results:
    if r['time_min'] > 0:
        time_str = f"{r['time_type']}{r['time_min']:.1f}m"
    else:
        time_str = "-"
    rt_str = f"{r['rt_ms']:.1f}" if r['rt_ms'] > 0 else "-"
    
    print(f"{r['ID']:<3} {r['aid']:<14} {r['csv']:<4} {r['ps']:<5} {r['d_h']:<4} {r['d_DS']:<4} {r['trials']:<4} {r['last']:<7} {r['correct']:<4} {r['acc']:<5.1f}% {r['ds_agree']:<5.1f}% {r['hit_rate']:<5.1f}% {r['fa_rate']:<4.1f}% {r['f1']:<4.1f}% {rt_str:<6} {time_str:<8} {r['toast']:<18} {r['complete']}")

print("-" * 175)

# Averages for complete users only
complete_results = [r for r in results if r['complete'] == '✅' and r['trials'] > 0]
if complete_results:
    avg_acc = sum(r['acc'] for r in complete_results) / len(complete_results)
    avg_ds = sum(r['ds_agree'] for r in complete_results) / len(complete_results)
    avg_hit = sum(r['hit_rate'] for r in complete_results) / len(complete_results)
    avg_fa = sum(r['fa_rate'] for r in complete_results) / len(complete_results)
    avg_f1 = sum(r['f1'] for r in complete_results) / len(complete_results)
    avg_rt = sum(r['rt_ms'] for r in complete_results) / len(complete_results)
    avg_time = sum(r['time_min'] for r in complete_results) / len(complete_results)
    
    print(f"{'AVG':<3} {'':<14} {'':<4} {'':<5} {'':<4} {'':<4} {'':<4} {'':<7} {'':<4} {avg_acc:<5.1f}% {avg_ds:<5.1f}% {avg_hit:<5.1f}% {avg_fa:<4.1f}% {avg_f1:<4.1f}% {avg_rt:<5.1f}  {avg_time:<7.1f}m {'(complete users)':<18}")

print("=" * 175)

# Flag issues
print("\n⚠️  ISSUES:")
issues = []
for r in results:
    if r['trials'] == 120 and r['complete'] == '❌':
        issues.append(f"   User {r['ID']}: Has 120 trials but NOT complete (closed before TOAST?)")
    if r['trials'] == 120 and r['toast'] == '-':
        issues.append(f"   User {r['ID']}: Has 120 trials but NO TOAST submitted")
    if r['trials'] > 0 and r['trials'] < 120 and r['complete'] == '✅':
        issues.append(f"   User {r['ID']}: Marked complete but only {r['trials']} trials")

if issues:
    for i in issues:
        print(i)
else:
    print("   None found ✅")

# Legend
print("\n📋 LEGEND:")
print("   Time: actual duration | ~Time: estimated from RT (incomplete users)")
print("   RT(s): Reaction time in seconds")
print("   TOAST: U=Usefulness, R=Reliability, T=Trust, C=Confidence, S=Satisfaction (1-7 scale)")
print("   Acc: Accuracy | DSAg: DS Agreement | Hit: Hit Rate | FA: False Alarm Rate | F1: F1 Score")

conn.close()
EOF
