import logging
import re
import time
from datetime import datetime
from typing import Dict, List

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

NAUKRI_SEARCH = "https://www.naukri.com/{keyword}-jobs-in-{location}"

def _slug(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")

def _clean(value) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()

def _first_text(card, selectors):
    for selector in selectors:
        try:
            loc = card.locator(selector).first
            if loc.count():
                text = _clean(loc.inner_text(timeout=1500))
                if text:
                    return text
        except Exception:
            continue
    return ""

def _first_attr(card, selectors, attr):
    for selector in selectors:
        try:
            loc = card.locator(selector).first
            if loc.count():
                value = _clean(loc.get_attribute(attr, timeout=1500))
                if value:
                    return value
        except Exception:
            continue
    return ""

def _extract_experience(card) -> str:
    return _first_text(card, [
        "span.expwdth",
        "span[title*='experience' i]",
        "[class*='experience']",
        "[class*='exp']",
    ])

def _extract_location(card) -> str:
    return _first_text(card, [
        "span.locWdth",
        "span[title*='location' i]",
        "[class*='location']",
        "[class*='loc']",
    ])

def _extract_skills(card) -> str:
    selectors = [
        ".tags-gt",
        ".job-desc ul li",
        "[class*='tag']",
        "[class*='skill']",
    ]
    for selector in selectors:
        try:
            nodes = card.locator(selector)
            values = []
            for i in range(min(nodes.count(), 30)):
                text = _clean(nodes.nth(i).inner_text(timeout=1000))
                if text and text not in values:
                    values.append(text)
            if values:
                return ", ".join(values)
        except Exception:
            continue
    return ""

def _extract_posted(card) -> str:
    value = _first_text(card, [
        "span.job-post-day",
        "span[title*='posted' i]",
        "[class*='posted']",
        "[class*='date']",
    ])
    return value or "N/A"

def scrape_naukri_jobs(keyword: str, location: str, pages: int = 1, timeout_ms: int = 30000) -> List[Dict]:
    """
    Scrape Naukri search-result cards using Playwright.

    The DOM on Naukri can change. Multiple selectors are intentionally used,
    and missing optional fields are returned as N/A rather than crashing.
    """
    jobs: List[Dict] = []
    seen_keys = set()

    url = NAUKRI_SEARCH.format(keyword=_slug(keyword), location=_slug(location))
    logger.info("Starting Playwright scrape: %s", url)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--no-sandbox"],
        )
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/128.0.0.0 Safari/537.36"
            ),
            locale="en-IN",
        )
        page = context.new_page()
        page.set_default_timeout(timeout_ms)

        try:
            for page_no in range(1, pages + 1):
                target = url if page_no == 1 else f"{url}-{page_no}"
                logger.info("Opening page %s", target)

                try:
                    response = page.goto(target, wait_until="domcontentloaded", timeout=timeout_ms)
                    if response and response.status >= 400:
                        raise RuntimeError(
                            f"Naukri returned HTTP {response.status}. "
                            "The site may be blocking automated traffic."
                        )
                    page.wait_for_timeout(1800)
                except PlaywrightTimeoutError:
                    logger.warning("Navigation timeout on page %d", page_no)
                    if page_no == 1:
                        raise RuntimeError(
                            "Naukri page load timed out. Check your internet connection "
                            "or retry later."
                        )

                body_text = _clean(page.locator("body").inner_text(timeout=5000))
                block_markers = [
                    "captcha", "access denied", "request blocked",
                    "unusual traffic", "verify you are human"
                ]
                if any(marker in body_text.lower() for marker in block_markers):
                    raise RuntimeError(
                        "Naukri presented a bot-protection/block page. "
                        "No jobs were treated as successfully scraped."
                    )

                cards = page.locator("article.jobTuple")
                if cards.count() == 0:
                    cards = page.locator("div.srp-jobtuple-wrapper")
                if cards.count() == 0:
                    cards = page.locator("div.jobTuple")

                count = cards.count()
                logger.info("Found %d candidate cards on page %d", count, page_no)

                if count == 0 and page_no == 1:
                    raise RuntimeError(
                        "No job cards were found. Naukri's page structure may have changed "
                        "or automated access may have been blocked."
                    )

                for i in range(count):
                    card = cards.nth(i)
                    title = _first_text(card, [
                        "a.title",
                        "a[class*='title']",
                        "h2 a",
                        "h3 a",
                    ])
                    company = _first_text(card, [
                        "a.comp-name",
                        "a[class*='comp']",
                        "[class*='company']",
                    ])
                    job_url = _first_attr(card, [
                        "a.title",
                        "a[class*='title']",
                        "h2 a",
                        "h3 a",
                    ], "href")

                    if not title or not job_url:
                        continue

                    if job_url.startswith("/"):
                        job_url = "https://www.naukri.com" + job_url

                    job_id = ""
                    match = re.search(r"-(\d{5,})/?(?:\?.*)?$", job_url)
                    if match:
                        job_id = match.group(1)

                    key = job_id or job_url.rstrip("/")
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)

                    jobs.append({
                        "Job ID": job_id or "N/A",
                        "Job Title": title,
                        "Company": company or "N/A",
                        "Location": _extract_location(card) or "N/A",
                        "Experience": _extract_experience(card) or "N/A",
                        "Skills": _extract_skills(card) or "N/A",
                        "Posted Date": _extract_posted(card),
                        "Job URL": job_url,
                        "Scraped At": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    })

                if page_no < pages:
                    time.sleep(1.0)

        finally:
            context.close()
            browser.close()

    return jobs
