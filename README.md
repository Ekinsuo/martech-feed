# Consent, Then Conversions — daily automated feed

This folder contains 4 files:

```
index.html                              ← the site (Pages serves this as the home page)
build_signals.py                        ← script that fetches the RSS feeds and builds signals.json
signals.json                            ← the fetched data (Actions refreshes it daily)
.github/workflows/daily-signals.yml     ← the automation that runs once a day
```

On load, the site reads `signals.json` first (fast, no proxy). If that file isn't
there, it falls back to the old browser-proxy method, and worst case it shows the
built-in archive.

---

## Setup (one-time, ~5 minutes)

> You do **not** need a new repo. Use the same repo that already has `index.html`.
> Just replace `index.html` and add the other 3 files.

### 1. Add the files to your repo
1. Open your repo on github.com.
2. **Add file → Upload files** → drag in `index.html` (overwrite the old one when
   asked), `build_signals.py`, and `signals.json`.
3. The `.github` folder won't drag-drop easily, so add it manually:
   **Add file → Create new file**, and type this as the file name (the slashes
   create the folders automatically):
   `.github/workflows/daily-signals.yml`
   Then paste the contents of `daily-signals.yml` into it.
4. **Commit changes**.

### 2. Enable GitHub Pages (skip if already on)
1. In the repo: **Settings → Pages**.
2. **Source: Deploy from a branch**, **Branch: main**, folder **/ (root)** → **Save**.
3. After 1–2 minutes the site is live at:
   `https://YOURUSERNAME.github.io/your-repo/`

### 3. Turn on the automation
1. In the repo: **Settings → Actions → General**.
2. At the bottom, **Workflow permissions** → choose **Read and write permissions**
   → **Save**. (Required so Actions can write `signals.json` back to the repo.)
3. Go to the **Actions** tab → pick **Build daily signals** on the left → click
   **Run workflow** to trigger the first fetch manually.
4. After ~1 minute `signals.json` is updated. Refresh the site — the top should
   read "Daily feed · N sources".

From then on it runs automatically every day at 06:00 UTC (~09:00 Turkey time).
You don't have to do anything.

---

## FAQ

**Change the time.** Edit the `cron: "0 6 * * *"` line in `daily-signals.yml`.
Use `crontab.guru` to build the schedule. For twice a day, add a second line:
`cron: "0 6 * * *"` and `cron: "0 18 * * *"`.

**Add/remove a source.** Keep the same list in two places:
`FEEDS` in `build_signals.py` and `const FEEDS` in `index.html`. Add/remove the
same `{cat, name, url}` entry in both.

**If a source returns 403/errors.** The script skips that source, fetches the
rest, and the site keeps working. If every source fails, the previous
`signals.json` is preserved (no empty file is written).

**Test locally.** Run `python build_signals.py` to generate `signals.json`, then
serve the folder with `python -m http.server` and open `localhost:8000`
(opening the file directly via `file://` may block `signals.json` from loading).

**Cost.** On a public repo, GitHub Pages and Actions are free. A once-a-day job
stays far under the monthly minutes quota.
