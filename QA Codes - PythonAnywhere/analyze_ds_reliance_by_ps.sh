#!/bin/bash
# Analyze DS reliance and performance by ps level
# Checks: accuracy, DS agreement, TOAST scores per ps
# Usage: bash "QA Codes - PythonAnywhere/analyze_ds_reliance_by_ps.sh"

# Get script directory and navigate to Experiment_Code
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
EXPERIMENT_CODE_DIR="$(dirname "$SCRIPT_DIR")/Experiment_Code"

if [ ! -d "$EXPERIMENT_CODE_DIR" ]; then
    EXPERIMENT_CODE_DIR="$HOME/ds-experiment-omri/Experiment_Code"
fi

cd "$EXPERIMENT_CODE_DIR" && python3 << 'EOF'
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime

conn = sqlite3.connect('DATA/db.sqlite3')

print("=" * 100)
print("🔬 DS RELIANCE ANALYSIS BY PS LEVEL")
print("=" * 100)
print(f"Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

# Load data
users = pd.read_sql_query("""
    SELECT user_id, aid, ps, human_sensitivity, ds_sensitivity, complete
    FROM experiment_experimentdata
    WHERE complete = 1
""", conn)

actions = pd.read_sql_query("""
    SELECT user_id_id as user_id, block_number, trial_number, 
           classification_decision, dss_judgment, correct_classification
    FROM experiment_experimentaction
""", conn)

toast = pd.read_sql_query("""
    SELECT user_id_id as user_id, usefulness, reliability, trust,
           confidence, satisfaction
    FROM experiment_toastresponse
""", conn)

print(f"📊 Data Overview:")
print(f"   Complete users: {len(users)}")
print(f"   Total actions: {len(actions)}")
print(f"   TOAST responses: {len(toast)}")
print()

# Merge actions with users
actions_with_ps = actions.merge(users[['user_id', 'ps']], on='user_id')

# Calculate metrics per ps
print("=" * 100)
print("📊 PERFORMANCE & DS RELIANCE BY PS LEVEL")
print("=" * 100)
print()

ps_levels = sorted(users['ps'].unique())

for ps_val in ps_levels:
    print(f"{'='*100}")
    print(f"PS = {ps_val} (Signal Probability)")
    print(f"{'='*100}")
    
    # Get users and actions for this ps
    ps_users = users[users['ps'] == ps_val]
    ps_actions = actions_with_ps[actions_with_ps['ps'] == ps_val].copy()
    
    print(f"\n👥 Sample Size:")
    print(f"   Users: {len(ps_users)}")
    print(f"   Total actions: {len(ps_actions)}")
    
    # Calculate accuracy
    ps_actions['is_correct'] = (
        ps_actions['classification_decision'] == ps_actions['correct_classification']
    ).astype(int)
    
    overall_acc = 100 * ps_actions['is_correct'].sum() / len(ps_actions)
    
    print(f"\n📈 ACCURACY:")
    print(f"   Overall: {overall_acc:.1f}%")
    
    # By block
    for block in [1, 2, 3]:
        block_actions = ps_actions[ps_actions['block_number'] == block]
        if len(block_actions) > 0:
            acc = 100 * block_actions['is_correct'].sum() / len(block_actions)
            print(f"   Block {block}: {acc:.1f}% ({block_actions['is_correct'].sum()}/{len(block_actions)})")
    
    # DS Agreement (Blocks 2-3 only where DS is shown)
    print(f"\n🤝 DS AGREEMENT (Blocks 2-3, where DS is shown):")
    
    ps_actions['agreed_with_ds'] = (
        ps_actions['classification_decision'] == ps_actions['dss_judgment']
    ).astype(int)
    
    for block in [2, 3]:
        block_actions = ps_actions[ps_actions['block_number'] == block]
        if len(block_actions) > 0:
            agreement = 100 * block_actions['agreed_with_ds'].sum() / len(block_actions)
            print(f"   Block {block}: {agreement:.1f}% ({block_actions['agreed_with_ds'].sum()}/{len(block_actions)})")
    
    # Overall agreement for blocks 2-3
    blocks_23 = ps_actions[ps_actions['block_number'] > 1]
    if len(blocks_23) > 0:
        agreement_23 = 100 * blocks_23['agreed_with_ds'].sum() / len(blocks_23)
        print(f"   Combined (B2+B3): {agreement_23:.1f}% ({blocks_23['agreed_with_ds'].sum()}/{len(blocks_23)})")
    
    # DS Accuracy (when they agreed with DS, were they correct?)
    print(f"\n✅ DS ACCURACY (When user followed DS, were they correct?):")
    
    for block in [2, 3]:
        block_actions = ps_actions[ps_actions['block_number'] == block]
        followed_ds = block_actions[block_actions['agreed_with_ds'] == 1]
        if len(followed_ds) > 0:
            ds_acc = 100 * followed_ds['is_correct'].sum() / len(followed_ds)
            print(f"   Block {block}: {ds_acc:.1f}% ({followed_ds['is_correct'].sum()}/{len(followed_ds)})")
    
    # Independent accuracy (when they disagreed with DS)
    print(f"\n🙋 INDEPENDENT ACCURACY (When user disagreed with DS):")
    
    for block in [2, 3]:
        block_actions = ps_actions[ps_actions['block_number'] == block]
        disagreed_ds = block_actions[block_actions['agreed_with_ds'] == 0]
        if len(disagreed_ds) > 0:
            indep_acc = 100 * disagreed_ds['is_correct'].sum() / len(disagreed_ds)
            print(f"   Block {block}: {indep_acc:.1f}% ({disagreed_ds['is_correct'].sum()}/{len(disagreed_ds)})")
    
    # TOAST responses for this ps
    ps_toast = toast[toast['user_id'].isin(ps_users['user_id'])]
    
    if len(ps_toast) > 0:
        print(f"\n📋 TOAST RESPONSES (DS-related):")
        print(f"   Usefulness:  {ps_toast['usefulness'].mean():.2f} ± {ps_toast['usefulness'].std():.2f}")
        print(f"   Reliability: {ps_toast['reliability'].mean():.2f} ± {ps_toast['reliability'].std():.2f}")
        print(f"   Trust:       {ps_toast['trust'].mean():.2f} ± {ps_toast['trust'].std():.2f}")
        print(f"   Confidence:  {ps_toast['confidence'].mean():.2f} ± {ps_toast['confidence'].std():.2f}")
        print(f"   Satisfaction: {ps_toast['satisfaction'].mean():.2f} ± {ps_toast['satisfaction'].std():.2f}")
    
    print()

# Summary comparison table
print("=" * 100)
print("📊 SUMMARY COMPARISON ACROSS PS LEVELS")
print("=" * 100)
print()

summary_data = []
for ps_val in ps_levels:
    ps_users = users[users['ps'] == ps_val]
    ps_actions = actions_with_ps[actions_with_ps['ps'] == ps_val].copy()
    
    # Accuracy
    ps_actions['is_correct'] = (
        ps_actions['classification_decision'] == ps_actions['correct_classification']
    ).astype(int)
    overall_acc = 100 * ps_actions['is_correct'].sum() / len(ps_actions)
    
    # Block 3 accuracy
    block3 = ps_actions[ps_actions['block_number'] == 3]
    block3_acc = 100 * block3['is_correct'].sum() / len(block3) if len(block3) > 0 else 0
    
    # DS agreement (blocks 2-3)
    ps_actions['agreed_with_ds'] = (
        ps_actions['classification_decision'] == ps_actions['dss_judgment']
    ).astype(int)
    blocks_23 = ps_actions[ps_actions['block_number'] > 1]
    agreement = 100 * blocks_23['agreed_with_ds'].sum() / len(blocks_23) if len(blocks_23) > 0 else 0
    
    # TOAST
    ps_toast = toast[toast['user_id'].isin(ps_users['user_id'])]
    toast_useful = ps_toast['usefulness'].mean() if len(ps_toast) > 0 else 0
    toast_reliable = ps_toast['reliability'].mean() if len(ps_toast) > 0 else 0
    toast_trust = ps_toast['trust'].mean() if len(ps_toast) > 0 else 0
    
    summary_data.append({
        'ps': ps_val,
        'n_users': len(ps_users),
        'overall_acc': overall_acc,
        'block3_acc': block3_acc,
        'ds_agreement': agreement,
        'toast_useful': toast_useful,
        'toast_reliable': toast_reliable,
        'toast_trust': toast_trust
    })

summary_df = pd.DataFrame(summary_data)

print("┌" + "─"*98 + "┐")
print("│ PS    │ N Users │ Overall Acc │ Block3 Acc │ DS Agreement │ TOAST: Useful │ Reliable │ Trust │")
print("├" + "─"*98 + "┤")
for _, row in summary_df.iterrows():
    print(f"│ {row['ps']:.2f}  │   {int(row['n_users']):3d}   │    {row['overall_acc']:5.1f}%   │   {row['block3_acc']:5.1f}%    │     {row['ds_agreement']:5.1f}%     │     {row['toast_useful']:4.2f}      │   {row['toast_reliable']:4.2f}   │ {row['toast_trust']:4.2f}  │")
print("└" + "─"*98 + "┘")
print()

# Statistical insights
print("🔍 KEY INSIGHTS:")
print()

# Check if agreement varies by ps
if len(summary_df) > 1:
    agreement_range = summary_df['ds_agreement'].max() - summary_df['ds_agreement'].min()
    print(f"1. DS Agreement Range: {agreement_range:.1f}% difference across ps levels")
    if agreement_range < 5:
        print(f"   → Consistent reliance on DS across all signal probabilities ✅")
    elif agreement_range < 10:
        print(f"   → Moderate variation in DS reliance")
    else:
        print(f"   → Significant variation - users adapt strategy based on ps")
    print()
    
    # Check if accuracy varies by ps
    acc_range = summary_df['overall_acc'].max() - summary_df['overall_acc'].min()
    print(f"2. Accuracy Range: {acc_range:.1f}% difference across ps levels")
    if acc_range < 5:
        print(f"   → Similar performance across all ps levels")
    else:
        print(f"   → Performance varies with signal probability (expected)")
    print()
    
    # Check TOAST consistency
    toast_range = summary_df['toast_trust'].max() - summary_df['toast_trust'].min()
    print(f"3. TOAST Trust Range: {toast_range:.2f} points across ps levels")
    if toast_range < 0.5:
        print(f"   → Consistent trust in DS regardless of ps ✅")
    else:
        print(f"   → Trust varies with task difficulty")

print()
print("=" * 100)
print("✅ ANALYSIS COMPLETE")
print("=" * 100)

conn.close()
EOF

