# Mnemox Metrics Dashboard

All Mnemox projects, one view. Built with Streamlit.

## What It Tracks

| Section | Source | Auto? |
|---------|--------|-------|
| GitHub stats (stars, forks, issues, PRs) | GitHub API | ✅ |
| GitHub traffic (views, clones, referrers) | GitHub API | ✅ (needs token) |
| PyPI downloads (daily, weekly, monthly) | pypistats API | ✅ |
| Website traffic | `website_traffic.json` | Manual |
| Open PRs & distribution channels | GitHub API + static | Semi-auto |
| Trading & Memory stats | Coming soon | — |

## Quick Start

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GITHUB_TOKEN` | Optional | GitHub PAT — raises rate limit from 60 to 5,000 req/hr. Needs `repo` scope for traffic data. |

## Deploy to Streamlit Cloud

1. Push to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect repo → select `app.py`
4. Add `GITHUB_TOKEN` in Secrets

## Website Traffic

Create/update `website_traffic.json`:

```json
{
  "views_14d": 40,
  "uniques_14d": 8,
  "updated_at": "2026-02-28",
  "top_pages": [
    {"path": "/", "views": 28, "uniques": 6},
    {"path": "/check", "views": 12, "uniques": 4}
  ]
}
```

## Future

- MT5 trading stats (PnL, win rate, drawdown)
- tradememory.db integration (trade count, reflections)
- Backtest results from BATCH-001
