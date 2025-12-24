
# ============================================================================
# MINIMAL CHANGES TO views.py - ONLY 2 MODIFICATIONS NEEDED!
# ============================================================================

# CHANGE 1: Add filelock import at the TOP of views.py
# --------------------------------------------------------
# Add this line near the other imports:

from filelock import FileLock  # pip install filelock

# ============================================================================

# CHANGE 2: Modify load_block_trials() function
# --------------------------------------------------------
# Replace the ENTIRE load_block_trials() function with this version.
# The ONLY difference is: FileLock wraps the CSV read + row selection + CSV write

def load_block_trials(csv_row_id=None) -> tuple:
    """
    Load trial data from CSV for a user.
    FIXED: Uses file lock to prevent race conditions.
    """
    STIMULI_SCALAR = 6.5

    # === NEW: Use the new CSV file for follow-up experiment ===
    csv_path = os.path.join(settings.BASE_DIR, "DATA", "conditions_followup_69_missing.csv")
    lock_path = csv_path + ".lock"  # Lock file path

    # Verify path exists
    if not os.path.exists(csv_path):
        logger.error(f"CRITICAL: CSV file not found at {csv_path}")
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    if csv_row_id:
        # Loading specific row (returning user) - no lock needed
        event_data = pd.read_csv(csv_path)
        matching_rows = event_data[event_data['id'] == csv_row_id]
        if len(matching_rows) == 0:
            logger.error(f"CRITICAL: CSV row {csv_row_id} not found in CSV!")
            raise ValueError(f"CSV row {csv_row_id} not found")
        selected_row = matching_rows.iloc[0]
        row_id = int(selected_row['id'])
        logger.debug(f"Loaded specific row {row_id}")
    else:
        # NEW USER - MUST USE LOCK to prevent race condition!
        # ======================================================
        with FileLock(lock_path, timeout=30):  # Wait up to 30 seconds for lock
            event_data = pd.read_csv(csv_path)

            fresh_rows = event_data[event_data['used'] == 0].copy()
            in_progress_rows = event_data[event_data['used'] == 0.5].copy()

            logger.info(f"Row availability: fresh={len(fresh_rows)}, in_progress={len(in_progress_rows)}")

            if len(fresh_rows) > 0:
                # Select a fresh row
                selected_row = fresh_rows.sample(n=1).iloc[0]
                row_id = int(selected_row['id'])

                # Mark as in-progress IMMEDIATELY (still inside lock!)
                event_data.loc[event_data['id'] == row_id, 'used'] = 0.5
                event_data.to_csv(csv_path, index=False)

                logger.info(f"Selected fresh row {row_id} and marked as 0.5 (ATOMIC)")
            elif len(in_progress_rows) > 0:
                # No fresh rows - use in-progress
                selected_row = in_progress_rows.sample(n=1).iloc[0]
                row_id = int(selected_row['id'])
                logger.warning(f"Selected in-progress row {row_id} (no fresh rows!)")
            else:
                # All completed - recycle any row
                selected_row = event_data.sample(n=1).iloc[0]
                row_id = int(selected_row['id'])
                logger.warning(f"RECYCLING completed row {row_id} (all rows used!)")
        # Lock is released here - other users can now access CSV

    # Extract ps and dprimes from the selected row
    ps = float(selected_row['ps'])
    dprime_h = float(selected_row['dprime_h'])
    dprime_s = float(selected_row['dprime_s'])

    # Load all 120 trials at once from this row
    data_dict = {1: {}, 2: {}, 3: {}}

    def format_trial_num(n):
        return f'0{n}' if n < 10 else f'{n}'

    # Block 1: Trials 1-10 (no DS shown)
    for trial_num in range(1, 11):
        t_str = format_trial_num(trial_num)
        data_dict[1][trial_num] = {
            'event': selected_row[f'event_t{t_str}'],
            'stimuli': float(selected_row[f'h_t{t_str}']) + STIMULI_SCALAR,
            'ds_stimuli': float(selected_row[f's_t{t_str}']) + STIMULI_SCALAR,
            'ds_judgment': int(selected_row[f'ds_dec_t{t_str}'])
        }

    # Block 2: Trials 11-20 (with DS shown)
    for trial_num in range(11, 21):
        block_trial_num = trial_num - 10
        t_str = format_trial_num(trial_num)
        data_dict[2][block_trial_num] = {
            'event': selected_row[f'event_t{t_str}'],
            'stimuli': float(selected_row[f'h_t{t_str}']) + STIMULI_SCALAR,
            'ds_stimuli': float(selected_row[f's_t{t_str}']) + STIMULI_SCALAR,
            'ds_judgment': int(selected_row[f'ds_dec_t{t_str}'])
        }

    # Block 3: Trials 1-100 (with DS shown)
    for trial_num in range(1, 101):
        csv_trial_num = trial_num + 20
        t_str = format_trial_num(csv_trial_num)
        data_dict[3][trial_num] = {
            'event': selected_row[f'event_t{t_str}'],
            'stimuli': float(selected_row[f'h_t{t_str}']) + STIMULI_SCALAR,
            'ds_stimuli': float(selected_row[f's_t{t_str}']) + STIMULI_SCALAR,
            'ds_judgment': int(selected_row[f'ds_dec_t{t_str}'])
        }

    return data_dict, row_id, ps, dprime_h, dprime_s


# ============================================================================
# CHANGE 3: REMOVE the separate mark_row_in_progress() call in landing_page()
# ============================================================================
# In landing_page(), DELETE or COMMENT OUT these lines (around line 448-456):
#
#     # Mark row as in_progress (0.5) IMMEDIATELY to prevent race condition
#     try:
#         mark_row_in_progress(csv_row_id)
#         logger.info(f"Marked row {csv_row_id} as in-progress (0.5)")
#     except Exception as e:
#         logger.error(f"CRITICAL: Failed to mark_row_in_progress for row {csv_row_id}, AID {aid}: {e}")
#         ...
#
# The marking is now done INSIDE load_block_trials() atomically!


# ============================================================================
# SUMMARY OF CHANGES:
# ============================================================================
# 1. Add "from filelock import FileLock" at top
# 2. Change CSV path to: conditions_followup_69_missing.csv
# 3. Wrap CSV read + mark in FileLock
# 4. Remove separate mark_row_in_progress() call
#
# That's it! The rest of the code stays the same.
# ============================================================================
