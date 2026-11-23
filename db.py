import sqlite3
import statistics
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS prices(
    store TEXT, sku TEXT, name TEXT, price REAL, list_price REAL, url TEXT, ts INTEGER);
CREATE INDEX IF NOT EXISTS idx_prices ON prices(store, sku, ts);
CREATE TABLE IF NOT EXISTS alerts(
    store TEXT, sku TEXT, price REAL, ts INTEGER, PRIMARY KEY(store, sku, price));
CREATE TABLE IF NOT EXISTS seen_posts(
    link TEXT PRIMARY KEY, feed TEXT, ts INTEGER);
"""

REFRESH_SECONDS = 6 * 3600  # guarda una observación aunque no cambie el precio


class DB:
    def __init__(self, path):
        self.conn = sqlite3.connect(path)
        self.conn.executescript(SCHEMA)

    def history(self, store, sku, days):
        since = int(time.time()) - days * 86400
        rows = self.conn.execute(
            "SELECT price FROM prices WHERE store=? AND sku=? AND ts>=?",
            (store, sku, since)).fetchall()
        return [r[0] for r in rows]

    def median_price(self, store, sku, days, min_obs):
        h = self.history(store, sku, days)
        return statistics.median(h) if len(h) >= min_obs else None

    def record_price(self, p):
        last = self.conn.execute(
            "SELECT price, ts FROM prices WHERE store=? AND sku=? ORDER BY ts DESC LIMIT 1",
            (p.store, p.sku)).fetchone()
        now = int(time.time())
        if last and last[0] == p.price and now - last[1] < REFRESH_SECONDS:
            return
        self.conn.execute(
            "INSERT INTO prices VALUES(?,?,?,?,?,?,?)",
            (p.store, p.sku, p.name, p.price, p.list_price, p.url, now))
        self.conn.commit()

    def already_alerted(self, store, sku, price):
        return self.conn.execute(
            "SELECT 1 FROM alerts WHERE store=? AND sku=? AND price=?",
            (store, sku, price)).fetchone() is not None

    def mark_alerted(self, store, sku, price):
        self.conn.execute("INSERT OR IGNORE INTO alerts VALUES(?,?,?,?)",
                          (store, sku, price, int(time.time())))
        self.conn.commit()

    def feed_initialized(self, feed):
        return self.conn.execute(
            "SELECT 1 FROM seen_posts WHERE feed=? LIMIT 1", (feed,)).fetchone() is not None

    def post_seen(self, link):
        return self.conn.execute(
            "SELECT 1 FROM seen_posts WHERE link=?", (link,)).fetchone() is not None

    def mark_post(self, link, feed):
        self.conn.execute("INSERT OR IGNORE INTO seen_posts VALUES(?,?,?)",
                          (link, feed, int(time.time())))
        self.conn.commit()
