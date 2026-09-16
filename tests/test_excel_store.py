from pathlib import Path
from storage.excel_store import append_new_jobs, read_all_jobs


def test_duplicate_safe_append(tmp_path: Path):
    path = tmp_path / 'jobs.xlsx'
    job = {'job_id':'123','title':'Python Developer','company':'Example','location':'Chennai','experience':'2-4 Yrs','skills':'Python','posted_date':'Today','job_url':'https://www.naukri.com/job-listings-example-123','scraped_at':'2026-09-16 07:00:00'}
    assert len(append_new_jobs(path, [job], 'Python Developer','Chennai')) == 1
    assert len(append_new_jobs(path, [job], 'Python Developer','Chennai')) == 0
    assert len(read_all_jobs(path)) == 1
