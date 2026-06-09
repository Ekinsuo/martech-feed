#!/usr/bin/env python3
"""
Tüm RSS/Atom kaynaklarını çeker ve signals.json üretir.
GitHub Actions günde bir çalıştırır; site açılışta bu dosyayı okur.
Hiçbir harici kütüphane gerektirmez — sadece Python standart kütüphanesi.
"""
import json, sys, re, datetime, urllib.request, xml.etree.ElementTree as ET

# --- index.html'deki FEEDS ile aynı kaynaklar ---
FEEDS = [
    # --- Google Cloud release notes (official XML feeds) ---
    {"cat": "general",      "name": "Google Cloud — All release notes", "url": "https://cloud.google.com/feeds/gcp-release-notes.xml",
     "limit": 12, "keywords": ["analytic", "bigquery", "looker", "dataform", "consent", "tag", "ga4", "advertis", "marketing", "privacy", "measurement", "attribution"]},
    {"cat": "bigquery",     "name": "BigQuery Release Notes",      "url": "https://cloud.google.com/feeds/bigquery-release-notes.xml"},
    {"cat": "bigquery",     "name": "BigQuery ML Revision History","url": "https://cloud.google.com/feeds/bigquery-ml-revision-history.xml"},
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
    {"cat": "privacy",      "name": "EDPB — GDPR news",            "url": "https://edpb.europa.eu/feed/news_en"},
]

# --- HTML scraping ile çekilen kaynaklar (RSS'i olmayan release-note sayfaları) ---
# Bunlar JS yardım sayfaları; ana metin yine de HTML'de bulunuyor. Tarih + paragraf
# bloklarını ayıklarız. Kırılgan olabilir; başarısız olursa sessizce atlanır.
SCRAPE = [
    {"cat": "gtm",  "name": "GTM / Tag Gateway — Release notes",
     "url": "https://support.google.com/tagmanager/answer/4620708?hl=en"},
    {"cat": "ga4",  "name": "GA4 — What's new",
     "url": "https://support.google.com/analytics/answer/9164320?hl=en"},
    {"cat": "sgtm", "name": "sGTM — Release notes",
     "url": "https://developers.google.com/tag-platform/tag-manager/server-side/release-notes"},
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
    # "June 3, 2026" / "January 29, 2026"
    full = {"january":1,"february":2,"march":3,"april":4,"may":5,"june":6,
            "july":7,"august":8,"september":9,"october":10,"november":11,"december":12}
    m = re.search(r"([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})", raw)
    if m and m.group(1).lower() in full:
        mon, d, y = full[m.group(1).lower()], int(m.group(2)), int(m.group(3))
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

    limit = feed.get("limit", ITEMS_PER_FEED)
    keywords = feed.get("keywords")  # verilirse, sadece bu kelimeleri içeren maddeler

    taken = 0
    for i, e in enumerate(entries):
        if taken >= limit:
            break
        title = strip_html(find_text(e, "title"))
        if not title:
            continue

        # summary (filtre ve çıktı için lazım)
        summary = (find_text(e, "summary") or find_text(e, "description")
                   or find_text(e, "content"))
        summary = strip_html(summary)

        # anahtar kelime filtresi (birleşik GCP feed'i için)
        if keywords:
            hay = (title + " " + summary).lower()
            if not any(k in hay for k in keywords):
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

        summary = summary[:240] or "(no summary — open source)"

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
        taken += 1
    return out


MONTHS_RE = (r"(January|February|March|April|May|June|July|August|September|"
             r"October|November|December)\s+\d{1,2},?\s+\d{4}")


def scrape_release_page(html, src):
    """RSS'i olmayan Google yardım/release sayfalarından tarih başlıklı blokları ayıklar.
    Strateji: HTML etiketlerini temizle, 'Month DD, YYYY' başlıklarına göre böl,
    her bloğun ilk cümlelerini özet yap. Bulamazsa boş döner (site bozulmaz)."""
    import html as _html
    out = []
    # script/style at, etiketleri boşlukla değiştir
    text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = _html.unescape(text)
    text = re.sub(r"#{1,6}\s*", " ", text)   # markdown başlık işaretlerini at
    text = re.sub(r"\s+", " ", text).strip()

    # tarih başlıklarının konumlarını bul
    matches = list(re.finditer(MONTHS_RE, text))
    seen = set()
    # sadece son ~150 günün release-note'larını al (eskiler gürültü)
    cutoff = (datetime.date.today() - datetime.timedelta(days=150)).isoformat()
    for idx, m in enumerate(matches):
        if len(out) >= 8:
            break
        date_str = m.group(0)
        start = m.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else min(len(text), start + 600)
        body = text[start:end].strip(" .-—:")
        # gürültü ifadelerinden önce kes (navigasyon/footer metni)
        for noise in ["Was this helpful", "Send feedback", "Help Center", "Need more help", "Skip to main"]:
            p = body.find(noise)
            if p > 0:
                body = body[:p].strip(" .-—:")
        if len(body) < 25:
            continue
        date = to_iso_date(date_str)
        if date < cutoff:          # çok eski → atla
            continue
        if date in seen:           # aynı güne ikinci blok → atla
            continue
        seen.add(date)
        # Başlık: ilk cümle, ama feature başlığı + açıklama bitişikse kısa tut.
        # Önce cümleye böl; ilk cümle hâlâ uzunsa ~9 kelime / 60 karakterle kırp.
        parts = re.split(r"(?<=[.!?])\s+", body, 1)
        first_sentence = parts[0].strip(" .-—:")
        words = first_sentence.split()
        if len(words) > 11:
            head = " ".join(words[:9]).rstrip(" .,-—:") + "…"
            # başlığa girmeyen kelimeler + sonraki cümle özete gider
            leftover = " ".join(words[9:])
            rest = (leftover + " " + (parts[1] if len(parts) > 1 else "")).strip()
        else:
            head = first_sentence
            rest = parts[1].strip() if len(parts) > 1 else ""
        if len(head) > 80:
            head = head[:80].rsplit(" ", 1)[0] + "…"
        summary = (rest[:240] if rest else body[:240]) or "(see source)"
        out.append({
            "id": f"scrape-{src['name']}-{idx}",
            "cat": src["cat"],
            "date": date,
            "title": head,
            "summary": summary,
            "src": src["name"],
            "url": src["url"],
            "live": True,
        })
    return out


def main():
    all_signals = []
    ok_sources = 0
    fail_sources = 0
    seen_titles = set()
    source_status = []   # her kaynağın tek tek durumu

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
                source_status.append({"name": feed["name"], "cat": feed["cat"],
                                      "ok": True, "items": added})
            else:
                fail_sources += 1
                print(f"  – {feed['name']}: 0 items")
                source_status.append({"name": feed["name"], "cat": feed["cat"],
                                      "ok": False, "items": 0, "error": "no items"})
        except Exception as e:
            fail_sources += 1
            print(f"  ✗ {feed['name']}: {e}", file=sys.stderr)
            source_status.append({"name": feed["name"], "cat": feed["cat"],
                                  "ok": False, "items": 0, "error": str(e)[:80]})

    # --- HTML scraping kaynakları (RSS'i olmayan release-note sayfaları) ---
    for src in SCRAPE:
        try:
            req = urllib.request.Request(src["url"], headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                html = resp.read().decode("utf-8", "ignore")
            items = scrape_release_page(html, src)
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
                print(f"  ✓ {src['name']} (scrape): {added} items")
                source_status.append({"name": src["name"], "cat": src["cat"],
                                      "ok": True, "items": added, "scraped": True})
            else:
                fail_sources += 1
                print(f"  – {src['name']} (scrape): 0 items")
                source_status.append({"name": src["name"], "cat": src["cat"],
                                      "ok": False, "items": 0, "scraped": True, "error": "no datable items"})
        except Exception as e:
            fail_sources += 1
            print(f"  ✗ {src['name']} (scrape): {e}", file=sys.stderr)
            source_status.append({"name": src["name"], "cat": src["cat"],
                                  "ok": False, "items": 0, "scraped": True, "error": str(e)[:80]})

    # en yeni en üstte
    all_signals.sort(key=lambda s: s["date"], reverse=True)

    payload = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "ok_sources": ok_sources,
        "fail_sources": fail_sources,
        "count": len(all_signals),
        "sources": source_status,
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
