# GRCSAC Studio on Instagram: the campaign

Written 2026-11-16. The studio Instagram account exists; the posting pipeline for it
is in this repo (`content/studio_instagram.json`, `studio.py`, `ig_studio.py`). It has
been live since 2026-11-16: the first nine posts were scheduled in Meta Business
Suite, and from 2026-12-09 the repo posts through Meta's API
([STUDIO-SCHEDULING.md](STUDIO-SCHEDULING.md)).

## What it is for

One account that shows everything GRCSAC makes, in one voice: the apps on
www.grcsac.com, the games, and the public repos. Not the books; those stay on
@compassionunleashed. The job of the account is to be the place a person lands
after seeing one app and discovers the other ten, and to make the studio's stance
(pay once, no trackers, say it plainly) visible without a pitch.

## Cadence

- 3 posts a week, Mon/Wed/Fri at 11:00 Eastern. Buffer is not involved (its free
  plan is full). Through 7 Dec 2026 the posts sit in Meta Business Suite; from
  9 Dec a GitHub Actions workflow publishes them through Meta's API.
- The library has 33 cards across 13 subjects, interleaved so a week never repeats
  an app, plus seven short App Store clips that each run once, between the cards,
  from 9 Dec 2026 to 6 Jan 2027. One full cycle of the cards is about 11 weeks;
  after that it repeats, which is fine on Instagram, and new items are added as
  apps ship.
- No paid promotion, no follower goals, no posting on a day there is nothing true
  to say. Measure at 90 days, not before.

## Content pillars (what the 33 cards cover)

| Pillar | Cards |
|---|---|
| The product, one claim at a time | one lead card per app: In The Zone, PavLove, Fit This, Findr, Siftlet, Sunk Cost, CySec, NextFix, Infinite Worlds, Zelzi, CineDrive, Earnest |
| Price and privacy stance | "$1.99. Once.", "Buy it once.", "Most of what we make never leaves your phone." |
| Honest limits | CySec "One honest limit.", CineDrive "We would rather say it plainly." |
| Public repos | NextFix (Apache 2.0), Infinite Worlds desktop build, and this repo itself |
| The studio | "One thread runs through all of it." |
| App Store clips (video, once each) | In The Zone, Fit This, CySec, Findr, Infinite Worlds, Siftlet, Sunk Cost |

Every line comes from the app's own site. Nothing promises a feature that has not
shipped. Status words on the card (On the App Store, Coming soon, In development)
are taken from the grcsac.com tiles and must be updated when a tile changes.

## What changes over time

- **An app ships or changes price:** edit its cards in the JSON (status, price,
  platform), re-render with `python studio.py ... --all`, check the preview, push.
  Append new cards rather than reordering; the cursor only tolerates reordering
  when it sits at 0.
- **A new app appears on grcsac.com:** add its icon to `assets/apps/`, its accent
  to `studio.py`, and two or three cards. Slot them into the interleave by hand.
- **Video:** the pipeline posts Reels as well as cards. Put a 1080x1920 MP4 under
  20 MB in `public/video/`, add an item with `"video"` and a caption after the
  cursor, and run the workflow's `probe` to confirm Meta accepts it. Mark a clip
  `"once": true` if it carries a date or a claim that will age. There is no
  original footage yet; the capture list in the In The Zone marketing docs is
  the model for it.

## Scorecard (check at 30, 60, 90 days)

From Instagram Insights on the studio account, into `docs/scorecards/` if this
repo grows one: reach per post, profile visits, link taps to www.grcsac.com, and
which app's cards earn the most saves. Saves are the signal that a card is worth
keeping; reach is mostly noise at this size. App Store and Play downloads are
tracked per app in their own consoles, not here.

## Bio and profile (Paul's side, one time)

- Name: GRCSAC Studio. Bio: one line in the house voice, for example
  "Apps and games that keep your data on your phone. Pay once, no trackers."
- Link: https://www.grcsac.com (every caption ends "link in bio").
- Profile image: `assets/apps/grcsac.png` (the square logo).
- Professional account type is required for Business Suite scheduling and for the API.
