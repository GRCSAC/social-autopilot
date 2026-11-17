# Scheduling the GRCSAC Studio Instagram (Meta Business Suite)

How @grcsac_studio actually gets its posts, as of 2026-11-16.

## Why this route

| Route | Verdict |
|---|---|
| Buffer | Free plan is full (three channels). Not used for this account. |
| Meta's Instagram API (`ig_studio.py`, `studio.yml`) | Built and tested. Blocked until 2026-11-17 because a Meta developer account needs a Facebook account; one now exists and the Meta app is set up (see "The API route" below). Still parked until a token is in place and `check_only` passes: the workflow has no schedule. |
| Instagram's own web composer | Uploads fine, but offers only Share now. No schedule control. |
| **Meta Business Suite** (business.facebook.com) | **Works.** "Continue with Instagram" signs in with the studio account, no Facebook needed. Its composer has "Set date and time". This is the route. |

So posts are scheduled in Meta's own tool, in a browser signed in as
@grcsac_studio, a few weeks at a time. Meta publishes them at the set time; this
repo only decides which card goes on which date and keeps the ledger.

## The moving parts

- `content/studio_instagram.json` — the 33 cards (see README).
- `studio_queue.py` — `status`, `plan --weeks N` (renders the next cards into
  `preview/queue/` and prints each one's date, caption and file), `done ID DATE`
  (records it and advances the cursor).
- `content/studio_schedule.json` — the ledger: every post scheduled, and
  `next_cursor`. `content/state.json` `studio_instagram` mirrors the cursor.
- Slots: **Mon/Wed/Fri 11:00 America/New_York**, three weeks ahead at most, so a
  card's status line ("Coming soon", a price) is never queued long before it runs.

## Topping up (about every two weeks)

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

## The API route (set up 2026-11-17, not switched on yet)

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
- The repository variable `IG_STUDIO_USER_ID`, holding the account's Instagram ID.

Meta now calls this "API setup with Unified login" and says the older "API setup
with Instagram login" is not available for newer apps. The difference matters:

| | Instagram login (old) | Unified login (this app) |
|---|---|---|
| Host | `graph.instagram.com` | `graph.facebook.com` |
| Token | 60 days, refreshed every run | system-user token, does not expire |
| Permissions | `instagram_business_*` | `instagram_basic`, `instagram_content_publish` (the template also asks for comments, messages and ads) |
| Account | found from the token (`/me`) | named by `IG_STUDIO_USER_ID` |

`ig_studio.py` handles both and works out which token it was given. The
Unified-login path has been tested only as far as Meta rejecting a made-up token;
it is **not verified** against a real one until the first `check_only` run.

**Generate token** opens a Facebook approval window (`facebook.com/.../dialog/oauth`)
in a new browser window. That window is the account owner's to complete: browser
automation cannot see it, and it may ask for the Facebook password.

To switch on:

1. On the app's "API setup with Unified login" tab, click **Generate token** next
   to grcsac_studio, approve in the Facebook window, and store the token as the
   GitHub secret `IG_STUDIO_TOKEN` (never in the repo, never in chat). The token
   does not expire, so treat it like a password.
2. Actions -> Studio Instagram -> Run workflow with `check_only`. It prints the
   account, the token's permissions and its expiry, and never any part of the
   token. Fix `ig_studio.py` if the check fails, then run once with `dry_run`.
3. Let the posts already scheduled in Business Suite run out, then put the cron
   back in `studio.yml` and stop the Business Suite top-ups. Never run both for the
   same dates: the ledger in `content/studio_schedule.json` is the single cursor.

## Changing or cancelling a scheduled post

Business Suite -> Content -> Posts & reels -> Scheduled -> the row's `...` menu ->
Reschedule, Edit or Delete. If you delete one, remove its row from the ledger too.
