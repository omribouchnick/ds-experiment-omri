# Experiment Project Guide: Structure & Adaptation

## 📁 Project Structure

```
purchase-of-info-omri/
│
├── 📂 PurchaseodInfo/          # Django project configuration
│   ├── settings.py             # Main settings (database, apps, etc.)
│   ├── urls.py                 # Root URL routing
│   └── wsgi.py                 # Web server interface
│
├── 📂 experiment/              # Main Django app (your experiment logic)
│   ├── models.py               # Database models (ExperimentData, ExperimentAction, TOASTResponse)
│   ├── views.py                # Backend logic (page handlers, data loading)
│   ├── urls.py                 # URL routing for experiment pages
│   └── migrations/             # Database schema changes
│
├── 📂 templates/               # HTML pages (what users see)
│   ├── landing_page.html       # Welcome page
│   ├── consent_form.html       # Consent form
│   ├── instructions.html       # Experiment instructions
│   ├── game.html               # Main game/trial page
│   ├── toast_1.html            # Post-experiment questionnaire (part 1)
│   ├── toast_2.html            # Post-experiment questionnaire (part 2)
│   └── end.html                # Thank you page
│
├── 📂 static/                  # Static files (CSS, images, fonts)
│   ├── images/                 # Images (glucometer, alarms, etc.)
│   └── fonts/                  # Custom fonts
│
├── 📂 data/                    # Data files
│   ├── conditions_experiment_3ps_11x11_120_A.csv  # Main experiment data
│   ├── experiment_data.csv     # Output: participant data
│   ├── experiment_actions.csv  # Output: all trial responses
│   └── TOAST.csv               # Output: questionnaire responses
│
├── manage.py                   # Django management script
├── db.sqlite3                  # SQLite database (stores all data)
└── requirements.txt            # Python dependencies
```

------
# 📁 ds-experiment-omri Project Structure Map

## 🎯 Where Everything Is Located

This is a **Django web application**, so the structure follows Django conventions:

### **Backend Logic (Views/Controllers)**
📍 **Location**: `experiment/views.py`

This file contains ALL the backend logic functions:
- `landing_page()` - Landing page handler
- `consent_form()` - Consent form handler  
- `instructions()` - Instructions page handler
- `game()` - **Main game/trial handler** ⭐
- `toast_1()` - Post-experiment questionnaire part 1
- `toast_2()` - Post-experiment questionnaire part 2
- `end()` - End page handler
- `save_db()` - Export data function
- `load_block_trials()` - Load trial data from CSV
- `progress()` - User progress tracking
- `recaptcha()` - reCAPTCHA verification

### **Frontend/UI (HTML Templates)**
📍 **Location**: `templates/` folder

All the HTML/UI files:
- `landing_page.html` - Welcome page
- `consent_form.html` - Consent form UI
- `instructions.html` - **Instructions UI** ⭐
- `game.html` - **Main game/trial UI** ⭐
- `toast_1.html` - Questionnaire part 1 UI
- `toast_2.html` - Questionnaire part 2 UI
- `end.html` - Thank you page
- `BlockSummary.html` - Block summary display
- `PurchaseDecision.html` - Purchase decision screen
- `user_progress.html` - Progress tracking UI

### **URL Routing**
📍 **Location**: `experiment/urls.py`

Maps URLs to view functions:
- `/` → `landing_page()`
- `/consent_form/` → `consent_form()`
- `/instructions/` → `instructions()`
- `/game/` → `game()` ⭐
- `/toast_1/` → `toast_1()`
- `/toast_2/` → `toast_2()`
- `/end/` → `end()`
- `/save_db/` → `save_db()`

### **Database Models**
📍 **Location**: `experiment/models.py`

Defines database structure:
- `ExperimentData` - Participant data
- `ExperimentAction` - Trial responses
- `TOASTResponse` - Questionnaire responses

### **Static Files (CSS, Images, Fonts)**
📍 **Location**: `static/` folder
- `static/images/` - All images (glucometer, car dashboard, etc.)
- `static/fonts/` - Custom fonts

### **Data Files**
📍 **Location**: `data/` folder
- `conditions_experiment_3ps_11x11_120_A.csv` - Trial conditions
- `experiment_data.csv` - Exported participant data
- `experiment_actions.csv` - Exported trial responses
- `TOAST.csv` - Exported questionnaire data

---

## 🔄 How It All Connects

```
User visits URL: /game/
    ↓
experiment/urls.py routes to: views.game()
    ↓
experiment/views.py: game() function processes request
    ↓
Renders template: templates/game.html
    ↓
User sees the game UI
```

---

## 📋 Quick Reference

| What You're Looking For | Where It Is |
|------------------------|-------------|
| **Game logic** | `experiment/views.py` → `game()` function |
| **Game UI/HTML** | `templates/game.html` |
| **Instructions logic** | `experiment/views.py` → `instructions()` function |
| **Instructions UI** | `templates/instructions.html` |
| **All view functions** | `experiment/views.py` |
| **All HTML templates** | `templates/` folder |
| **URL routing** | `experiment/urls.py` |
| **Database models** | `experiment/models.py` |
| **Images** | `static/images/` |
| **Data files** | `data/` folder |

---

## 🎮 Main Experiment Flow

1. **Landing** → `views.landing_page()` → `templates/landing_page.html`
2. **Consent** → `views.consent_form()` → `templates/consent_form.html`
3. **Instructions** → `views.instructions()` → `templates/instructions.html`
4. **Game/Trials** → `views.game()` → `templates/game.html` ⭐
5. **Questionnaire** → `views.toast_1()` → `templates/toast_1.html`
6. **Questionnaire 2** → `views.toast_2()` → `templates/toast_2.html`
7. **End** → `views.end()` → `templates/end.html`

---

## 💡 Key Files to Edit

- **Change game logic?** → Edit `experiment/views.py` → `game()` function
- **Change game UI?** → Edit `templates/game.html`
- **Change instructions?** → Edit `templates/instructions.html`
- **Add new page?** → Add function to `views.py` + add template + add URL route


-----

## How It Works: Experiment Flow

### **1. Landing Page** (`landing_page.html` → `views.landing_page()`)
- User arrives at the experiment
- Randomly assigns experimental condition (ps, d'H, d'S)
- Loads trial data from CSV
- Creates database entry for participant

### **2. Consent Form** (`consent_form.html` → `views.consent_form()`)
- User reads and accepts consent
- Redirects to reCAPTCHA

### **3. Instructions** (`instructions.html` → `views.instructions()`)
- Multi-screen instructions
- Explains task, scoring, blocks
- User clicks through screens
- Starts Block 1 (practice, 10 trials)

### **4. Game/Trials** (`game.html` → `views.game()`)
- **Block 1**: 10 practice trials (no DS system)
- **Block 2**: 10 practice trials (with DS system)
- **Block 3**: 100 main trials (with DS system) - OR split into 2 blocks of 50
- For each trial:
  - Shows evidence value (number)
  - Shows DS alarm (if purchased)
  - User clicks "Intervention" or "No intervention"
  - Feedback (correct/wrong)
  - Score updates
  - Data saved to database

### **5. Questionnaires** (`toast_1.html`, `toast_2.html`)
- Post-experiment questions about system trust, usefulness, etc.

### **6. End Page** (`end.html`)
- Thank you message
- Completion status

--------------------------

## 📊 Data Flow (Unchanged)

```
CSV File (conditions_experiment_3ps_11x11_120_A.csv)
    ↓
load_block_trials() loads data
    ↓
User sees trial (game.html)
    ↓
User makes decision
    ↓
ExperimentAction saved to database
    ↓
Next trial or end
    ↓
save_db() exports to CSV files
```

**This flow stays the same regardless of domain!**

---

## 🧪 Testing Your Changes

1. **Start server**: `python manage.py runserver`
2. **Open browser**: `http://localhost:8000`
3. **Go through experiment**: Check all text appears correctly
4. **Check database**: Verify data is saved correctly
5. **Export data**: Use admin panel or `save_db()` view



