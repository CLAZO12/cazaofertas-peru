"""Obtiene tu TELEGRAM_CHAT_ID automáticamente y lo guarda en datos_telegram.txt.
Antes: pon tu TELEGRAM_TOKEN en datos_telegram.txt y escríbele /start a tu bot.

CazaOfertas Perú · Elaborado por: HuachOfertas
"""
import json
import os
import re
import sys
import urllib.request

CARPETA = os.path.dirname(os.path.abspath(__file__))
ARCHIVO = os.path.join(CARPETA, "datos_telegram.txt")


def main():
    texto = open(ARCHIVO, encoding="utf-8-sig").read()
    m = re.search(r"^TELEGRAM_TOKEN=(.+)$", texto, re.M)
    token = m.group(1).strip() if m else ""
    if not token:
        print("Primero pega tu TELEGRAM_TOKEN en datos_telegram.txt y guarda (Ctrl + S).")
        return 1
    try:
        with urllib.request.urlopen(f"https://api.telegram.org/bot{token}/getUpdates", timeout=20) as r:
            data = json.loads(r.read())
    except Exception as e:  # noqa: BLE001
        print("No se pudo conectar con Telegram. ¿El token está bien copiado?\n", e)
        return 1
    chats = [u.get("message", {}).get("chat") for u in data.get("result", [])]
    chats = [c for c in chats if c and c.get("type") == "private"]
    if not chats:
        print("No encontré mensajes. Abre tu bot en Telegram, escríbele /start y vuelve a ejecutar esto.")
        return 1
    chat = chats[-1]
    chat_id = str(chat["id"])
    nombre = chat.get("first_name", "")
    if re.search(r"^TELEGRAM_CHAT_ID=.*$", texto, re.M):
        texto = re.sub(r"^TELEGRAM_CHAT_ID=.*$", f"TELEGRAM_CHAT_ID={chat_id}", texto, flags=re.M)
    else:
        texto += f"\nTELEGRAM_CHAT_ID={chat_id}\n"
    with open(ARCHIVO, "w", encoding="utf-8") as f:
        f.write(texto)
    print(f"Listo, {nombre}: tu ID es {chat_id} y ya quedó guardado en datos_telegram.txt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
