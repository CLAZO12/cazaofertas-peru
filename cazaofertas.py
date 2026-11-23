#!/usr/bin/env python3
"""CazaOfertas Perú — ofertas y errores de precio.

Uso:
    python cazaofertas.py            # corre en bucle cada INTERVAL_MINUTES
    python cazaofertas.py --once     # una sola pasada
    python cazaofertas.py --test     # envía un mensaje de prueba a Telegram
    python cazaofertas.py --diagnostico [término]       # prueba todas las tiendas
    python cazaofertas.py --debug-falabella [término]   # diagnóstico detallado de Falabella

Elaborado por: HuachOfertas — © 2026 · Hecho en Huacho, Perú
"""
import argparse
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from typing import Optional

import config
import canales
import notifier
import tarjeta
from db import DB
from stores import build_stores, Product

BANNER = f"""
==============================================================
  CAZAOFERTAS PERU  v{config.VERSION}  ({config.FECHA})
  Elaborado por: HuachOfertas
  (c) 2026 · Hecho en Huacho, Peru
=============================================================="""


@dataclass
class Alert:
    product: Product
    reference: float
    basis: str
    discount: float

    @property
    def is_error(self):
        return self.discount >= config.ERROR_DISCOUNT


def evaluate(db: DB, p: Product) -> Optional[Alert]:
    """Decide si el precio actual es una oferta notable. Llamar ANTES de guardar el precio."""
    if p.price < config.MIN_PRICE:
        return None
    ref = db.median_price(p.store, p.sku, config.HISTORY_DAYS, config.MIN_HISTORY)
    if ref:
        basis, threshold = "mediana de tu historial", config.MIN_DISCOUNT
    elif p.list_price and p.list_price > p.price:
        ref, basis, threshold = p.list_price, "precio de lista de la tienda", config.MIN_DISCOUNT_VS_LIST
    else:
        return None
    discount = 1 - p.price / ref
    if discount >= threshold:
        return Alert(p, ref, basis, discount)
    return None


_EXCLUDE = [re.compile(rf"\b{re.escape(w.lower())}\b") for w in config.EXCLUDE_WORDS]


def passes_filters(p: Product, min_price: float) -> bool:
    if p.price < min_price:
        return False
    name = p.name.lower()
    return not any(rx.search(name) for rx in _EXCLUDE)


def format_alert(a: Alert) -> str:
    p = a.product
    title = "🚨 <b>POSIBLE ERROR DE PRECIO</b>" if a.is_error else "🔥 <b>SÚPER OFERTA</b>"
    return (f"{title} <b>-{a.discount:.0%}</b>\n"
            f"🏬 <b>{notifier.esc(p.store.upper())}</b>" + (f" · {notifier.esc(p.category)}" if p.category else "") + "\n"
            f"<b>{notifier.esc(p.name)}</b>\n"
            f"💰 Ahora: <b>S/ {p.price:,.2f}</b>\n"
            f"📉 Antes: <s>S/ {a.reference:,.2f}</s> <i>({a.basis})</i>\n"
            + (f"💳 <b>{notifier.esc(p.note)}</b>\n" if p.note else "")
            + ("⚡ Los errores se corrigen rápido: revisa ya.\n" if a.is_error else "")
            + "Tip: guarda capturas del precio y de tu confirmación de pedido.\n"
            "<i>CazaOfertas Perú · HuachOfertas</i>")


def collect(store):
    """Lee todas las búsquedas de UNA tienda (corre en su propio hilo)."""
    found = []
    for category, cat in config.CATEGORIES.items():
        if getattr(store, "categories", None) and category not in store.categories:
            continue
        for term in cat["terms"]:
            try:
                for p in store.fetch(term):
                    if passes_filters(p, cat.get("min_price", 0)):
                        p.category = category
                        found.append(p)
            except Exception as e:  # una tienda caída no debe frenar al resto
                print(f"  {store.name}/{term}: error {e!r}")
    return store, found


def run_once(db: DB, stores):
    pending, seen = [], set()
    workers = max(1, min(config.PARALLEL_STORES, len(stores)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for store, found in pool.map(collect, stores):
            count = 0
            for p in found:   # la base de datos se usa solo en el hilo principal
                key = (p.store, p.sku)
                if key in seen:
                    continue
                seen.add(key)
                count += 1
                alert = evaluate(db, p)
                db.record_price(p)
                if alert and not db.already_alerted(p.store, p.sku, p.price):
                    pending.append(alert)
            print(f"  {store.name}: {count} productos revisados")

    # Primero los posibles errores, luego los descuentos más grandes
    pending.sort(key=lambda a: (not a.is_error, -a.discount))
    sent = 0
    for a in pending[:config.MAX_ALERTS_PER_RUN]:
        sent += 1
        png = tarjeta.crear(a.product.store, a.discount, a.is_error)
        notifier.send_photo(png, format_alert(a), a.product.url)
        db.mark_alerted(a.product.store, a.product.sku, a.product.price)
        time.sleep(0.4)
    if len(pending) > config.MAX_ALERTS_PER_RUN:
        print(f"  ({len(pending) - config.MAX_ALERTS_PER_RUN} ofertas menores quedaron sin avisar)")
    print(f"  -> {min(len(pending), config.MAX_ALERTS_PER_RUN)} alertas enviadas")

    posts = canales.revisar(db) if config.CHANNELS else 0
    heartbeat(db, len(seen), len(stores), sent, posts)

    if config.FEEDS:
        from feeds import check_feeds
        check_feeds(db)


LIMA = timezone(timedelta(hours=-5))


def heartbeat(db: DB, products, n_stores, sent, posts):
    """Suma las estadísticas del día y, a partir de HEARTBEAT_HOUR, manda el resumen una vez."""
    now = datetime.now(LIMA)
    day = now.strftime("%Y-%m-%d")
    db.add_daily(day, products, n_stores, sent, posts)
    if config.HEARTBEAT_HOUR is None or now.hour < config.HEARTBEAT_HOUR:
        return
    runs, prods, stores, alerts, nposts, reported = db.daily(day)
    if reported:
        return
    canal = ""
    if config.CHANNELS:
        canal = f"📢 Posts nuevos de canales: <b>{nposts}</b>\n"
    texto = (f"✅ <b>CazaOfertas activo</b> · {now.strftime('%d/%m')}\n"
             f"Hoy hice <b>{runs}</b> revisiones de <b>{prods:,}</b> productos en {stores} tiendas.\n"
             f"🔥 Súper ofertas enviadas: <b>{alerts}</b>\n"
             + canal +
             "Sigo vigilando cada 5 minutos 👀\n"
             "<i>CazaOfertas Perú · HuachOfertas</i>")
    if notifier.send(texto):
        db.mark_reported(day)


def diagnostico(term):
    print(f"\nProbando cada tienda con '{term}' (1 página)...\n")
    config.PAGES_PER_QUERY = 1
    for store in build_stores():
        try:
            prods = list(store.fetch(term))
            print(f"{store.name:14s} {'OK' if prods else 'AVISO: 0 productos'}  {len(prods)}")
            for p in prods[:2]:
                antes = f" (antes S/ {p.list_price:,.2f})" if p.list_price else ""
                print(f"    - {p.name[:55]} | S/ {p.price:,.2f}{antes}")
        except Exception as e:
            print(f"{store.name:14s} ERROR {e!r}")
    print("\nSi alguna tienda sale con AVISO o ERROR, copia esta salida y pásamela.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--diagnostico", nargs="?", const="celular", metavar="TERMINO")
    ap.add_argument("--debug-falabella", nargs="?", const="televisor", metavar="TERMINO")
    args = ap.parse_args()
    print(BANNER)

    if args.debug_falabella:
        from stores import debug_falabella
        debug_falabella(args.debug_falabella)
        return
    if args.diagnostico:
        diagnostico(args.diagnostico)
        return
    if args.test:
        ok = notifier.send("✅ <b>CazaOfertas Perú conectado</b>\nAquí te llegarán las alertas.\n"
                           "Cada alerta trae su botón 🛒 Comprar ahora que abre el producto.")
        print("Mensaje enviado a Telegram." if ok else "Revisa TELEGRAM_TOKEN y TELEGRAM_CHAT_ID en datos_telegram.txt")
        return

    db = DB(config.DB_PATH)
    stores = build_stores()
    print(f"Tiendas activas: {[s.name for s in stores]}")
    while True:
        start = time.time()
        print(time.strftime("\n[%H:%M:%S] revisando..."))
        run_once(db, stores)
        if args.once:
            break
        wait = max(30, config.INTERVAL_MINUTES * 60 - (time.time() - start))
        time.sleep(wait)


if __name__ == "__main__":
    main()
