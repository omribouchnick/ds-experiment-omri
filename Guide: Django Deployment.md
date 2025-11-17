# 🚀 Deployment FAQ - Quick Answers

## 1. Is PythonAnywhere a web service for Django?

**Yes!** PythonAnywhere is a hosting service specifically designed for Python web applications, including Django. It's:
- ✅ Free tier available (perfect for experiments)
- ✅ Pre-configured for Django
- ✅ Easy to use (no server management needed)
- ✅ Already in your `ALLOWED_HOSTS` settings

**Think of it like:** Your computer runs Django locally → PythonAnywhere runs it on the internet so others can access it.

---

## 2. Do I have to do all those steps?

**Yes, but it's simpler than it looks!** Here's the **minimal version**:

### Quick Steps (5 minutes):
1. **Sign up** at pythonanywhere.com (free)
2. **Upload your project** (drag & drop in Files tab)
3. **Install packages**: `pip install -r requirements.txt`
4. **Run migrations**: `python manage.py migrate`
5. **Collect static files**: `python manage.py collectstatic`
6. **Configure Web app** (copy-paste WSGI config)
7. **Reload** → Done!

The detailed guide has explanations, but the actual steps are straightforward.

---

## 3. Will data be saved so I can download CSV?

**Yes!** Your data is saved in two places:

### A. Database (SQLite)
- All participant data is saved to `db.sqlite3` on the server
- Every trial, decision, and questionnaire response is stored
- This file is on PythonAnywhere's server

### B. CSV Export
You have two ways to export:

**Option 1: Using the export script** (recommended)
```bash
# On PythonAnywhere console:
python export_data.py
```
This creates:
- `data/experiment_data.csv` - All participants
- `data/experiment_actions.csv` - All trial responses  
- `data/TOAST.csv` - All questionnaire responses

**Option 2: Using Django admin** (if you set it up)
- Access admin panel
- Export data directly

**How to download:**
- Go to PythonAnywhere "Files" tab
- Navigate to `data/` folder
- Download the CSV files

**Or use command line:**
```bash
# Download via Files tab web interface
# OR use scp/rsync if you have SSH access
```

---

## 4. Why can't I share http://127.0.0.1:8000/ with others?

**Because `127.0.0.1` (localhost) only works on YOUR computer!**

### What's happening:
- `127.0.0.1` = "this computer only"
- When you run `python manage.py runserver`, it only listens on your local machine
- Other people's computers can't reach your `127.0.0.1` - it's not on the internet

### The solution:
**Deploy to a web server** (like PythonAnywhere) which gives you:
- A real internet address: `https://yourusername.pythonanywhere.com`
- Accessible from anywhere in the world
- 24/7 availability (if you want)

### Analogy:
- **Localhost (127.0.0.1)**: Like a phone that only calls itself
- **Deployed site**: Like a phone with a real phone number everyone can call

---

## 🎯 Quick Decision Guide

**Want to share with others?** → **Deploy to PythonAnywhere** (or similar)

**Just testing yourself?** → **Keep using localhost:8000**

**Need data collection?** → **Deploy** (data will be saved on server)

---

## 📊 Data Flow After Deployment

```
User visits: https://yourusername.pythonanywhere.com
    ↓
Completes experiment
    ↓
Data saved to: db.sqlite3 (on PythonAnywhere server)
    ↓
You run: python export_data.py
    ↓
CSV files created in: data/ folder
    ↓
You download CSV files from PythonAnywhere Files tab
    ↓
Analyze data locally
```

---

## ⚡ Even Simpler Alternative

If you want to test quickly without full deployment:

**Use ngrok** (temporary tunnel):
```bash
# Install ngrok: https://ngrok.com/
ngrok http 8000
# This gives you a temporary public URL like: https://abc123.ngrok.io
# Share this URL (but it only works while your computer is on)
```

**But for real data collection, deploy properly!**

---

## 🆘 Need Help?

I can:
- Walk you through PythonAnywhere setup step-by-step
- Create a simplified deployment script
- Help troubleshoot any issues

Just ask! 🚀


