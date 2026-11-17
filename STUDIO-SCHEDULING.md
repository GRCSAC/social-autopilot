# Scheduling the GRCSAC Studio Instagram (Meta Business Suite)

How @grcsac_studio actually gets its posts, as of 2026-11-16.

## Why this route

| Route | Verdict |
|---|---|
| Buffer | Free plan is full (three channels). Not used for this account. |
| Meta's Instagram API (`ig_studio.py`, `studio.yml`) | Built and tested, but a Meta developer account can only be registered "while logged into your Facebook account", and there is no Facebook account. Parked: the workflow has no schedule. |
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

## Changing or cancelling a scheduled post

Business Suite -> Content -> Posts & reels -> Scheduled -> the row's `...` menu ->
Reschedule, Edit or Delete. If you delete one, remove its row from the ledger too.
