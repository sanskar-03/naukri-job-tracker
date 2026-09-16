import io
import logging
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

from scraper import scrape_naukri_jobs
from storage import merge_jobs, read_excel, write_excel

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    filename=LOG_DIR / "naukri_tracker.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

st.set_page_config(page_title="Naukri Job Tracker", page_icon="💼", layout="wide")

def ensure_playwright_browser():
    """Install Chromium on first run when the deployment environment does not have it."""
    marker = Path("/tmp/naukri_playwright_chromium_ready")
    if marker.exists():
        return
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            try:
                p.chromium.executable_path
                browser = p.chromium.launch(headless=True)
                browser.close()
                marker.touch()
                return
            except Exception:
                pass
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        marker.touch()
    except Exception as exc:
        logger.exception("Playwright browser setup failed: %s", exc)
        raise RuntimeError(
            "Playwright Chromium could not be prepared. "
            "On Streamlit Cloud, make sure packages.txt and requirements.txt "
            "are present, then redeploy."
        ) from exc

st.title("💼 Naukri Job Tracker")
st.caption("Python + Playwright • Excel persistence • Job URL/ID deduplication")

with st.sidebar:
    st.header("Search")
    keyword = st.text_input("Job keyword", "Python Developer")
    location = st.text_input("Location", "Bangalore")
    pages = st.number_input("Pages", min_value=1, max_value=5, value=1, step=1)
    timeout_ms = st.number_input(
        "Page timeout (ms)", min_value=10000, max_value=60000, value=30000, step=5000
    )
    st.divider()
    st.markdown("### Existing Excel")
    uploaded = st.file_uploader(
        "Upload previous master Excel (optional)",
        type=["xlsx"],
        help="The app compares new results with this file and preserves all existing rows.",
    )

if "master_df" not in st.session_state:
    st.session_state.master_df = pd.DataFrame()

if uploaded is not None:
    try:
        uploaded_df = read_excel(uploaded)
        if st.session_state.master_df.empty:
            st.session_state.master_df = uploaded_df
        st.success(f"Loaded {len(uploaded_df):,} existing records.")
    except Exception as exc:
        st.error(f"Could not read the Excel file: {exc}")

if st.button("🔎 Scrape Naukri", type="primary", use_container_width=True):
    if not keyword.strip():
        st.error("Enter a job keyword.")
        st.stop()

    try:
        ensure_playwright_browser()
        with st.spinner("Opening Naukri and extracting job listings with Playwright..."):
            new_jobs = scrape_naukri_jobs(
                keyword=keyword.strip(),
                location=location.strip(),
                pages=int(pages),
                timeout_ms=int(timeout_ms),
            )

        new_df = pd.DataFrame(new_jobs)
        combined_df, added_df, duplicate_count = merge_jobs(
            st.session_state.master_df, new_df
        )
        st.session_state.master_df = combined_df

        logger.info(
            "Search keyword=%r location=%r scraped=%d added=%d duplicates=%d",
            keyword, location, len(new_df), len(added_df), duplicate_count
        )

        st.success(
            f"Scraped {len(new_df):,} jobs • Added {len(added_df):,} new • "
            f"Skipped {duplicate_count:,} duplicates • Master total {len(combined_df):,}"
        )
    except Exception as exc:
        logger.exception("Scrape failed")
        st.error(str(exc))
        st.info(
            "If Naukri blocks the request or presents a challenge page, retry later "
            "or run the same project locally. The application intentionally reports "
            "the block instead of pretending that data was extracted."
        )

st.divider()

df = st.session_state.master_df
if not df.empty:
    c1, c2, c3 = st.columns(3)
    c1.metric("Master jobs", f"{len(df):,}")
    c2.metric("Columns", f"{len(df.columns):,}")
    c3.metric("Unique Job IDs/URLs", f"{len(df):,}")

    st.dataframe(df, use_container_width=True, hide_index=True)

    excel_bytes = write_excel(df)
    st.download_button(
        "⬇️ Download Master Excel",
        data=excel_bytes,
        file_name="naukri_jobs_master.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
else:
    st.info(
        "No jobs loaded yet. Enter a keyword/location and click Scrape Naukri. "
        "For later runs, upload the previously downloaded master Excel."
    )

st.caption("For evaluation/demo use. Respect Naukri.com terms, robots rules, and applicable law.")
