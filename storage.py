import io
import re
from typing import Tuple

import pandas as pd

COLUMNS = [
    "Job ID",
    "Job Title",
    "Company",
    "Location",
    "Experience",
    "Skills",
    "Posted Date",
    "Job URL",
    "Scraped At",
]

def _norm(value) -> str:
    if pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value)).strip().lower()

def _key(row) -> str:
    job_id = _norm(row.get("Job ID", ""))
    url = _norm(row.get("Job URL", ""))
    if job_id and job_id != "n/a":
        return "id:" + job_id
    if url and url != "n/a":
        return "url:" + url.rstrip("/")
    return ""

def read_excel(file_obj) -> pd.DataFrame:
    df = pd.read_excel(file_obj)
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = ""
    return df[COLUMNS].copy()

def merge_jobs(existing: pd.DataFrame, scraped: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, int]:
    existing = existing.copy() if existing is not None else pd.DataFrame(columns=COLUMNS)
    scraped = scraped.copy() if scraped is not None else pd.DataFrame(columns=COLUMNS)

    for col in COLUMNS:
        if col not in existing.columns:
            existing[col] = ""
        if col not in scraped.columns:
            scraped[col] = ""

    existing = existing[COLUMNS].copy()
    scraped = scraped[COLUMNS].copy()

    # First remove duplicates already present in the old workbook, preserving first occurrence.
    existing_keys = set()
    keep_existing = []
    for _, row in existing.iterrows():
        key = _key(row)
        if key and key in existing_keys:
            continue
        if key:
            existing_keys.add(key)
        keep_existing.append(row)
    existing = pd.DataFrame(keep_existing, columns=COLUMNS)

    new_rows = []
    seen_new = set()
    duplicate_count = 0

    for _, row in scraped.iterrows():
        key = _key(row)
        if not key:
            continue
        if key in existing_keys or key in seen_new:
            duplicate_count += 1
            continue
        seen_new.add(key)
        new_rows.append(row)

    added = pd.DataFrame(new_rows, columns=COLUMNS)
    combined = pd.concat([existing, added], ignore_index=True)
    return combined, added, duplicate_count

def write_excel(df: pd.DataFrame) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Jobs")
        ws = writer.book["Jobs"]
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        widths = {
            "A": 14, "B": 35, "C": 28, "D": 28, "E": 18,
            "F": 45, "G": 18, "H": 65, "I": 22
        }
        for col, width in widths.items():
            ws.column_dimensions[col].width = width
    output.seek(0)
    return output.getvalue()
