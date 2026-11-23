import html
import json
import requests
import config


def esc(text):
    return html.escape(str(text))


def send(text, buy_url=None):
    """Envía un mensaje HTML por Telegram, con botón '🛒 Comprar ahora' si hay enlace.
    Si no hay token, lo imprime en consola. Devuelve True si se envió."""
    if not config.TELEGRAM_TOKEN or not config.TELEGRAM_CHAT_ID:
        print("[sin Telegram configurado]\n" + text + (f"\n👉 {buy_url}" if buy_url else "") + "\n")
        return False
    payload = {"chat_id": config.TELEGRAM_CHAT_ID, "text": text,
               "parse_mode": "HTML", "disable_web_page_preview": False}
    if buy_url:
        payload["reply_markup"] = {"inline_keyboard": [[{"text": "🛒 Comprar ahora", "url": buy_url}]]}
    try:
        r = requests.post(f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage",
                          json=payload, timeout=15)
        if not r.ok:
            print("Error Telegram:", r.status_code, r.text[:200])
        return r.ok
    except requests.RequestException as e:
        print("Error enviando a Telegram:", e)
        return False


def send_photo(png, caption, buy_url=None):
    """Envía una imagen (bytes PNG) con texto y botón. Si falla, manda solo el texto."""
    if not png or not config.TELEGRAM_TOKEN or not config.TELEGRAM_CHAT_ID:
        return send(caption, buy_url)
    data = {"chat_id": config.TELEGRAM_CHAT_ID, "caption": caption[:1024], "parse_mode": "HTML"}
    if buy_url:
        data["reply_markup"] = json.dumps(
            {"inline_keyboard": [[{"text": "🛒 Comprar ahora", "url": buy_url}]]})
    try:
        r = requests.post(f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendPhoto",
                          data=data, files={"photo": ("oferta.png", png, "image/png")}, timeout=20)
        if r.ok:
            return True
        print("Error Telegram (foto):", r.status_code, r.text[:200])
    except requests.RequestException as e:
        print("Error enviando foto a Telegram:", e)
    return send(caption, buy_url)
