# How to Update Database and Test New Users

## Part 1: Update Existing Users (Local - Jupyter Notebook)

### What: Update the 52 existing users with their correct `csv_row_id`

### Where: On your local computer, in Jupyter Notebook

### Steps:

1. **Open Jupyter Notebook:**
   ```bash
   cd /Users/omri.bouchnick/Documents/omribouch_personal_py_projects/thesis_python/ds-experiment-omri
   jupyter notebook experiment_analysis.ipynb
   ```

2. **Run cells in order:**
   - **Cell 1**: Imports (click Run)
   - **Cell 2**: Helper functions (click Run)
   - **Cell 4**: Data loading (click Run) - loads data from `data/old_data_0912/db.sqlite3`
   - **Cell 5**: Update csv_row_id (click Run) - updates the database
   - **Cell 6**: Validation (click Run) - checks everything
   - **Cell 7**: Verification (click Run) - shows 2 users comparison

3. **What Cell 5 does:**
   - Reads `data/old_data_0912/user_csv_row_mapping.csv`
   - Updates `data/old_data_0912/db.sqlite3` with `csv_row_id` for all 52 users
   - Updates `ps`, `dprime_h`, `dprime_s` from correct CSV row

4. **After Cell 5 runs:**
   - ✅ Database updated locally
   - ⚠️ **BUT**: This is your LOCAL copy of the database!
   - You need to upload the updated database to PythonAnywhere

---

## Part 2: Upload Updated Database to PythonAnywhere

### What: Copy the updated database to your server

### Steps:

1. **Upload the updated database:**
   ```bash
   # From your local computer
   scp data/old_data_0912/db.sqlite3 your_username@ssh.pythonanywhere.com:~/ds-experiment-omri/data/old_data_0912/
   ```

   OR use PythonAnywhere's Files tab to upload `data/old_data_0912/db.sqlite3`

2. **Verify on PythonAnywhere:**
   ```bash
   # SSH into PythonAnywhere
   cd ~/ds-experiment-omri
   source venv/bin/activate
   python manage.py shell
   ```
   ```python
   from experiment.models import ExperimentData
   # Check if csv_row_id exists
   user = ExperimentData.objects.first()
   print(hasattr(user, 'csv_row_id'))
   print(user.csv_row_id if hasattr(user, 'csv_row_id') else "Column doesn't exist")
   ```

---

## Part 3: Deploy Code Changes to PythonAnywhere

### What: Upload the fixed code so new users get `csv_row_id` automatically

### Steps:

1. **Upload updated files:**
   - `experiment/models.py` (has `csv_row_id` field)
   - `experiment/views.py` (has new logic)
   - `experiment/migrations/0007_add_csv_row_id.py` (migration file)

2. **Run migration on PythonAnywhere:**
   ```bash
   cd ~/ds-experiment-omri
   source venv/bin/activate
   python manage.py migrate
   ```

3. **Reload web app:**
   - Go to PythonAnywhere Dashboard → Web tab
   - Click "Reload" button

---

## Part 4: Test with New User (Incognito Mode)

### What: Test that new users automatically get `csv_row_id`

### Steps:

1. **Open incognito/private browser window**

2. **Go to your experiment URL:**
   ```
   https://yourusername.pythonanywhere.com/?aid=test_new_user_123
   ```

3. **Complete the experiment:**
   - Go through all blocks
   - Complete TOAST questionnaire
   - Finish experiment

4. **Check the database:**
   ```bash
   # On PythonAnywhere
   python manage.py shell
   ```
   ```python
   from experiment.models import ExperimentData
   # Find the new user
   new_user = ExperimentData.objects.filter(aid='test_new_user_123').first()
   if new_user:
       print(f"User ID: {new_user.user_id}")
       print(f"csv_row_id: {new_user.csv_row_id}")
       print(f"ps: {new_user.ps}")
       print(f"Complete: {new_user.complete}")
   ```

---

## Part 5: Download Updated Data and Analyze

### What: Get the updated data with `csv_row_id` and analyze

### Steps:

1. **Download updated database from PythonAnywhere:**
   ```bash
   # Download via Files tab or:
   scp your_username@ssh.pythonanywhere.com:~/ds-experiment-omri/data/old_data_0912/db.sqlite3 data/old_data_0912/
   ```

2. **Run notebook analysis:**
   - Open `experiment_analysis.ipynb`
   - Run Cell 4 (data loading)
   - **Now you should see:**
     ```
     ✅ Loaded users with csv_row_id column
     ```
   - Run Cell 6 (validation)
   - **You should see:**
     ```
     ✅ csv_row_id column exists in database
     Users with csv_row_id: 53  (52 old + 1 new)
     ✅ Each completed user has unique csv_row_id
     ```

3. **Check the new user:**
   - Run Cell 7 (verification)
   - Change `sample_users = [31, 32]` to include the new user ID
   - Verify their data matches their CSV row

---

## Expected Results After Testing

### In Database (PythonAnywhere):
- ✅ 52 old users have `csv_row_id` (from Cell 5 update)
- ✅ 1 new user has `csv_row_id` (automatically assigned)
- ✅ All users have correct `ps`, `dprime_h`, `dprime_s`

### In Notebook Analysis:
- ✅ Cell 4 loads with `csv_row_id` column
- ✅ Cell 6 validation shows all users have `csv_row_id`
- ✅ Cell 7 verification shows data matches CSV rows

### What to Check:
1. **New user got a CSV row:**
   - `csv_row_id` is not None
   - `csv_row_id` is a valid number (1-363)

2. **New user's data matches CSV row:**
   - Run Cell 7 with new user ID
   - All blocks should match (100% match)

3. **CSV row marked as used:**
   - Check `conditions_experiment_3ps_11x11_120_A.csv`
   - The row should have `used=1` and `used_type='reg'`

---

## Summary

**Local (Jupyter Notebook):**
- Cell 4: Load data
- Cell 5: Update old users with `csv_row_id`
- Cell 6: Validate
- Cell 7: Verify 2 users

**PythonAnywhere (Server):**
- Upload updated database
- Run migration
- Deploy code changes
- Test with new user

**After Test:**
- Download updated database
- Run notebook analysis
- Verify new user has `csv_row_id` and data matches

