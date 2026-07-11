# Setup — DONE ✅ (system is live)

Everything is wired up, tested, and **posting for real**:

- ✅ **Workflow installed** — `.github/workflows/autopilot.yml` (weekly Sunday cron).
- ✅ **Repo public + image hosting live** — cards served free via jsDelivr; `PUBLIC_BASE_URL` set.
- ✅ **Buffer token added** — GitHub secret `BUFFER_TOKEN` is set.
- ✅ **First real run succeeded (2026-07-11)** — 3 LinkedIn + 3 Instagram posts queued to Buffer
  (Instagram cards rendered, hosted, and attached by URL). Verified in the Buffer queue.

From here it's hands-off: every Sunday it queues the next week of posts, and Buffer publishes
them on your Mon/Wed/Fri schedule. To change what it posts, edit `content/*.json` (see
[README.md](README.md)).

---

## ⚠️ One recurring maintenance item: the Buffer token expires

Buffer personal API keys are **short-lived** — the current one (`autopilot`) was created
**2026-07-11** and **expires 2026-08-10** (30 days). When it expires, the Sunday run will start
failing with an auth error and posting will silently stop.

**To rotate it (~2 min, ~monthly):**
1. buffer.com → Settings → API → Personal Keys → create a new key (or regenerate). Copy it.
2. GitHub repo → Settings → Secrets and variables → Actions → `BUFFER_TOKEN` → **Update**.

If Buffer offers a longer expiry when creating the key, use it to make this less frequent.

## Manual controls
- **Run now:** Actions → Social Autopilot → Run workflow (leave `dry_run` off).
- **Test without posting:** same, but tick `dry_run`.

### If a post is ever rejected
The run is idempotent — a failed post doesn't advance the rotation, so it retries next run.
The most likely cause is the free-plan queue cap (10/channel); it self-corrects as posts publish.
