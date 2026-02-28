"""Mnemox Metrics Dashboard — 全專案一頁總覽

單檔 Streamlit app，中文介面，超密集佈局，3 秒看完全部。
資料來源：GitHub API, pypistats API, 手動 JSON。

Usage:  streamlit run app.py
Env:    GITHUB_TOKEN (optional, 提高 rate limit + 啟用 traffic 數據)
"""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
REPOS = [
    "mnemox-ai/idea-reality-mcp",
    "mnemox-ai/tradememory-protocol",
    "mnemox-ai/idea-check-action",
]
PYPI_PACKAGES = ["idea-reality-mcp", "tradememory-protocol"]
WEBSITE_DATA_FILE = Path(__file__).parent / "website_traffic.json"
CACHE_TTL = 600  # 10 min — avoid rate limits

# ---------------------------------------------------------------------------
# CSS — 超密集佈局 + mnemox.ai 風格
# ---------------------------------------------------------------------------

CUSTOM_CSS = """
<style>
/* 全域壓縮 */
.block-container { padding: 0.5rem 1rem 0.5rem 1rem !important; max-width: 100% !important; }
header[data-testid="stHeader"] { display: none !important; }
[data-testid="stBottom"] { display: none !important; }

/* metric 壓縮 */
[data-testid="stMetric"] { padding: 4px 8px !important; }
[data-testid="stMetricValue"] { font-size: 1.1rem !important; line-height: 1.2 !important; }
[data-testid="stMetricLabel"] { font-size: 0.7rem !important; }
[data-testid="stMetricDelta"] { font-size: 0.65rem !important; }

/* 標題壓縮 */
h1 { font-size: 1.3rem !important; margin: 0 0 2px 0 !important; padding: 0 !important; }
h2 { font-size: 0.95rem !important; margin: 6px 0 2px 0 !important; padding: 0 !important;
     color: #4A90D9 !important; border-bottom: 1px solid #1e2a3a; padding-bottom: 2px !important; }
h3 { font-size: 0.8rem !important; margin: 2px 0 !important; padding: 0 !important; color: #7eb8e0 !important; }

/* column gap 壓縮 */
[data-testid="stHorizontalBlock"] { gap: 0.3rem !important; }

/* dataframe 壓縮 */
[data-testid="stDataFrame"] { font-size: 0.7rem !important; }
[data-testid="stDataFrame"] td, [data-testid="stDataFrame"] th { padding: 1px 6px !important; }

/* caption */
.stCaption p { font-size: 0.6rem !important; margin: 0 !important; color: #666 !important; }

/* divider 壓縮 */
hr { margin: 4px 0 !important; }

/* expander 壓縮 */
[data-testid="stExpander"] { border: 1px solid #1e2a3a !important; }
[data-testid="stExpander"] summary { padding: 4px 8px !important; font-size: 0.75rem !important; }
[data-testid="stExpander"] div[data-testid="stExpanderDetails"] { padding: 4px 8px !important; }

/* 小圖表 */
[data-testid="stVegaLiteChart"] { margin: -8px 0 !important; }

/* status pills — 自訂 */
.status-row { display: flex; flex-wrap: wrap; gap: 3px; margin: 2px 0; }
.pill { display: inline-block; padding: 1px 6px; border-radius: 8px; font-size: 0.6rem; font-weight: 500; }
.pill-ok { background: #1a3a1a; color: #4ade80; border: 1px solid #2d5a2d; }
.pill-wait { background: #3a3a1a; color: #fbbf24; border: 1px solid #5a5a2d; }
.pill-pr { background: #1a2a3a; color: #60a5fa; border: 1px solid #2d4a6a; }

/* 頁尾 */
.footer { text-align: center; font-size: 0.55rem; color: #444; margin-top: 4px; }
.footer a { color: #4A90D9; text-decoration: none; }
</style>
"""

# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------


def _gh_headers() -> dict:
    h = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return h


def _safe_get(url: str, **kwargs) -> requests.Response | None:
    """GET with retry on 429."""
    for attempt in range(3):
        try:
            r = requests.get(url, timeout=10, **kwargs)
            if r.status_code == 429:
                time.sleep(2 ** attempt)
                continue
            r.raise_for_status()
            return r
        except Exception:
            if attempt < 2:
                time.sleep(1)
    return None


@st.cache_data(ttl=CACHE_TTL)
def fetch_github_repo(repo: str) -> dict:
    r = _safe_get(f"https://api.github.com/repos/{repo}", headers=_gh_headers())
    return r.json() if r else {"error": "API failed"}


@st.cache_data(ttl=CACHE_TTL)
def fetch_github_prs(repo: str) -> int:
    r = _safe_get(
        f"https://api.github.com/repos/{repo}/pulls?state=open&per_page=100",
        headers=_gh_headers(),
    )
    return len(r.json()) if r else 0


@st.cache_data(ttl=CACHE_TTL)
def fetch_github_traffic(repo: str) -> dict:
    if not GITHUB_TOKEN:
        return {}
    result = {}
    for kind in ("views", "clones"):
        r = _safe_get(
            f"https://api.github.com/repos/{repo}/traffic/{kind}",
            headers=_gh_headers(),
        )
        if r:
            result[kind] = r.json()
    return result


@st.cache_data(ttl=CACHE_TTL)
def fetch_github_referrers(repo: str) -> list:
    if not GITHUB_TOKEN:
        return []
    r = _safe_get(
        f"https://api.github.com/repos/{repo}/traffic/popular/referrers",
        headers=_gh_headers(),
    )
    return r.json() if r else []


@st.cache_data(ttl=CACHE_TTL)
def fetch_pypi_all(package: str) -> dict:
    """Single API call → derive daily + recent totals (avoids /recent 429)."""
    r = _safe_get(f"https://pypistats.org/api/packages/{package}/overall?mirrors=true")
    if not r:
        return {"daily": [], "last_day": 0, "last_week": 0, "last_month": 0}
    data = r.json().get("data", [])
    daily = sorted(
        [{"date": d["date"], "downloads": d["downloads"]}
         for d in data if d.get("category") == "with_mirrors"],
        key=lambda x: x["date"],
    )
    last_14 = daily[-14:] if len(daily) >= 14 else daily
    last_7 = daily[-7:] if len(daily) >= 7 else daily
    last_30 = daily[-30:] if len(daily) >= 30 else daily
    return {
        "daily": last_14,
        "last_day": last_14[-1]["downloads"] if last_14 else 0,
        "last_week": sum(d["downloads"] for d in last_7),
        "last_month": sum(d["downloads"] for d in last_30),
    }


def load_website_traffic() -> dict | None:
    if WEBSITE_DATA_FILE.exists():
        try:
            return json.loads(WEBSITE_DATA_FILE.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


@st.cache_data(ttl=CACHE_TTL)
def fetch_pr_state(repo: str, number: int) -> dict:
    r = _safe_get(f"https://api.github.com/repos/{repo}/pulls/{number}", headers=_gh_headers())
    if r:
        d = r.json()
        return {"state": d.get("state", "?").upper(), "comments": d.get("comments", 0)}
    return {"state": "?", "comments": 0}


# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------

st.set_page_config(page_title="Mnemox Dashboard", page_icon="📊", layout="wide")
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# Title bar
t1, t2 = st.columns([4, 1])
t1.markdown("# 📊 Mnemox 全專案儀表板")
t2.caption(f"更新 {datetime.now(timezone.utc).strftime('%H:%M UTC')}")

# ===========================================================================
# ROW 1: GitHub Repos (3 columns) + PyPI (2 columns) = 5 columns
# ===========================================================================

st.markdown("## GitHub 專案 / PyPI 下載")

c1, c2, c3, c4, c5 = st.columns([2, 2, 2, 1.5, 1.5])

# --- GitHub repos ---
for i, (col, repo) in enumerate(zip([c1, c2, c3], REPOS)):
    data = fetch_github_repo(repo)
    prs = fetch_github_prs(repo)
    name = repo.split("/")[1]

    with col:
        st.markdown(f"### {name}")
        if "error" in data:
            st.caption(f"Error: {data['error']}")
            continue
        m1, m2 = st.columns(2)
        m1.metric("Stars", f"{data.get('stargazers_count', 0):,}")
        m2.metric("Forks", f"{data.get('forks_count', 0):,}")
        m3, m4 = st.columns(2)
        m3.metric("Issues", data.get("open_issues_count", 0))
        m4.metric("PRs", prs)
        st.caption(f"{data.get('language', '')} · {data.get('pushed_at', '')[:10]}")

# --- PyPI ---
for i, (col, pkg) in enumerate(zip([c4, c5], PYPI_PACKAGES)):
    pypi = fetch_pypi_all(pkg)
    short = pkg.replace("-protocol", "")

    with col:
        st.markdown(f"### PyPI: {short}")
        st.metric("日下載 Daily", f"{pypi['last_day']:,}")
        st.metric("週下載 Week", f"{pypi['last_week']:,}")
        st.metric("月下載 Month", f"{pypi['last_month']:,}")
        if pypi["daily"]:
            df = pd.DataFrame(pypi["daily"])
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date")
            st.bar_chart(df["downloads"], height=80, use_container_width=True)

# ===========================================================================
# ROW 2: Traffic + Referrers + Website + Trading
# ===========================================================================

st.markdown("## 流量 Traffic / 網站 / 交易")

if GITHUB_TOKEN:
    r1, r2, r3, r4 = st.columns([2.5, 2.5, 1.5, 1.5])

    # --- Traffic: idea-reality-mcp ---
    traffic_irm = fetch_github_traffic("mnemox-ai/idea-reality-mcp")
    with r1:
        st.markdown("### idea-reality-mcp 流量 (14d)")
        views = traffic_irm.get("views", {})
        clones = traffic_irm.get("clones", {})
        a, b, c, d = st.columns(4)
        a.metric("瀏覽 Views", f"{views.get('count', 0):,}")
        b.metric("獨立 Unique", f"{views.get('uniques', 0):,}")
        c.metric("複製 Clones", f"{clones.get('count', 0):,}")
        d.metric("獨立 Unique", f"{clones.get('uniques', 0):,}")
        # Mini chart
        vd = views.get("views", [])
        if vd:
            df = pd.DataFrame(vd)
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.set_index("timestamp")
            st.line_chart(df["count"], height=70, use_container_width=True)

    # --- Referrers ---
    with r2:
        st.markdown("### 來源 Top Referrers")
        refs = fetch_github_referrers("mnemox-ai/idea-reality-mcp")
        if refs:
            for ref in refs[:6]:
                st.caption(f"**{ref['referrer']}** — {ref['count']} views / {ref['uniques']} uniq")
        else:
            st.caption("需要 push access token")
else:
    r1, r2, r3, r4 = st.columns([2.5, 2.5, 1.5, 1.5])
    with r1:
        st.markdown("### GitHub 流量")
        st.caption("設定 GITHUB_TOKEN 啟用流量數據")
    with r2:
        st.markdown("### 來源 Referrers")
        st.caption("設定 GITHUB_TOKEN 啟用")

# --- Website ---
with r3:
    st.markdown("### 網站 mnemox.ai")
    web = load_website_traffic()
    if web:
        st.metric("瀏覽 Views (14d)", f"{web.get('views_14d', 0):,}")
        st.metric("獨立 Unique (14d)", f"{web.get('uniques_14d', 0):,}")
        pages = web.get("top_pages", [])
        for p in pages:
            st.caption(f"{p['path']} — {p['views']}v / {p['uniques']}u")
    else:
        st.caption("建立 website_traffic.json")

# --- Trading placeholder ---
with r4:
    st.markdown("### 交易 NG_Gold")
    st.metric("餘額 Balance", "$9,863")
    st.metric("交易數 Trades", "7")
    st.metric("勝率 Win Rate", "42.9%")
    st.metric("損益 PnL", "-$69.99")
    st.caption("Shadow Mode · 手動更新")

# ===========================================================================
# ROW 3: PR Tracker + Distribution (compact pills)
# ===========================================================================

st.markdown("## 發布通路 Distribution / PR 追蹤")

d1, d2 = st.columns([1, 2])

# --- PR status ---
with d1:
    st.markdown("### 待處理 PR")
    pr = fetch_pr_state("punkpeye/awesome-mcp-servers", 2346)
    st.caption(f"awesome-mcp-servers #2346 — **{pr['state']}** ({pr['comments']} comments)")

    prs_to_track = [
        ("ClaudeMCP #45", "⏳"),
        ("mcp-get #176", "⏳"),
        ("Fleur #37", "⏳"),
    ]
    for name, status in prs_to_track:
        st.caption(f"{name} — {status}")

# --- Distribution pills ---
with d2:
    st.markdown("### 發布平台 Channels")
    channels_html = '<div class="status-row">'
    ok = [("PyPI", "✅"), ("MCP Registry", "✅"), ("Smithery", "✅"),
          ("Glama", "✅"), ("Dev.to", "✅"), ("PulseMCP", "✅"), ("MCP Market", "✅")]
    wait = [("awesome-mcp", "⏳"), ("Marketplace", "⏳")]
    for name, _ in ok:
        channels_html += f'<span class="pill pill-ok">{name}</span>'
    for name, _ in wait:
        channels_html += f'<span class="pill pill-wait">{name}</span>'
    channels_html += '</div>'
    st.markdown(channels_html, unsafe_allow_html=True)

    # Quick summary line
    st.caption(f"已發布 Published: {len(ok)} / 待處理 Pending: {len(wait)}")

# ===========================================================================
# Footer
# ===========================================================================

st.markdown(
    '<div class="footer">'
    'Built by <a href="https://mnemox.ai">Mnemox AI</a> · '
    '<a href="https://github.com/mnemox-ai/idea-reality-mcp">idea-reality-mcp</a> · '
    '<a href="https://github.com/mnemox-ai/tradememory-protocol">tradememory-protocol</a>'
    '</div>',
    unsafe_allow_html=True,
)
