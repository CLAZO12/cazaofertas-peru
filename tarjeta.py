"""Tarjeta de imagen para cada alerta: nombre de la tienda en su color + % de descuento.

CazaOfertas Perú · Elaborado por: HuachOfertas
"""
import io
import os

# Color de fondo y texto que se muestra por tienda
ESTILOS = {
    "Falabella": ("#AAD500", "#1E1E1E", "FALABELLA"),
    "Ripley":    ("#58216D", "#FFFFFF", "RIPLEY"),
    "Oechsle":   ("#E4002B", "#FFFFFF", "OECHSLE"),
    "Hiraoka":   ("#0057A8", "#FFFFFF", "HIRAOKA"),
    "Plaza Vea": ("#E30613", "#FFFFFF", "PLAZA VEA"),
    "Promart":   ("#F37021", "#FFFFFF", "PROMART"),
    "Nike":      ("#111111", "#FFFFFF", "NIKE"),
    "Bata":      ("#D7182A", "#FFFFFF", "BATA"),
    "Puma":      ("#000000", "#FFFFFF", "PUMA"),
    "Claro":     ("#DA291C", "#FFFFFF", "CLARO"),
    "Metro":     ("#FFD100", "#1E1E1E", "METRO"),
    "Wong":      ("#C8102E", "#FFFFFF", "WONG"),
    "Sodimac":   ("#F15A22", "#FFFFFF", "SODIMAC"),
    "Mercado Libre": ("#FFE600", "#2D3277", "MERCADO LIBRE"),
}

_FUENTES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",       # Linux / GitHub
    "C:/Windows/Fonts/arialbd.ttf",                               # Windows
    "C:/Windows/Fonts/segoeuib.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",          # Mac
]


def _fuente(tam):
    from PIL import ImageFont
    for ruta in _FUENTES:
        if os.path.exists(ruta):
            return ImageFont.truetype(ruta, tam)
    try:
        return ImageFont.load_default(size=tam)
    except TypeError:
        return ImageFont.load_default()


def _ajustar(draw, texto, ancho_max, tam):
    while tam > 20:
        f = _fuente(tam)
        if draw.textlength(texto, font=f) <= ancho_max:
            return f
        tam -= 4
    return _fuente(tam)


def crear(tienda, descuento, es_error):
    """Devuelve PNG (bytes) o None si Pillow no está instalado."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None
    fondo, color, nombre = ESTILOS.get(tienda, ("#333333", "#FFFFFF", tienda.upper()))
    W, H = 900, 300
    img = Image.new("RGB", (W, H), fondo)
    d = ImageDraw.Draw(img)

    # Porcentaje (derecha) y nombre de la tienda en el espacio que queda (izquierda)
    pct = f"-{descuento:.0%}"
    f_pct = _fuente(110)
    ancho_pct = d.textlength(pct, font=f_pct)
    d.text((W - 48, H // 2 - 18), pct, font=f_pct, fill=color, anchor="rm")
    f_nombre = _ajustar(d, nombre, W - 96 - ancho_pct - 50, 96)
    d.text((48, H // 2 - 18), nombre, font=f_nombre, fill=color, anchor="lm")

    # Franja inferior
    franja = "POSIBLE ERROR DE PRECIO" if es_error else "SÚPER OFERTA"
    d.rectangle([0, H - 70, W, H], fill="#B00020" if es_error else "#111111")
    d.text((W // 2, H - 35), franja, font=_fuente(40), fill="#FFFFFF", anchor="mm")

    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()
