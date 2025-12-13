# 🚀 Deployment Guide - Upload Experiment Online

## Overview
Your Django experiment needs to be deployed to a web server so others can access it. Here are the best options:

---

## Option 1: PythonAnywhere (Recommended - Free & Easy)

### Why PythonAnywhere?
- ✅ Free tier available
- ✅ Easy setup for Django
- ✅ Already configured in your `ALLOWED_HOSTS`
- ✅ No credit card required

### Steps:

#### 1. Create Account
- Go to: https://www.pythonanywhere.com/
- Sign up for free "Beginner" account

#### 2. Upload Your Project
**Option A: Using Git (Recommended)**
```bash
# On PythonAnywhere console:
git clone <your-repo-url>
# OR upload via Files tab in web interface
```

**Option B: Upload via Web Interface**
- Go to "Files" tab
- Upload your entire `ds-experiment-omri` folder

#### 3. Set Up Virtual Environment
```bash
# In PythonAnywhere Bash console:
cd ~/ds-experiment-omri
python3.9 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### 4. Configure Settings for Production
Create `PurchaseodInfo/settings_production.py` or update `settings.py`:

```python
# Add to settings.py (or create separate production settings)
import os

DEBUG = False  # IMPORTANT: Set to False for production
ALLOWED_HOSTS = ['yourusername.pythonanywhere.com', 'www.yourusername.pythonanywhere.com']

# Static files
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']

# Media files (if needed)
MEDIA_ROOT = BASE_DIR / 'media'
MEDIA_URL = '/media/'
```

#### 5. Collect Static Files
```bash
python manage.py collectstatic --noinput
```

#### 6. Run Migrations
```bash
python manage.py migrate
```

#### 7. Configure Web App
- Go to "Web" tab in PythonAnywhere
- Click "Add a new web app"
- Choose "Manual configuration"
- Select Python 3.9
- In "WSGI configuration file", edit it:

```python
import os
import sys

path = '/home/yourusername/ds-experiment-omri'
if path not in sys.path:
    sys.path.insert(0, path)

os.environ['DJANGO_SETTINGS_MODULE'] = 'PurchaseodInfo.settings'

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

#### 8. Set Static Files Mapping
In "Web" tab → "Static files":
- URL: `/static/`
- Directory: `/home/yourusername/ds-experiment-omri/staticfiles`

#### 9. Reload Web App
Click the green "Reload" button

#### 10. Access Your Site
Your experiment will be at: `https://yourusername.pythonanywhere.com`

---

## Option 2: Railway (Modern & Easy)

### Why Railway?
- ✅ Free tier with $5 credit/month
- ✅ Automatic deployments from Git
- ✅ Easy setup

### Steps:

#### 1. Install Railway CLI
```bash
npm install -g @railway/cli
railway login
```

#### 2. Initialize Project
```bash
cd ds-experiment-omri
railway init
```

#### 3. Add Environment Variables
```bash
railway variables set DEBUG=False
railway variables set SECRET_KEY=your-secret-key-here
railway variables set ALLOWED_HOSTS=your-app.railway.app
```

#### 4. Deploy
```bash
railway up
```

---

## Option 3: Render (Free Tier Available)

### Steps:

#### 1. Create Account
- Go to: https://render.com/
- Sign up with GitHub

#### 2. Create New Web Service
- Connect your GitHub repo
- Choose "Web Service"
- Settings:
  - Build Command: `pip install -r requirements.txt && python manage.py collectstatic --noinput`
  - Start Command: `gunicorn PurchaseodInfo.wsgi:application`
  - Environment: Python 3

#### 3. Add Environment Variables
- `DEBUG=False`
- `SECRET_KEY=your-secret-key`
- `ALLOWED_HOSTS=your-app.onrender.com`

---

## 🔒 Security Checklist (IMPORTANT!)

Before deploying, make sure:

1. **Set DEBUG = False** in production
2. **Change SECRET_KEY** - generate new one:
   ```python
   from django.core.management.utils import get_random_secret_key
   print(get_random_secret_key())
   ```
3. **Set ALLOWED_HOSTS** to your actual domain
4. **Use HTTPS** (most platforms provide this automatically)
5. **Set up proper static files** (collectstatic)

---

## 📝 Quick Production Settings Update

I can help you create a production-ready settings file. The main changes needed:

1. `DEBUG = False`
2. `ALLOWED_HOSTS = ['your-domain.com']`
3. `STATIC_ROOT` for static files
4. Secure `SECRET_KEY` (use environment variable)

---

## 🆘 Troubleshooting

### Static files not loading?
- Run `python manage.py collectstatic`
- Check STATIC_ROOT and STATIC_URL settings
- Verify static files mapping in web server config

### 500 Internal Server Error?
- Check server logs
- Verify DEBUG=False doesn't hide errors (check logs)
- Ensure all migrations are run
- Check file permissions

### Database errors?
- Ensure SQLite file has write permissions
- Or switch to PostgreSQL for production (recommended)

---

## 📊 Which Option Should You Choose?

- **PythonAnywhere**: Best for beginners, free tier, already configured
- **Railway**: Modern, automatic deployments, good free tier
- **Render**: Easy GitHub integration, free tier available
- **VPS (DigitalOcean, AWS)**: More control, requires more setup

**Recommendation**: Start with **PythonAnywhere** since it's already in your config!

---

## Next Steps

1. Choose a platform
2. I can help you update settings.py for production
3. Deploy and test
4. Share the URL with participants!

Would you like me to:
- Update your settings.py for production?
- Create a production settings file?
- Help with a specific platform setup?

