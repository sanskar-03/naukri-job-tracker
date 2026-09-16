# Final Deployment Checklist

[ ] Push repository to GitHub
[ ] Keep `data/naukri_jobs.xlsx` tracked in Git
[ ] Add `DEFAULT_KEYWORD`, `DEFAULT_LOCATION`, `DEFAULT_PAGES` repository variables
[ ] Enable Actions and allow the workflow to write repository contents
[ ] Run the workflow manually once and verify `data/naukri_jobs.xlsx` changes only when new jobs are found
[ ] Open the Streamlit Community Cloud deployment and verify the dashboard reads the workbook
[ ] Copy the generated `https://<subdomain>.streamlit.app` URL into the submission form/report
[ ] For the final ZIP, exclude `.git`, `.venv`, browser caches, SQLite databases, logs and `__pycache__`
