# Manual Download Instructions

If you don't have SSH/SCP access, you can download files manually from PythonAnywhere:

## Option 1: Using PythonAnywhere Web Interface

1. Go to https://www.pythonanywhere.com/
2. Log in to your account
3. Go to **Files** tab
4. Navigate to: `/home/Omribouch/ds-experiment-omri/Experiment_Code/DATA/`
5. Download these files:
   - `db.sqlite3`
   - `conditions_experiment_3ps_11x11_120_A.csv`
6. Save them to your local machine at:
   - `ds-experiment-omri/Experiment_Code/DATA/db.sqlite3`
   - `ds-experiment-omri/Experiment_Code/DATA/conditions_experiment_3ps_11x11_120_A.csv`

## Option 2: Using Bash Script on PythonAnywhere

Run this on PythonAnywhere console:

```bash
cd ~/ds-experiment-omri/Experiment_Code
tar -czf data_backup_$(date +%Y%m%d_%H%M%S).tar.gz DATA/db.sqlite3 DATA/conditions_experiment_3ps_11x11_120_A.csv
```

Then download the `.tar.gz` file from PythonAnywhere Files tab and extract it locally.

## Option 3: Using Python Script on PythonAnywhere

Create a script to download via web:

```python
# On PythonAnywhere, create download script
import os
from flask import Flask, send_file

app = Flask(__name__)

@app.route('/download/db')
def download_db():
    return send_file('DATA/db.sqlite3', as_attachment=True)

@app.route('/download/csv')
def download_csv():
    return send_file('DATA/conditions_experiment_3ps_11x11_120_A.csv', as_attachment=True)
```

Then access via your PythonAnywhere URL.

## After Download

1. Replace your local files:
   - `ds-experiment-omri/Experiment_Code/DATA/db.sqlite3`
   - `ds-experiment-omri/Experiment_Code/DATA/conditions_experiment_3ps_11x11_120_A.csv`

2. Run your validation notebook again to check with latest data.


