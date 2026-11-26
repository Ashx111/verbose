# Chicago Crime Analytics — Capstone (Flask + SQLite3 + Streamlit)

Simple, viva-ready Python implementation for the Accenture × Chicago Police Department crime analytics case study.

## Architecture

- **`app/` (Modular Flask Backend)**:
  - `app/__init__.py`: Creates the Flask app and registers blueprints.
  - `app/db.py`: Standard library `sqlite3` connection and CSV seeding helper.
  - `app/routes_community.py`: CRUD endpoints (`GET`, `POST`, `PUT`, `PATCH`, `DELETE`, `crime-summary`) on `/api/community` with exact `community_code` search (`?search=<code>`).
  - `app/routes_dashboard.py`: `/` (redirects to the Streamlit dashboard), `/health`, `/api/dashboard`, and `/api/dashboard/export` (PNG report).
  - `app/routes_ai.py` & `app/ai_sql.py`: `POST /api/ask-ai` using Groq (`openai/gpt-oss-120b`) to convert natural language into SQLite queries (`SELECT`, `INSERT`, `UPDATE`, `DELETE`) with 1-retry SQL error recovery.
- **`run.py`**: Starts the Flask server on `http://127.0.0.1:5000`.
- **`streamlit_app.py`**: Streamlit UI (`http://127.0.0.1:8501`) with three pages:
  - **Dashboard & Analytics**: KPIs, insights, Matplotlib/Seaborn charts, SQL views, and PNG download.
  - **Community CRUD**: Top action selector (`Create`, `Read / Search`, `Full Update`, `Partial Update`, `Delete`, `Crime Summary`) with a Search / Refresh button.
  - **Ask AI**: Natural-language SQL chat powered by Groq (`openai/gpt-oss-120b`).
- **`chicago_crime.db`**: SQLite3 warehouse with 6 tables (`crime`, `community`, `district`, `police_beat`, `iucr`, `ward_office`) and 2 views (`vw_crime_yearly`, `vw_crime_by_category`).
- **`notebooks/chicago_crime_analysis_copy.ipynb`**: Full Use Cases 1–5 analysis with all task headings and answers.
- **`Chicago_Crime_Analytics_Report_v3.docx`**: Summary Word document with screenshot placeholders, notebook cell references, and insights.

## Quick Start (Windows PowerShell)

```powershell
# 1. Create and activate a virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt

# 3. (Optional, for Ask AI) Set your Groq API key
copy .env.example .env
# Or set in PowerShell: $env:GROQ_API_KEY="your_key_here"
```

**Terminal 1 — Start Flask Backend:**
```powershell
.\venv\Scripts\Activate.ps1
python run.py
```

**Terminal 2 — Start Streamlit Dashboard:**
```powershell
.\venv\Scripts\Activate.ps1
streamlit run streamlit_app.py
```

Visiting `http://127.0.0.1:5000/` automatically redirects to the Streamlit dashboard at `http://127.0.0.1:8501/`. Dashboard, Charts, PNG Export, and Community CRUD work offline without an API key; **Ask AI** requires a `GROQ_API_KEY` (via `.env`, environment variable, or the Streamlit sidebar).

## Running Tests

```powershell
pytest -v
```

Covers 10 tests in `tests/test_app.py` (root redirect, health, full CRUD lifecycle, duplicate/404 handling, exact `community_code` search, dashboard JSON & PNG export, crime summary, and mocked Ask AI `SELECT`/`INSERT`/`UPDATE` flows).
