# Scheduling the GRCSAC Studio Instagram

How @grcsac_studio gets its posts.

**Since 2026-11-20 the account posts twice a day, every day, at 11:00 and 19:00
Eastern, and never posts the same item twice.**

- `.github/workflows/studio.yml` publishes through Meta's API, with no browser
  involved. See "The API route".
- Ten 11:00 slots between 18 Nov and 9 Dec 2026 hold posts that were scheduled
  by hand in Meta Business Suite before the API route started. Meta publishes
  those; the workflow sees them in the ledger and fills only the other slot on
  those days.
- **No repeats:** `content/studio_schedule.json` is the whole history of the
  account. The next post is always the first library item whose id is not in
  it. When every item has been posted, nothing is posted until new items are
  added. A scheduled session adds them; see "Keeping the library full".
- **When Meta's API refuses the token** (it did from 2026-11-18 to 2026-11-19),
  a daily routine on the laptop schedules the next days' posts in Meta Business
  Suite instead and records them, so the API never fills those slots as well.
  See "The safety net".

## Why this route

| Route | Verdict |
|---|---|
| Buffer | Free plan is full (three channels). Not used for this account. |
| Meta's Instagram API (`ig_studio.py`, `studio.yml`) | **The route, from 2026-11-20.** It was blocked until 2026-11-17 because a Meta developer account needs a Facebook account; one now exists. Token checked, all media accepted by Meta in a rehearsal. |
| Instagram's own web composer | Uploads fine, but offers only Share now. No schedule control. |
| Meta Business Suite (business.facebook.com) | Works, and carried the first nine posts. "Continue with Instagram" signs in with the studio account, no Facebook needed. Its composer has "Set date and time". Now the safety net for when the API is refused: it needs a browser, so it is not the first choice. |

The first posts were scheduled in Meta's own tool, in a browser signed in as
@grcsac_studio. Everything else is published by the workflow. Either way this
repo decides which post goes in which slot and keeps the ledger.

## The moving parts

- `content/studio_instagram.json` — the library: every post, written ahead of
  time (see README and [STUDIO-CONTENT.md](STUDIO-CONTENT.md)).
- `ig_studio.py` — the API route (`check`, `gate`, `build`, `publish`, `probe`),
  the safety net's commands (`health`, `handoff N`, `handoff-done ID DATE SLOT`)
  and the library's (`stock`, `lint`, `angles`).
- `studio_queue.py status` — the ledger from today on, and what is waiting.
- `content/studio_schedule.json` — the ledger: every post ever scheduled or
  published, with its date and slot. An id in it is never posted again.
- `content/state.json` `studio_failed` — how often Meta refused a waiting item;
  after three refusals the item is set aside and the queue moves on.
- Slots: **11:00 and 19:00 America/New_York, every day.**

## Keeping the library full

Two posts a day with no repeats uses fourteen items a week. A scheduled task in
Claude's desktop app on the laptop (`grcsac-studio-content`, Monday and Thursday
mornings) keeps about four weeks of posts waiting:

1. `python ig_studio.py stock` says how many items are waiting and how many days
   they cover. Twenty-eight days or more ends the run.
2. Otherwise it writes new items by the rules in
   [STUDIO-CONTENT.md](STUDIO-CONTENT.md): every claim read from the app's own
   page that day, and a point no earlier item makes
   (`python ig_studio.py angles <app>` lists what has been said).
3. `python ig_studio.py lint` must pass, every new card is rendered and looked
   at, and only then is the library committed and pushed.

When an app has nothing new and true left to say, the routine adds nothing for
it. If the whole library runs dry the workflow skips its slots and shows a
warning on the run; it does not fall back to repeating. New screenshots in
`assets/shots/` and clips in `public/video/` are what give it more to say.

## The safety net (since 2026-11-19)

Meta can refuse the API token without warning; it did on 2026-11-18, a day after
the token passed every check. Posting must not depend on that, so a scheduled
task on the laptop (`grcsac-studio-instagram-topup`, every day at about 09:30
Eastern, in Claude's desktop app) does this:

1. `python ig_studio.py handoff 3` lists the slots from now through three days
   ahead that have no post in the ledger, each with the next image item from
   the library, rendered into `preview/queue/`. An empty list ends the run.
2. It starts the workflow with `health_only`, which prints `health: ok` or
   `health: BLOCKED (...)` and never fails, so a refused token does not send a
   failure email every morning. `ok` ends the run: the API will post.
3. If blocked, it schedules each listed post in Business Suite for its slot
   (11:00 AM or 7:00 PM), in Chrome signed in as @grcsac_studio, checks the
   Scheduled list, and runs `python ig_studio.py handoff-done ID DATE SLOT`,
   then commits and pushes `content/studio_schedule.json`.

What that does to the queue:

- The fallback posts images only: cards, screenshot cards and carousels (a
  carousel is its slides uploaded together in one go). Reels stay in the
  library for the API.
- The slot goes into the ledger with `"via": "business-suite"`. The gate skips
  any slot in the ledger and no id in the ledger is posted again, so the API
  cannot double up. When the API works again it takes the next free slot.

What it depends on: the laptop awake at 09:30 with Chrome open, and Instagram
signed in as @grcsac_studio in that Chrome. Because it looks three days ahead
and runs daily, one missed morning costs nothing.

If the API is refused between two morning checks, that day's API slots are
missed and GitHub emails the failures. The next morning's run covers the
following days.

## Notes for driving it with browser automation

Learned the hard way on 2026-11-16; the composer is not automation-friendly.

- **"Add photo/video" opens a native file picker** from a detached
  `<input type=file>`. Before clicking it, patch `HTMLInputElement.prototype.click`
  so a file input is appended to the page instead of opened; then set its files.
  Clicking the button without the patch leaves a native dialog open and the tab
  stops taking keyboard input.
- **Do not type the caption key by key.** Each keystroke re-renders the preview and
  a full caption freezes the tab for a minute. Dispatch a `paste` ClipboardEvent
  with the text on the editor (`[role=combobox][contenteditable=true]`) instead.
  The editor's `innerText` then shows three newlines between paragraphs; that is
  one blank line in the post.
- Date field: `input[placeholder="mm/dd/yyyy"]`, type `MM/DD/YYYY` then Enter; it
  then reads like `Dec 2, 2026`. Time: three spinbuttons labelled `hours`,
  `minutes`, `meridiem`; focus each and type `11`, `00`, `A`.
- **Guard before clicking Schedule**: date reads as expected, time reads 11:00AM,
  caption starts with the right words, and the media row says `1080 x 1350`.
  Exactly one button is labelled Schedule once the switch is on; before that the
  same button says Publish, which posts immediately.
- After Schedule the composer can sit on "Scheduling your post" with "We're having
  trouble completing your request" underneath. The post is scheduled anyway. Do not
  click again; check the Scheduled list.
- A fresh composer needs about ten seconds before its buttons exist.
- **Carousel:** the file input takes several files; set all the slides on it in
  one go, in order. The media list then shows one `1080 x 1350` row per slide.
- After the caption is pasted a hashtag suggestion list opens; press Escape.
- **Leaving the composer hangs the tab** on Chrome's "Leave site?" prompt, which
  automation cannot answer. Before navigating away or closing, run
  `window.addEventListener('beforeunload', e => e.stopImmediatePropagation(), true)`
  in the page. A tab already stuck on the prompt cannot be rescued this way.
- Use the composer and Scheduled-list addresses with the current portfolio's
  `business_id`; the routine's instructions carry them.

## The API route (switched on 2026-11-17, first post 2026-11-20)

What exists on Meta's side, so nobody repeats it:

- A Facebook account and a Meta for Developers registration (role: Developer).
- A Meta app, **GRCSAC Studio Autopilot**, in development mode, with the use case
  "Manage messaging & content on Instagram" (it is under the Content management
  filter, not Featured) and the permissions `instagram_business_basic` and
  `instagram_business_content_publish`.
- A business portfolio connected to the app. Meta's setup tab will not open without
  one, even though the app wizard lets you skip it. Meta rejects all-capitals
  portfolio names, and a brand-new Facebook account must wait about an hour before
  it may create one.
- @grcsac_studio added under App roles -> Roles as an **Instagram Tester**, and the
  invitation accepted at instagram.com -> Settings -> Apps and websites -> Tester
  Invites. After that the account appears under "Generate access tokens" with a
  **Generate token** link.
- A login configuration, **Instagram API (Unified Login)**, created from Meta's
  template under "1. Configure your app" and selected. Without it, Generate token
  answers "Select a configuration in Step 1 before generating an access token."
  The template was then edited (Facebook Login for Business -> Configurations ->
  Edit): **Ad accounts** unticked under Assets, and the permissions cut to
  `instagram_basic` and `instagram_content_publish`. As shipped, the template makes
  the approval window create a new ad account, with no way to decline.
- @grcsac_studio added to the business portfolio (Business settings -> Instagram
  profiles -> Add). Without it the Facebook approval window offers no Instagram
  account ("No matching results"). The Add button opens an Instagram window with
  "Log in as grcsac_studio"; the confirmation only counts when it is clicked in
  the window Meta opened, so it has to be done by hand.
- The repository variable `IG_STUDIO_USER_ID`, holding the account's Instagram ID.

Meta now calls this "API setup with Unified login" and says the older "API setup
with Instagram login" is not available for newer apps. The difference matters:

| | Instagram login (old) | Unified login (this app) |
|---|---|---|
| Host | `graph.instagram.com` | `graph.facebook.com` |
| Token | 60 days, refreshed every run | system-user token, does not expire |
| Permissions | `instagram_business_*` | `instagram_basic`, `instagram_content_publish` only |
| Account | found from the token (`/me`) | named by `IG_STUDIO_USER_ID` |

`ig_studio.py` handles both and works out which token it was given. Checked on
2026-11-17 with the real token:

- `check_only` identifies @grcsac_studio, and Meta confirms the token may publish
  (a read-only quota call).
- `dry_run` renders and hosts the next card.
- `probe` had Meta fetch and process all seven App Store clips and one card. All
  eight were accepted.
- `rehearse` took the ten posts added later that day (five screenshot cards, three
  carousels, one icon card, one generated Reel) as far as Meta accepting them.
  All ten were accepted. Containers left unpublished expire on their own.

**2026-11-18: the token stopped working.** `check_only` failed twice (16:27Z and
16:31Z) with `API access blocked. (code 200, subcode 5258005)` from
graph.facebook.com. The same token passed every check on 2026-11-17. Nothing in the
repo changed in between. A blocked check stops the run before anything is rendered
or posted, so a scheduled run fails safely. On 2026-11-19 the check was taught
to ask five read-only questions when refused: every one is refused, including
"who am I" and "which app", so the block is on the token, the app or the
portfolio, not on the Instagram account. **Cause, found 2026-11-19:** Meta locked
the developer account. developers.facebook.com shows "Account confirmation
needed. We've noticed unusual activity on this developer account", and the way
back is a Facebook checkpoint that emails a confirmation code to the account
owner. Only the owner can do that. While the account is locked every token of
its apps answers "API access blocked", and the Facebook sign-in screen's
Continue button does nothing. Until it is lifted the safety net above carries
the posts; afterwards run the workflow with `health_only` and expect
`health: ok`. **Lifted 2026-11-19 evening:** the owner completed the
confirmation, `health_only` answered `health: ok (@grcsac_studio may publish)`
with the same token (nothing was reissued), and the developer site's Required
actions page is empty. If "API access blocked" returns, look at
developers.facebook.com under the owner's Facebook login first. Posts scheduled in Business
Suite are not affected: the 18 Nov post went out and the other eight are in place.

**The one step never run is the final publish call**, because it posts at once. The
first scheduled API run is the first real one: 19:00 on Fri 2026-11-20.

**Generate token** opens a Facebook approval window (`facebook.com/.../dialog/oauth`)
in a new browser window. That window is the account owner's to complete: browser
automation cannot see it, and it may ask for the Facebook password.
In it, pick the portfolio and grcsac_studio, then Next, Confirm, Finish. The token
then appears once in a "Token generated" box on the developer page: tick "I
understand", press Copy, and paste it straight into the GitHub secret.

Signing in to Facebook in a browser hides the Instagram sign-in that Business
Suite was using there. The scheduled posts can still be reached; see "Changing or
cancelling a post scheduled in Business Suite". All nine were checked on
2026-11-17 and are intact.

### How the schedule runs

- The workflow is set to fire every hour, at seven minutes past. It has to be
  that often because **GitHub starts this repository's scheduled runs late**:
  between twenty minutes and seven hours late in every run since July 2026, and
  some never start. On 2026-11-20 the run meant for 11:07 started at 17:11.
- So a run does not post when it happens to start. `python ig_studio.py wait`
  looks for today's next free slot. If it is at most five hours away, the run
  sleeps until the slot's exact time and then carries on, so the post goes out
  at 11:00 or 19:00 New York time whatever GitHub's delay was. If another run
  is already waiting for that slot, or the slot is further off, the run does
  not wait. The wait happens in a job of its own that holds no lock, so a
  health check or a rehearsal started by hand in the meantime runs at once.
- `python ig_studio.py gate` decides whether a run posts. It looks for the
  earliest of today's two slots whose hour has come and which has no entry in
  `content/studio_schedule.json`. If there is one, and the date is not before
  `studio.api_start` in `config.json`, and something in the library is still
  waiting, the run posts. So the first run at or after a slot fills it, the
  later ones find it filled and stop, and a run that failed or never started is
  made up by the next one. A slot nobody filled on time is therefore filled
  late, by the first run that starts after it, up to midnight New York time. That same rule keeps the API off slots filled in
  Business Suite.
- A run posts one item: the first in `content/studio_instagram.json` whose id is
  not in the ledger, preferring an app that is not already posting that day and
  did not have the previous post. It then writes the post into the ledger and
  commits it.
- A failed run records nothing, the next run retries the same item, and GitHub
  emails the repository owner. If Meta refuses the same item three times for a
  reason of its own (not a refused token or a rate limit), the item is set
  aside in `content/state.json` and the run after posts the next one.
  `python ig_studio.py stock` lists anything set aside.
- Runs started by hand skip the gate. With no box ticked, **Run workflow posts
  the next item immediately** and takes that day's next free slot. Tick
  `check_only`, `dry_run`, `probe` or `health_only`, or fill in `rehearse`,
  unless that is what you want.
- `as_scheduled` makes a run started by hand behave exactly like a scheduled
  one: it waits for a slot up to five hours away and posts only into a slot
  that is due and free. It is the box to use if something other than GitHub's
  own clock is ever set up to start the workflow on time.

### What a library item can be

| The item has | It is posted as |
|---|---|
| `headline`, `sub` | one typographic card (add `"icons": ["findr", ...]` for a row of app icons) |
| `headline`, `shot` | one card with a real screenshot from `assets/shots/` in a phone frame |
| `slides: [...]` | a carousel, one image per slide; each slide is one of the two above |
| `video` | a Reel from `public/video/` |

Every item is posted once. (`"once": true` on older items is no longer read.)
The order in the file is the order of posting, apart from the rule that keeps
one app from posting twice running.

To add a clip: put the file in `public/video/` (1080x1920 MP4, under 20 MB so
jsDelivr serves it) and add the item to the library. To add a screenshot: put
it in `assets/shots/` (900 px wide JPEG) and name it in `shot`. Screenshots come
from the apps' own store listings; check each one for anything personal before
it goes into this public repo. Then push and run the workflow with the item's id
in the `rehearse` box: it renders, hosts and has Meta accept the item, and
publishes nothing.

`tools/make_meter_reel.py` renders the animated Sunk Cost meter Reel with Pillow
and ffmpeg. Run it on a laptop; the MP4 is committed, so the workflow never
renders video.

Meta fetches media the moment it is asked, and a file pushed seconds earlier may
not be on every CDN edge yet. Meta then answers error 2207052. `ig_studio.py`
waits 30 seconds and tries again, up to six times.

### To pause or stop

Actions -> Studio Instagram -> the `...` menu -> Disable workflow. Nothing else
needs to change, and enabling it again carries on with the next item that has not been posted.

### If the token ever has to be replaced

1. On the app's "API setup with Unified login" tab, click **Generate token** next
   to grcsac_studio, approve in the Facebook window, and store the token as the
   GitHub secret `IG_STUDIO_TOKEN` (never in the repo, never in chat). It does
   not expire, so treat it like a password.
2. Actions -> Studio Instagram -> Run workflow with `check_only`. It also lists
   the account's latest posts, which is the quickest way to see whether a post
   went out.

## Changing or cancelling a post scheduled in Business Suite

Getting in: with a Facebook account signed in to the same browser, Business Suite
shows "Unable to access Meta Business Suite with this account". Click **Log in
with Instagram** on that page. It opens Business Suite as @grcsac_studio in a new
tab. The developer site then shows "Go to WWW" in place of the app dashboard.
On 2026-11-18, the day after this was first done, facebook.com in the same browser
was at its sign-in screen, so expect to sign in to Facebook again before using the
developer dashboard. Whether the Instagram login caused that is not established.

Swapping the image of a scheduled post (done on 2026-11-17 for the 23 Nov Siftlet
card, whose platform line wrongly said "iPhone + Android"): the row's `...` menu
-> Manage post -> Edit post. Add the new image, delete the old one with its bin
icon, check the date and time are unchanged, then **Schedule**. A "Leave page?"
prompt can appear straight after; choose **Continue editing** and the page goes on
to "Scheduling your post". Do not click Schedule twice. Reopen the post to confirm.


Business Suite -> Content -> Posts & reels -> Scheduled -> the row's `...` menu ->
Reschedule, Edit or Delete. If you delete one, remove its row from the ledger too.
