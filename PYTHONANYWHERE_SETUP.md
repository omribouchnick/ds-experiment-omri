# 🚀 PythonAnywhere Setup Guide - Step by Step

## Prerequisites
- GitHub repository: `https://github.com/omribouchnick/ds-experiment-omri`
- PythonAnywhere account (free tier works)

---

## Step 1: Clone Repository on PythonAnywhere

1. **Log into PythonAnywhere**: https://www.pythonanywhere.com/
2. **Open Bash Console**: Click "Bash" tab (or "Consoles" → "Bash")
3. **Clone your repo**:
```bash
cd ~
git clone https://github.com/omribouchnick/ds-experiment-omri.git
cd ds-experiment-omri
```

---

## Step 2: Create Virtual Environment

```bash
# Create virtual environment (Python 3.9)
python3.9 -m venv venv

# Activate it
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip
```

---

## Step 3: Install Dependencies

```bash
# Make sure you're in the project directory and venv is activated
pip install -r requirements.txt
```

---

## Step 4: Update Settings for Production

Edit `PurchaseodInfo/settings.py`:

**Important changes:**
1. Set `DEBUG = False` (for production)
2. Update `ALLOWED_HOSTS` with your PythonAnywhere username
3. Add `STATIC_ROOT` for static files

```python
# In settings.py, update these lines:

DEBUG = False  # Change from True to False

ALLOWED_HOSTS = ['yourusername.pythonanywhere.com', 'www.yourusername.pythonanywhere.com']
# Replace 'yourusername' with your actual PythonAnywhere username

# Add this if not present:
STATIC_ROOT = BASE_DIR / 'staticfiles'
```

**To find your PythonAnywhere username:**
- Look at the top right of PythonAnywhere dashboard
- Or check your web app URL: `https://yourusername.pythonanywhere.com`

---

## Step 5: Run Database Migrations

```bash
# Make sure venv is activated
source venv/bin/activate

# Run migrations to create database
python manage.py migrate
```

This creates a fresh `db.sqlite3` with all your tables.

---

## Step 6: Collect Static Files

```bash
# Collect all static files (CSS, images, etc.)
python manage.py collectstatic --noinput
```

This creates a `staticfiles/` folder with all your static files.

---

## Step 7: Create Web App

1. **Go to "Web" tab** in PythonAnywhere dashboard
2. **Click "Add a new web app"** (or use existing one)
3. **Choose "Manual configuration"**
4. **Select Python 3.9** (or 3.10 if available)
5. **Click "Next"**

---

## Step 8: Configure WSGI File

1. **Click on the WSGI configuration file link** (usually `/var/www/yourusername_pythonanywhere_com_wsgi.py`)
2. **Delete everything** in the file
3. **Replace with this** (update `yourusername`):

```python
import os
import sys

# Add your project directory to the path
path = '/home/yourusername/ds-experiment-omri'
if path not in sys.path:
    sys.path.insert(0, path)

# Set Django settings module
os.environ['DJANGO_SETTINGS_MODULE'] = 'PurchaseodInfo.settings'

# Activate virtual environment
activate_this = '/home/yourusername/ds-experiment-omri/venv/bin/activate_this.py'
with open(activate_this) as file_:
    exec(file_.read(), dict(__file__=activate_this))

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

**Important:** Replace `yourusername` with your actual PythonAnywhere username in both places!

---

## Step 9: Configure Static Files

1. **In "Web" tab**, scroll down to **"Static files"** section
2. **Add static file mapping**:
   - **URL**: `/static/`
   - **Directory**: `/home/yourusername/ds-experiment-omri/staticfiles`
   - Click **"Add"**

3. **Add media files mapping** (if needed):
   - **URL**: `/media/`
   - **Directory**: `/home/yourusername/ds-experiment-omri/media`
   - Click **"Add"**

---

## Step 10: Reload Web App

1. **Scroll to top** of "Web" tab
2. **Click the green "Reload" button**
3. **Wait a few seconds** for it to reload

---

## Step 11: Test Your Site

Visit: `https://yourusername.pythonanywhere.com`

You should see your landing page!

---

## Troubleshooting

### If you get 500 error:
1. Check **"Error log"** in Web tab
2. Common issues:
   - Wrong path in WSGI file
   - `ALLOWED_HOSTS` not set correctly
   - Missing dependencies

### If static files don't load:
1. Make sure `collectstatic` ran successfully
2. Check static files mapping in Web tab
3. Verify `STATIC_ROOT` in settings.py

### If database errors:
1. Make sure migrations ran: `python manage.py migrate`
2. Check file permissions: `chmod 664 db.sqlite3`

### To check logs:
```bash
# In Bash console:
tail -f /var/log/yourusername.pythonanywhere.com.error.log
```

---

## Quick Commands Reference

```bash
# Navigate to project
cd ~/ds-experiment-omri

# Activate virtual environment
source venv/bin/activate

# Run migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput

# Create superuser (if needed)
python manage.py createsuperuser

# Check Django version
python -c "import django; print(django.get_version())"
```

---

## Updating Your Site (After Code Changes)

1. **Pull latest code**:
```bash
cd ~/ds-experiment-omri
git pull origin main
```

2. **If requirements changed**:
```bash
source venv/bin/activate
pip install -r requirements.txt
```

3. **If database changes**:
```bash
python manage.py migrate
```

4. **If static files changed**:
```bash
python manage.py collectstatic --noinput
```

5. **Reload web app** in Web tab

---

## Security Notes

⚠️ **Important for Production:**
- Set `DEBUG = False` in settings.py
- Change `SECRET_KEY` (generate new one)
- Use environment variables for sensitive data
- Consider using PostgreSQL instead of SQLite for production

---

## Need Help?

- PythonAnywhere Docs: https://help.pythonanywhere.com/
- Django Deployment: https://docs.djangoproject.com/en/4.2/howto/deployment/
- Check error logs in Web tab

