"""Mnemox Metrics Dashboard — Cyberpunk Edition

Single-file Streamlit app. Neon-dark UI, all data in one viewport.
Data: GitHub API, pypistats API, manual JSON.

Usage:  streamlit run app.py
Env:    GITHUB_TOKEN (optional)
"""

import json
import os
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

try:
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
except Exception:
    GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
REPOS = [
    "mnemox-ai/idea-reality-mcp",
    "mnemox-ai/tradememory-protocol",
    "mnemox-ai/idea-check-action",
]
PYPI_PACKAGES = ["idea-reality-mcp", "tradememory-protocol"]
WEBSITE_DATA_FILE = Path(__file__).parent / "website_traffic.json"
CACHE_TTL = 600

# Colors
NEON_CYAN = "#00f0ff"
NEON_PURPLE = "#bf00ff"
NEON_GREEN = "#00ff88"
NEON_RED = "#ff3366"
BG_DARK = "#0a0a0f"
CARD_BG = "#12121a"
CARD_BORDER = "rgba(0,240,255,0.15)"
TEXT_DIM = "#5a6070"
TEXT_MID = "#8a8fa0"

# ---------------------------------------------------------------------------
# CSS — Cyberpunk / Grafana Dark — 1920x1080 single viewport
# ---------------------------------------------------------------------------

CYBER_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=JetBrains+Mono:wght@400;700&display=swap');

/* === GLOBAL === */
html {{ zoom: 1.8; }}
@media (min-width: 2400px) {{ html {{ zoom: 2.0; }} }}
.stApp {{ background: {BG_DARK} !important; }}
.block-container {{
    padding: 0.4rem 0.5rem 0 0.5rem !important;
    max-width: 100% !important;
}}
header[data-testid="stHeader"] {{ display: none !important; }}
[data-testid="stBottom"] {{ display: none !important; }}
[data-testid="stVerticalBlock"] {{ gap: 0.15rem !important; }}
[data-testid="stHorizontalBlock"] {{ gap: 0.35rem !important; }}

/* === TITLE BAR === */
.cyber-header {{
    display: flex; align-items: center; justify-content: space-between;
    padding: 3px 0; margin-bottom: 2px;
    border-bottom: 1px solid {CARD_BORDER};
}}
.cyber-title {{
    font-family: 'Orbitron', monospace; font-size: 0.95rem; font-weight: 700;
    color: {NEON_CYAN}; letter-spacing: 2px; text-transform: uppercase;
    text-shadow: 0 0 20px rgba(0,240,255,0.3);
}}
.cyber-subtitle {{
    font-family: 'JetBrains Mono', monospace; font-size: 0.5rem;
    color: {TEXT_DIM}; letter-spacing: 1px;
}}

/* === SECTION HEADERS === */
.section-label {{
    font-family: 'Orbitron', monospace; font-size: 0.55rem; font-weight: 700;
    color: {NEON_PURPLE}; letter-spacing: 3px; text-transform: uppercase;
    margin: 3px 0 2px 0; padding-bottom: 1px;
    border-bottom: 1px solid rgba(191,0,255,0.2);
    text-shadow: 0 0 12px rgba(191,0,255,0.3);
}}

/* === CARDS === */
.cyber-card {{
    background: {CARD_BG}; border: 1px solid {CARD_BORDER};
    border-radius: 4px; padding: 4px 8px; margin-bottom: 2px;
    box-shadow: 0 0 8px rgba(0,240,255,0.04), inset 0 1px 0 rgba(0,240,255,0.05);
    position: relative; overflow: hidden;
}}
.cyber-card::before {{
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 1px;
    background: linear-gradient(90deg, transparent, {NEON_CYAN}40, transparent);
}}
.card-title {{
    font-family: 'Orbitron', monospace; font-size: 0.5rem; font-weight: 700;
    color: {TEXT_MID}; letter-spacing: 1.5px; text-transform: uppercase;
    margin-bottom: 3px;
}}
.card-subtitle {{
    font-family: 'JetBrains Mono', monospace; font-size: 0.4rem;
    color: {TEXT_DIM}; margin-left: 4px;
}}

/* === METRICS === */
.neon-val {{
    font-family: 'JetBrains Mono', monospace; font-size: 1.5rem; font-weight: 700;
    color: {NEON_CYAN}; line-height: 1;
    text-shadow: 0 0 15px rgba(0,240,255,0.25);
}}
.neon-val-sm {{
    font-family: 'JetBrains Mono', monospace; font-size: 0.95rem; font-weight: 700;
    color: {NEON_CYAN}; line-height: 1;
}}
.neon-val-green {{ color: {NEON_GREEN} !important; text-shadow: 0 0 12px rgba(0,255,136,0.25); }}
.neon-val-red {{ color: {NEON_RED} !important; text-shadow: 0 0 12px rgba(255,51,102,0.25); }}
.neon-val-purple {{ color: {NEON_PURPLE} !important; text-shadow: 0 0 12px rgba(191,0,255,0.25); }}
.metric-label {{
    font-family: 'JetBrains Mono', monospace; font-size: 0.45rem;
    color: {TEXT_DIM}; letter-spacing: 0.5px; text-transform: uppercase;
    margin-bottom: 0px;
}}
.metric-row {{ display: flex; gap: 10px; flex-wrap: wrap; }}
.metric-item {{ min-width: 40px; }}

/* === PILLS === */
.pill-row {{ display: flex; flex-wrap: wrap; gap: 3px; margin: 2px 0; }}
.pill {{
    font-family: 'JetBrains Mono', monospace; display: inline-block;
    padding: 1px 6px; border-radius: 10px; font-size: 0.5rem; font-weight: 500;
}}
.pill-ok {{ background: rgba(0,255,136,0.1); color: {NEON_GREEN}; border: 1px solid rgba(0,255,136,0.25); }}
.pill-wait {{ background: rgba(255,187,36,0.1); color: #fbbf24; border: 1px solid rgba(255,187,36,0.25); }}
.pill-info {{ background: rgba(0,240,255,0.1); color: {NEON_CYAN}; border: 1px solid rgba(0,240,255,0.2); }}

/* === PLOTLY FIX === */
[data-testid="stPlotlyChart"] {{
    min-height: 40px !important;
    margin: 0 !important;
    padding: 0 !important;
}}

/* === MISC === */
.dim-text {{ font-family: 'JetBrains Mono', monospace; font-size: 0.45rem; color: {TEXT_DIM}; }}
.footer-bar {{
    text-align: center; font-family: 'JetBrains Mono', monospace;
    font-size: 0.4rem; color: {TEXT_DIM}; margin-top: 2px;
    border-top: 1px solid {CARD_BORDER}; padding-top: 2px;
}}
.footer-bar a {{ color: {NEON_CYAN}; text-decoration: none; }}

/* === HIDE streamlit default elements === */
[data-testid="stMetric"] {{ display: none !important; }}
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
        r = _safe_get(f"https://api.github.com/repos/{repo}/traffic/{kind}", headers=_gh_headers())
        if r:
            result[kind] = r.json()
    return result


@st.cache_data(ttl=CACHE_TTL)
def fetch_github_referrers(repo: str) -> list:
    if not GITHUB_TOKEN:
        return []
    r = _safe_get(f"https://api.github.com/repos/{repo}/traffic/popular/referrers", headers=_gh_headers())
    return r.json() if r else []


@st.cache_data(ttl=CACHE_TTL)
def fetch_pypi_daily(package: str) -> pd.DataFrame | None:
    """Fetch recent daily download data."""
    r = _safe_get(f"https://pypistats.org/api/packages/{package}/overall?mirrors=true")
    if not r:
        return None
    data = r.json().get("data", [])
    rows = [{"date": d["date"], "downloads": d["downloads"]}
            for d in data if d.get("category") == "with_mirrors"]
    if not rows:
        return None
    df = pd.DataFrame(rows).sort_values("date").tail(7).reset_index(drop=True)
    df["label"] = pd.to_datetime(df["date"]).dt.strftime("%m/%d")
    return df


@st.cache_data(ttl=CACHE_TTL)
def fetch_pypi_summary(package: str) -> dict:
    """Derive day/week/month totals from daily data."""
    r = _safe_get(f"https://pypistats.org/api/packages/{package}/overall?mirrors=true")
    if not r:
        return {"last_day": 0, "last_week": 0, "last_month": 0}
    data = r.json().get("data", [])
    rows = [{"date": d["date"], "downloads": d["downloads"]}
            for d in data if d.get("category") == "with_mirrors"]
    rows.sort(key=lambda x: x["date"])
    return {
        "last_day": rows[-1]["downloads"] if rows else 0,
        "last_week": sum(r["downloads"] for r in rows[-7:]),
        "last_month": sum(r["downloads"] for r in rows[-30:]),
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
# Plotly chart helpers
# ---------------------------------------------------------------------------


def make_pypi_chart(df: pd.DataFrame, color: str = NEON_CYAN) -> go.Figure:
    """Bar chart for PyPI daily downloads."""
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df["label"], y=df["downloads"], marker_color=color,
        texttemplate="%{y:,}",
        textposition="inside",
        textangle=0,
        textfont=dict(size=9, color="#fff"),
        hovertemplate="%{x}: %{y:,}<extra></extra>",
        cliponaxis=False,
    ))
    fig.update_layout(
        height=150,
        margin=dict(l=5, r=5, t=5, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(
            showgrid=False, color="#888",
            tickfont=dict(size=10, color="#888"),
            type="category",
        ),
        yaxis=dict(
            showgrid=False, showticklabels=False,
        ),
        font=dict(size=10),
        bargap=0.2,
        showlegend=False,
        dragmode=False,
    )
    return fig


def make_traffic_chart(timestamps: list, counts: list, color: str = NEON_CYAN) -> go.Figure:
    """Line chart for GitHub traffic views. Last 7 days only."""
    if len(timestamps) > 7:
        timestamps = timestamps[-7:]
        counts = counts[-7:]

    labels = []
    for ts in timestamps:
        try:
            labels.append(datetime.fromisoformat(ts.replace("Z", "+00:00")).strftime("%m/%d"))
        except Exception:
            labels.append(str(ts)[:5])

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=labels, y=counts, mode="lines+markers",
        line=dict(color=color, width=2),
        marker=dict(color=color, size=5),
        fill="tozeroy",
        fillcolor=f"rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)},0.08)",
        hovertemplate="%{x}: %{y:,}<extra></extra>",
    ))
    y_max = max(counts) if counts else 1
    fig.update_layout(
        height=120,
        margin=dict(l=30, r=5, t=5, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(
            showgrid=False, color="#888",
            tickfont=dict(size=10, color="#888"),
            type="category",
        ),
        yaxis=dict(
            showgrid=True, gridcolor="rgba(255,255,255,0.04)",
            color="#888", tickfont=dict(size=10, color="#888"),
            range=[0, y_max * 1.2],
        ),
        font=dict(size=10),
        showlegend=False,
        dragmode=False,
    )
    return fig


def make_referrer_chart(refs: list, color: str = NEON_CYAN) -> go.Figure:
    """Horizontal bar chart for referrers."""
    names = [r["referrer"] for r in refs[:5]][::-1]
    values = [r["count"] for r in refs[:5]][::-1]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=values, y=names, orientation="h",
        marker_color=color, marker_opacity=0.6,
        text=[f"{v:,}" for v in values],
        textposition="outside",
        textfont=dict(size=9, color="#888"),
        hovertemplate="%{y}: %{x:,}<extra></extra>",
    ))
    fig.update_layout(
        height=150,
        margin=dict(l=110, r=35, t=5, b=5),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False, showticklabels=False),
        yaxis=dict(
            showgrid=False, color="#888",
            tickfont=dict(size=9, color="#aaa"),
        ),
        font=dict(size=9),
        showlegend=False,
        dragmode=False,
        bargap=0.3,
    )
    return fig


# ---------------------------------------------------------------------------
# HTML helpers
# ---------------------------------------------------------------------------


def metric_html(label: str, value: str, css_class: str = "neon-val-sm") -> str:
    return f'<div class="metric-item"><div class="metric-label">{label}</div><div class="{css_class}">{value}</div></div>'


def card_open(title: str, subtitle: str = "") -> str:
    sub = f'<span class="card-subtitle">{subtitle}</span>' if subtitle else ""
    return f'<div class="cyber-card"><div class="card-title">{title}{sub}</div>'


CARD_CLOSE = '</div>'


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

st.set_page_config(page_title="Mnemox Dashboard", page_icon="📊", layout="wide")
st.markdown(CYBER_CSS, unsafe_allow_html=True)

TW = timezone(timedelta(hours=8))
now_str = datetime.now(TW).strftime("%Y-%m-%d %H:%M CST")

# === HEADER ===
st.markdown(f'''
<div class="cyber-header">
    <div class="cyber-title">MNEMOX COMMAND CENTER</div>
    <div class="cyber-subtitle">🔄 {now_str} &nbsp;|&nbsp; Mnemox AI</div>
</div>
''', unsafe_allow_html=True)

# ===========================================================================
# ROW 1: GitHub Repos (3) + PyPI (2)
# ===========================================================================

st.markdown('<div class="section-label">GITHUB REPOS &nbsp;/&nbsp; PYPI DOWNLOADS</div>', unsafe_allow_html=True)

c1, c2, c3, c4, c5 = st.columns([2, 2, 2, 1.5, 1.5])

# --- GitHub repos ---
for col, repo in zip([c1, c2, c3], REPOS):
    data = fetch_github_repo(repo)
    prs = fetch_github_prs(repo)
    name = repo.split("/")[1]

    with col:
        if "error" in data:
            st.markdown(f'{card_open(name)}<span class="dim-text">API Error</span>{CARD_CLOSE}', unsafe_allow_html=True)
            continue

        stars = data.get("stargazers_count", 0)
        forks = data.get("forks_count", 0)
        issues = data.get("open_issues_count", 0)
        updated = data.get("pushed_at", "")[:10]

        html = card_open(name)
        html += '<div class="metric-row">'
        html += metric_html("⭐ Stars", f"{stars:,}", "neon-val")
        html += metric_html("🍴 Forks", f"{forks:,}", "neon-val-sm")
        html += '</div>'
        html += '<div class="metric-row" style="margin-top:2px">'
        html += metric_html("Issues", str(issues), "neon-val-sm neon-val-green" if issues == 0 else "neon-val-sm neon-val-red")
        html += metric_html("PRs", str(prs), "neon-val-sm neon-val-green" if prs == 0 else "neon-val-sm neon-val-red")
        html += '</div>'
        html += f'<div class="dim-text" style="margin-top:1px">{data.get("language", "")} · {updated}</div>'
        html += CARD_CLOSE
        st.markdown(html, unsafe_allow_html=True)

# --- PyPI ---
for col, pkg in zip([c4, c5], PYPI_PACKAGES):
    summary = fetch_pypi_summary(pkg)
    df_daily = fetch_pypi_daily(pkg)
    short = pkg.split("-")[0]  # "idea" / "tradememory"
    chart_color = NEON_CYAN if "idea" in pkg else NEON_PURPLE
    latest_date = df_daily["date"].iloc[-1] if df_daily is not None and not df_daily.empty else "?"

    with col:
        html = card_open(f"PyPI: {short}", f"至 {latest_date}")
        html += '<div class="metric-row">'
        html += metric_html("日 Day", f"{summary['last_day']:,}", "neon-val")
        html += '</div>'
        html += '<div class="metric-row" style="margin-top:1px">'
        html += metric_html("週 Week", f"{summary['last_week']:,}", "neon-val-sm neon-val-purple")
        html += metric_html("月 Month", f"{summary['last_month']:,}", "neon-val-sm")
        html += '</div>'
        html += CARD_CLOSE
        st.markdown(html, unsafe_allow_html=True)

        if df_daily is not None and not df_daily.empty:
            fig = make_pypi_chart(df_daily, chart_color)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        else:
            st.markdown('<div class="dim-text">數據載入中...</div>', unsafe_allow_html=True)

# ===========================================================================
# ROW 2: Traffic + Referrers + Website + Trading
# ===========================================================================

st.markdown('<div class="section-label">TRAFFIC &nbsp;/&nbsp; 網站 &nbsp;/&nbsp; 交易 NG_GOLD</div>', unsafe_allow_html=True)

r1, r2, r3, r4 = st.columns([2.5, 2.5, 1.5, 1.5])

# --- Traffic (14D totals from API, 7D chart) ---
with r1:
    if GITHUB_TOKEN:
        traffic = fetch_github_traffic("mnemox-ai/idea-reality-mcp")
        views = traffic.get("views", {})
        clones = traffic.get("clones", {})
        html = card_open("IDEA-REALITY 流量 14D")
        html += '<div class="metric-row">'
        html += metric_html("Views", f"{views.get('count', 0):,}", "neon-val")
        html += metric_html("Uniq", f"{views.get('uniques', 0):,}", "neon-val-sm")
        html += metric_html("Clone", f"{clones.get('count', 0):,}", "neon-val-sm neon-val-purple")
        html += metric_html("Uniq", f"{clones.get('uniques', 0):,}", "neon-val-sm")
        html += '</div>'
        html += CARD_CLOSE
        st.markdown(html, unsafe_allow_html=True)
        vd = views.get("views", [])
        if vd:
            fig = make_traffic_chart(
                [v["timestamp"] for v in vd],
                [v["count"] for v in vd],
                NEON_CYAN,
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    else:
        html = card_open("GITHUB 流量")
        html += f'<span class="dim-text">設定 GITHUB_TOKEN 啟用</span>'
        html += CARD_CLOSE
        st.markdown(html, unsafe_allow_html=True)

# --- Referrers ---
with r2:
    html = card_open("來源 REFERRERS")
    html += CARD_CLOSE
    st.markdown(html, unsafe_allow_html=True)
    if GITHUB_TOKEN:
        refs = fetch_github_referrers("mnemox-ai/idea-reality-mcp")
        if refs:
            fig = make_referrer_chart(refs, NEON_CYAN)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        else:
            st.markdown('<div class="dim-text">No data</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="dim-text">需要 GITHUB_TOKEN</div>', unsafe_allow_html=True)

# --- Website ---
with r3:
    web = load_website_traffic()
    html = card_open("網站 MNEMOX.AI")
    if web:
        html += '<div class="metric-row">'
        html += metric_html("瀏覽 14d", f"{web.get('views_14d', 0):,}", "neon-val-sm")
        html += metric_html("獨立 14d", f"{web.get('uniques_14d', 0):,}", "neon-val-sm")
        html += '</div>'
        for p in web.get("top_pages", []):
            html += f'<div class="dim-text">{p["path"]} → {p["views"]}v / {p["uniques"]}u</div>'
    else:
        html += '<span class="dim-text">建立 website_traffic.json</span>'
    html += CARD_CLOSE
    st.markdown(html, unsafe_allow_html=True)

# --- Trading ---
with r4:
    html = card_open("交易 NG_GOLD")
    html += '<div class="metric-row">'
    html += metric_html("餘額", "$9,863", "neon-val-sm neon-val-green")
    html += '</div>'
    html += '<div class="metric-row" style="margin-top:1px">'
    html += metric_html("交易", "7", "neon-val-sm")
    html += metric_html("勝率", "42.9%", "neon-val-sm")
    html += '</div>'
    html += '<div class="metric-row" style="margin-top:1px">'
    html += metric_html("損益", "-$69.99", "neon-val-sm neon-val-red")
    html += '</div>'
    html += f'<div class="dim-text">Shadow Mode · 手動更新</div>'
    html += CARD_CLOSE
    st.markdown(html, unsafe_allow_html=True)

# ===========================================================================
# ROW 3: Distribution / PR
# ===========================================================================

st.markdown('<div class="section-label">DISTRIBUTION &nbsp;/&nbsp; PR 追蹤</div>', unsafe_allow_html=True)

d1, d2 = st.columns([1.2, 2.8])

with d1:
    pr = fetch_pr_state("punkpeye/awesome-mcp-servers", 2346)
    html = card_open("PR TRACKER")
    html += f'<div class="dim-text">awesome-mcp #2346 — <span class="pill pill-info">{pr["state"]}</span> {pr["comments"]}💬</div>'
    for name in ["ClaudeMCP #45", "mcp-get #176", "Fleur #37"]:
        html += f'<div class="dim-text">{name} — <span class="pill pill-wait">⏳</span></div>'
    html += CARD_CLOSE
    st.markdown(html, unsafe_allow_html=True)

with d2:
    ok_channels = ["PyPI", "MCP Registry", "Smithery", "Glama", "Dev.to", "PulseMCP", "MCP Market"]
    wait_channels = ["awesome-mcp", "Marketplace"]
    html = card_open(f"CHANNELS — {len(ok_channels)}✅ {len(wait_channels)}⏳")
    html += '<div class="pill-row">'
    for ch in ok_channels:
        html += f'<span class="pill pill-ok">{ch}</span>'
    for ch in wait_channels:
        html += f'<span class="pill pill-wait">{ch}</span>'
    html += '</div>'
    html += CARD_CLOSE
    st.markdown(html, unsafe_allow_html=True)

# === FOOTER ===
st.markdown(f'''
<div class="footer-bar">
    <a href="https://mnemox.ai">Mnemox AI</a> ·
    <a href="https://github.com/mnemox-ai/idea-reality-mcp">idea-reality-mcp</a> ·
    <a href="https://github.com/mnemox-ai/tradememory-protocol">tradememory-protocol</a>
</div>
''', unsafe_allow_html=True)
