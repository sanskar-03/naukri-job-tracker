
import argparse
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

from playwright.sync_api import (
    sync_playwright,
    TimeoutError as PlaywrightTimeoutError,
)

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1])
)

from storage.excel_store import append_new_jobs


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[1]

RUNTIME_DIR = Path(
    os.environ.get(
        "RUNTIME_DIR",
        BASE_DIR / "runtime"
    )
)

RUNTIME_DIR.mkdir(
    parents=True,
    exist_ok=True
)



LOG_FILE = (
    RUNTIME_DIR /
    "naukri_scraper.log"
)


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format=(
        "%(asctime)s | "
        "%(levelname)s | "
        "%(message)s"
    ),
)

log = logging.getLogger(
    "naukri"
)


# ============================================================
# SETTINGS
# ============================================================

MAX_PAGES = 5

NAVIGATION_TIMEOUT = 60000

CARD_WAIT_SECONDS = 25

PAGE_RETRIES = 2


# ============================================================
# CLEAN
# ============================================================

def clean(value):

    if value is None:
        return ""

    value = str(value)

    value = value.replace(
        "\xa0",
        " "
    )

    value = re.sub(
        r"\s+",
        " ",
        value
    )

    return value.strip()


# ============================================================
# CITY NORMALIZATION
# ============================================================

def normalize_city(value):

    value = clean(
        value
    ).lower()

    value = value.replace(
        "&",
        " and "
    )

    value = re.sub(
        r"[^a-z0-9,\-/ ]",
        " ",
        value
    )

    value = re.sub(
        r"\s+",
        " ",
        value
    )

    return value.strip()


# ============================================================
# STRICT LOCATION CHECK
# ============================================================

def location_is_match(
    actual,
    requested
):

    requested = normalize_city(
        requested
    )

    actual = normalize_city(
        actual
    )

    if not requested:
        return False

    if not actual:
        return False

    requested_parts = [
        clean(x)
        for x in re.split(
            r"[,/\-]+",
            requested
        )
        if clean(x)
    ]

    requested_city = (
        requested_parts[0]
        if requested_parts
        else requested
    )

    aliases = {

        "delhi": {
            "delhi",
            "new delhi",
        },

        "new delhi": {
            "delhi",
            "new delhi",
        },

        "bengaluru": {
            "bengaluru",
            "bangalore",
        },

        "bangalore": {
            "bengaluru",
            "bangalore",
        },

        "mumbai": {
            "mumbai",
            "bombay",
        },

        "bombay": {
            "mumbai",
            "bombay",
        },

        "gurugram": {
            "gurugram",
            "gurgaon",
        },

        "gurgaon": {
            "gurugram",
            "gurgaon",
        },

        "chennai": {
            "chennai",
            "madras",
        },

        "madras": {
            "chennai",
            "madras",
        },

        "kolkata": {
            "kolkata",
            "calcutta",
        },

        "calcutta": {
            "kolkata",
            "calcutta",
        },

        "pune": {
            "pune",
            "poona",
        },

        "poona": {
            "pune",
            "poona",
        },
    }

    accepted_names = aliases.get(
        requested_city,
        {requested_city}
    )

    # --------------------------------------------------------
    # IMPORTANT:
    #
    # For a strict search, a multi-city result is rejected.
    #
    # Example:
    #
    # Delhi / NCR                 ACCEPT
    # New Delhi                   ACCEPT
    #
    # Delhi / NCR, Hyderabad     REJECT
    # Delhi, Pune                REJECT
    # Delhi, Bengaluru           REJECT
    # --------------------------------------------------------

    found_requested = False

    for city in accepted_names:

        pattern = (
            r"(?<![a-z])"
            + re.escape(city)
            + r"(?![a-z])"
        )

        if re.search(
            pattern,
            actual
        ):

            found_requested = True

            break

    if not found_requested:
        return False

    # --------------------------------------------------------
    # Reject explicit competing cities.
    # --------------------------------------------------------

    competing_cities = {
        "delhi": {
            "pune",
            "hyderabad",
            "bengaluru",
            "bangalore",
            "mumbai",
            "chennai",
            "kolkata",
            "noida",
            "gurugram",
            "gurgaon",
            "ahmedabad",
            "jaipur",
            "indore",
            "lucknow",
            "nagpur",
        },

        "new delhi": {
            "pune",
            "hyderabad",
            "bengaluru",
            "bangalore",
            "mumbai",
            "chennai",
            "kolkata",
            "noida",
            "gurugram",
            "gurgaon",
        },

        "chennai": {
            "pune",
            "hyderabad",
            "bengaluru",
            "bangalore",
            "delhi",
            "new delhi",
            "mumbai",
            "kolkata",
        },

        "pune": {
            "delhi",
            "new delhi",
            "hyderabad",
            "bengaluru",
            "bangalore",
            "mumbai",
            "chennai",
        },

        "hyderabad": {
            "delhi",
            "new delhi",
            "pune",
            "bengaluru",
            "bangalore",
            "mumbai",
            "chennai",
        },

        "bengaluru": {
            "delhi",
            "new delhi",
            "pune",
            "hyderabad",
            "mumbai",
            "chennai",
            "kolkata",
        },

        "bangalore": {
            "delhi",
            "new delhi",
            "pune",
            "hyderabad",
            "mumbai",
            "chennai",
            "kolkata",
        },
    }

    competitors = competing_cities.get(
        requested_city,
        set()
    )

    for competitor in competitors:

        pattern = (
            r"(?<![a-z])"
            + re.escape(competitor)
            + r"(?![a-z])"
        )

        if re.search(
            pattern,
            actual
        ):

            return False

    return True


# ============================================================
# VERIFY
# ============================================================

def verify_job_location(
    job,
    requested_location
):

    actual = clean(
        job.get("location")
    )

    if not actual:

        print(
            "LOCATION_REJECTED|"
            "reason=missing|"
            f"requested={requested_location}|"
            f"title={job.get('title', '')}"
        )

        return False

    if location_is_match(
        actual,
        requested_location
    ):

        print(
            "LOCATION_ACCEPTED|"
            f"requested={requested_location}|"
            f"actual={actual}|"
            f"title={job.get('title', '')}"
        )

        return True

    print(
        "LOCATION_REJECTED|"
        f"requested={requested_location}|"
        f"actual={actual}|"
        f"title={job.get('title', '')}"
    )

    return False


# ============================================================
# KEYWORD
# ============================================================

def normalize_search_keyword(
    keyword
):

    keyword = clean(
        keyword
    )

    replacements = {
        "devoloper": "developer",
        "develper": "developer",
        "developr": "developer",
    }

    words = keyword.split()

    fixed = []

    for word in words:

        fixed.append(
            replacements.get(
                word.lower(),
                word
            )
        )

    return " ".join(
        fixed
    )


# ============================================================
# URL
# ============================================================

def build_search_url(
    keyword,
    location,
    page_number
):

    keyword = normalize_search_keyword(
        keyword
    )

    keyword_part = (
        quote_plus(keyword)
        .replace("+", "-")
    )

    if location:

        location_part = (
            quote_plus(location)
            .replace("+", "-")
        )

        url = (
            "https://www.naukri.com/"
            f"{keyword_part}-jobs-in-"
            f"{location_part}"
        )

    else:

        url = (
            "https://www.naukri.com/"
            f"{keyword_part}-jobs"
        )

    if page_number > 1:

        url += (
            f"-{page_number}"
        )

    return url


# ============================================================
# CARD SELECTORS
# ============================================================

CARD_SELECTORS = [

    "div.srp-jobtuple-wrapper",

    "article.jobTuple",

    "div.cust-job-tuple",

    "div.jobTuple",

    "[data-job-id]",

    "div[class*='jobTuple']",

    "div[class*='job-tuple']",
]


def find_cards(page):

    best_locator = None

    best_count = 0

    best_selector = ""

    for selector in CARD_SELECTORS:

        try:

            locator = page.locator(
                selector
            )

            count = locator.count()

            if count > best_count:

                best_locator = locator

                best_count = count

                best_selector = selector

        except Exception:
            continue

    if best_locator is not None:

        print(
            "JOB_CARDS|"
            f"selector={best_selector}|"
            f"count={best_count}"
        )

        return best_locator

    return None


# ============================================================
# SCROLL
# ============================================================

def scroll_results(
    page
):

    try:

        page.evaluate(
            """
            async () => {

                const sleep = ms =>
                    new Promise(
                        resolve =>
                            setTimeout(
                                resolve,
                                ms
                            )
                    );

                let oldHeight = 0;

                for (
                    let i = 0;
                    i < 8;
                    i++
                ) {

                    window.scrollTo(
                        0,
                        document.body.scrollHeight
                    );

                    await sleep(700);

                    const newHeight =
                        document.body.scrollHeight;

                    if (
                        newHeight === oldHeight
                    ) {
                        break;
                    }

                    oldHeight = newHeight;
                }

                window.scrollTo(
                    0,
                    0
                );

                await sleep(500);
            }
            """
        )

    except Exception as exc:

        log.debug(
            "Scroll error: %s",
            exc
        )


# ============================================================
# WAIT
# ============================================================

def wait_for_cards(
    page,
    seconds=25
):

    import time

    start = time.time()

    while (
        time.time() - start
        < seconds
    ):

        cards = find_cards(
            page
        )

        if cards is not None:

            try:

                if cards.count() > 0:

                    return cards

            except Exception:
                pass

        try:

            page.wait_for_timeout(
                1000
            )

        except Exception:

            time.sleep(1)

    return None


# ============================================================
# ACCESS CHECK
# ============================================================

def is_blocked(
    page
):

    try:

        text = clean(
            page.locator(
                "body"
            ).inner_text(
                timeout=3000
            )
        ).lower()

    except Exception:

        return False

    blocked = [
        "access denied",
        "verify you are human",
        "captcha",
        "unusual traffic",
        "robot check",
    ]

    return any(
        x in text
        for x in blocked
    )


# ============================================================
# DEBUG
# ============================================================

def save_debug(
    page,
    page_number,
    attempt
):

    path = (
        RUNTIME_DIR /
        f"naukri_debug_{page_number}_{attempt}.html"
    )

    try:

        path.write_text(
            page.content(),
            encoding="utf-8"
        )

    except Exception:
        pass


# ============================================================
# TEXT
# ============================================================

def first_text(
    card,
    selectors
):

    for selector in selectors:

        try:

            locator = card.locator(
                selector
            )

            if locator.count() > 0:

                value = clean(
                    locator.first.inner_text(
                        timeout=1500
                    )
                )

                if value:
                    return value

        except Exception:
            continue

    return ""


def first_attr(
    card,
    selectors,
    attribute
):

    for selector in selectors:

        try:

            locator = card.locator(
                selector
            )

            if locator.count() > 0:

                value = clean(
                    locator.first.get_attribute(
                        attribute,
                        timeout=1500
                    )
                )

                if value:
                    return value

        except Exception:
            continue

    return ""


# ============================================================
# URL
# ============================================================

def normalize_url(
    url
):

    if not url:
        return ""

    url = clean(
        url
    )

    if url.startswith("/"):

        url = (
            "https://www.naukri.com"
            + url
        )

    return url.split("?")[0]


# ============================================================
# JOB ID
# ============================================================

def extract_job_id(
    url,
    card
):

    for attr in [
        "data-job-id",
        "data-jobid",
    ]:

        try:

            value = card.get_attribute(
                attr
            )

            if value:
                return clean(value)

        except Exception:
            pass

    if url:

        match = re.search(
            r"/job-listings/[^/?#]+-(\d+)",
            url,
            re.I
        )

        if match:
            return match.group(1)

        match = re.search(
            r"[?&]id=(\d+)",
            url,
            re.I
        )

        if match:
            return match.group(1)

    return ""


# ============================================================
# LOCATION
# ============================================================

def extract_location(
    card,
    requested_location
):

    selectors = [

        ".locWdth",

        ".loc",

        ".job-location",

        "[class*='location']",

        "[class*='locWdth']",

        "[data-testid*='location']",
    ]

    candidates = []

    for selector in selectors:

        try:

            locator = card.locator(
                selector
            )

            count = locator.count()

            for i in range(
                min(count, 10)
            ):

                try:

                    text = clean(
                        locator.nth(i).inner_text(
                            timeout=1000
                        )
                    )

                    if text:
                        candidates.append(
                            text
                        )

                except Exception:
                    continue

        except Exception:
            continue

    # --------------------------------------------------------
    # Prefer the candidate containing requested location.
    # --------------------------------------------------------

    for candidate in candidates:

        if location_is_match(
            candidate,
            requested_location
        ):

            return candidate

    if candidates:

        return candidates[0]

    return ""


# ============================================================
# EXTRACT ONE CARD
# ============================================================

def extract_job(
    card,
    requested_location
):

    title = first_text(
        card,
        [
            "a.title",
            "a[class*='title']",
            "h2 a",
            "h2",
            "h3",
            ".jobTupleHeader",
        ]
    )

    company = first_text(
        card,
        [
            "a.comp-name",
            "a[class*='comp']",
            ".comp-name",
            ".companyInfo",
        ]
    )

    location = extract_location(
        card,
        requested_location
    )

    experience = first_text(
        card,
        [
            ".expwdth",
            ".exp",
            "[class*='experience']",
        ]
    )

    skills = first_text(
        card,
        [
            ".tags-gt",
            ".tags",
            "[class*='skills']",
        ]
    )

    posted_date = first_text(
        card,
        [
            ".job-post-day",
            ".type",
            "[class*='date']",
        ]
    )

    job_url = first_attr(
        card,
        [
            "a.title",
            "a[href*='job-listings']",
            "a[href*='/job/']",
        ],
        "href"
    )

    job_url = normalize_url(
        job_url
    )

    job_id = extract_job_id(
        job_url,
        card
    )

    if not job_url:

        try:

            links = card.locator(
                "a"
            )

            count = links.count()

            for i in range(
                min(count, 20)
            ):

                href = normalize_url(
                    links.nth(i).get_attribute(
                        "href"
                    )
                )

                if (
                    href
                    and
                    (
                        "job-listings"
                        in href
                        or "/job/"
                        in href
                    )
                ):

                    job_url = href

                    break

        except Exception:
            pass

    if not title and job_url:

        try:

            title = clean(
                card.locator(
                    "a"
                ).first.inner_text(
                    timeout=1500
                )
            )

        except Exception:
            pass

    if not title and not job_url:

        return None

    if not job_id:

        job_id = (
            job_url
            or
            (
                title
                + "|"
                + company
                + "|"
                + location
            )
        )

    return {

        "job_id": job_id,

        "title": title,

        "company": company,

        "location": location,

        "experience": experience,

        "skills": skills,

        "posted_date": posted_date,

        "job_url": job_url,

        "scraped_at":
            datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
    }


# ============================================================
# SCRAPE ONE PAGE
# ============================================================

def scrape_page(
    page,
    keyword,
    location,
    page_number
):

    url = build_search_url(
        keyword,
        location,
        page_number
    )

    print()
    print(
        "-" * 70
    )

    print(
        f"PAGE_START|page={page_number}"
    )

    print(
        f"Opening: {url}"
    )

    for attempt in range(
        1,
        PAGE_RETRIES + 1
    ):

        print(
            "PAGE_ATTEMPT|"
            f"page={page_number}|"
            f"attempt={attempt}/"
            f"{PAGE_RETRIES}"
        )

        try:

            response = page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=NAVIGATION_TIMEOUT
            )

            status = (
                response.status
                if response
                else None
            )

            print(
                "HTTP_STATUS|"
                f"page={page_number}|"
                f"status={status}"
            )

        except PlaywrightTimeoutError:

            print(
                "NAVIGATION_TIMEOUT|"
                f"page={page_number}"
            )

        except Exception as exc:

            print(
                "NAVIGATION_ERROR|"
                f"page={page_number}|"
                f"error={exc}"
            )

            if attempt < PAGE_RETRIES:

                try:
                    page.wait_for_timeout(
                        2500
                    )
                except Exception:
                    pass

                continue

            return []

        # ----------------------------------------------------
        # Give page a moment.
        # ----------------------------------------------------

        try:

            page.wait_for_timeout(
                1500
            )

        except Exception:
            pass

        # ----------------------------------------------------
        # Block check.
        # ----------------------------------------------------

        if is_blocked(page):

            print(
                "ACCESS_RESTRICTION|"
                f"page={page_number}"
            )

            save_debug(
                page,
                page_number,
                attempt
            )

            if attempt < PAGE_RETRIES:

                try:
                    page.wait_for_timeout(
                        3000
                    )
                except Exception:
                    pass

                continue

            return []

        # ----------------------------------------------------
        # Initial cards.
        # ----------------------------------------------------

        cards = find_cards(
            page
        )

        # ----------------------------------------------------
        # Scroll if necessary.
        # ----------------------------------------------------

        if cards is None:

            print(
                "CARDS_NOT_FOUND|"
                f"page={page_number}|"
                "scrolling"
            )

            scroll_results(
                page
            )

            cards = wait_for_cards(
                page
            )

        else:

            # Still scroll once because Naukri
            # can lazy-load additional cards.

            scroll_results(
                page
            )

            try:

                page.wait_for_timeout(
                    1000
                )

            except Exception:
                pass

            refreshed = find_cards(
                page
            )

            if refreshed is not None:
                cards = refreshed

        # ----------------------------------------------------
        # No cards.
        # ----------------------------------------------------

        if cards is None:

            print(
                "PAGE_EMPTY|"
                f"page={page_number}"
            )

            save_debug(
                page,
                page_number,
                attempt
            )

            if attempt < PAGE_RETRIES:
                continue

            return []

        try:

            count = cards.count()

        except Exception:

            count = 0

        if count == 0:

            print(
                "PAGE_EMPTY|"
                f"page={page_number}"
            )

            if attempt < PAGE_RETRIES:
                continue

            return []

        print(
            "CARDS_FOUND|"
            f"page={page_number}|"
            f"count={count}"
        )

        # ----------------------------------------------------
        # ONE CARD = ONE JOB
        # ----------------------------------------------------

        jobs = []

        for index in range(
            count
        ):

            try:

                job = extract_job(
                    cards.nth(index),
                    location
                )

                if job is None:

                    continue

                jobs.append(
                    job
                )

            except Exception as exc:

                print(
                    "CARD_ERROR|"
                    f"page={page_number}|"
                    f"card={index + 1}|"
                    f"error={exc}"
                )

        print(
            "PAGE_PARSED|"
            f"page={page_number}|"
            f"parsed={len(jobs)}"
        )

        return jobs

    return []


# ============================================================
# DEDUPLICATE
# ============================================================

def deduplicate_jobs(
    jobs
):

    unique = {}

    duplicates = 0

    for job in jobs:

        key = clean(
            job.get("job_id")
        )

        if not key:

            key = clean(
                job.get("job_url")
            )

        if not key:

            key = (
                clean(
                    job.get("title")
                )
                + "|"
                + clean(
                    job.get("company")
                )
                + "|"
                + clean(
                    job.get("location")
                )
            )

        if key in unique:

            duplicates += 1

            continue

        unique[key] = job

    print(
        "DUPLICATES|"
        f"removed={duplicates}"
    )

    return list(
        unique.values()
    )


# ============================================================
# STRICT FILTER
# ============================================================

def filter_verified_jobs(
    jobs,
    requested_location
):

    accepted = []

    rejected = 0

    for job in jobs:

        if verify_job_location(
            job,
            requested_location
        ):

            accepted.append(
                job
            )

        else:

            rejected += 1

    print(
        "LOCATION_SUMMARY|"
        f"requested={requested_location}|"
        f"accepted={len(accepted)}|"
        f"rejected={rejected}"
    )

    return accepted


# ============================================================
# MAIN
# ============================================================

def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--keyword",
        required=True
    )

    parser.add_argument(
        "--location",
        default=""
    )

    parser.add_argument(
        "--pages",
        type=int,
        default=1
    )

    parser.add_argument(
        "--excel",
        required=True
    )

    args = parser.parse_args()

    pages = max(
        1,
        min(
            args.pages,
            MAX_PAGES
        )
    )

    print()
    print(
        "=" * 70
    )
    print(
        "PLAYWRIGHT HEADED MODE"
    )
    print(
        "=" * 70
    )

    print(
        f"Keyword : {args.keyword}"
    )

    print(
        f"Location: {args.location}"
    )

    print(
        f"Pages   : {pages}"
    )

    print(f"Headless: {os.getenv('HEADLESS', '1')}")

    print(
        "=" * 70
    )

    all_jobs = []

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=os.getenv("HEADLESS", "1") == "1",
            args=["--disable-dev-shm-usage"],
        )
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            locale="en-IN",
        )

        page = (
            context.pages[0]
            if context.pages
            else context.new_page()
        )

        page.set_default_timeout(
            10000
        )

        try:

            for page_number in range(
                1,
                pages + 1
            ):

                jobs = scrape_page(
                    page,
                    args.keyword,
                    args.location,
                    page_number
                )

                print(
                    "PAGE_RESULT|"
                    f"page={page_number}|"
                    f"jobs={len(jobs)}"
                )

                all_jobs.extend(
                    jobs
                )

                if page_number < pages:

                    try:

                        page.wait_for_timeout(
                            2000
                        )

                    except Exception:
                        pass

        finally:

            context.close()
            browser.close()

    # ========================================================
    # DEDUPLICATE BEFORE LOCATION FILTER
    # ========================================================

    all_jobs = deduplicate_jobs(
        all_jobs
    )

    print()
    print(
        f"SCRAPED_JOBS|{len(all_jobs)}"
    )

    # ========================================================
    # LOCATION FILTER
    # ========================================================

    verified_jobs = filter_verified_jobs(
        all_jobs,
        args.location
    )

    print(
        "FINAL_VERIFIED_SET|"
        f"count={len(verified_jobs)}"
    )

    # ========================================================
    # CRITICAL SAFETY CHECK
    #
    # ONLY verified_jobs goes to Excel.
    # ========================================================

    safe_jobs = []

    for job in verified_jobs:

        if verify_job_location(
            job,
            args.location
        ):

            safe_jobs.append(
                job
            )

    print(
        "EXCEL_SAFE_SET|"
        f"count={len(safe_jobs)}"
    )

    # ========================================================
    # STORE ONLY SAFE JOBS
    # ========================================================

    new_jobs = append_new_jobs(
        args.excel,
        safe_jobs,
        args.keyword,
        args.location
    )

    already_stored = (
        len(safe_jobs)
        - len(new_jobs)
    )

    if already_stored < 0:
        already_stored = 0

    print()
    print(
        "RESULT|"
        f"scraped={len(all_jobs)}|"
        f"verified={len(safe_jobs)}|"
        f"new_jobs={len(new_jobs)}|"
        f"already_stored={already_stored}|"
        f"rejected={len(all_jobs) - len(safe_jobs)}"
    )

    print()
    print(
        "Excel updated successfully."
    )

    print(
        f"New jobs added: {len(new_jobs)}"
    )

    print(
        f"Already stored: {already_stored}"
    )

    print(
        f"Rejected: {len(all_jobs) - len(safe_jobs)}"
    )


if __name__ == "__main__":
    main()
