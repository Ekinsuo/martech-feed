#!/usr/bin/env python3
"""
Tüm RSS/Atom kaynaklarını çeker ve signals.json üretir.
GitHub Actions günde bir çalıştırır; site açılışta bu dosyayı okur.
Hiçbir harici kütüphane gerektirmez — sadece Python standart kütüphanesi.
"""
import json, sys, re, datetime, urllib.request, xml.etree.ElementTree as ET

# --- index.html'deki FEEDS ile aynı kaynaklar ---
FEEDS = [
    {"cat": "bigquery",     "name": "BigQuery Release Notes",      "url": "https://cloud.google.com/feeds/bigquery-release-notes.xml"},
    {"cat": "looker",       "name": "Looker Release Notes",        "url": "https://cloud.google.com/feeds/looker-release-notes.xml"},
    {"cat": "lookerstudio", "name": "Looker Studio Release Notes", "url": "https://cloud.google.com/feeds/looker-studio-release-notes.xml"},
    {"cat": "general",      "name": "Simo Ahava",                  "url": "https://www.simoahava.com/index.xml"},
    {"cat": "general",      "name": "Analytics Mania",             "url": "https://www.analyticsmania.com/blog-feed.xml"},
    {"cat": "gads",         "name": "Google Ads Developer Blog",   "url": "https://ads-developers.googleblog.com/feeds/posts/default"},
    {"cat": "sgtm",         "name": "Tim Hutton",                  "url": "https://timhuttonco.medium.com/feed"},
    {"cat": "general",      "name": "ceaksan.com",                 "url": "https://ceaksan.com/tr/feed"},
    {"cat": "pantheon",     "name": "sGTM Pantheon (GitHub commits)", "url": "https://github.com/google-marketing-solutions/gps-sgtm-pantheon/commits/main.atom"},
    {"cat": "general",      "name": "MarTech.org",                 "url": "https://martech.org/feed/"},
    {"cat": "privacy",      "name": "WebKit Blog (ITP / Safari)",  "url": "https://webkit.org/feed/"},
    {"cat": "apple",        "name": "Apple Developer News",        "url": "https://developer.apple.com/news/rss/news.rss"},
]

ITEMS_PER_FEED = 8
TIMEOUT = 25
UA = "Mozilla/5.0 (compatible; MartechFeedBot/1.0; +https://github.com)"


def strip_html(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&#\d+;", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def to_iso_date(raw):
    if not raw:
        return datetime.date.today().isoformat()
    raw = raw.strip()
    # Atom: 2026-06-07T...
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", raw)
    if m:
        return m.group(0)
    # RSS RFC822: Sat, 07 Jun 2026 ...
    months = {m: i for i, m in enumerate(
        ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}
    m = re.search(r"(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})", raw)
    if m:
        d, mon, y = int(m.group(1)), months.get(m.group(2), 1), int(m.group(3))
        return f"{y:04d}-{mon:02d}-{d:02d}"
    return datetime.date.today().isoformat()


def localname(tag):
    return tag.split("}")[-1] if "}" in tag else tag


def find(el, name):
    for child in el:
        if localname(child.tag) == name:
            return child
    return None


def find_text(el, name):
    c = find(el, name)
    return (c.text or "").strip() if c is not None and c.text else ""


def parse_feed(xml_bytes, feed):
    out = []
    try:
        root = ET.fromstring(xml_bytes)
    except Exception as e:
        print(f"  ! parse error for {feed['name']}: {e}", file=sys.stderr)
        return out

    # Atom <entry> veya RSS <item>
    entries = []
    for el in root.iter():
        if localname(el.tag) in ("entry", "item"):
            entries.append(el)

    for i, e in enumerate(entries[:ITEMS_PER_FEED]):
        title = strip_html(find_text(e, "title"))
        if not title:
            continue

        # link
        link = ""
        for child in e:
            if localname(child.tag) == "link":
                href = child.attrib.get("href")
                if href:
                    link = href
                    break
                if child.text:
                    link = child.text.strip()
        if not link:
            link = find_text(e, "guid") or find_text(e, "id")

        # date
        raw_date = (find_text(e, "updated") or find_text(e, "pubDate")
                    or find_text(e, "published") or find_text(e, "date"))
        date = to_iso_date(raw_date)

        # summary
        summary = (find_text(e, "summary") or find_text(e, "description")
                   or find_text(e, "content"))
        summary = strip_html(summary)[:240] or "(no summary — open source)"

        out.append({
            "id": f"live-{feed['name']}-{i}",
            "cat": feed["cat"],
            "date": date,
            "title": title,
            "summary": summary,
            "src": feed["name"],
            "url": link or "#",
            "live": True,
        })
    return out


def main():
    all_signals = []
    ok_sources = 0
    fail_sources = 0
    seen_titles = set()

    for feed in FEEDS:
        try:
            req = urllib.request.Request(feed["url"], headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                data = resp.read()
            items = parse_feed(data, feed)
            if items:
                ok_sources += 1
                added = 0
                for it in items:
                    key = it["title"].lower()[:50]
                    if key in seen_titles:
                        continue
                    seen_titles.add(key)
                    all_signals.append(it)
                    added += 1
                print(f"  ✓ {feed['name']}: {added} items")
            else:
                fail_sources += 1
                print(f"  – {feed['name']}: 0 items")
        except Exception as e:
            fail_sources += 1
            print(f"  ✗ {feed['name']}: {e}", file=sys.stderr)

    # en yeni en üstte
    all_signals.sort(key=lambda s: s["date"], reverse=True)

    payload = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "ok_sources": ok_sources,
        "fail_sources": fail_sources,
        "count": len(all_signals),
        "signals": all_signals,
    }

    with open("signals.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"\nWrote signals.json — {len(all_signals)} signals from "
          f"{ok_sources} sources ({fail_sources} failed).")

    # Tüm kaynaklar başarısızsa Actions'ı kırma — eski signals.json kalsın
    if ok_sources == 0:
        print("WARNING: no sources succeeded; keeping previous signals.json if present.",
              file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()
