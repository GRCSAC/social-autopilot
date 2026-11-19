# GRCSAC Studio on Instagram: the campaign

Written 2026-11-16. The studio Instagram account exists; the posting pipeline for it
is in this repo (`content/studio_instagram.json`, `studio.py`, `ig_studio.py`). It has
been live since 2026-11-16: the first posts were scheduled in Meta Business
Suite, and since 2026-11-20 the repo posts through Meta's API twice a day
([STUDIO-SCHEDULING.md](STUDIO-SCHEDULING.md)).

## What it is for

One account that shows everything GRCSAC makes, in one voice: the apps on
www.grcsac.com, the games, and the public repos. Not the books; those stay on
@compassionunleashed. The job of the account is to be the place a person lands
after seeing one app and discovers the other ten, and to make the studio's stance
(pay once, no trackers, say it plainly) visible without a pitch.

## Cadence

- **Two posts a day, every day, at 11:00 and 19:00 Eastern** (the owner's call on
  2026-11-19; it was three a week before). Buffer is not involved.
- **No post is ever repeated.** An item goes out once. The library therefore has
  to grow by fourteen items a week; a scheduled session writes them by the
  rules in [STUDIO-CONTENT.md](STUDIO-CONTENT.md), and when there is nothing new
  and true to say the account posts less rather than repeat or pad.
- The library began with 50 items across 13 subjects: 33 typographic cards,
  seven App Store clips, and ten posts built from the apps' own screens (five
  screenshot cards, three swipeable carousels, one Android round-up, one
  animated Reel).
- No paid promotion and no follower goals. Measure at 90 days, not before.

## Content pillars

| Pillar | Cards |
|---|---|
| The product, one claim at a time | one lead card per app: In The Zone, PavLove, Fit This, Findr, Siftlet, Sunk Cost, CySec, NextFix, Infinite Worlds, Zelzi, CineDrive, Earnest |
| Price and privacy stance | "$1.99. Once.", "Buy it once.", "Most of what we make never leaves your phone." |
| Honest limits | CySec "One honest limit.", CineDrive "We would rather say it plainly." |
| Public repos | NextFix (Apache 2.0), Infinite Worlds desktop build, and this repo itself |
| The studio | "One thread runs through all of it." |
| App Store clips (video, once each) | In The Zone, Fit This, CySec, Findr, Infinite Worlds, Siftlet, Sunk Cost |
| Android | "Three of our apps are on Google Play." plus Android posts for Findr, Sunk Cost (a carousel and the animated meter Reel) and Infinite Worlds (a carousel) |
| The app's own screen | In The Zone treadmill, PavLove 9 PM pattern, Fit This recovery, CySec radar, Siftlet from link to lock-screen timer |

Every line comes from the app's own site or its store screenshots. Numbers shown on a screenshot are example data and the caption says so. Nothing promises a feature that has not
shipped. Status words on the card (On the App Store, Coming soon, In development)
are taken from the grcsac.com tiles and must be updated when a tile changes.

## What changes over time

- **An app ships or changes price:** edit its cards in the JSON (status, price,
  platform), re-render with `python studio.py ... --all`, check the preview, push.
  Only items that have not been posted can be edited; the ledger is history.
- **A new app appears on grcsac.com:** add its icon to `assets/apps/`, its accent
  to `studio.py`, and two or three cards at the end of the library.
- **Android:** only Findr, Sunk Cost and Infinite Worlds are on Google Play today.
  Siftlet's site says Android is next; do not call it available until its tile
  and site say so. When another app reaches Google Play, add it to the round-up
  card's `icons` and sub-line.
- **Third-party art:** Findr's store screenshots show film posters and actors.
  The posts here use its taste chart instead, which shows neither.
- **Video:** the pipeline posts Reels as well as cards. Put a 1080x1920 MP4 under
  20 MB in `public/video/`, add an item with `"video"` and a caption to the
  library, and run the workflow's `probe` to confirm Meta accepts it. Every item
  runs once, so a dated clip cannot come round again. There is no
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
