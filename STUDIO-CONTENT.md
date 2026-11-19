# Writing new posts for the GRCSAC Studio Instagram

The account (@grcsac_studio) posts twice a day, every day, and never posts the
same item twice. That only works if the library in
`content/studio_instagram.json` keeps growing. This page is the rulebook for
adding to it, whether a person or a scheduled session does the writing.

The order of importance: **true, then new, then good-looking.** A post that
fails any of the three is not added. Fewer posts is better than a padded one.

## 1. True

- Every factual claim (what an app does, what it costs, where it is available,
  what it does with data) must be on one of GRCSAC's own pages **on the day the
  item is written**. Read the page; do not write from memory or from an older
  item. `python tools/page_text.py https://<app>.grcsac.com/` prints a page as
  text. Sources, in order: the app's own site (home, privacy, support, terms),
  the tile on www.grcsac.com, games.grcsac.com, and for NextFix its public
  repository's README and docs.
- The status line on the card ("On the App Store", "On Google Play", "In
  development", "Coming soon") and the platform line come from the app's tile
  and site that day. If they changed, fix the app's waiting items in the same
  commit.
- Do not write anything that will stop being true before it posts. An item can
  wait three weeks. So: no price for an app whose site announces a price
  change, no "new", "this week", "just shipped", no version numbers, no
  seasonal or holiday posts, no dates.
- Never invent or imply: reviews, ratings, download or user numbers,
  testimonials, awards, press, comparisons with a named competitor, results a
  user will get, medical, health, nutrition, allergen or food-safety claims,
  security guarantees, or a feature that has not shipped.
- A number on a screenshot is example data. Say so in the caption.
- Per-app limits that the sites already respect, and so must the posts:
  - **Siftlet:** say only the platforms its site lists as available. Nothing
    about nutrition, allergens or food safety.
  - **CineDrive:** in development. Video on the car screen depends on car
    makers turning on a CarPlay feature; say that plainly whenever the car
    screen is mentioned, exactly as the site does.
  - **PavLove, In The Zone, Fit This:** they help someone notice or track.
    They do not treat, cure, diagnose or guarantee a change.
  - **CySec, NextFix:** they help decide what to look at first. They do not
    make anything secure. For NextFix describe what it does, never how it was
    built.
  - **Zelzi:** never name or allude to another card game.
  - **Earnest:** coming soon; say only what its page says.
  - **Infinite Worlds:** all-ages wording only.
- Not on this account: the books and the coaching practice, politics, news,
  giveaways, discounts, countdowns, memes about other companies.
- A stance post (pay once, no trackers, plain speaking) is allowed, as long as
  every app it names really works that way according to its own site.

## 2. New

- Run `python ig_studio.py angles <app>` before writing. It lists every
  headline and caption opening already in the library for that app, posted or
  waiting. A new item must make a **point none of those makes**. The same fact
  in different words is a repeat. A different, specific fact about the same
  feature is not.
- Good places to find a new point: one feature the site describes that no item
  covers; one line of the privacy page (what is stored, what is never sent); a
  question the support page answers; an honest limit; who the app is for and
  who it is not for; one screen and what it tells you; how two GRCSAC apps
  share a principle.
- When an app has nothing new and true left, add nothing for it. Do not
  stretch. New material arrives when an app ships something or a new
  screenshot or clip is added to `assets/`.
- Spread: at most two new items per app in one batch, and prefer the apps with
  the fewest items waiting (`python ig_studio.py stock` shows the counts).

## 3. Good-looking

Three kinds of item can be written here. Field names are exact.

A card:

```json
{ "id": "ig-studio-findr-6", "app": "findr", "name": "Findr",
  "platform": "iPhone + Android", "status": "On the App Store",
  "headline": "Up to 70 characters. One plain claim.",
  "sub": "Optional. Up to 180 characters. One sentence that completes it.",
  "footer": "findr.grcsac.com",
  "caption": "Opening line that is not the headline.\n\nTwo or three short paragraphs.\n\nfindr.grcsac.com (link in bio)\n\n#three #to #six #hashtags #grcsac" }
```

A screenshot card: the same, plus `"shot": "file.jpg"` naming a file in
`assets/shots/`. The headline says what that screen shows. Do not use the same
screenshot for the same point twice; `angles` lists which screenshots each
item uses.

A carousel: `app`, `name`, `platform`, `status`, `footer`, `caption`, and
`"slides": [ {"headline": "...", "sub": "..."}, {"headline": "...", "shot": "..."} ]`
with two to five slides. Use it when a point has steps or parts. Each slide
must stand on its own.

- `id` is `ig-studio-<app>-<next number>`. Append new items at the end of the
  file. Never edit or remove an item that is in the ledger
  (`content/studio_schedule.json`); it is history.
- `app` must have an icon in `assets/apps/` and a colour in `studio.py`.
- Videos (`"video"`) are made by hand and added separately. Do not write items
  that need a file that does not exist.
- Voice: plain, specific, second person, short sentences. Two-beat headlines
  are the house style ("Pace lies. Your heart doesn't."). No long dashes, no
  exclamation marks, no emoji, no "not X, not Y, just Z" triplets, no
  questions as headlines more than once in a batch, no hype words
  (revolutionary, seamless, effortless, game-changing, unlock, elevate).
- Captions: 250 to 600 characters, the site and "(link in bio)" on their own
  line, then three to six lowercase hashtags ending with `#grcsac`.

## 4. Check before committing

```
python ig_studio.py lint
python studio.py content/studio_instagram.json <new id> -o preview/new/<new id>.jpg
```

`lint` must pass. Then open every rendered image and look at it: the headline
is not cut off or shrunk to nothing, the sub line does not run into the footer,
a screenshot is the right way up and readable. Fix or drop anything that looks
wrong. Commit only `content/studio_instagram.json` (and a new file under
`assets/` if one was added), then push.
