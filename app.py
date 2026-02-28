"""Mnemox Metrics Dashboard — all projects, one view.

Single-file Streamlit app. No database needed.
Data sources: GitHub API, pypistats API, manual JSON for website traffic.

Usage:
    streamlit run app.py

Optional env vars:
    GITHUB_TOKEN  — raises GitHub API rate limit from 60 to 5,000 req/hr
"""

import json
import os
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

PYPI_PACKAGES = [
    "idea-reality-mcp",
    "tradememory-protocol",
]

WEBSITE_DATA_FILE = Path(__file__).parent / "website_traffic.json"

# How long to cache API calls (seconds)
CACHE_TTL = 300  # 5 min

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _gh_headers() -> dict:
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return headers


@st.cache_data(ttl=CACHE_TTL)
def fetch_github_repo(repo: str) -> dict:
    """Fetch basic repo info from GitHub API."""
    url = f"https://api.github.com/repos/{repo}"
    try:
        r = requests.get(url, headers=_gh_headers(), timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}


@st.cache_data(ttl=CACHE_TTL)
def fetch_github_open_prs(repo: str) -> int:
    """Count open PRs for a repo."""
    url = f"https://api.github.com/repos/{repo}/pulls?state=open&per_page=1"
    try:
        r = requests.get(url, headers=_gh_headers(), timeout=10)
        r.raise_for_status()
        # GitHub returns total in Link header; for small repos just count
        return len(requests.get(
            f"https://api.github.com/repos/{repo}/pulls?state=open&per_page=100",
            headers=_gh_headers(), timeout=10,
        ).json())
    except Exception:
        return 0


@st.cache_data(ttl=CACHE_TTL)
def fetch_github_traffic(repo: str) -> dict:
    """Fetch 14-day traffic (views + clones). Requires push access token."""
    result = {"views": None, "clones": None}
    if not GITHUB_TOKEN:
        return result
    for kind in ("views", "clones"):
        url = f"https://api.github.com/repos/{repo}/traffic/{kind}"
        try:
            r = requests.get(url, headers=_gh_headers(), timeout=10)
            r.raise_for_status()
            result[kind] = r.json()
        except Exception:
            pass
    return result


@st.cache_data(ttl=CACHE_TTL)
def fetch_github_referrers(repo: str) -> list:
    """Top 10 referrers (requires push access token)."""
    if not GITHUB_TOKEN:
        return []
    url = f"https://api.github.com/repos/{repo}/traffic/popular/referrers"
    try:
        r = requests.get(url, headers=_gh_headers(), timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return []


@st.cache_data(ttl=CACHE_TTL)
def fetch_pypi_recent(package: str) -> dict:
    """Fetch recent download stats from pypistats API."""
    url = f"https://pypistats.org/api/packages/{package}/recent"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        return r.json().get("data", {})
    except Exception as e:
        return {"error": str(e)}


@st.cache_data(ttl=CACHE_TTL)
def fetch_pypi_daily(package: str) -> list:
    """Fetch per-day download data from pypistats overall API."""
    url = f"https://pypistats.org/api/packages/{package}/overall?mirrors=true"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json().get("data", [])
        # Filter to "with_mirrors" category and last 14 days
        daily = [
            {"date": d["date"], "downloads": d["downloads"]}
            for d in data
            if d.get("category") == "with_mirrors"
        ]
        return sorted(daily, key=lambda x: x["date"])[-14:]
    except Exception:
        return []


def load_website_traffic() -> dict | None:
    """Load website traffic from local JSON file."""
    if WEBSITE_DATA_FILE.exists():
        try:
            return json.loads(WEBSITE_DATA_FILE.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Mnemox Dashboard",
    page_icon="📊",
    layout="wide",
)

st.title("📊 Mnemox Metrics Dashboard")
st.caption(f"Last refreshed: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")

if not GITHUB_TOKEN:
    st.info("💡 Set `GITHUB_TOKEN` env var for traffic data & higher rate limits.")

# ---------------------------------------------------------------------------
# Section 1: GitHub Overview
# ---------------------------------------------------------------------------

st.header("🐙 GitHub Repos")

cols = st.columns(len(REPOS))

for i, repo in enumerate(REPOS):
    data = fetch_github_repo(repo)
    open_prs = fetch_github_open_prs(repo)
    short_name = repo.split("/")[1]

    with cols[i]:
        if "error" in data:
            st.error(f"**{short_name}**\n\n{data['error']}")
            continue

        st.subheader(short_name)

        # Metrics row
        m1, m2 = st.columns(2)
        m1.metric("⭐ Stars", f"{data.get('stargazers_count', 0):,}")
        m2.metric("🍴 Forks", f"{data.get('forks_count', 0):,}")

        m3, m4 = st.columns(2)
        m3.metric("🔴 Issues", data.get("open_issues_count", 0))
        m4.metric("🔀 Open PRs", open_prs)

        # Extra info
        lang = data.get("language", "N/A")
        updated = data.get("pushed_at", "")[:10]
        st.caption(f"{lang} · Updated {updated}")

# ---------------------------------------------------------------------------
# Section 2: GitHub Traffic (requires token with push access)
# ---------------------------------------------------------------------------

if GITHUB_TOKEN:
    st.header("📈 GitHub Traffic (14 days)")

    traffic_cols = st.columns(len(REPOS))
    for i, repo in enumerate(REPOS):
        traffic = fetch_github_traffic(repo)
        short_name = repo.split("/")[1]

        with traffic_cols[i]:
            st.subheader(short_name)

            views_data = traffic.get("views")
            clones_data = traffic.get("clones")

            if views_data:
                v1, v2 = st.columns(2)
                v1.metric("👀 Views", f"{views_data.get('count', 0):,}")
                v2.metric("👤 Unique", f"{views_data.get('uniques', 0):,}")

                # Views chart
                views_daily = views_data.get("views", [])
                if views_daily:
                    df = pd.DataFrame(views_daily)
                    df["timestamp"] = pd.to_datetime(df["timestamp"])
                    df = df.set_index("timestamp")
                    st.line_chart(df["count"], height=150)
            else:
                st.caption("No views data (token needs push access)")

            if clones_data:
                c1, c2 = st.columns(2)
                c1.metric("📥 Clones", f"{clones_data.get('count', 0):,}")
                c2.metric("👤 Unique", f"{clones_data.get('uniques', 0):,}")

    # Referrers for main repo
    st.subheader("🔗 Top Referrers (idea-reality-mcp)")
    referrers = fetch_github_referrers("mnemox-ai/idea-reality-mcp")
    if referrers:
        ref_df = pd.DataFrame(referrers)
        st.dataframe(ref_df, use_container_width=True, hide_index=True)
    else:
        st.caption("No referrer data available.")

# ---------------------------------------------------------------------------
# Section 3: PyPI Downloads
# ---------------------------------------------------------------------------

st.header("📦 PyPI Downloads")

pypi_cols = st.columns(len(PYPI_PACKAGES))

for i, pkg in enumerate(PYPI_PACKAGES):
    recent = fetch_pypi_recent(pkg)
    daily = fetch_pypi_daily(pkg)

    with pypi_cols[i]:
        st.subheader(pkg)

        if "error" in recent:
            st.error(recent["error"])
            continue

        p1, p2, p3 = st.columns(3)
        p1.metric("Last Day", f"{recent.get('last_day', 0):,}")
        p2.metric("Last Week", f"{recent.get('last_week', 0):,}")
        p3.metric("Last Month", f"{recent.get('last_month', 0):,}")

        # Daily chart
        if daily:
            df = pd.DataFrame(daily)
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date")
            st.bar_chart(df["downloads"], height=200)

# ---------------------------------------------------------------------------
# Section 4: Website Traffic (manual JSON)
# ---------------------------------------------------------------------------

st.header("🌐 Website Traffic (mnemox.ai)")

web_data = load_website_traffic()

if web_data:
    w1, w2, w3 = st.columns(3)
    w1.metric("Views (14d)", f"{web_data.get('views_14d', 'N/A'):,}")
    w2.metric("Unique (14d)", f"{web_data.get('uniques_14d', 'N/A'):,}")
    w3.metric("Last Updated", web_data.get("updated_at", "N/A"))

    # Per-page data if available
    pages = web_data.get("top_pages", [])
    if pages:
        st.dataframe(pd.DataFrame(pages), use_container_width=True, hide_index=True)
else:
    st.caption(
        "No website traffic data. Create `website_traffic.json` with format:\n"
        '```json\n{"views_14d": 40, "uniques_14d": 8, "updated_at": "2026-02-28"}\n```'
    )

# ---------------------------------------------------------------------------
# Section 5: PR & Distribution Tracker
# ---------------------------------------------------------------------------

st.header("📋 Open PRs & Distribution")

pr_tracker = {
    "awesome-mcp-servers #2346": {
        "repo": "punkpeye/awesome-mcp-servers",
        "number": 2346,
        "purpose": "Get listed in awesome-mcp-servers",
    },
}

pr_data = []
for label, info in pr_tracker.items():
    url = f"https://api.github.com/repos/{info['repo']}/pulls/{info['number']}"
    try:
        r = requests.get(url, headers=_gh_headers(), timeout=10)
        r.raise_for_status()
        d = r.json()
        pr_data.append({
            "PR": label,
            "State": d.get("state", "unknown").upper(),
            "Title": d.get("title", "")[:60],
            "Comments": d.get("comments", 0),
            "Updated": d.get("updated_at", "")[:10],
            "Purpose": info["purpose"],
        })
    except Exception:
        pr_data.append({
            "PR": label,
            "State": "ERROR",
            "Title": "",
            "Comments": 0,
            "Updated": "",
            "Purpose": info["purpose"],
        })

if pr_data:
    st.dataframe(pd.DataFrame(pr_data), use_container_width=True, hide_index=True)

# Distribution status (static, update manually)
st.subheader("📡 Distribution Channels")
channels = [
    {"Platform": "PyPI", "Status": "✅ Published", "URL": "pypi.org/project/idea-reality-mcp"},
    {"Platform": "MCP Registry", "Status": "✅ Published", "URL": "registry.modelcontextprotocol.io"},
    {"Platform": "Smithery", "Status": "✅ Listed", "URL": "smithery.ai"},
    {"Platform": "Glama", "Status": "✅ Approved", "URL": "glama.ai/mcp/servers/@mnemox-ai/idea-reality-mcp"},
    {"Platform": "awesome-mcp-servers", "Status": "⏳ PR Open", "URL": "github.com/punkpeye/awesome-mcp-servers"},
    {"Platform": "GitHub Marketplace", "Status": "⏳ Pending Agreement", "URL": ""},
    {"Platform": "Dev.to", "Status": "✅ Published", "URL": "dev.to"},
    {"Platform": "PulseMCP", "Status": "✅ Submitted", "URL": "pulsemcp.com"},
    {"Platform": "MCP Market", "Status": "✅ Submitted", "URL": "mcpmarket.com"},
]
st.dataframe(pd.DataFrame(channels), use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Section 6: Placeholder — Trading & Memory (future)
# ---------------------------------------------------------------------------

st.header("💹 Trading & Memory (coming soon)")

st.caption(
    "Future sections:\n"
    "- **NG_Gold**: Shadow Mode stats (PnL, win rate, drawdown) from MT5\n"
    "- **TradeMemory**: trade count, reflection count, strategy performance from tradememory.db\n"
    "- **Backtest Results**: top variants from BATCH-001\n\n"
    "These will be added when data connectors are ready."
)

# Placeholder metrics
tc1, tc2, tc3, tc4 = st.columns(4)
tc1.metric("🏦 Demo Balance", "$9,863")
tc2.metric("📊 Trades", "7")
tc3.metric("🎯 Win Rate", "42.9%")
tc4.metric("💰 PnL", "-$69.99")
st.caption("⬆️ Hardcoded — will auto-update when MT5/tradememory connectors are added")

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

st.divider()
st.caption(
    "Built by [Mnemox AI](https://mnemox.ai) · "
    "[idea-reality-mcp](https://github.com/mnemox-ai/idea-reality-mcp) · "
    "[tradememory-protocol](https://github.com/mnemox-ai/tradememory-protocol)"
)
