"""Vigía de canales públicos de Telegram (CONCUPON, etc.).

Lee la vista pública https://t.me/s/<canal>, y te reenvía a tu bot cada publicación nueva
(todas, o solo las que tengan tus palabras clave). No necesita que tu bot esté en el canal.

CazaOfertas Perú · Elaborado por: HuachOfertas
"""
import html
import re

import requests

import config
import notifier

_POST = re.compile(r'<div class="tgme_widget_message [^"]*"[^>]*data-post="([^"/]+)/(\d+)"')
_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/131.0 Safari/537.36",
            "Accept-Language": "es-PE,es;q=0.9"}


def _texto(bloque):
    m = re.search(r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', bloque, re.S)
    if not m:
        return ""
    t = re.sub(r"<br\s*/?>", "\n", m.group(1))
    t = re.sub(r"<[^>]+>", "", t)
    t = html.unescape(t)
    t = re.sub(r"[ \t]+\n", "\n", t)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def _visible(fragmento):
    t = html.unescape(re.sub(r"<[^>]+>", "", fragmento))
    return bool(re.sub(r"[\s\u200b\u200c\u200d\u2060\ufeff]", "", t))


def leer_canal(usuario):
    """Devuelve las últimas publicaciones: [{id, texto, foto, enlace}] (de la más vieja a la más nueva)."""
    r = requests.get(f"https://t.me/s/{usuario}", headers=_HEADERS, timeout=20)
    r.raise_for_status()
    pagina = r.text
    marcas = list(_POST.finditer(pagina))
    posts = []
    for i, m in enumerate(marcas):
        fin = marcas[i + 1].start() if i + 1 < len(marcas) else len(pagina)
        b = pagina[m.start():fin]
        foto = re.search(r"tgme_widget_message_photo_wrap[^>]*background-image:url\('([^']+)'\)", b)
        cuerpo = re.search(r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', b, re.S)
        # Enlaces con texto visible (se ignora el enlace oculto que repiten en todos los posts)
        anclas = re.findall(r'<a [^>]*href="(https?://[^"]+)"[^>]*>(.*?)</a>', cuerpo.group(1), re.S) if cuerpo else []
        enlaces = [html.unescape(u) for u, txt in anclas
                   if _visible(txt) and "t.me/" not in u and "telegram." not in u]
        posts.append({"id": int(m.group(2)), "texto": _texto(b),
                      "foto": foto.group(1) if foto else None,
                      "enlace": enlaces[0] if enlaces else None})
    return posts


def _pasa_filtro(texto, palabras):
    if not palabras:
        return True
    t = texto.lower()
    return any(p.lower() in t for p in palabras)


def armar(canal, post):
    texto = post["texto"] or "(publicación con imagen)"
    cabecera = f"📢 <b>{html.escape(canal['name'])}</b>\n\n"
    limite = 1000 - len(cabecera)
    if len(texto) > limite:
        texto = texto[:limite - 1].rstrip() + "…"
    return cabecera + html.escape(texto)


def revisar(db):
    enviados = 0
    for canal in config.CHANNELS:
        usuario = canal["user"]
        clave = f"canal:{usuario}"
        try:
            posts = leer_canal(usuario)
        except Exception as e:  # noqa: BLE001
            print(f"  Canal {canal['name']}: error {e!r}")
            continue
        primera_vez = not db.feed_initialized(clave)
        nuevos = 0
        for p in posts:
            link_post = f"https://t.me/{usuario}/{p['id']}"
            if db.post_seen(link_post):
                continue
            db.mark_post(link_post, clave)
            if primera_vez:          # la 1ª vez solo memoriza, para no inundarte
                continue
            if not _pasa_filtro(p["texto"], canal.get("keywords") or []):
                continue
            botones = []
            if p["enlace"]:
                botones.append({"text": "🛒 Ver oferta", "url": p["enlace"]})
            botones.append({"text": "📢 Ver publicación", "url": link_post})
            notifier.send_rich(armar(canal, p), botones, photo_url=p["foto"])
            nuevos += 1
        enviados += nuevos
        estado = "memorizado (desde ahora te llegan los nuevos)" if primera_vez else f"{nuevos} nuevos"
        print(f"  Canal {canal['name']}: {estado}")
    return enviados
