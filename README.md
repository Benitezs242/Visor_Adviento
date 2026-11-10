# Vigilante del calendario de adviento (Trendy Shop)

Revisa la tienda cada 5 minutos, sin parar, y te avisa por WhatsApp (y opcionalmente por Telegram) de cualquier cambio: producto nuevo, ya disponible, agotado, cambio de precio, producto que desaparece, y si la tienda deja de responder.

Necesita Python 3 (no hay que instalar nada más).

## 1. Activar WhatsApp con CallMeBot (2 minutos)

CallMeBot es un servicio gratuito de terceros (no oficial de WhatsApp) que te manda mensajes a tu propio número.

1. Guarda en tus contactos el número **+34 611 01 16 37** con el nombre que quieras. Ese número puede cambiar, así que confírmalo en la página oficial de CallMeBot (callmebot.com) antes de hacerlo.
2. Por WhatsApp, envíale a ese contacto exactamente: `I allow callmebot to send me messages`
3. Te responde con "API Activated for your phone number. Your APIKEY is XXXXXX". Esa es tu apikey. Si no llega en 2 minutos, reintenta pasadas 24 horas.

## 2. Configurar

Copia `.env.example` como `.env` en la misma carpeta que `monitor_adviento.py`. Pon tu número (con +57) y la apikey.

## 3. Probar

```bash
python3 monitor_adviento.py --test
```

Debe llegarte un WhatsApp de prueba. Si no llega, revisa el número, la apikey y que hayas hecho la activación.

## 4. Dejarlo corriendo

```bash
python3 monitor_adviento.py
```

La primera vez manda un mensaje "Vigilante activo" con los productos que ya coinciden; desde ahí avisa solo los cambios. El estado queda en `estado_adviento.json`.

Para que siga aunque cierres la terminal:

- **Linux / máquina virtual:** `nohup python3 monitor_adviento.py >> log.txt 2>&1 &`
- **Con cron** (una revisión cada 5 min, sin bucle): `*/5 * * * * /usr/bin/python3 /ruta/monitor_adviento.py --once >> /ruta/log.txt 2>&1`
- **Windows:** Programador de tareas, ejecutar `python monitor_adviento.py` al iniciar sesión.

El computador o máquina virtual debe estar encendido y con internet.

## 5. Página de alerta para el celular (opcional)

`web_alerta.py` hace lo mismo que el vigilante y además sirve una página para abrir en el celular: muestra en grande si hay producto disponible y, cuando hay un cambio, suena, vibra, parpadea en rojo y muestra el enlace. Los avisos por WhatsApp/Telegram siguen funcionando.

1. Pon una `ACCESS_KEY` larga en el `.env`.
2. Corre `python3 web_alerta.py` (en vez de `monitor_adviento.py`, no los dos a la vez).
3. En el celular, abre `http://IP-DEL-COMPUTADOR:8080/?k=TU_CLAVE`. Si están en la misma red Wi-Fi, la IP la sacas con `ipconfig` (Windows) o `ip a` (Linux).
4. Toca **"Activar alertas"** una vez (los navegadores no dejan sonar sin ese toque), y deja la pantalla encendida y la página abierta.

Para abrirla desde fuera de tu Wi-Fi hace falta exponerla a internet, por ejemplo con un túnel (Cloudflare Tunnel o ngrok) o subiéndola a un hosting. En ese caso la `ACCESS_KEY` es obligatoria.

Límites del celular: si se bloquea la pantalla o cambias de app, el navegador puede pausar la página y no sonar. La página intenta mantener la pantalla encendida donde el navegador lo permite. En iPhone la vibración no funciona. Por eso el WhatsApp sigue siendo el respaldo.

## Notas

- CallMeBot solo envía texto a tu propio número, y como es un servicio gratuito de terceros puede fallar o cambiar. Por eso conviene dejar también Telegram configurado como respaldo: si pones las dos, el aviso sale por ambos canales.
- `KEYWORDS` en `.env`: palabras que busca en nombre, enlace y categoría. Por defecto `adviento,advent,calendario`.
- `CHECK_EVERY_SECONDS`: cada cuánto revisa. Mínimo 120.
- Para empezar de cero, borra `estado_adviento.json`.
