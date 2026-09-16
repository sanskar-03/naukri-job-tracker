from pathlib import Path
import io
import pandas as pd
import streamlit as st

APP_DIR = Path(__file__).resolve().parent
DATA_FILE = APP_DIR / 'data' / 'naukri_jobs.xlsx'
HEADERS = ['job_id','title','company','location','experience','skills','posted_date','job_url','scraped_at']

st.set_page_config(page_title='Naukri Job Tracker', page_icon='J', layout='wide')

st.markdown('''
<style>
:root { color-scheme: light; }
.block-container { padding-top: 2rem; padding-bottom: 3rem; max-width: 1400px; }
.hero { padding: 1.6rem 1.8rem; border: 1px solid #d9dde3; border-radius: 18px; background: linear-gradient(135deg,#111827 0%,#1f2937 100%); color:#fff; margin-bottom:1rem; }
.eyebrow { letter-spacing:.12em; font-size:.75rem; font-weight:700; opacity:.75; }
.metric-card { border:1px solid #e5e7eb; border-radius:16px; padding:1rem 1.1rem; background:#fff; box-shadow:0 2px 8px rgba(17,24,39,.05); }
.small-note { color:#6b7280; font-size:.88rem; }
</style>
''', unsafe_allow_html=True)

@st.cache_data(ttl=60)
def load_data(path: str):
    if not Path(path).exists():
        return pd.DataFrame(columns=HEADERS), {}
    xls = pd.ExcelFile(path)
    frames=[]
    for sheet in xls.sheet_names:
        if sheet == 'Master History': continue
        df = pd.read_excel(path, sheet_name=sheet)
        if not df.empty:
            frames.append(df)
    master = pd.read_excel(path, sheet_name='Master History') if 'Master History' in xls.sheet_names else pd.DataFrame(columns=HEADERS)
    return (pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=HEADERS)), {'master':master, 'sheets':xls.sheet_names}


df, meta = load_data(str(DATA_FILE))
master = meta.get('master', pd.DataFrame(columns=HEADERS))

st.markdown('<div class="hero"><div class="eyebrow">PYTHON + PLAYWRIGHT + GITHUB ACTIONS + EXCEL + STREAMLIT</div><h1>Naukri Job Tracker</h1><p>Automated job collection with duplicate-safe Excel history and a read-only live dashboard.</p></div>', unsafe_allow_html=True)

c1,c2,c3,c4 = st.columns(4)
with c1: st.metric('Total jobs', int(len(master)))
with c2: st.metric('Searches', max(0,len(meta.get('sheets',[]))-1))
with c3: st.metric('Companies', int(master['company'].nunique()) if 'company' in master else 0)
with c4: st.metric('Locations', int(master['location'].nunique()) if 'location' in master else 0)

st.caption('This live app reads the committed Excel history. The Playwright scraper is intentionally not run from Streamlit.')

with st.sidebar:
    st.header('Filters')
    query = st.text_input('Keyword or company')
    location = st.text_input('Location')
    cols = [c for c in ['title','company','location','experience','skills','posted_date','job_url'] if c in df.columns]
    filtered=df.copy()
    if query:
        mask = filtered[cols].fillna('').astype(str).apply(lambda s: s.str.contains(query, case=False, regex=False)).any(axis=1)
        filtered = filtered[mask]
    if location and 'location' in filtered:
        filtered = filtered[filtered['location'].fillna('').astype(str).str.contains(location, case=False, regex=False)]
    st.download_button('Download master Excel', data=DATA_FILE.read_bytes() if DATA_FILE.exists() else b'', file_name='naukri_jobs.xlsx', mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', disabled=not DATA_FILE.exists(), use_container_width=True)
    if st.button('Refresh data', use_container_width=True):
        st.cache_data.clear(); st.rerun()

st.subheader('Job listings')
display_cols=[c for c in ['title','company','location','experience','skills','posted_date','job_url','scraped_at'] if c in filtered.columns]
st.dataframe(filtered[display_cols], use_container_width=True, hide_index=True, column_config={
    'job_url': st.column_config.LinkColumn('Job URL', display_text='Open job'),
})

st.subheader('Search history')
history=[]
for sheet in meta.get('sheets',[]):
    if sheet != 'Master History':
        count = int(len(pd.read_excel(DATA_FILE, sheet_name=sheet)))
        history.append({'Search sheet':sheet,'Jobs':count})
st.dataframe(pd.DataFrame(history), use_container_width=True, hide_index=True) if history else st.info('No search-specific sheets are available yet.')

st.markdown('---')
st.caption('Deployment architecture: GitHub Actions runs the scraper and commits updated Excel history; Streamlit Community Cloud serves the read-only dashboard.')
