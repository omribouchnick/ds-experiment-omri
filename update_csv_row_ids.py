#!/usr/bin/env python
"""
Update database with csv_row_id values from mapping file.
Also updates ps, dprime_h, dprime_s from the CSV row.

Note: This accounts for the fact that Block 3 trials 1-20 are repeats
of Block 1 and 2 (old bug before fix).
"""

import os
import sys
import django
import pandas as pd

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ds_experiment.settings')
django.setup()

from experiment.models import ExperimentData

# Load mapping file
mapping_file = 'data/old_data_0912/user_csv_row_mapping.csv'
conditions_file = 'data/conditions_experiment_3ps_11x11_120_A.csv'

print("=" * 60)
print("Updating csv_row_id in database")
print("=" * 60)

# Load mapping
mapping_df = pd.read_csv(mapping_file)
print(f"\n✅ Loaded mapping: {len(mapping_df)} users")

# Load conditions CSV to get ps, dprime_h, dprime_s
conditions_df = pd.read_csv(conditions_file)
print(f"✅ Loaded conditions CSV: {len(conditions_df)} rows")

# Update each user
updated = 0
not_found = []
errors = []

for _, row in mapping_df.iterrows():
    user_id = int(float(row['user_id']))  # Handle float user_ids (31.0 -> 31)
    csv_row_id = int(row['csv_row_id'])
    
    try:
        # Get user from database
        user = ExperimentData.objects.get(user_id=user_id)
        
        # Get ps, dprime_h, dprime_s from CSV row
        csv_row = conditions_df[conditions_df['id'] == csv_row_id].iloc[0]
        ps = float(csv_row['ps'])
        dprime_h = float(csv_row['dprime_h'])
        dprime_s = float(csv_row['dprime_s'])
        
        # Update user
        user.csv_row_id = csv_row_id
        user.ps = ps
        user.human_sensitivity = dprime_h
        user.ds_sensitivity = dprime_s
        user.save()
        
        updated += 1
        
    except ExperimentData.DoesNotExist:
        not_found.append(user_id)
    except Exception as e:
        errors.append((user_id, str(e)))

# Summary
print("\n" + "=" * 60)
print("UPDATE SUMMARY")
print("=" * 60)
print(f"✅ Updated: {updated} users")
if not_found:
    print(f"⚠️  Not found in database: {len(not_found)} users {not_found[:10]}")
if errors:
    print(f"❌ Errors: {len(errors)}")
    for user_id, error in errors[:5]:
        print(f"   User {user_id}: {error}")

print("\n✅ Done!")
print("=" * 60)

