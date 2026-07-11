# Setup — one time, ~15 minutes

After this, the system runs itself every week forever. There's a one-click
workflow install, two credentials to wire up (a Buffer token and an image-host
URL), plus a 2-minute test. You do these because they involve your accounts —
I never handle the token.

---

## 0. Install the schedule (30 seconds)

The automation file ships at **`setup/autopilot.yml`** because my access couldn't
push it into the workflows folder directly. Put it in place — do this from the
GitHub website, logged in as yourself:

1. Open **`setup/autopilot.yml`** in this repo and click **Raw** → select all → copy.
2. Click **Add file → Create new file**. Name it exactly **`.github/workflows/autopilot.yml`**.
3. Paste the contents → **Commit**.

That's the scheduler installed. (You can leave the copy in `setup/` or delete it.)

## 1. Buffer API token → GitHub secret

1. Go to **buffer.com → Settings → Developers** (or **[buffer.com/developers](https://buffer.com/developers)**) and create an app / API token. On the free plan you get one. Copy the token.
2. In this GitHub repo: **Settings → Secrets and variables → Actions → New repository secret**.
   - Name: `BUFFER_TOKEN`
   - Value: *(paste the token)*
3. Save. GitHub encrypts it; it's never visible again and never printed in logs.

## 2. Image hosting on Cloudflare Pages → GitHub variable

Instagram posts need each image at a public URL. Cloudflare Pages serves the
`public/` folder of this repo (you already use Cloudflare for grcsac.com).

1. **Cloudflare dashboard → Workers & Pages → Create → Pages → Connect to Git.**
2. Authorize Cloudflare's GitHub app for this repo and select it.
3. Build settings:
   - Framework preset: **None**
   - Build command: *(leave empty)*
   - **Build output directory: `public`**
4. Deploy. Note the URL it gives you, e.g. `https://social-autopilot-xyz.pages.dev`.
5. Back in GitHub: **Settings → Secrets and variables → Actions → Variables → New repository variable**.
   - Name: `PUBLIC_BASE_URL`
   - Value: *(the Pages URL, no trailing slash)* e.g. `https://social-autopilot-xyz.pages.dev`

Cloudflare now auto-redeploys every time the autopilot commits a new image.

## 3. Test it (no posts sent)

1. GitHub repo → **Actions → Social Autopilot → Run workflow.**
2. Tick **dry_run: true** → **Run workflow.**
3. Open the run. You should see it render 3 Instagram cards, and print the Buffer
   calls it *would* make for 6 posts (3 IG + 3 LinkedIn) — without sending them.

If that looks right, run it once more with **dry_run: false** to queue a real
week, or just wait for the Sunday schedule. Check Buffer — six posts appear in
the queues, and they publish on your Mon/Wed/Fri slots automatically.

---

## That's it

From here it's hands-off. Every Sunday it queues the next week from the content
library and rotates through it. To change anything, see **README.md** — but you
never have to touch it again if you don't want to.

### If something looks off
- **No Instagram image / image error:** confirm `PUBLIC_BASE_URL` is set and the Cloudflare Pages site is live (open `PUBLIC_BASE_URL/cards/` after a run).
- **Buffer rejects a post:** usually the free-plan cap of 10 queued per channel. It self-corrects as posts publish. Lower `posts_per_run` in `config.json` if needed.
- **Token issues:** re-create the Buffer token and update the `BUFFER_TOKEN` secret.
