# Naukri Job Tracker — Python + Playwright

A portfolio-ready Python application that uses **Playwright** to extract Naukri.com job listings and maintains a master Excel workbook without duplicate jobs.

## Features

- Playwright-based browser scraping using Chromium.
- The scraper opens a normal Chromium browser context, loads the search page, reads the job cards, and closes the browser after the run.
- `PLAYWRIGHT_HEADLESS=true` is the default for Streamlit Cloud; set it to `false` locally if you want to watch the browser window.
- Extracts:
  - Job ID
  - Job Title
  - Company
  - Location
  - Experience
  - Skills
  - Posted Date
  - Job URL
  - Scraped At
- Excel output using `pandas` + `openpyxl`.
- Deduplication using **Job ID**, falling back to **Job URL**.
- Preserves previously scraped jobs.
- Upload the previous master Excel on a new run.
- Streamlit interface for a simple demo.
- Basic error handling and logging.
- Streamlit Cloud deployment files included.

## Important persistence note

Streamlit Cloud/serverless-style environments should not be treated as permanent local storage.

The application therefore uses a reliable workflow:

1. Run a scrape.
2. Download `naukri_jobs_master.xlsx`.
3. On the next run, upload that workbook under **Existing Excel**.
4. Scrape again.
5. The application compares Job ID/URL, keeps all old records, and appends only new records.
6. Download the updated master workbook.

This satisfies the required "preserve previous jobs" behavior without depending on ephemeral server storage.

## Local setup

### 1. Python

Recommended: Python 3.10+.

### 2. Create a virtual environment

Windows:

```powershell
python -m venv .venv
.venv\Scripts\activate
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
python -m playwright install chromium

# Optional local visual-browser mode (PowerShell):
$env:PLAYWRIGHT_HEADLESS="false"
```

If Linux reports missing browser libraries, use:

```bash
python -m playwright install --with-deps chromium
```

### 4. Run

```bash
streamlit run app.py
```

Open the local URL shown by Streamlit.

## Streamlit Cloud deployment

1. Push this project to GitHub.
2. In Streamlit Community Cloud, create a new app from the repository.
3. Select `app.py` as the main file.
4. Deploy.

`packages.txt` contains the Linux libraries required by Chromium, and the application also attempts to install Chromium automatically if it is not already available.

## GitHub

Suggested repository name:

`naukri-job-tracker`

Suggested description:

> Python + Playwright Naukri job scraper with Excel persistence and URL/Job-ID deduplication.

## How to demonstrate it to a company

Use this flow during the demo:

1. Enter `Python Developer` and a location.
2. Click **Scrape Naukri**.
3. Show the extracted job table.
4. Download the Excel workbook.
5. Run a second scrape using the same search.
6. Upload the first workbook.
7. Scrape again.
8. Show that duplicates are skipped and only new jobs are appended.
9. Open the Excel file and show the preserved records.

## Error handling

The scraper does not silently treat a blocked page as successful data extraction. It reports:

- HTTP errors
- page-load timeouts
- missing job cards
- bot-protection/challenge pages
- browser setup failures

Logs are written to `logs/naukri_tracker.log` when running locally.

## Naukri access note

Naukri may change its HTML structure or apply bot-protection to automated browsers. This project uses multiple selectors and explicit block detection, but no scraper can guarantee uninterrupted access to a third-party site. For a company submission, demonstrate the application locally if the hosted Streamlit instance is temporarily blocked.

## Project structure

```text
naukri-job-tracker/
├── app.py
├── scraper.py
├── storage.py
├── requirements.txt
├── packages.txt
├── README.md
├── .gitignore
└── data/
```

## Deliverables checklist

- [x] Python source code
- [x] Playwright scraper
- [x] Excel output
- [x] New-job comparison
- [x] Job URL/Job ID deduplication
- [x] Previous records preserved
- [x] Error handling
- [x] Logging
- [x] requirements.txt
- [x] README setup instructions


## Browser behavior

This project does not use stealth plugins, CAPTCHA solvers, proxy rotation, or other bot-protection bypasses. Playwright controls Chromium for the requested scrape, then closes it. If Naukri returns HTTP 403 or a challenge page, the application stops and reports the block instead of fabricating results.

For Streamlit Cloud, the browser runs headlessly because the cloud server has no desktop display. This is still a real Chromium page load; only the window is not visible to the person using the web app.
