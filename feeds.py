"""Fuentes comunitarias por RSS (comcupon, perucomprasbaratas, etc.)."""
import feedparser
import config
import notifier


def check_feeds(db):
    for feed in config.FEEDS:
        name, url = feed["name"], feed["url"]
        try:
            parsed = feedparser.parse(url)
        except Exception as e:
            print(f"  feed {name}: error {e}")
            continue
        if parsed.bozo and not parsed.entries:
            print(f"  feed {name}: no se pudo leer {url}")
            continue

        first_time = not db.feed_initialized(name)  # evita inundarte en la 1ª corrida
        for e in parsed.entries:
            link = e.get("link")
            if not link or db.post_seen(link):
                continue
            db.mark_post(link, name)
            if first_time:
                continue
            title = e.get("title", "")
            if config.FEED_KEYWORDS and not any(
                    k.lower() in title.lower() for k in config.FEED_KEYWORDS):
                continue
            notifier.send(f"📰 <b>{notifier.esc(name)}</b>\n"
                          f"{notifier.esc(title)}\n{link}")
