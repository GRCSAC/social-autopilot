# GRCSAC Social Autopilot

Hands-off social posting for **LinkedIn (GRCSAC)** and **Instagram
(@compassionunleashed)**. Every week it picks the next posts from a curated
library, renders on-brand images for Instagram, and queues everything to Buffer —
which publishes on the Mon/Wed/Fri schedule. No servers, no logins, no manual
uploads. New setup? Read **[SETUP.md](SETUP.md)** first (~15 min, one time).

## How it works

```
GitHub Actions (weekly cron)
  1. run.py build   → pick next items from content/*.json; render Instagram
                       cards (Pillow, bundled fonts) into public/
  2. git commit public/  → this public repo's images are served free via jsDelivr
  3. run.py post    → verify images are live, then call the Buffer API to queue
                       each post (text for LinkedIn; text + image URL for Instagram)
  4. git commit content/state.json  → advance the rotation pointer
        │
        ▼
     Buffer  → auto-publishes on the Mon/Wed/Fri schedule you set per channel
```

The trick that makes it fully automatic: Buffer attaches images **by URL**
(`assets:[{image:{url}}]`), so the image never has to be uploaded through a
browser — Buffer fetches it from the CDN. That's the wall that blocks manual
automation, sidestepped. This repo is public so jsDelivr can serve the card images
(`https://cdn.jsdelivr.net/gh/GRCSAC/social-autopilot@main/public/cards/…`); it holds
no secrets — the Buffer token lives only in GitHub Actions secrets.

## Files

| Path | What it is |
|---|---|
| `content/instagram.json` | Library of Instagram posts (quote/feature cards + captions) |
| `content/linkedin.json` | Library of LinkedIn text posts |
| `content/studio_instagram.json` | GRCSAC Studio stream: one card per app or public repo, for the studio's own Instagram (see below) |
| `studio.py` + `assets/apps/` | Portrait (1080x1350) card renderer for the studio stream, plus every app's icon |
| `studio_queue.py` + `content/studio_schedule.json` | Plans and records the studio posts scheduled in Meta Business Suite (see STUDIO-SCHEDULING.md) |
| `ig_studio.py` + `.github/workflows/studio.yml` | Parked direct-API publisher for the studio stream (needs a Meta developer token) |
| `content/state.json` | Rotation pointer (which item is next per channel) — managed automatically |
| `config.json` | Channel IDs and posts-per-run |
| `generate.py` / `brand.py` | The image renderer + brand system |
| `llm_content.py` | Weekly post generation (Claude) when `config.json` mode is `generate` |
| `quality.py` / `content/slop.json` | Quality gate every generated post must pass before it is queued |
| `buffer_client.py` | Buffer GraphQL API client |
| `run.py` | Orchestrator (`build` / `post`) |
| `assets/fonts`, `assets/covers` | Bundled fonts + book covers |
| `.github/workflows/autopilot.yml` | The weekly schedule |

## Changing what it posts

**Add or edit posts** — just edit the JSON. It's a plain list; the system rotates
through it and repeats only after the whole library cycles.

Instagram quote card:
```json
{ "id": "ig-my-post", "type": "quote",
  "eyebrow": "Small Label On Top", "quote": "The line that appears big.",
  "attribution": "Paul Zarou",
  "caption": "Full Instagram caption with #hashtags" }
```
Instagram book-feature card:
```json
{ "id": "ig-my-feature", "type": "feature",
  "eyebrow": "Small Label", "hook": "The line on the left.",
  "cover": "unbreakable.jpg", "footer": "BOOK TITLE . OUT NOW",
  "caption": "Full caption with #hashtags" }
```
LinkedIn post:
```json
{ "id": "li-my-post", "text": "Full post text with line breaks and #hashtags" }
```

**Preview a card locally** (needs Python + Pillow):
```bash
python generate.py quote "Your quote here" --eyebrow "LABEL" --attrib "Paul Zarou" -o preview.jpg
```

**Change cadence / volume** — `config.json` `posts_per_run` (default 3 each), and
the cron in `.github/workflows/autopilot.yml`. When to post is set in Buffer's
per-channel posting schedule, not here.

**Change the schedule of publishing** — in Buffer (Channel settings → Posting
Schedule). This repo only controls *what* gets queued; Buffer controls *when*.

## Quality gate (generated posts)

In `generate` mode every draft is checked by `quality.py` before it goes near
Buffer: stock AI vocabulary and phrases (`content/slop.json`), the sentence
shapes models default to ("it's not X, it's Y", emoji, hashtag walls),
invisible or non-keyboard characters, and a LinkedIn first line that fits the
mobile "...more" cut (140 characters). A draft that trips it goes back to the
model with the reasons, up to three times. If it still fails, the run posts
from the curated library that week instead and says so in the log. The gate is
calibrated so Paul's own library passes clean; keep it that way when adding
words:

```bash
python quality.py --library     # must report 0 issues
echo "draft text" | python quality.py - --linkedin
```

Generated LinkedIn posts open with a hook on its own line: a plain, specific
claim under 120 characters, because that line is all a phone shows.

## The GRCSAC Studio stream (apps and repos)

A second Instagram account, for the apps on grcsac.com rather than the books. It
is a **curated** stream, never LLM-generated: every headline and caption is a
checked product fact (price, platform, store status) taken from the app's own
site, so a wrong claim can only come from a human edit. Items in
`content/studio_instagram.json`:

```json
{ "id": "ig-studio-siftlet-1", "app": "siftlet", "name": "Siftlet",
  "platform": "iPhone + Android", "status": "On the App Store",
  "headline": "Just the recipe.", "sub": "One sentence under the headline.",
  "footer": "siftlet.grcsac.com",
  "caption": "Full caption, ending in up to six #hashtags" }
```

`app` picks the icon (`assets/apps/<app>.png`) and the accent colour (`studio.py`
`ACCENT`, taken from the grcsac.com tile palette). The library is interleaved
round-robin across apps so one week never shows three cards for the same app.

Preview: `python studio.py content/studio_instagram.json ig-studio-siftlet-1 -o preview.jpg`
or `--all -o preview/` for the whole library.

**This stream does not go through Buffer** (its free plan is full) **and not yet
through Meta's API** (the Meta app was set up on 2026-11-17 but has no token yet).
It is scheduled in **Meta Business Suite**, signed in with the studio
Instagram account, three weeks ahead, Mon/Wed/Fri at 11:00 Eastern. `studio_queue.py`
decides which card goes on which date and keeps the ledger in
`content/studio_schedule.json`; the procedure is in
[STUDIO-SCHEDULING.md](STUDIO-SCHEDULING.md).

`ig_studio.py` and `.github/workflows/studio.yml` are the direct-API publisher,
built and tested but parked: the workflow has no schedule. The Meta app behind it
exists since 2026-11-17; the remaining steps are in STUDIO-SCHEDULING.md under
"The API route".

House rules for new studio items: plain founder voice, second person, no em or
en dashes, straight quotes, no emoji, at most six hashtags, and nothing an app
does not do today. A price goes in only if it is stable; "pay once" is safer than
a number that will change. Run the same verifiers as for the book libraries.

## Notes & limits

- **Free-plan cap:** Buffer allows 10 queued posts per channel. At 3/week added and
  3/week published, the queue stays balanced. If it ever rejects a post, it's this
  cap; it self-corrects.
- **Rotation:** repeats after the library cycles (~4 weeks at 3/week with 12 items).
  Add more items to lengthen the rotation.
- **Fonts:** EB Garamond (serif) + Barlow (labels), bundled under OFL so CI renders
  identically to a laptop.
- **Idempotent:** a failed run doesn't advance the rotation, so it safely retries.
