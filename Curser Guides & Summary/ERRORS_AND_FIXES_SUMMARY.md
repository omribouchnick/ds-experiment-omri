# Errors and Fixes Summary

## Error 1: Wrong ps/dprime_s values in database (73% of users)

**Problem:**
- 38 out of 52 users (73%) have incorrect `ps` and `dprime_s` values in database
- Database shows wrong values, but users actually saw trials from different CSV rows

**Why it happened:**
- `landing_page()` is called every time the page loads
- If user refreshes page or session expires, a NEW CSV row is selected
- But `ExperimentData` is only created once (when `user_id` doesn't exist)
- Result: Database has ps from first row, but user sees trials from different row

**How fixed:**
- Matched all 52 users to their actual CSV rows by comparing trial sequences
- Created mapping file: `user_csv_row_mapping.csv`
- Ready to update database with correct ps/dprime_s values

---

## Error 2: CSV is_used column not updated

**Problem:**
- Only 1 row marked as `used=1` in CSV (should be 51)
- Rows weren't marked as used after experiment completion

**Why it happened:**
- `mark_row_as_used()` uses `request.session['csv_row_id']`
- If user refreshed, session had wrong `csv_row_id` from last call
- Result: Wrong row marked as used, or no row marked

**How fixed:**
- Matched all users to their actual CSV rows
- Marked 51 unique rows as `used=1` in CSV
- Added `used_type` column to track row usage type

---

## Error 3: Block 3 uses wrong CSV columns (overlaps with Block 1/2)

**Problem:**
- Block 3 uses `event_t01` to `event_t100` (repeats Block 1 and Block 2)
- Columns `event_t101` to `event_t120` are never used
- Block 3 trials 1-20 are repeats (not new trials)

**Why it happened:**
- Code bug: Block 3 loop uses `range(1, 101)` with `event_t{trial_num}`
- Should use `range(21, 121)` or map `trial_num + 20` to use columns 21-120

**How fixed:**
- Updated code to map Block 3 trial 1-100 to CSV columns 21-120
- Now: Block 1 (1-10), Block 2 (11-20), Block 3 (21-120) - no overlap
- Added `used_type='learning'` for old users, `'reg'` for future users

---

## Impact on Analysis

**Current data (52 users):**
- All users have valid trial data
- Block 3 includes 20 repeated trials (trials 1-20)
- Can analyze all 100 trials OR only trials 21-100 (unique)
- Shows learning effect: repeats (70% accuracy) vs new (87.5% accuracy)

**Recommendations:**
- For ps analysis: Use all Block 3 trials (repeats are fine)
- For learning effects: Compare Block 3 trials 1-20 vs 21-100
- Data is NOT useless - just different than intended

---

## Files Created/Updated

1. `user_csv_row_mapping.csv` - Maps each user to their CSV row
2. `conditions_experiment_3ps_11x11_120_A.csv` - Updated with `used=1` and `used_type`
3. `experiment/views.py` - Fixed Block 3 column mapping and `mark_row_as_used()`

---

## Next Steps

1. Update database with correct ps/dprime_s values from mapping
2. Re-run statistical analysis with corrected data
3. Decide: Use all Block 3 trials or only trials 21-100?


