# Consent, Then Conversions

A single-page dashboard that keeps you up to date on privacy-first digital
analytics — GA4, GTM, server-side tagging, Consent Mode, ITP/Safari privacy,
Apple Ads attribution, BigQuery, Looker Studio, and more.

Instead of you checking a dozen blogs and release-note pages every morning, the
site pulls the latest posts from all those sources into one clean, searchable
feed. It refreshes itself once a day, automatically.

## What's in this folder

```
index.html        the website itself — this is what people see
build_signals.py  a small script that goes out and collects the latest posts
signals.json      the collected posts, saved as a data file
.github/...yml     the schedule that re-runs the script every day
```

## How it works (the short version)

- A daily job (GitHub Actions) runs the script, which fetches the newest posts
  from every source and saves them into `signals.json`.
- When someone opens the site, it just reads that file — fast, and always shows
  the latest. If anything goes wrong, it still shows a built-in archive so the
  page is never empty.

You don't touch anything day to day. Set it up once, and it stays current on
its own.

## Good to know

- **It's free.** On a public repo, both the website hosting and the daily job
  cost nothing.
- **Adding or removing a source** means editing the source list in two places:
  `build_signals.py` and `index.html`. (Ask if you want a hand with this.)
- **If one source goes down**, the script just skips it and keeps the rest — the
  site keeps working.
