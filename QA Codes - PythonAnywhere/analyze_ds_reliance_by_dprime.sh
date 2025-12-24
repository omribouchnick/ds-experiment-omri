#!/bin/bash
# Analyze DS reliance and performance by DS d-prime level (grouped)
# Groups: Low (0.5-0.9), Mid (1.1-1.7), High (1.9-2.5)
# Usage: bash "QA Codes - PythonAnywhere/analyze_ds_reliance_by_dprime.sh"

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
print("🔬 DS RELIANCE ANALYSIS BY DS D-PRIME LEVEL")
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

# Define DS d-prime groups
# Low: 0.5, 0.7, 0.9 (3 levels)
# Mid: 1.1, 1.3, 1.5, 1.7 (4 levels)
# High: 1.9, 2.1, 2.3, 2.5 (4 levels)

def categorize_dprime(dprime):
    if dprime <= 0.9:
        return 'Low (0.5-0.9)'
    elif dprime <= 1.7:
        return 'Mid (1.1-1.7)'
    else:
        return 'High (1.9-2.5)'

users['dprime_group'] = users['ds_sensitivity'].apply(categorize_dprime)

print(f"📊 DS D-Prime Distribution:")
print(users['dprime_group'].value_counts().sort_index())
print()

# Merge actions with users
actions_with_dprime = actions.merge(users[['user_id', 'ds_sensitivity', 'dprime_group']], on='user_id')

# Analysis per group
print("=" * 100)
print("📊 PERFORMANCE & DS RELIANCE BY DS D-PRIME GROUP")
print("=" * 100)
print()

dprime_groups = ['Low (0.5-0.9)', 'Mid (1.1-1.7)', 'High (1.9-2.5)']

for group_name in dprime_groups:
    print(f"{'='*100}")
    print(f"{group_name} DS SENSITIVITY")
    print(f"{'='*100}")
    
    # Get users and actions for this group
    group_users = users[users['dprime_group'] == group_name]
    group_actions = actions_with_dprime[actions_with_dprime['dprime_group'] == group_name].copy()
    
    # Show individual d-primes in this group
    dprime_counts = group_users['ds_sensitivity'].value_counts().sort_index()
    dprime_str = ", ".join([f"{d}({c})" for d, c in dprime_counts.items()])
    
    print(f"\n👥 Sample Size:")
    print(f"   Users: {len(group_users)}")
    print(f"   D-prime breakdown: {dprime_str}")
    print(f"   Total actions: {len(group_actions)}")
    
    # Calculate accuracy
    group_actions['is_correct'] = (
        group_actions['classification_decision'] == group_actions['correct_classification']
    ).astype(int)
    
    overall_acc = 100 * group_actions['is_correct'].sum() / len(group_actions)
    
    print(f"\n📈 ACCURACY:")
    print(f"   Overall: {overall_acc:.1f}%")
    
    # By block
    for block in [1, 2, 3]:
        block_actions = group_actions[group_actions['block_number'] == block]
        if len(block_actions) > 0:
            acc = 100 * block_actions['is_correct'].sum() / len(block_actions)
            print(f"   Block {block}: {acc:.1f}% ({block_actions['is_correct'].sum()}/{len(block_actions)})")
    
    # DS Agreement (Blocks 2-3 only where DS is shown)
    print(f"\n🤝 DS AGREEMENT (Blocks 2-3, where DS is shown):")
    
    group_actions['agreed_with_ds'] = (
        group_actions['classification_decision'] == group_actions['dss_judgment']
    ).astype(int)
    
    for block in [2, 3]:
        block_actions = group_actions[group_actions['block_number'] == block]
        if len(block_actions) > 0:
            agreement = 100 * block_actions['agreed_with_ds'].sum() / len(block_actions)
            print(f"   Block {block}: {agreement:.1f}% ({block_actions['agreed_with_ds'].sum()}/{len(block_actions)})")
    
    # Overall agreement for blocks 2-3
    blocks_23 = group_actions[group_actions['block_number'] > 1]
    if len(blocks_23) > 0:
        agreement_23 = 100 * blocks_23['agreed_with_ds'].sum() / len(blocks_23)
        print(f"   Combined (B2+B3): {agreement_23:.1f}% ({blocks_23['agreed_with_ds'].sum()}/{len(blocks_23)})")
    
    # DS Accuracy (when they agreed with DS, were they correct?)
    print(f"\n✅ DS ACCURACY (When user followed DS, were they correct?):")
    
    for block in [2, 3]:
        block_actions = group_actions[group_actions['block_number'] == block]
        followed_ds = block_actions[block_actions['agreed_with_ds'] == 1]
        if len(followed_ds) > 0:
            ds_acc = 100 * followed_ds['is_correct'].sum() / len(followed_ds)
            print(f"   Block {block}: {ds_acc:.1f}% ({followed_ds['is_correct'].sum()}/{len(followed_ds)})")
    
    # Overall DS accuracy for blocks 2-3
    blocks_23_followed = blocks_23[blocks_23['agreed_with_ds'] == 1]
    if len(blocks_23_followed) > 0:
        ds_acc_23 = 100 * blocks_23_followed['is_correct'].sum() / len(blocks_23_followed)
        print(f"   Combined (B2+B3): {ds_acc_23:.1f}% ({blocks_23_followed['is_correct'].sum()}/{len(blocks_23_followed)})")
    
    # Independent accuracy (when they disagreed with DS)
    print(f"\n🙋 INDEPENDENT ACCURACY (When user disagreed with DS):")
    
    for block in [2, 3]:
        block_actions = group_actions[group_actions['block_number'] == block]
        disagreed_ds = block_actions[block_actions['agreed_with_ds'] == 0]
        if len(disagreed_ds) > 0:
            indep_acc = 100 * disagreed_ds['is_correct'].sum() / len(disagreed_ds)
            print(f"   Block {block}: {indep_acc:.1f}% ({disagreed_ds['is_correct'].sum()}/{len(disagreed_ds)})")
    
    # Overall independent accuracy for blocks 2-3
    blocks_23_disagreed = blocks_23[blocks_23['agreed_with_ds'] == 0]
    if len(blocks_23_disagreed) > 0:
        indep_acc_23 = 100 * blocks_23_disagreed['is_correct'].sum() / len(blocks_23_disagreed)
        print(f"   Combined (B2+B3): {indep_acc_23:.1f}% ({blocks_23_disagreed['is_correct'].sum()}/{len(blocks_23_disagreed)})")
    
    # TOAST responses for this group
    group_toast = toast[toast['user_id'].isin(group_users['user_id'])]
    
    if len(group_toast) > 0:
        print(f"\n📋 TOAST RESPONSES (DS-related):")
        print(f"   Usefulness:  {group_toast['usefulness'].mean():.2f} ± {group_toast['usefulness'].std():.2f}")
        print(f"   Reliability: {group_toast['reliability'].mean():.2f} ± {group_toast['reliability'].std():.2f}")
        print(f"   Trust:       {group_toast['trust'].mean():.2f} ± {group_toast['trust'].std():.2f}")
        print(f"   Confidence:  {group_toast['confidence'].mean():.2f} ± {group_toast['confidence'].std():.2f}")
        print(f"   Satisfaction: {group_toast['satisfaction'].mean():.2f} ± {group_toast['satisfaction'].std():.2f}")
    
    print()

# Summary comparison table
print("=" * 100)
print("📊 SUMMARY COMPARISON ACROSS DS D-PRIME GROUPS")
print("=" * 100)
print()

summary_data = []
for group_name in dprime_groups:
    group_users = users[users['dprime_group'] == group_name]
    group_actions = actions_with_dprime[actions_with_dprime['dprime_group'] == group_name].copy()
    
    # Accuracy
    group_actions['is_correct'] = (
        group_actions['classification_decision'] == group_actions['correct_classification']
    ).astype(int)
    overall_acc = 100 * group_actions['is_correct'].sum() / len(group_actions)
    
    # Block 3 accuracy
    block3 = group_actions[group_actions['block_number'] == 3]
    block3_acc = 100 * block3['is_correct'].sum() / len(block3) if len(block3) > 0 else 0
    
    # DS agreement (blocks 2-3)
    group_actions['agreed_with_ds'] = (
        group_actions['classification_decision'] == group_actions['dss_judgment']
    ).astype(int)
    blocks_23 = group_actions[group_actions['block_number'] > 1]
    agreement = 100 * blocks_23['agreed_with_ds'].sum() / len(blocks_23) if len(blocks_23) > 0 else 0
    
    # DS accuracy (when followed)
    blocks_23_followed = blocks_23[blocks_23['agreed_with_ds'] == 1]
    ds_acc = 100 * blocks_23_followed['is_correct'].sum() / len(blocks_23_followed) if len(blocks_23_followed) > 0 else 0
    
    # TOAST
    group_toast = toast[toast['user_id'].isin(group_users['user_id'])]
    toast_useful = group_toast['usefulness'].mean() if len(group_toast) > 0 else 0
    toast_reliable = group_toast['reliability'].mean() if len(group_toast) > 0 else 0
    toast_trust = group_toast['trust'].mean() if len(group_toast) > 0 else 0
    
    summary_data.append({
        'group': group_name,
        'n_users': len(group_users),
        'overall_acc': overall_acc,
        'block3_acc': block3_acc,
        'ds_agreement': agreement,
        'ds_accuracy': ds_acc,
        'toast_useful': toast_useful,
        'toast_reliable': toast_reliable,
        'toast_trust': toast_trust
    })

summary_df = pd.DataFrame(summary_data)

print("┌" + "─"*110 + "┐")
print("│ DS D-Prime Group │ N Users │ Overall │ Block3 │ Agreement │ DS Accuracy │ TOAST: Useful │ Reliable │ Trust │")
print("├" + "─"*110 + "┤")
for _, row in summary_df.iterrows():
    print(f"│ {row['group']:16s} │   {int(row['n_users']):3d}   │  {row['overall_acc']:5.1f}% │ {row['block3_acc']:5.1f}% │   {row['ds_agreement']:5.1f}%   │    {row['ds_accuracy']:5.1f}%    │     {row['toast_useful']:4.2f}      │   {row['toast_reliable']:4.2f}   │ {row['toast_trust']:4.2f}  │")
print("└" + "─"*110 + "┘")
print()

# Statistical insights
print("🔍 KEY INSIGHTS:")
print()

# Check if agreement varies by dprime
if len(summary_df) > 1:
    agreement_range = summary_df['ds_agreement'].max() - summary_df['ds_agreement'].min()
    print(f"1. DS Agreement Range: {agreement_range:.1f}% difference across d-prime levels")
    
    # Check correlation direction
    low_agreement = summary_df[summary_df['group'] == 'Low (0.5-0.9)']['ds_agreement'].values[0]
    high_agreement = summary_df[summary_df['group'] == 'High (1.9-2.5)']['ds_agreement'].values[0]
    
    if high_agreement > low_agreement + 5:
        print(f"   → Users rely MORE on high-quality DS (High: {high_agreement:.1f}% vs Low: {low_agreement:.1f}%)")
        print(f"   → Suggests users can discriminate DS quality! ✅")
    elif low_agreement > high_agreement + 5:
        print(f"   → Users rely MORE on low-quality DS (Low: {low_agreement:.1f}% vs High: {high_agreement:.1f}%)")
        print(f"   → Suggests over-reliance on poor DS ⚠️")
    else:
        print(f"   → Similar reliance regardless of DS quality (Consistent ~{agreement_range:.1f}%)")
        print(f"   → Users may not perceive DS quality differences")
    print()
    
    # Check DS accuracy difference
    ds_acc_range = summary_df['ds_accuracy'].max() - summary_df['ds_accuracy'].min()
    print(f"2. DS Accuracy Range: {ds_acc_range:.1f}% difference")
    
    low_ds_acc = summary_df[summary_df['group'] == 'Low (0.5-0.9)']['ds_accuracy'].values[0]
    high_ds_acc = summary_df[summary_df['group'] == 'High (1.9-2.5)']['ds_accuracy'].values[0]
    
    print(f"   Low DS d-prime → {low_ds_acc:.1f}% correct when followed")
    print(f"   High DS d-prime → {high_ds_acc:.1f}% correct when followed")
    if high_ds_acc > low_ds_acc + 5:
        print(f"   → High-quality DS IS more accurate! ✅")
    else:
        print(f"   → Similar accuracy - d-prime may not affect correctness in this range")
    print()
    
    # Check TOAST sensitivity
    toast_range = summary_df['toast_trust'].max() - summary_df['toast_trust'].min()
    print(f"3. TOAST Trust Range: {toast_range:.2f} points across d-prime levels")
    
    low_trust = summary_df[summary_df['group'] == 'Low (0.5-0.9)']['toast_trust'].values[0]
    high_trust = summary_df[summary_df['group'] == 'High (1.9-2.5)']['toast_trust'].values[0]
    
    if high_trust > low_trust + 0.5:
        print(f"   → Users TRUST high-quality DS more (High: {high_trust:.2f} vs Low: {low_trust:.2f})")
        print(f"   → Subjective ratings align with DS quality ✅")
    elif toast_range < 0.5:
        print(f"   → Consistent trust regardless of DS quality")
        print(f"   → Users may not consciously perceive quality differences")
    else:
        print(f"   → Trust varies, but not clearly with DS quality")

print()
print("=" * 100)
print("✅ ANALYSIS COMPLETE")
print("=" * 100)

conn.close()
EOF



