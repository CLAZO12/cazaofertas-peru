"""Pone nombre, descripción y texto de presentación a tu bot de Telegram.
Usa el TELEGRAM_TOKEN de datos_telegram.txt.

CazaOfertas Perú · Elaborado por: HuachOfertas
"""
import json
import os
import re
import sys
import urllib.parse
import urllib.request

CARPETA = os.path.dirname(os.path.abspath(__file__))

NOMBRE = "CazaOfertas Perú"
DESCRIPCION = (
    "🛒 CazaOfertas Perú — Tu bot de ofertas y promociones 🇵🇪\n\n"
    "Vigilo Falabella, Ripley, Oechsle, Hiraoka, Plaza Vea y Promart y te aviso "
    "al instante cuando un precio baja fuerte o aparece un posible ERROR DE PRECIO.\n\n"
    "🔥 Ofertas reales comparadas con el historial\n"
    "🚨 Alertas de errores de precio\n"
    "🛒 Botón directo para comprar\n\n"
    "Toca INICIAR para recibir las alertas."
)
DESCRIPCION_CORTA = "Tu bot de ofertas y promociones en Perú 🇵🇪 Alertas de precios bajos y errores de precio."


def token():
    texto = open(os.path.join(CARPETA, "datos_telegram.txt"), encoding="utf-8-sig").read()
    m = re.search(r"^TELEGRAM_TOKEN=(.+)$", texto, re.M)
    return m.group(1).strip() if m else ""


def llamar(tk, metodo, datos):
    req = urllib.request.Request(f"https://api.telegram.org/bot{tk}/{metodo}",
                                 data=urllib.parse.urlencode(datos).encode())
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read()).get("ok", False)


def main():
    tk = token()
    if not tk:
        print("Falta tu TELEGRAM_TOKEN en datos_telegram.txt")
        return 1
    pasos = [
        ("Nombre", "setMyName", {"name": NOMBRE}),
        ("Descripción", "setMyDescription", {"description": DESCRIPCION}),
        ("Descripción corta", "setMyShortDescription", {"short_description": DESCRIPCION_CORTA}),
    ]
    for etiqueta, metodo, datos in pasos:
        try:
            print(f"{etiqueta}: {'OK' if llamar(tk, metodo, datos) else 'no se pudo'}")
        except Exception as e:  # noqa: BLE001
            print(f"{etiqueta}: error ({e})")
    print("\nListo. Para la foto: en @BotFather escribe /setuserpic, elige tu bot y envía logo_cazaofertas.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
