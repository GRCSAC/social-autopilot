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
| `content/state.json` | Rotation pointer (which item is next per channel) — managed automatically |
| `config.json` | Channel IDs and posts-per-run |
| `generate.py` / `brand.py` | The image renderer + brand system |
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

## Notes & limits

- **Free-plan cap:** Buffer allows 10 queued posts per channel. At 3/week added and
  3/week published, the queue stays balanced. If it ever rejects a post, it's this
  cap; it self-corrects.
- **Rotation:** repeats after the library cycles (~4 weeks at 3/week with 12 items).
  Add more items to lengthen the rotation.
- **Fonts:** EB Garamond (serif) + Barlow (labels), bundled under OFL so CI renders
  identically to a laptop.
- **Idempotent:** a failed run doesn't advance the rotation, so it safely retries.
