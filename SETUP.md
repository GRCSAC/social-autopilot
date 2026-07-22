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

### When posts actually appear

The Sunday job only *queues* to Buffer. Buffer publishes on its own per-channel slots, which
are configured in Buffer and are not visible anywhere in this repo. Observed: the **Instagram
Wednesday slot is around 12:07 ET**. So an empty feed on a post morning is normal and is not
evidence of a failure. Check the Buffer queue before investigating anything.

A queued post shows in Buffer as *sent*, *failed*, or *awaiting a reminder* (that last one
means the channel cannot auto-publish and is waiting on a manual post). Those three states
tell you far more than the feed does.

### House style for new posts

Copy in `content/*.json` is written to read as Paul, not as a machine. When adding items, run
them through the [humanizer](https://github.com/blader/humanizer) rules. The one that matters
most in practice:

- **No em dashes (—), en dashes (–), or a spaced hyphen ( - ) used as one.** Use a period, a
  comma, or a colon. This is the most common tell and it was the only one present across the
  original 24 posts.
- Avoid negative parallelisms ("it's not X, it's Y"), forced groups of three, aphorism
  formulas, and generic upbeat sign-offs.
- Never add a biographical claim, statistic, or client story that isn't genuinely Paul's.
  These post under his name and carry his real history.
- Leave his established lines alone, even where they trip a rule. *"Compassion isn't the
  opposite of strength. It's what makes strength sustainable"* is his, and it stays.

Instagram `hook` and `quote` text is rendered onto the card image, so keep any rewrite the
same length or shorter.

Check before committing:

```bash
python -c "import json,re;print(sum(len(re.findall(r'[—–]| - ',json.dumps(json.load(open(f,encoding='utf-8'))))) for f in ['content/instagram.json','content/linkedin.json']))"
# must print 0
```

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
