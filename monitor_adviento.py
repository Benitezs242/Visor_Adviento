#!/usr/bin/env python3
"""
Vigilante del calendario de adviento (Trendy Shop, VTEX; también sirve Shopify).

Corre sin parar y revisa la tienda cada 5 minutos. Te avisa por WhatsApp
(CallMeBot) y/o Telegram cuando:
  - aparece un producto nuevo que coincide con las palabras clave
  - un producto pasa de agotado a disponible (o se agota)
  - cambia el precio de un producto
  - un producto desaparece del catálogo
  - la tienda deja de responder (y cuando se recupera)

Uso:
  python3 monitor_adviento.py          # corre en bucle, para siempre
  python3 monitor_adviento.py --test   # manda un mensaje de prueba a Telegram
  python3 monitor_adviento.py --once   # una sola revisión (para cron)

Configuración: archivo .env junto al script (ver .env.example) o variables de
entorno. Solo usa la librería estándar de Python.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))


def load_dotenv(path):
    """Carga KEY=VALUE de un .env sin pisar variables ya definidas."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    except FileNotFoundError:
        pass


load_dotenv(os.path.join(HERE, ".env"))

STORE_URL = os.environ.get("STORE_URL", "https://www.maquillajetrendyshop.com").rstrip("/")
PLATFORM = os.environ.get("PLATFORM", "auto").lower()  # auto | vtex | shopify
KEYWORDS = [
    k.strip().lower()
    for k in os.environ.get("KEYWORDS", "adviento,advent,calendario").split(",")
    if k.strip()
]
INTERVAL = max(120, int(os.environ.get("CHECK_EVERY_SECONDS", "300")))
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
WHATSAPP_PHONE = os.environ.get("WHATSAPP_PHONE", "")  # formato internacional, ej: +573001234567
WHATSAPP_APIKEY = os.environ.get("WHATSAPP_APIKEY", "")
CALLMEBOT_URL = os.environ.get("CALLMEBOT_URL", "https://api.callmebot.com/whatsapp.php")
STATE_FILE = os.environ.get("STATE_FILE", os.path.join(HERE, "estado_adviento.json"))
FAILS_BEFORE_ALERT = 6  # ~30 min con el intervalo por defecto
USER_AGENT = "Mozilla/5.0 (compatible; VigilanteAdviento/2.0; uso personal)"


def http_get(url, timeout=25):
    req = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def text_matches(*parts):
    haystack = " ".join(p for p in parts if p).lower()
    return any(k in haystack for k in KEYWORDS)


# ---------------------------------------------------------------- Shopify

def fetch_shopify():
    raw, page = [], 1
    while True:
        data = json.loads(http_get(f"{STORE_URL}/products.json?limit=250&page={page}"))
        if "products" not in data:
            raise ValueError("Respuesta sin 'products'")
        batch = data["products"]
        if not batch:
            break
        raw.extend(batch)
        if len(batch) < 250:
            break
        page += 1
        time.sleep(1)

    items = []
    for p in raw:
        tags = p.get("tags", [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",")]
        if not text_matches(p.get("title"), p.get("handle"), p.get("product_type"), " ".join(tags)):
            continue
        variants = p.get("variants", [])
        items.append(
            {
                "id": str(p["id"]),
                "title": p.get("title", ""),
                "url": f"{STORE_URL}/products/{p.get('handle', '')}",
                "available": any(v.get("available") for v in variants),
                "price": variants[0].get("price") if variants else "?",
                "release": "",
            }
        )
    return items


# ------------------------------------------------------------------- VTEX

def _vtex_normalize(products):
    items = {}
    for p in products:
        if not isinstance(p, dict) or "productId" not in p:
            continue
        categories = " ".join(p.get("categories", []) or [])
        if not text_matches(p.get("productName"), p.get("linkText"), categories):
            continue
        available, prices = False, []
        for it in p.get("items", []) or []:
            for seller in it.get("sellers", []) or []:
                offer = seller.get("commertialOffer", {}) or {}
                if offer.get("IsAvailable") or (offer.get("AvailableQuantity") or 0) > 0:
                    available = True
                if offer.get("Price"):
                    prices.append(offer["Price"])
        pid = str(p["productId"])
        items[pid] = {
            "id": pid,
            "title": p.get("productName", ""),
            "url": p.get("link") or f"{STORE_URL}/{p.get('linkText', '')}/p",
            "available": available,
            "price": min(prices) if prices else "?",
            "release": (p.get("releaseDate") or "")[:10],
        }
    return items


def fetch_vtex():
    found, classic_ok = {}, False
    for kw in KEYWORDS:
        url = (
            f"{STORE_URL}/api/catalog_system/pub/products/search"
            f"?ft={urllib.parse.quote(kw)}&_from=0&_to=49"
        )
        try:
            data = json.loads(http_get(url))
            if isinstance(data, list):
                classic_ok = True
                found.update(_vtex_normalize(data))
        except (urllib.error.URLError, ValueError):
            pass
        time.sleep(1)

    if not classic_ok:  # respaldo: búsqueda inteligente de VTEX
        for kw in KEYWORDS:
            url = (
                f"{STORE_URL}/api/io/_v/api/intelligent-search/product_search/"
                f"?query={urllib.parse.quote(kw)}&count=50&page=1"
            )
            data = json.loads(http_get(url))
            found.update(_vtex_normalize(data.get("products", [])))
            time.sleep(1)
    return list(found.values())


def fetch_items():
    if PLATFORM == "shopify":
        return fetch_shopify()
    if PLATFORM == "vtex":
        return fetch_vtex()
    try:  # auto: la web de Trendy es VTEX, pero se prueba Shopify primero
        return fetch_shopify()
    except (urllib.error.URLError, ValueError):
        return fetch_vtex()


# ------------------------------------------------------------ Estado/avisos

def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def save_state(state):
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE_FILE)


def now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def send_whatsapp(text):
    """WhatsApp a tu propio número con CallMeBot (servicio gratuito de terceros)."""
    query = urllib.parse.urlencode(
        {"phone": WHATSAPP_PHONE, "text": text[:900], "apikey": WHATSAPP_APIKEY}
    )
    try:
        req = urllib.request.Request(f"{CALLMEBOT_URL}?{query}", headers={"User-Agent": USER_AGENT})
        urllib.request.urlopen(req, timeout=30).read()
        return True
    except Exception as e:
        print(f"   No se pudo enviar a WhatsApp: {e}", flush=True)
        return False


def send_telegram(text):
    api = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    body = urllib.parse.urlencode({"chat_id": TELEGRAM_CHAT_ID, "text": text}).encode()
    try:
        urllib.request.urlopen(api, data=body, timeout=20).read()
        return True
    except Exception as e:
        print(f"   No se pudo enviar a Telegram: {e}", flush=True)
        return False


def notify(text):
    """Imprime el aviso y lo manda por WhatsApp y/o Telegram, según lo configurado."""
    print(f"[{now()}] [ALERTA] {text}", flush=True)
    sent = False
    if WHATSAPP_PHONE and WHATSAPP_APIKEY:
        sent = send_whatsapp(text) or sent
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        sent = send_telegram(text) or sent
    if not sent and not (WHATSAPP_PHONE and WHATSAPP_APIKEY) and not (TELEGRAM_TOKEN and TELEGRAM_CHAT_ID):
        print("   (Sin WhatsApp ni Telegram configurado: solo se imprime en consola)", flush=True)
    return sent


def fmt_price(p):
    return f"${p:,.0f}".replace(",", ".") if isinstance(p, (int, float)) else f"${p}"


def check_once():
    current = {item["id"]: item for item in fetch_items()}
    previous = load_state()

    if previous is None:  # primera vez: línea base
        lines = [
            f"- {i['title']} ({'DISPONIBLE' if i['available'] else 'no disponible'})"
            for i in list(current.values())[:10]
        ]
        resumen = "\n".join(lines) if lines else "- (ninguno todavía)"
        notify(
            f"✅ Vigilante activo en {STORE_URL}\n"
            f"Palabras clave: {', '.join(KEYWORDS)}\n"
            f"Coinciden {len(current)} producto(s):\n{resumen}"
        )
        save_state(current)
        return current

    for pid, item in current.items():
        old = previous.get(pid)
        rel = f"\nLanzamiento: {item['release']}" if item.get("release") else ""
        if old is None:
            if item["available"]:
                notify(f"🎄 ¡NUEVO y DISPONIBLE!: {item['title']} ({fmt_price(item['price'])}){rel}\n{item['url']}")
            else:
                notify(f"👀 Apareció un producto nuevo (aún no disponible): {item['title']}{rel}\n{item['url']}")
            continue
        if item["available"] and not old.get("available"):
            notify(f"🛒 ¡YA SE PUEDE COMPRAR!: {item['title']} ({fmt_price(item['price'])})\n{item['url']}")
        elif not item["available"] and old.get("available"):
            notify(f"⛔ Se agotó o dejó de estar disponible: {item['title']}\n{item['url']}")
        if item["price"] != old.get("price"):
            notify(
                f"💲 Cambió el precio de {item['title']}: "
                f"{fmt_price(old.get('price'))} → {fmt_price(item['price'])}\n{item['url']}"
            )

    for pid, old in previous.items():
        if pid not in current:
            notify(f"🫥 Ya no aparece en la búsqueda: {old['title']}")

    save_state(current)
    return current


def run_forever():
    print(f"[{now()}] Vigilando {STORE_URL} cada {INTERVAL}s. Palabras clave: {KEYWORDS}", flush=True)
    fails, alerted = 0, False
    while True:
        try:
            check_once()
            if alerted:
                notify("🟢 La tienda volvió a responder, el vigilante sigue activo.")
            fails, alerted = 0, False
        except Exception as e:
            fails += 1
            print(f"[{now()}] Error en la revisión ({fails}): {e}", flush=True)
            if fails >= FAILS_BEFORE_ALERT and not alerted:
                notify(f"🔴 Llevo {fails} revisiones seguidas sin poder leer la tienda: {e}")
                alerted = True
        time.sleep(INTERVAL)


def main():
    args = set(sys.argv[1:])
    if "--test" in args:
        ok = notify("🔔 Mensaje de prueba del vigilante del calendario de adviento.")
        sys.exit(0 if ok else 1)
    if "--once" in args:
        try:
            check_once()
        except (urllib.error.URLError, ValueError) as e:
            sys.exit(f"No se pudo leer el catálogo de la tienda: {e}")
        return
    try:
        run_forever()
    except KeyboardInterrupt:
        print("\nDetenido.")


if __name__ == "__main__":
    main()
