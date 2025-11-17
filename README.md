# ds-experiment-omri

Django web application for decision support experiment.

## Project Structure

- **Backend Logic**: `experiment/views.py` - Contains all view functions (game, instructions, etc.)
- **Frontend/UI**: `templates/` - HTML templates for all pages
- **Database Models**: `experiment/models.py` - Django models
- **Static Files**: `static/` - Images, fonts, CSS
- **Data**: `data/` - CSV files with experiment data

## Quick Start

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run migrations:
```bash
python manage.py migrate
```

3. Start the development server:
```bash
python manage.py runserver
```

4. Open in browser: `http://localhost:8000`

## Documentation

- See `PROJECT_GUIDE & Structure Mapping.md` for detailed project structure
- See `DEPLOYMENT_GUIDE.md` for deployment instructions

