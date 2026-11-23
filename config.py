"""Configuración de CazaOfertas Perú. Edita este archivo a tu gusto.

Elaborado por: HuachOfertas
"""
import os

VERSION = "2.0.0"
FECHA = "22/11/2026"


# --- Lee datos_telegram.txt (o .env) con TELEGRAM_TOKEN=... y TELEGRAM_CHAT_ID=... ---
def _cargar_env():
    carpeta = os.path.dirname(os.path.abspath(__file__))
    for nombre in ("datos_telegram.txt", ".env"):
        ruta = os.path.join(carpeta, nombre)
        if os.path.exists(ruta):
            _leer(ruta)


def _leer(ruta):
    with open(ruta, encoding="utf-8-sig") as f:
        for linea in f:
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue
            clave, valor = linea.split("=", 1)
            os.environ.setdefault(clave.strip(), valor.strip().strip('"').strip("'"))


_cargar_env()

# --- Telegram (ponlos en datos_telegram.txt, no aquí) ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# --- Mercado Libre (opcional, también en datos_telegram.txt): app gratis en developers.mercadolibre.com.pe ---
ML_CLIENT_ID = os.getenv("ML_CLIENT_ID", "")
ML_CLIENT_SECRET = os.getenv("ML_CLIENT_SECRET", "")

# --- Frecuencia ---
INTERVAL_MINUTES = int(os.getenv("CAZA_MINUTOS", "10"))  # no bajes de 5 o te pueden bloquear

# --- Reglas de detección (0.40 = 40% de descuento) ---
MIN_DISCOUNT = 0.50            # bajada vs. su precio habitual (mediana del historial)
MIN_DISCOUNT_VS_LIST = 0.70    # sin historial: bajada vs. precio de lista (más estricto, la lista puede estar inflada)
ERROR_DISCOUNT = 0.75          # a partir de aquí se marca como POSIBLE ERROR DE PRECIO
MIN_HISTORY = 3                # observaciones mínimas para usar el historial
HISTORY_DAYS = 30
MIN_PRICE = 1.0                # ignora solo precios menores a S/ 1 (S/ 0 = dato vacío)
MAX_ALERTS_PER_RUN = 20        # evita que te lleguen cientos de mensajes en una pasada

# --- Lectura de tiendas ---
PAGES_PER_QUERY = int(os.getenv("CAZA_PAGINAS", "2"))  # páginas por búsqueda (en GitHub se usa 1)
PAGE_SIZE = 50                 # máximo de VTEX y Mercado Libre
REQUEST_DELAY = tuple(float(x) for x in os.getenv("CAZA_PAUSA", "1.0,2.5").split(","))  # pausa aleatoria (s)

DB_PATH = "cazaofertas.db"

# --- Categorías: qué se busca y precio mínimo (filtra accesorios baratos) ---
CATEGORIES = {
    "Artefactos": {
        "terms": ["televisor", "refrigeradora", "lavadora", "laptop", "audifonos",
                  "freidora de aire", "microondas", "consola", "tablet", "smartwatch"],
        "min_price": 80,
    },
    "Celulares": {
        "terms": ["celular", "iphone", "samsung galaxy", "xiaomi redmi"],
        "min_price": 150,
    },
    "Zapatillas": {
        "terms": ["zapatillas", "zapatillas nike", "zapatillas adidas"],
        "min_price": 60,
    },
    "Ropa": {
        "terms": ["casaca", "polo", "jean", "buzo", "vestido"],
        "min_price": 25,
    },
    "Juguetes": {
        "terms": ["juguetes", "lego", "hot wheels", "barbie", "peluche", "juego de mesa"],
        "min_price": 20,
    },
    "Marcas": {
        "terms": ["adidas", "nike", "puma", "bata", "calimod"],
        "min_price": 40,
    },
}

# Productos con estas palabras en el nombre se ignoran
EXCLUDE_WORDS = ["funda", "case", "mica", "protector", "cargador", "cable",
                 "repuesto", "reacondicionado", "usado", "correa"]

# Tiendas. type "vtex" funciona con cualquier tienda basada en VTEX.
STORES = [
    # Mercado Libre: desde nov-2026 pide iniciar sesión para ver listados y su API ya no permite buscar.
    {"name": "Mercado Libre", "type": "mercadolibre", "base": "https://www.mercadolibre.com.pe", "enabled": False},
    {"name": "Falabella", "type": "falabella", "base": "https://www.falabella.com.pe", "enabled": True},
    {"name": "Ripley",    "type": "ripley",    "base": "https://simple.ripley.com.pe",  "enabled": True},
    {"name": "Oechsle",   "type": "vtex",      "base": "https://www.oechsle.pe",        "enabled": True},
    {"name": "Hiraoka",   "type": "hiraoka",   "base": "https://hiraoka.com.pe",        "enabled": True},
    {"name": "Plaza Vea", "type": "vtex",      "base": "https://www.plazavea.com.pe",   "enabled": True},
    {"name": "Promart",   "type": "vtex",      "base": "https://www.promart.pe",        "enabled": True},
    # Tiendas de marca y operadoras: solo buscan en las categorías que venden
    {"name": "Nike",  "type": "sfcc", "base": "https://www.nike.com.pe", "enabled": True,
     "categories": ["Zapatillas", "Ropa", "Marcas"]},
    {"name": "Bata",  "type": "bata", "base": "https://www.bata.com",    "enabled": True,
     "categories": ["Zapatillas", "Marcas"]},
    {"name": "Puma",  "type": "puma", "base": "https://pe.puma.com",     "enabled": True,
     "categories": ["Zapatillas", "Ropa", "Marcas"]},
    {"name": "Claro", "type": "vtex", "base": "https://tienda.claro.com.pe", "enabled": True,
     "categories": ["Celulares"]},
    {"name": "Metro",   "type": "vtex",    "base": "https://www.metro.pe",       "enabled": True},
    {"name": "Wong",    "type": "vtex",    "base": "https://www.wong.pe",        "enabled": True},
    {"name": "Sodimac", "type": "sodimac", "base": "https://www.sodimac.com.pe", "enabled": True,
     "categories": ["Artefactos", "Juguetes"]},
]

# Tiendas que se revisan al mismo tiempo (cada tienda va a su ritmo, sin saturarla)
PARALLEL_STORES = int(os.getenv("CAZA_PARALELO", "8"))

# Filtros opcionales por variable de entorno:
#   CAZA_SOLO_TIENDAS=Ripley        -> revisa solo esas tiendas (lo usa iniciar.bat en tu PC)
#   CAZA_SIN_TIENDAS=Ripley         -> revisa todas menos esas (lo usa GitHub)
_solo = {t.strip().lower() for t in os.getenv("CAZA_SOLO_TIENDAS", "").split(",") if t.strip()}
_sin = {t.strip().lower() for t in os.getenv("CAZA_SIN_TIENDAS", "").split(",") if t.strip()}
for _s in STORES:
    if (_solo and _s["name"].lower() not in _solo) or _s["name"].lower() in _sin:
        _s["enabled"] = False

# --- Canales públicos de Telegram que se vigilan ---
# keywords vacío = te llega TODO lo que publiquen; con palabras = solo lo que las mencione.
# Para agregar otro canal: copia una línea y cambia "user" por lo que va después de t.me/
OFERTA_KEYWORDS = ["zapatilla", "ropa", "polo", "casaca", "jean", "buzo", "vestido", "polera",
                   "juguete", "lego", "muñeca", "peluche", "hot wheels", "barbie",
                   "error de precio", "súper oferta", "super oferta", "remate", "liquidación"]
CHANNELS = [
    {"name": "CONCUPON Perú", "user": "concuponperu", "keywords": []},          # todo
    # {"name": "Otro canal", "user": "nombre_del_canal", "keywords": OFERTA_KEYWORDS},
]
# En tu PC (modo solo Ripley/Bata) no se revisan canales, para que no te lleguen repetidos
if _solo:
    CHANNELS = []

# --- Resumen diario "sigo vivo" (hora de Perú). Pon None para desactivarlo ---
HEARTBEAT_HOUR = 21
if _solo:                      # en tu PC (solo Ripley/Bata) no se envía, lo manda GitHub
    HEARTBEAT_HOUR = None

# --- Fuentes comunitarias (RSS). Agrega aquí los feeds que verifiques. ---
# Prueba añadiendo /feed a la URL de la web. Ejemplo:
# FEEDS = [{"name": "Comcupon", "url": "https://comcupon.pe/feed"}]
FEEDS = []

# Palabras clave que te interesan en los títulos de los feeds (vacío = todo)
FEED_KEYWORDS = [
    "televisor", "tv", "laptop", "celular", "iphone", "samsung", "zapatillas",
    "consola", "playstation", "lego", "juguete", "error de precio", "error",
]
