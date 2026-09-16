# Naukri Job Tracker - Deployment Ready

A deployment-ready Python + Playwright job scraper with duplicate-safe Excel history and a read-only Streamlit dashboard.

## Architecture

- **GitHub Actions:** runs the Playwright scraper on demand or on a schedule.
- **Excel history in Git:** `data/naukri_jobs.xlsx` is the persistent project data store.
- **Streamlit Community Cloud:** reads the Excel file and provides the live public dashboard.

Playwright is not executed from the public dashboard.

## Assignment coverage

- Job title, company, location, experience, skills, posted date and URL
- Job ID / URL duplicate prevention
- Preserve previously stored jobs
- Add only newly discovered jobs
- Excel output
- Logging and basic error handling
- Live web dashboard

## Local scraper

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install -r requirements-scraper.txt
python -m playwright install chromium
python scraper/naukri_scraper.py --keyword "Python Developer" --location "Chennai" --pages 1 --excel data/naukri_jobs.xlsx
```

## Local dashboard

```bash
pip install -r requirements.txt
streamlit run app.py
```

## GitHub Actions setup

Create repository variables in **Settings -> Secrets and variables -> Actions -> Variables**:

- `DEFAULT_KEYWORD`
- `DEFAULT_LOCATION`
- `DEFAULT_PAGES`

The workflow also supports **Run workflow** with keyword, location and pages inputs.

The workflow requests only `contents: write` so it can commit the updated workbook.

## Streamlit Community Cloud

Deploy the repository from `https://share.streamlit.io/` and choose `app.py` as the entrypoint. The root `requirements.txt` contains dashboard dependencies.

## Important operational note

The scraper checks for access restrictions and stops when the target page presents an access-control/CAPTCHA signal. It does not attempt to bypass access controls, authentication or rate limits. Site HTML can change, so selectors may require maintenance.

## Output

- `data/naukri_jobs.xlsx` - persistent master history and search sheets.
- Streamlit dashboard - live read-only presentation of that history.
