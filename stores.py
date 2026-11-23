"""Lectores de tiendas. Cada tienda expone fetch(term) -> iterable de Product."""
import json
import random
import re
import time
from dataclasses import dataclass
from html import unescape
from typing import Iterator, Optional
from urllib.parse import quote, urljoin

import requests
import config

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json",
}


@dataclass
class Product:
    store: str
    sku: str
    name: str
    price: float
    list_price: Optional[float]
    url: str
    note: str = ""  # p. ej. "Requiere tarjeta CMR"
    category: str = ""


def _pause():
    time.sleep(random.uniform(*config.REQUEST_DELAY))


class VtexStore:
    """Cualquier tienda VTEX (Oechsle, Plaza Vea, Promart, etc.)."""

    def __init__(self, name, base):
        self.name = name
        self.base = base.rstrip("/")

    def fetch(self, term) -> Iterator[Product]:
        url = f"{self.base}/api/catalog_system/pub/products/search"
        for page in range(config.PAGES_PER_QUERY):
            start = page * config.PAGE_SIZE
            params = {"ft": term, "_from": start,
                      "_to": start + config.PAGE_SIZE - 1}
            r = requests.get(url, params=params, headers=HEADERS, timeout=20)
            # VTEX responde 206 (contenido parcial) cuando todo va bien
            if r.status_code not in (200, 206):
                print(f"  {self.name}: HTTP {r.status_code} en '{term}'")
                return
            data = r.json()
            if not data:
                return
            for prod in data:
                p = self._parse(prod)
                if p:
                    yield p
            _pause()

    def _parse(self, prod) -> Optional[Product]:
        try:
            item = prod["items"][0]
            seller = item["sellers"][0]
            offer = seller["commertialOffer"]  # (sí, VTEX lo escribe así)
            if offer.get("AvailableQuantity", 0) <= 0:
                return None  # sin stock: ignorar
            price = offer.get("Price")
            if not price:
                return None
            list_price = offer.get("ListPrice") or None
            return Product(self.name, str(item["itemId"]), prod["productName"],
                           float(price), float(list_price) if list_price else None,
                           prod.get("link") or self.base)
        except (KeyError, IndexError, TypeError, ValueError):
            return None


_NEXT_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)
HTML_HEADERS = {
    "User-Agent": HEADERS["User-Agent"],
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "es-PE,es;q=0.9",
}


def _parse_money(value):
    """'1,299.90' -> 1299.9 (formato peruano: coma = miles, punto = decimal)."""
    if isinstance(value, list):
        value = value[0] if value else None
    if value is None:
        return None
    s = re.sub(r"[^\d.,]", "", str(value))
    if not s:
        return None
    if "," in s and "." in s and s.rfind(",") > s.rfind("."):
        s = s.replace(".", "").replace(",", ".")   # formato 1.299,90
    else:
        s = s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


_REGULAR_TYPES = {"eventprice", "internetprice", "normalprice"}


def _price_note(ptype):
    """Avisa si el precio más bajo requiere tarjeta u otra promo."""
    t = (ptype or "").lower()
    if not t or t in _REGULAR_TYPES:
        return ""
    if t == "cmrprice":
        return "Requiere tarjeta CMR"
    return f"Precio promocional/tarjeta ({ptype})"


def _find_products(node):
    """Busca en el JSON la lista de productos (dicts con 'prices'), sin depender de la ruta exacta."""
    if isinstance(node, list):
        if node and all(isinstance(x, dict) for x in node) and any(
                "prices" in x and any(k in x for k in ("displayName", "skuId", "productId"))
                for x in node[:3]):
            return node
        for x in node:
            found = _find_products(x)
            if found:
                return found
    elif isinstance(node, dict):
        for v in node.values():
            found = _find_products(v)
            if found:
                return found
    return None


class FalabellaStore:
    """Falabella Perú: lee el JSON __NEXT_DATA__ embebido en la página de búsqueda."""

    def __init__(self, name, base):
        self.name = name
        self.base = base.rstrip("/")
        self.session = requests.Session()
        self._seeded = False

    def _get(self, term, page):
        if not self._seeded:  # una visita al inicio para obtener cookies anónimas
            try:
                self.session.get(self.base, headers=HTML_HEADERS, timeout=20)
            except requests.RequestException:
                pass
            self._seeded = True
        return self.session.get(f"{self.base}/falabella-pe/search",
                                params={"Ntt": term, "page": page},
                                headers=HTML_HEADERS, timeout=20)

    def fetch(self, term) -> Iterator[Product]:
        for page in range(1, config.PAGES_PER_QUERY + 1):
            r = self._get(term, page)
            if r.status_code != 200:
                print(f"  {self.name}: HTTP {r.status_code} en '{term}'")
                return
            products = self.parse_html(r.text)
            if not products:
                return
            yield from products
            _pause()

    def parse_html(self, html):
        m = _NEXT_RE.search(html)
        if not m:
            print(f"  {self.name}: no se encontró __NEXT_DATA__ (¿bloqueo o cambio de página?)")
            return []
        try:
            items = _find_products(json.loads(m.group(1))) or []
        except ValueError:
            return []
        out = []
        for item in items:
            p = self._parse_item(item)
            if p:
                out.append(p)
        return out

    def _parse_item(self, item) -> Optional[Product]:
        current, crossed = [], []   # current: (precio, tipo)
        for pr in item.get("prices") or []:
            val = _parse_money(pr.get("price"))
            if val is None:
                continue
            if pr.get("crossed"):
                crossed.append(val)
            else:
                current.append((val, pr.get("type") or ""))
        if not current:
            return None
        price, ptype = min(current)  # el más bajo, incluidos precios con tarjeta
        sku = item.get("skuId") or item.get("productId")
        name = item.get("displayName") or item.get("name")
        url = item.get("url") or ""
        if not sku or not name:
            return None
        if url.startswith("/"):
            url = self.base + url
        return Product(self.name, str(sku), str(name), price,
                       max(crossed) if crossed else None, url,
                       _price_note(ptype))


def debug_falabella(term="televisor"):
    """Diagnóstico: python cazaofertas.py --debug-falabella televisor"""
    store = FalabellaStore("Falabella", "https://www.falabella.com.pe")
    r = store._get(term, 1)
    print("HTTP:", r.status_code, "| bytes:", len(r.text))
    m = _NEXT_RE.search(r.text)
    print("__NEXT_DATA__ encontrado:", bool(m))
    if not m:
        print("Primeros 300 caracteres:", r.text[:300])
        return
    items = _find_products(json.loads(m.group(1)))
    print("productos en el JSON:", len(items) if items else 0)
    if items:
        print("claves del primer producto:", sorted(items[0].keys()))
        print("prices del primero:", items[0].get("prices"))
        for p in store.parse_html(r.text)[:5]:
            print("  ->", p)


# =============================================================================
# Lector genérico: encuentra productos dentro del JSON que traen las páginas
# (JSON-LD, __NEXT_DATA__, window.__PRELOADED_STATE__, etc.)
# =============================================================================
_K_NAME = ("displayName", "productName", "name", "title")
_K_PRICE = ("offerPrice", "internetPrice", "eventPrice", "salePrice", "bestPrice",
            "finalPrice", "sellingPrice", "price", "Price", "lowPrice")
_K_LIST = ("listPrice", "ListPrice", "normalPrice", "originalPrice", "regularPrice",
           "oldPrice", "PriceWithoutDiscount", "highPrice")
_K_CARD = ("cardPrice", "ripleyCardPrice", "cmrPrice", "tarjetaPrice")
_K_URL = ("url", "link", "permalink", "productUrl", "href", "uri")
_K_ID = ("productId", "sku", "skuId", "partNumber", "id", "productID")


def _json_blocks(html):
    blocks = [m.group(1) for m in re.finditer(
        r"<script[^>]*type=[\"']application/(?:ld\+)?json[\"'][^>]*>(.*?)</script>", html, re.S | re.I)]
    for m in re.finditer(r"window\.__[A-Z_]+__\s*=\s*", html):
        blocks.append(_balanced(html, m.end()))
    out = []
    for b in blocks:
        try:
            out.append(json.loads(b.strip()))
        except (ValueError, AttributeError):
            pass
    return out


def _balanced(text, start):
    """Devuelve el objeto {...} completo que empieza en `start`."""
    if start >= len(text) or text[start] not in "{[":
        return None
    open_c, close_c = text[start], "}" if text[start] == "{" else "]"
    depth, in_str, esc = 0, False, False
    for i in range(start, min(len(text), start + 8_000_000)):
        c = text[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c == open_c:
            depth += 1
        elif c == close_c:
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


def _first(d, keys):
    for k in keys:
        v = d.get(k)
        if v not in (None, "", [], {}):
            return v
    return None


def _flat_prices(d):
    flat = dict(d)
    for sub in ("prices", "offers", "price", "priceRange", "pricing"):
        v = d.get(sub)
        items = [v] if isinstance(v, dict) else v if isinstance(v, list) else []
        for e in items:
            if not isinstance(e, dict):
                continue
            t = e.get("type")
            if isinstance(t, str) and "price" in e:
                flat.setdefault(t, e["price"])
            else:
                for k, val in e.items():
                    flat.setdefault(k, val)
    price = _first(flat, _K_PRICE)
    return (None if isinstance(price, dict) else price), _first(flat, _K_LIST), _first(flat, _K_CARD)


def products_from_json(obj, store, base, card_label="Requiere tarjeta de la tienda"):
    out, seen = [], set()

    def visit(o, depth=0):
        if depth > 40:
            return
        if isinstance(o, dict):
            name = _first(o, _K_NAME)
            if isinstance(name, str) and len(name) > 3:
                price, lst, card = _flat_prices(o)
                url = _first(o, _K_URL)
                price, lst, card = _parse_money(price), _parse_money(lst), _parse_money(card)
                if price and isinstance(url, str):
                    note = ""
                    if card and card < price:
                        price, note = card, card_label
                    pid = _first(o, _K_ID)
                    sku = str(pid) if isinstance(pid, (str, int)) else url
                    if sku not in seen:
                        seen.add(sku)
                        out.append(Product(store, sku, " ".join(name.split()), price,
                                           lst if lst and lst > price else None,
                                           urljoin(base + "/", url), note))
            for v in o.values():
                visit(v, depth + 1)
        elif isinstance(o, list):
            for v in o:
                visit(v, depth + 1)

    visit(obj)
    return out


class _HtmlStore:
    """Base para tiendas que se leen desde la página de búsqueda."""
    card_label = "Requiere tarjeta de la tienda"

    def __init__(self, name, base):
        self.name = name
        self.base = base.rstrip("/")
        self.session = requests.Session()

    def page_url(self, term, page):
        raise NotImplementedError

    def parse_html(self, html):
        out = []
        for block in _json_blocks(html):
            out.extend(products_from_json(block, self.name, self.base, self.card_label))
        return out

    def fetch(self, term) -> Iterator[Product]:
        seen = set()
        for page in range(1, config.PAGES_PER_QUERY + 1):
            r = self.session.get(self.page_url(term, page), headers=HTML_HEADERS, timeout=25)
            if r.status_code != 200:
                print(f"  {self.name}: HTTP {r.status_code} en '{term}'")
                return
            nuevos = [p for p in self.parse_html(r.text) if p.sku not in seen]
            if not nuevos:
                return
            for p in nuevos:
                seen.add(p.sku)
                yield p
            _pause()


# =============================================================================
# MERCADO LIBRE: API oficial; si pide credenciales, lee la web pública
# =============================================================================
class MercadoLibreStore(_HtmlStore):
    API = "https://api.mercadolibre.com"

    def __init__(self, name, base):
        super().__init__(name, base)
        self._token, self._token_exp, self._api_ok = None, 0, True

    def _auth(self):
        if not (config.ML_CLIENT_ID and config.ML_CLIENT_SECRET):
            return {}
        if not self._token or time.time() > self._token_exp:
            r = requests.post(f"{self.API}/oauth/token", timeout=20, data={
                "grant_type": "client_credentials",
                "client_id": config.ML_CLIENT_ID, "client_secret": config.ML_CLIENT_SECRET})
            r.raise_for_status()
            j = r.json()
            self._token = j["access_token"]
            self._token_exp = time.time() + int(j.get("expires_in", 21600)) - 300
        return {"Authorization": f"Bearer {self._token}"}

    def fetch(self, term) -> Iterator[Product]:
        if self._api_ok:
            try:
                yield from self._fetch_api(term)
                return
            except PermissionError:
                self._api_ok = False
                print("  Mercado Libre: la API pide credenciales; uso la web pública "
                      "(pon ML_CLIENT_ID y ML_CLIENT_SECRET en datos_telegram.txt para más precisión)")
        yield from super().fetch(term)

    def _fetch_api(self, term):
        for page in range(config.PAGES_PER_QUERY):
            r = requests.get(f"{self.API}/sites/MPE/search", timeout=20,
                             params={"q": term, "offset": page * config.PAGE_SIZE,
                                     "limit": config.PAGE_SIZE},
                             headers={**HEADERS, **self._auth()})
            if r.status_code in (401, 403):
                raise PermissionError
            r.raise_for_status()
            results = r.json().get("results") or []
            if not results:
                return
            yield from self.parse_api(r.json())
            _pause()

    def parse_api(self, data):
        out = []
        for it in data.get("results") or []:
            price = it.get("price")
            if not price or not it.get("permalink"):
                continue
            orig = it.get("original_price")
            out.append(Product(self.name, str(it.get("id")), it.get("title", ""), float(price),
                               float(orig) if orig and orig > price else None, it["permalink"]))
        return out

    def page_url(self, term, page):
        slug = re.sub(r"\s+", "-", term.strip())
        desde = "" if page == 1 else f"_Desde_{(page - 1) * 48 + 1}"
        return f"https://listado.mercadolibre.com.pe/{quote(slug)}{desde}_NoIndex_True"

    def parse_html(self, html):
        out = super().parse_html(html)
        return out or self.parse_cards(html)

    def parse_cards(self, html):
        """Lee las tarjetas de producto del listado (poly-card)."""
        out = []
        for block in re.split(r'<li[^>]+class="[^"]*ui-search-layout__item', html)[1:]:
            a = re.search(r'<a[^>]*class="[^"]*(?:poly-component__title|ui-search-link)[^"]*"[^>]*>', block) \
                or re.search(r'<h[23][^>]*>\s*<a[^>]*>', block)
            if not a:
                continue
            href = re.search(r'href="([^"]+)"', a.group(0))
            title_end = block.find("</a>", a.end())
            name = re.sub(r"<[^>]+>", "", block[a.end():title_end]).strip()
            prev = re.search(r'andes-money-amount--previous.*?andes-money-amount__fraction[^>]*>([\d.,]+)<',
                             block, re.S)
            cur_zone = block[prev.end():] if prev else block
            cur = re.search(r'andes-money-amount__fraction[^>]*>([\d.,]+)<', cur_zone)
            if not (href and name and cur):
                continue
            price = float(re.sub(r"\D", "", cur.group(1)))
            old = float(re.sub(r"\D", "", prev.group(1))) if prev else None
            url = href.group(1).split("#")[0]
            mid = re.search(r"(MPE-?\d+)", url)
            out.append(Product(self.name, mid.group(1).replace("-", "") if mid else url,
                               unescape(name), price, old if old and old > price else None, url))
        return out


# =============================================================================
# RIPLEY
# =============================================================================
class RipleyStore(_HtmlStore):
    card_label = "Requiere Tarjeta Ripley"

    def page_url(self, term, page):
        return f"{self.base}/search/{quote(term)}?page={page}"


# =============================================================================
# HIRAOKA (Magento)
# =============================================================================
class HiraokaStore(_HtmlStore):
    def page_url(self, term, page):
        return f"{self.base}/catalogsearch/result/?q={quote(term)}&p={page}&product_list_limit=36"

    def parse_html(self, html):
        return super().parse_html(html) or self.parse_magento(html)

    def parse_magento(self, html):
        out = []
        for b in re.split(r'<li[^>]+class="[^"]*product-item[^"]*"', html)[1:]:
            a = re.search(r'<a[^>]+class="[^"]*product-item-link[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', b, re.S)
            fin = re.search(r'data-price-amount="([\d.]+)"[^>]*data-price-type="finalPrice"', b) or \
                re.search(r'data-price-type="finalPrice"[^>]*data-price-amount="([\d.]+)"', b)
            if not (a and fin):
                continue
            old = re.search(r'data-price-amount="([\d.]+)"[^>]*data-price-type="oldPrice"', b) or \
                re.search(r'data-price-type="oldPrice"[^>]*data-price-amount="([\d.]+)"', b)
            pid = re.search(r'data-product-id="(\d+)"', b)
            price = float(fin.group(1))
            old_p = float(old.group(1)) if old else None
            out.append(Product(self.name, pid.group(1) if pid else a.group(1),
                               unescape(re.sub(r"<[^>]+>", "", a.group(2)).strip()), price,
                               old_p if old_p and old_p > price else None, a.group(1)))
        return out


def build_stores():
    types = {"vtex": VtexStore, "falabella": FalabellaStore, "mercadolibre": MercadoLibreStore,
             "ripley": RipleyStore, "hiraoka": HiraokaStore}
    return [types[s["type"]](s["name"], s["base"])
            for s in config.STORES if s.get("enabled") and s["type"] in types]
