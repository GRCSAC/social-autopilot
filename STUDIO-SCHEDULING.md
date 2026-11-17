# Scheduling the GRCSAC Studio Instagram

How @grcsac_studio gets its posts.

- **18 Nov to 7 Dec 2026:** nine posts scheduled by hand in Meta Business Suite on
  2026-11-16. Meta publishes them; nothing in this repo has to run.
- **From 9 Dec 2026:** `.github/workflows/studio.yml` posts through Meta's API,
  Mon/Wed/Fri at 11:00 Eastern, with no browser involved. See "The API route".

## Why this route

| Route | Verdict |
|---|---|
| Buffer | Free plan is full (three channels). Not used for this account. |
| Meta's Instagram API (`ig_studio.py`, `studio.yml`) | **The route from 2026-12-09.** It was blocked until 2026-11-17 because a Meta developer account needs a Facebook account; one now exists. Token checked, all media accepted by Meta in a rehearsal. |
| Instagram's own web composer | Uploads fine, but offers only Share now. No schedule control. |
| Meta Business Suite (business.facebook.com) | Works, and carried the first nine posts. "Continue with Instagram" signs in with the studio account, no Facebook needed. Its composer has "Set date and time". Retired once those nine have run: it needs a browser, and signing in to Facebook in the same browser locks it out. |

The first nine posts were scheduled in Meta's own tool, in a browser signed in as
@grcsac_studio. Everything after them is published by the workflow. Either way
this repo decides which post goes on which date and keeps the ledger.

## The moving parts

- `content/studio_instagram.json` — the 33 cards (see README).
- `studio_queue.py` — `status`, `plan --weeks N` (renders the next cards into
  `preview/queue/` and prints each one's date, caption and file), `done ID DATE`
  (records it and advances the cursor).
- `content/studio_schedule.json` — the ledger: every post scheduled, and
  `next_cursor`. `content/state.json` `studio_instagram` mirrors the cursor.
- Slots: **Mon/Wed/Fri 11:00 America/New_York**, three weeks ahead at most, so a
  card's status line ("Coming soon", a price) is never queued long before it runs.

## Topping up in Business Suite (retired 2026-11-17)

Kept for reference only. The Monday routine that did this is paused and must stay
paused while the API schedule is on, or posts will double. Video items in the
library cannot be scheduled this way.

1. `git pull`, then `python studio_queue.py plan --weeks 3`. No output rows means
   the queue is already full.
2. For each row, **check the card is still true**: its `status_on_card` against the
   tile on www.grcsac.com, and any price in the caption against the app's site. If
   something changed, fix the card in the JSON first and re-run `plan`.
3. Open `https://business.facebook.com/latest/composer/` signed in as
   @grcsac_studio (Home -> Create post). For each row: add the image, paste the
   caption, turn on **Set date and time**, set the date and 11:00 AM, **Schedule**.
4. Confirm it under Content -> Posts & reels -> **Scheduled** (one row per date),
   then `python studio_queue.py done <id> <YYYY-MM-DD>`.
5. Commit `content/studio_schedule.json` and `content/state.json`, push.

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

## The API route (switched on 2026-11-17, first post 2026-12-09)

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

**The one step never run is the final publish call**, because it posts at once. The
first scheduled run on 2026-12-09 is the first real one.

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

- The workflow fires Mon/Wed/Fri at 15:00 and 16:00 UTC. One of the two is 11:00
  in New York (16:00 UTC in winter, 15:00 UTC in summer). GitHub may start a
  scheduled run late, sometimes by half an hour or more.
- `python ig_studio.py gate` decides whether a run posts. It says no before
  `studio.api_start` in `config.json` (2026-12-09), on any day but Mon/Wed/Fri,
  before 11:00 New York, and on any date that already has a post in
  `content/studio_schedule.json`. That last rule is what keeps the API off the
  Business Suite dates and stops a second post on one day.
- A run posts the next item in `content/studio_instagram.json`, then writes the
  cursor to `content/state.json` and the post to the ledger, and commits both.
- A failed run does not advance the cursor. The next slot retries the same item,
  and GitHub emails the repository owner about the failed run.
- Runs started by hand skip the gate. With no box ticked, **Run workflow posts
  the next item immediately.** Tick `check_only`, `dry_run` or `probe`, or fill in
  `rehearse`, unless that is what you want.

### What a library item can be

| The item has | It is posted as |
|---|---|
| `headline`, `sub` | one typographic card (add `"icons": ["findr", ...]` for a row of app icons) |
| `headline`, `shot` | one card with a real screenshot from `assets/shots/` in a phone frame |
| `slides: [...]` | a carousel, one image per slide; each slide is one of the two above |
| `video` | a Reel from `public/video/` |

`"once": true` posts an item a single time and skips it when the library comes
round again. The seven App Store clips added on 2026-11-17 are all `once`,
because a clip that says "Updated November 9, 2026" does not age well.

The queue from the cursor onward is laid out by hand so that no week shows the
same app twice and the dated clips go early: a clip, a new post, a card. The
last App Store clip runs on 2027-01-11.

To add a clip: put the file in `public/video/` (1080x1920 MP4, under 20 MB so
jsDelivr serves it) and add the item after the cursor. To add a screenshot: put
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
needs to change, and enabling it again resumes from the same cursor.

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
tab and does not sign Facebook out; the developer site then offers "Go to WWW" to
switch back to the Facebook account.

Swapping the image of a scheduled post (done on 2026-11-17 for the 23 Nov Siftlet
card, whose platform line wrongly said "iPhone + Android"): the row's `...` menu
-> Manage post -> Edit post. Add the new image, delete the old one with its bin
icon, check the date and time are unchanged, then **Schedule**. A "Leave page?"
prompt can appear straight after; choose **Continue editing** and the page goes on
to "Scheduling your post". Do not click Schedule twice. Reopen the post to confirm.


Business Suite -> Content -> Posts & reels -> Scheduled -> the row's `...` menu ->
Reschedule, Edit or Delete. If you delete one, remove its row from the ledger too.
