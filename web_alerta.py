#!/usr/bin/env python3
"""
Página web de alerta para el celular (usa el mismo vigilante de monitor_adviento.py).

Levanta un servidor que:
  - revisa la tienda cada WEB_CHECK_SECONDS (60 por defecto, mínimo 30)
  - sigue mandando los avisos por WhatsApp/Telegram si los configuraste
  - sirve una página para abrir en el celular que muestra el estado y, cuando hay
    un cambio, suena, vibra, parpadea y muestra el enlace del producto

Uso:
  python3 web_alerta.py

Variables (en el mismo .env de monitor_adviento.py):
  WEB_PORT           Puerto. Por defecto 8080
  ACCESS_KEY         Clave opcional. Si la pones, la página solo abre con
                     http://HOST:PUERTO/?k=TU_CLAVE  (muy recomendado si la
                     expones a internet)
  WEB_CHECK_SECONDS  Cada cuánto revisa la tienda. Por defecto 60

No corras a la vez este script y monitor_adviento.py: los dos revisan la tienda
y se duplicarían los avisos. Este ya hace el trabajo de los dos.
"""

import hmac
import json
import os
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import monitor_adviento as m  # carga el .env y la configuración

WEB_PORT = int(os.environ.get("PORT") or os.environ.get("WEB_PORT") or "8080")  # PORT lo pone el hosting
ACCESS_KEY = os.environ.get("ACCESS_KEY", "")
WEB_INTERVAL = max(30, int(os.environ.get("WEB_CHECK_SECONDS", "60")))

LOCK = threading.Lock()
STATUS = {"items": [], "checked_at": None, "error": None, "events": [], "last_event_id": 0}


# --------------------------------------------------- Captura de avisos

_original_notify = m.notify


def web_notify(text):
    """Guarda cada aviso para que la página lo muestre, y luego lo envía como siempre."""
    with LOCK:
        STATUS["last_event_id"] += 1
        STATUS["events"].append({"id": STATUS["last_event_id"], "time": m.now(), "text": text})
        del STATUS["events"][:-30]
    return _original_notify(text)


m.notify = web_notify  # check_once() usa notify() del módulo, así que queda enganchado


# ------------------------------------------------------- Revisión

def do_check():
    """Una revisión; actualiza STATUS. Lanza la excepción si falla."""
    current = m.check_once()
    items = sorted(current.values(), key=lambda i: (not i["available"], i["title"]))
    with LOCK:
        STATUS["items"] = items
        STATUS["checked_at"] = m.now()
        STATUS["error"] = None


def loop():
    fails, alerted = 0, False
    while True:
        try:
            do_check()
            if alerted:
                web_notify("🟢 La tienda volvió a responder.")
            fails, alerted = 0, False
        except Exception as e:
            fails += 1
            with LOCK:
                STATUS["error"] = f"{e}"
            print(f"[{m.now()}] Error en la revisión ({fails}): {e}", flush=True)
            if fails >= m.FAILS_BEFORE_ALERT and not alerted:
                web_notify(f"🔴 Llevo {fails} revisiones seguidas sin poder leer la tienda: {e}")
                alerted = True
        time.sleep(WEB_INTERVAL)


# ---------------------------------------------------------- Servidor

INDEX_HTML = r"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#14111a">
<title>Alerta calendario</title>
<style>
  :root { --bg:#14111a; --card:#201b2b; --text:#f4f0fa; --muted:#a79fb8; --ok:#22c55e; --warn:#f59e0b; --bad:#ef4444; }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:var(--text); font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
         padding: max(16px, env(safe-area-inset-top)) 16px 32px; min-height:100vh; }
  h1 { font-size:1.15rem; margin:0 0 4px; }
  .sub { color:var(--muted); font-size:.85rem; margin-bottom:16px; }
  .state { border-radius:18px; padding:22px 18px; text-align:center; font-weight:700; font-size:1.5rem; background:var(--card); margin-bottom:14px; }
  .state small { display:block; font-weight:400; font-size:.9rem; color:var(--muted); margin-top:6px; }
  .state.ok { background:var(--ok); color:#06210f; } .state.ok small { color:#0a3a1c; }
  .state.wait { background:#2a2438; }
  button { width:100%; font-size:1.05rem; padding:15px; border-radius:14px; border:0; font-weight:700; margin-bottom:12px; }
  #arm { background:#8b5cf6; color:white; } #arm.on { background:#2a2438; color:var(--muted); }
  #stop { background:var(--bad); color:white; display:none; }
  .list { background:var(--card); border-radius:14px; padding:6px 14px; margin-bottom:14px; }
  .item { padding:10px 0; border-bottom:1px solid #2f2840; }
  .item:last-child { border-bottom:0; }
  .item a { color:#c4b5fd; text-decoration:none; font-weight:600; }
  .tag { font-size:.75rem; padding:2px 8px; border-radius:999px; margin-left:6px; }
  .tag.y { background:var(--ok); color:#06210f; } .tag.n { background:#3a3350; color:var(--muted); }
  .ev { font-size:.85rem; padding:8px 0; border-bottom:1px solid #2f2840; white-space:pre-wrap; word-break:break-word; }
  .ev time { color:var(--muted); display:block; font-size:.75rem; }
  h2 { font-size:.95rem; margin:18px 0 8px; color:var(--muted); }
  .err { color:var(--bad); font-size:.85rem; margin-bottom:10px; }
  .note { color:var(--muted); font-size:.8rem; line-height:1.4; }
  body.alarm { animation: flash .6s infinite alternate; }
  @keyframes flash { from { background:#14111a; } to { background:#7f1d1d; } }
</style>
</head>
<body>
<h1>🎄 Vigilante del calendario</h1>
<div class="sub" id="meta">Cargando…</div>

<button id="arm">🔔 Activar alertas (toca una vez)</button>
<button id="stop">🔕 Silenciar alarma</button>

<div class="state wait" id="state">Revisando…<small></small></div>
<div class="err" id="err" hidden></div>

<h2>Productos que coinciden</h2>
<div class="list" id="items"><div class="item">—</div></div>

<h2>Últimos avisos</h2>
<div class="list" id="events"><div class="ev">Sin avisos todavía.</div></div>

<p class="note">Deja esta página abierta y la pantalla encendida. Si el celular se bloquea, el navegador puede pausar la página: por eso también te llega el aviso por WhatsApp.</p>

<script>
(function () {
  var K = new URLSearchParams(location.search).get('k') || '';
  var lastId = null, armed = false, ctx = null, beepTimer = null, wake = null;
  var $ = function (id) { return document.getElementById(id); };

  function safeUrl(u) { return /^https?:\/\//i.test(u || '') ? u : null; }

  function beep() {
    if (!ctx) return;
    try {
      var o = ctx.createOscillator(), g = ctx.createGain();
      o.type = 'square'; o.frequency.value = 880;
      g.gain.value = 0.25;
      o.connect(g); g.connect(ctx.destination);
      o.start(); o.stop(ctx.currentTime + 0.35);
    } catch (e) {}
  }
  function startAlarm() {
    if (beepTimer) return;
    document.body.classList.add('alarm');
    $('stop').style.display = 'block';
    beep(); if (navigator.vibrate) navigator.vibrate([400, 150, 400]);
    beepTimer = setInterval(function () {
      beep(); if (navigator.vibrate) navigator.vibrate([400, 150, 400]);
    }, 1300);
  }
  function stopAlarm() {
    clearInterval(beepTimer); beepTimer = null;
    document.body.classList.remove('alarm');
    $('stop').style.display = 'none';
    if (navigator.vibrate) navigator.vibrate(0);
  }
  $('stop').onclick = stopAlarm;

  async function requestWake() {
    try { if ('wakeLock' in navigator) wake = await navigator.wakeLock.request('screen'); } catch (e) {}
  }
  document.addEventListener('visibilitychange', function () {
    if (armed && document.visibilityState === 'visible') requestWake();
  });

  $('arm').onclick = async function () {
    try { ctx = ctx || new (window.AudioContext || window.webkitAudioContext)(); await ctx.resume(); } catch (e) {}
    armed = true;   // el sonido queda activo de inmediato, sin esperar los permisos
    this.textContent = '✅ Alertas activas (suena, vibra y avisa)';
    this.className = 'on';
    beep();
    try { if ('Notification' in window && Notification.permission === 'default') Notification.requestPermission(); } catch (e) {}
    requestWake();
  };

  function notifyOS(text) {
    try {
      if ('Notification' in window && Notification.permission === 'granted') new Notification('🎄 Calendario', { body: text });
    } catch (e) {}
  }

  function render(d) {
    $('meta').textContent = (d.store || '') + ' · última revisión: ' + (d.checked_at || '—');
    var avail = d.items.filter(function (i) { return i.available; });
    var st = $('state');
    if (avail.length) {
      st.className = 'state ok';
      st.firstChild.nodeValue = '¡HAY PRODUCTO DISPONIBLE!';
      st.querySelector('small').textContent = avail.map(function (i) { return i.title; }).join(' · ');
    } else {
      st.className = 'state wait';
      st.firstChild.nodeValue = 'Aún no está disponible';
      st.querySelector('small').textContent = d.items.length ? 'Hay ' + d.items.length + ' producto(s) que coinciden, ninguno a la venta.' : 'Todavía no aparece ningún producto del calendario.';
    }
    var err = $('err'); err.hidden = !d.error; err.textContent = d.error ? 'No pude leer la tienda: ' + d.error : '';

    var box = $('items'); box.textContent = '';
    if (!d.items.length) { var e = document.createElement('div'); e.className = 'item'; e.textContent = 'Ninguno por ahora.'; box.appendChild(e); }
    d.items.forEach(function (i) {
      var row = document.createElement('div'); row.className = 'item';
      var url = safeUrl(i.url), el;
      if (url) { el = document.createElement('a'); el.href = url; el.target = '_blank'; el.rel = 'noopener'; }
      else { el = document.createElement('span'); }
      el.textContent = i.title; row.appendChild(el);
      var tag = document.createElement('span'); tag.className = 'tag ' + (i.available ? 'y' : 'n');
      tag.textContent = i.available ? 'disponible' : 'no disponible'; row.appendChild(tag);
      box.appendChild(row);
    });

    var evBox = $('events'); evBox.textContent = '';
    if (!d.events.length) { var n = document.createElement('div'); n.className = 'ev'; n.textContent = 'Sin avisos todavía.'; evBox.appendChild(n); }
    d.events.slice().reverse().forEach(function (ev) {
      var row = document.createElement('div'); row.className = 'ev';
      var t = document.createElement('time'); t.textContent = ev.time; row.appendChild(t);
      row.appendChild(document.createTextNode(ev.text));
      evBox.appendChild(row);
    });
  }

  function handleNew(d) {
    var maxId = d.events.length ? d.events[d.events.length - 1].id : 0;
    if (lastId === null) { lastId = maxId; return; }   // al abrir, no suena por avisos viejos
    var fresh = d.events.filter(function (e) { return e.id > lastId; });
    lastId = maxId;
    if (!fresh.length) return;
    var important = fresh.filter(function (e) { return !/^✅|^🟢/.test(e.text); });
    if (!important.length) return;
    notifyOS(important[important.length - 1].text);
    if (armed) startAlarm();
  }

  async function poll() {
    try {
      var r = await fetch('/api/status?k=' + encodeURIComponent(K), { cache: 'no-store' });
      if (r.status === 403) { $('meta').textContent = 'Acceso denegado: falta la clave en el enlace (?k=...)'; return; }
      var d = await r.json();
      render(d); handleNew(d);
    } catch (e) {
      $('meta').textContent = 'Sin conexión con el servidor… reintentando';
    }
  }
  poll(); setInterval(poll, 10000);
})();
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(u.query)
        if ACCESS_KEY:
            given = qs.get("k", [""])[0]
            if not hmac.compare_digest(given.encode(), ACCESS_KEY.encode()):
                return self._send(403, "Acceso denegado", "text/plain; charset=utf-8")
        if u.path in ("/", "/index.html"):
            return self._send(200, INDEX_HTML, "text/html; charset=utf-8")
        if u.path == "/api/status":
            with LOCK:
                payload = dict(STATUS, store=m.STORE_URL, interval=WEB_INTERVAL)
                body = json.dumps(payload, ensure_ascii=False)
            return self._send(200, body, "application/json; charset=utf-8")
        self._send(404, "No encontrado", "text/plain; charset=utf-8")

    def log_message(self, *args):
        pass


def main():
    threading.Thread(target=loop, daemon=True).start()
    server = ThreadingHTTPServer(("0.0.0.0", WEB_PORT), Handler)
    clave = f"/?k={ACCESS_KEY}" if ACCESS_KEY else "/"
    print(f"[{m.now()}] Página de alerta en http://localhost:{WEB_PORT}{clave}", flush=True)
    if not ACCESS_KEY:
        print("   AVISO: sin ACCESS_KEY, cualquiera con el enlace puede ver la página.", flush=True)
    print(f"   Revisando {m.STORE_URL} cada {WEB_INTERVAL}s. Ctrl+C para detener.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDetenido.")


if __name__ == "__main__":
    main()
