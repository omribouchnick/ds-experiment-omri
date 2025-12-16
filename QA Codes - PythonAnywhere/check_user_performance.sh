#!/bin/bash
# Comprehensive user performance check with classification metrics
# Usage: bash check_user_performance.sh [user_id]
# If no user_id provided, checks the newest user

USER_ID=${1:-""}

cd ~/ds-experiment-omri && python3 << EOF
import sqlite3
import pandas as pd
from datetime import datetime

conn = sqlite3.connect('db.sqlite3')
user_id = "$USER_ID"

# Get user
if user_id:
    users = pd.read_sql_query(f"""
        SELECT user_id, aid, csv_row_id, ps, human_sensitivity, ds_sensitivity, 
               complete, start_time, end_time
        FROM experiment_experimentdata
        WHERE user_id = {user_id}
    """, conn)
else:
    users = pd.read_sql_query("""
        SELECT user_id, aid, csv_row_id, ps, human_sensitivity, ds_sensitivity, 
               complete, start_time, end_time
        FROM experiment_experimentdata
        ORDER BY user_id DESC LIMIT 1
    """, conn)

if len(users) == 0:
    print("❌ User not found")
    conn.close()
    exit()

u = users.iloc[0]
status = "✅ COMPLETE" if u['complete'] else "❌ INCOMPLETE"

print("=" * 85)
print(f"📊 USER PERFORMANCE REPORT - USER {u['user_id']}")
print("=" * 85)

# Basic info
print(f"\n📋 USER INFO:")
print(f"   AID:          {u['aid']}")
print(f"   CSV Row:      {u['csv_row_id']}")
print(f"   Status:       {status}")

# Experiment parameters
print(f"\n📊 EXPERIMENT PARAMETERS:")
print(f"   PS (signal prob):  {u['ps']}")
print(f"   d'_human:          {u['human_sensitivity']}")
print(f"   d'_DS:             {u['ds_sensitivity']}")

# Time calculation
print(f"\n⏱️  TIME:")
print(f"   Start:        {u['start_time']}")
if u['end_time']:
    print(f"   End:          {u['end_time']}")
    try:
        start = pd.to_datetime(u['start_time'])
        end = pd.to_datetime(u['end_time'])
        duration = (end - start).total_seconds()
        print(f"   Duration:     {duration/60:.1f} minutes ({duration:.0f} seconds)")
    except:
        pass
else:
    print(f"   End:          N/A (incomplete)")

# Get all actions
actions = pd.read_sql_query(f"""
    SELECT block_number, trial_number, stimulus_seen, dss_judgment, 
           classification_decision, correct_classification, decision_time
    FROM experiment_experimentaction
    WHERE user_id_id = {u['user_id']}
    ORDER BY block_number, trial_number
""", conn)

print(f"\n📈 PROGRESS:")
print(f"   Total Trials: {len(actions)}/40")
if len(actions) > 0:
    last = actions.iloc[-1]
    print(f"   Last Trial:   Block {int(last['block_number'])}, Trial {int(last['trial_number'])}")

if len(actions) == 0:
    print("\n⚠️  No trial data yet")
    conn.close()
    exit()

# Calculate metrics function
def calc_metrics(df, name=""):
    if len(df) == 0:
        return None
    
    # Ground truth and predictions
    y_true = df['correct_classification']  # actual correct answer
    y_pred = df['classification_decision']  # user's response
    y_ds = df['dss_judgment']  # DS recommendation
    
    # Basic accuracy
    correct = (y_pred == y_true).sum()
    accuracy = correct / len(df) * 100
    
    # DS agreement
    ds_agree = (y_pred == y_ds).sum()
    ds_agree_pct = ds_agree / len(df) * 100
    
    # Signal Detection metrics (user performance)
    # TP: user said signal, was actually signal
    # TN: user said noise, was actually noise
    # FP: user said signal, was actually noise (False Alarm)
    # FN: user said noise, was actually signal (Miss)
    
    tp = ((y_pred == 'signal') & (y_true == 'signal')).sum()
    tn = ((y_pred == 'noise') & (y_true == 'noise')).sum()
    fp = ((y_pred == 'signal') & (y_true == 'noise')).sum()
    fn = ((y_pred == 'noise') & (y_true == 'signal')).sum()
    
    # Precision, Recall, F1 for signal detection
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0  # Hit Rate
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    
    # False Alarm Rate
    fa_rate = fp / (fp + tn) if (fp + tn) > 0 else 0
    
    # DS metrics
    ds_correct = (y_ds == y_true).sum()
    ds_accuracy = ds_correct / len(df) * 100
    
    # Reaction time
    mean_rt = df['decision_time'].mean() if 'decision_time' in df.columns else 0
    
    return {
        'n': len(df),
        'correct': correct,
        'accuracy': accuracy,
        'tp': tp, 'tn': tn, 'fp': fp, 'fn': fn,
        'precision': precision,
        'recall': recall,  # Hit Rate
        'f1': f1,
        'fa_rate': fa_rate,
        'ds_agree': ds_agree,
        'ds_agree_pct': ds_agree_pct,
        'ds_accuracy': ds_accuracy,
        'mean_rt': mean_rt
    }

# Overall metrics
print("\n" + "=" * 85)
print("📊 CLASSIFICATION PERFORMANCE")
print("=" * 85)

overall = calc_metrics(actions, "Overall")

print(f"\n🎯 OVERALL (n={overall['n']}):")
print(f"   Accuracy:         {overall['correct']}/{overall['n']} ({overall['accuracy']:.1f}%)")
print(f"   DS Agreement:     {overall['ds_agree']}/{overall['n']} ({overall['ds_agree_pct']:.1f}%)")
print(f"   DS Accuracy:      {overall['ds_accuracy']:.1f}%")
print(f"   Mean RT:          {overall['mean_rt']:.0f}ms")

print(f"\n📈 SIGNAL DETECTION METRICS:")
print(f"   Hit Rate (Recall):  {overall['recall']*100:.1f}% (TP={overall['tp']}, FN={overall['fn']})")
print(f"   False Alarm Rate:   {overall['fa_rate']*100:.1f}% (FP={overall['fp']}, TN={overall['tn']})")
print(f"   Precision:          {overall['precision']*100:.1f}%")
print(f"   F1 Score:           {overall['f1']*100:.1f}%")

print(f"\n📋 CONFUSION MATRIX (User vs Truth):")
print(f"                    Actual Signal    Actual Noise")
print(f"   User: Signal     TP={overall['tp']:<8}      FP={overall['fp']}")
print(f"   User: Noise      FN={overall['fn']:<8}      TN={overall['tn']}")

# Per-block metrics
print("\n" + "=" * 85)
print("📊 PER-BLOCK PERFORMANCE")
print("=" * 85)
print(f"\n{'Block':<8} {'Trials':<8} {'Correct':<10} {'Accuracy':<10} {'DS Agree':<10} {'Hit Rate':<10} {'FA Rate':<10} {'F1':<8} {'RT(ms)'}")
print("-" * 85)

for block in [1, 2, 3]:
    ba = actions[actions['block_number'] == block]
    if len(ba) > 0:
        m = calc_metrics(ba, f"Block {block}")
        print(f"Block {block:<3} {m['n']:<8} {m['correct']}/{m['n']:<7} {m['accuracy']:<9.1f}% {m['ds_agree_pct']:<9.1f}% {m['recall']*100:<9.1f}% {m['fa_rate']*100:<9.1f}% {m['f1']*100:<7.1f}% {m['mean_rt']:.0f}")

# Summary comparison
print("\n" + "=" * 85)
print("📊 SUMMARY COMPARISON")
print("=" * 85)
print(f"\n   User Accuracy:    {overall['accuracy']:.1f}%")
print(f"   DS Accuracy:      {overall['ds_accuracy']:.1f}%")
print(f"   User vs DS:       {'User better' if overall['accuracy'] > overall['ds_accuracy'] else 'DS better' if overall['ds_accuracy'] > overall['accuracy'] else 'Equal'}")
print(f"\n   When user agreed with DS:  ", end="")
agreed = actions[actions['classification_decision'] == actions['dss_judgment']]
if len(agreed) > 0:
    agreed_correct = (agreed['classification_decision'] == agreed['correct_classification']).sum()
    print(f"{agreed_correct}/{len(agreed)} correct ({100*agreed_correct/len(agreed):.1f}%)")
else:
    print("N/A")

print(f"   When user disagreed with DS: ", end="")
disagreed = actions[actions['classification_decision'] != actions['dss_judgment']]
if len(disagreed) > 0:
    disagreed_correct = (disagreed['classification_decision'] == disagreed['correct_classification']).sum()
    print(f"{disagreed_correct}/{len(disagreed)} correct ({100*disagreed_correct/len(disagreed):.1f}%)")
else:
    print("N/A")

conn.close()
print("\n" + "=" * 85)
EOF





