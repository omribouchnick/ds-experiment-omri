#!/usr/bin/env python3
"""
Update DS decisions in CSV to use symmetric threshold (s_t > 0) instead of Bayesian.

This replaces the Bayesian P(S|s_t) > 0.5 approach with a simple threshold:
- If s_t > 0 → signal (1)
- If s_t <= 0 → noise (0)

This is equivalent to threshold = 6.5 on shifted values (s_t + 6.5 > 6.5).
"""

import pandas as pd
import numpy as np
from pathlib import Path

def update_ds_decisions_symmetric(csv_path):
    """Update all ds_dec columns to use symmetric threshold s_t > 0"""
    
    print("=" * 70)
    print("UPDATING DS DECISIONS TO SYMMETRIC THRESHOLD (s_t > 0)")
    print("=" * 70)
    
    # Load CSV
    df = pd.read_csv(csv_path)
    print(f"\nLoaded CSV: {len(df)} rows")
    
    updated_count = 0
    
    for idx, row in df.iterrows():
        # Get s_t values
        s_values = []
        for i in range(1, 121):
            s_col = f's_t{str(i).zfill(2)}'
            s_values.append(float(row[s_col]))
        
        s_values = np.array(s_values)
        
        # Calculate new decisions: s_t > 0 → signal (1), else noise (0)
        new_decisions = (s_values > 0).astype(int)
        
        # Update ds_dec columns
        for i, decision in enumerate(new_decisions, 1):
            ds_col = f'ds_dec_t{str(i).zfill(2)}'
            df.at[idx, ds_col] = int(decision)
        
        updated_count += 1
        if updated_count % 50 == 0:
            print(f"  Updated {updated_count}/{len(df)} rows...", end='\r')
    
    print(f"\n  Updated all {len(df)} rows")
    
    # Save updated CSV
    df.to_csv(csv_path, index=False)
    print(f"\n✅ Saved updated CSV to: {csv_path}")
    
    # Show summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print("\nNew decision rule:")
    print("  - If s_t > 0 → signal (1)")
    print("  - If s_t <= 0 → noise (0)")
    print("\nThis is equivalent to:")
    print("  - If (s_t + 6.5) > 6.5 → signal (1)")
    print("  - If (s_t + 6.5) <= 6.5 → noise (0)")
    print("\n(After the +6.5 shift in views.py)")

if __name__ == "__main__":
    # Update both CSV files
    csv_files = [
        'data/conditions_experiment_3ps_11x11_120_A.csv',
        'data/old_data_0912/conditions_experiment_3ps_11x11_120_A.csv'
    ]
    
    for csv_file in csv_files:
        csv_path = Path(csv_file)
        if csv_path.exists():
            print(f"\n{'='*70}")
            print(f"Updating: {csv_file}")
            print(f"{'='*70}")
            update_ds_decisions_symmetric(csv_path)
        else:
            print(f"⚠️  File not found: {csv_file}")

