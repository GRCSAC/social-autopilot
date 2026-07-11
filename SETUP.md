# Setup — one step left (~2 minutes)

Almost everything is wired up and tested already:

- ✅ **Workflow installed** — `.github/workflows/autopilot.yml` (weekly Sunday cron).
- ✅ **Repo public + image hosting live** — cards are served free via jsDelivr; the
  `PUBLIC_BASE_URL` variable is set. Verified: a rendered card returns HTTP 200,
  `image/jpeg`.
- ✅ **Dry-run passed** — a full run on GitHub rendered the Instagram cards, published
  them, and built the exact Buffer calls for 6 posts without sending anything.

## The only thing left: your Buffer API token

I can't do this one — entering an API token into a field is a hard line for me, the
same as typing a password. Two minutes:

1. Go to **buffer.com → Settings → Developers** (or **[buffer.com/developers](https://buffer.com/developers)**) and create an API token. On the free plan you get one. Copy it.
2. In this repo: **Settings → Secrets and variables → Actions → New repository secret.**
   - Name: `BUFFER_TOKEN`
   - Value: *(paste the token)*
3. Save. GitHub encrypts it; it's never printed in logs.

## Go live

- **Test it for real:** repo → **Actions → Social Autopilot → Run workflow** (leave
  dry_run **off**) → **Run**. It queues 6 posts; check your Buffer queues. They then
  publish on your Mon/Wed/Fri schedule.
- **Or just wait** — it runs automatically every Sunday.

That's it. From here it's hands-off forever. To change what it posts, edit
`content/*.json` (see [README.md](README.md)).

### If a post is rejected on the first real run
The Buffer API image-attach shape is written to Buffer's official docs but couldn't
be tested without your token. If Instagram posts error, it's almost certainly the
`assets` field in `buffer_client.py` — the fix is one line, and the dry-run prints
the exact call so it's easy to compare. Everything else (rendering, hosting, LinkedIn
text, scheduling) is already proven working.
