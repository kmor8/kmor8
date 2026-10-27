"""Generate a terminal-style GitHub stats card (SVG) for a profile README.

Runs inside a GitHub Action with the built-in GITHUB_TOKEN, so it needs no
external service. Usage:
    python scripts/profile_stats.py --user kmor8 --out dist
    python scripts/profile_stats.py --mock --out dist   # local preview
"""
import argparse
import datetime as dt
import json
import os
import random
import urllib.request
from xml.sax.saxutils import escape

QUERY = """
query($login: String!) {
  user(login: $login) {
    repositories(ownerAffiliations: OWNER, privacy: PUBLIC) { totalCount }
    repositoriesContributedTo(contributionTypes: [COMMIT, PULL_REQUEST, ISSUE, REPOSITORY]) { totalCount }
    contributionsCollection {
      totalCommitContributions
      restrictedContributionsCount
      totalPullRequestContributions
      totalIssueContributions
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""

# Palette shared with assets/terminal.svg
LIME, PINK, TXT, FRAME, DIM, PERI = "#cde77f", "#f4a7c4", "#e6e6e6", "#7f8b99", "#9aa4ae", "#7d93c4"
FONT = "Cascadia Mono, Cascadia Code, Consolas, 'Fira Code', 'DejaVu Sans Mono', monospace"


def fetch(user, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": user}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.load(r)
    if "errors" in payload:
        raise SystemExit(f"GraphQL error: {payload['errors']}")
    return payload["data"]["user"]


def mock():
    today = dt.date.today()
    days = []
    for i in range(364, -1, -1):
        d = today - dt.timedelta(days=i)
        days.append({"date": d.isoformat(), "contributionCount": random.choice([0, 0, 1, 2, 3, 5, 8]) if i > 3 else 2})
    weeks = [{"contributionDays": days[i:i + 7]} for i in range(0, len(days), 7)]
    return {
        "repositories": {"totalCount": 4},
        "repositoriesContributedTo": {"totalCount": 7},
        "contributionsCollection": {
            "totalCommitContributions": 312, "restrictedContributionsCount": 120,
            "totalPullRequestContributions": 9, "totalIssueContributions": 4,
            "contributionCalendar": {"totalContributions": sum(d["contributionCount"] for d in days), "weeks": weeks},
        },
    }


def streaks(days):
    counts = [d["contributionCount"] for d in days]
    longest = run = 0
    for c in counts:
        run = run + 1 if c > 0 else 0
        longest = max(longest, run)
    current = 0
    i = len(counts) - 1
    if i >= 0 and counts[i] == 0:  # today without contributions doesn't break the streak yet
        i -= 1
    while i >= 0 and counts[i] > 0:
        current += 1
        i -= 1
    best = max(days, key=lambda d: d["contributionCount"]) if days else None
    return current, longest, best


def render(u):
    cc = u["contributionsCollection"]
    cal = cc["contributionCalendar"]
    days = [d for w in cal["weeks"] for d in w["contributionDays"]]
    cur, longest, best = streaks(days)
    last = days[-30:]

    W, H = 960, 350
    wx, wy, ww, wh = 0, 0, W, H
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="GitHub stats">',
         f'<style>text{{font-family:{FONT};}} .l{{fill:{LIME};font-weight:700;font-size:15px}} .t{{fill:{TXT};font-size:15px}} '
         f'.h{{fill:{LIME};font-size:15px}} .d{{fill:{DIM};font-size:12px}}</style>',
         f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="10" fill="#1b2026" stroke="#a9c48a" stroke-opacity=".55"/>',
         f'<rect x="1" y="1" width="{W-2}" height="38" rx="10" fill="#14181d"/><rect x="1" y="28" width="{W-2}" height="11" fill="#14181d"/>',
         f'<text x="22" y="25" class="d" style="font-size:14px">&gt;_</text><text x="50" y="25" class="t" style="font-size:14px">kami@github: ~/stats</text>',
         f'<text x="{W-110}" y="25" class="d" style="font-size:15px">—    ☐    ✕</text>']

    def box(x, y, bw, title, rows, lh=22):
        h = len(rows) * lh + 20
        tw = len(title) * 9 + 16
        cx = x + bw / 2
        o.append(f'<path d="M{x+4},{y+h} V{y} H{cx-tw/2}" fill="none" stroke="{FRAME}"/>')
        o.append(f'<path d="M{cx+tw/2},{y} H{x+bw} V{y+h} H{x+4}" fill="none" stroke="{FRAME}" stroke-opacity=".7"/>')
        o.append(f'<text x="{cx}" y="{y+5}" text-anchor="middle" class="h">{escape(title)}</text>')
        for i, (k, v) in enumerate(rows):
            yy = y + 26 + i * lh
            o.append(f'<path d="M{x+4},{yy-5} H{x+14}" stroke="{FRAME}"/>')
            o.append(f'<text x="{x+20}" y="{yy}" class="l">{escape(k)}</text>')
            o.append(f'<text x="{x+bw-14}" y="{yy}" text-anchor="end" class="t">{escape(str(v))}</text>')

    year = cal["totalContributions"]
    box(24, 64, 430, "Activity · last 12 months", [
        ("CONTRIBUTIONS", f"{year:,}"),
        ("COMMITS", f"{cc['totalCommitContributions']:,}"),
        ("PRIVATE", f"{cc['restrictedContributionsCount']:,}"),
        ("PULL REQUESTS", f"{cc['totalPullRequestContributions']:,}"),
        ("ISSUES", f"{cc['totalIssueContributions']:,}"),
    ])
    best_txt = "—"
    if best and best["contributionCount"] > 0:
        bd = dt.date.fromisoformat(best["date"])
        best_txt = f"{best['contributionCount']} on {bd.strftime('%d %b %Y')}"
    box(490, 64, 446, "Streaks & repos", [
        ("CURRENT", f"{cur} day{'s' if cur != 1 else ''}"),
        ("LONGEST", f"{longest} day{'s' if longest != 1 else ''}"),
        ("BEST DAY", best_txt),
        ("PUBLIC REPOS", u["repositories"]["totalCount"]),
        ("CONTRIBUTED TO", u["repositoriesContributedTo"]["totalCount"]),
    ])

    # 30-day bar chart
    gx, gy, gw, gh = 28, 238, W - 56, 70
    mx = max([d["contributionCount"] for d in last] + [1])
    bw = gw / len(last)
    o.append(f'<text x="{gx}" y="{gy-8}" class="h">last 30 days</text>')
    o.append(f'<line x1="{gx}" y1="{gy+gh}" x2="{gx+gw}" y2="{gy+gh}" stroke="{FRAME}" stroke-opacity=".6"/>')
    for i, d in enumerate(last):
        c = d["contributionCount"]
        x = gx + i * bw + 3
        if c == 0:
            o.append(f'<rect x="{x}" y="{gy+gh-3}" width="{bw-6}" height="2" fill="{DIM}" fill-opacity=".5"/>')
            continue
        h = max(4, gh * c / mx)
        fill = PINK if i == len(last) - 1 else LIME
        o.append(f'<rect x="{x}" y="{gy+gh-h}" width="{bw-6}" height="{h}" rx="2" fill="{fill}" fill-opacity="{0.45 + 0.55 * c / mx:.2f}">'
                 f'<title>{d["date"]}: {c} contribution{"s" if c != 1 else ""}</title></rect>')
    first = dt.date.fromisoformat(last[0]["date"]).strftime("%d %b")
    lastd = dt.date.fromisoformat(last[-1]["date"]).strftime("%d %b")
    o.append(f'<text x="{gx}" y="{gy+gh+18}" class="d">{first}</text>')
    o.append(f'<text x="{gx+gw}" y="{gy+gh+18}" text-anchor="end" class="d">{lastd}</text>')
    o.append(f'<text x="{W/2}" y="{gy+gh+18}" text-anchor="middle" class="d">updated {dt.date.today().isoformat()}</text>')
    o.append("</svg>")
    return "\n".join(o)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default=os.environ.get("GITHUB_REPOSITORY_OWNER", ""))
    ap.add_argument("--out", default="dist")
    ap.add_argument("--mock", action="store_true")
    a = ap.parse_args()
    data = mock() if a.mock else fetch(a.user, os.environ["GITHUB_TOKEN"])
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "stats.svg"), "w", encoding="utf-8") as f:
        f.write(render(data))
    print("wrote", os.path.join(a.out, "stats.svg"))


if __name__ == "__main__":
    main()
