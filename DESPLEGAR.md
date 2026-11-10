# Poner la alerta en internet (un solo enlace para ella)

Objetivo: tú lo subes una vez, y ella solo abre un enlace en su celular y toca "Activar alertas". Nada más que instalar ni configurar de su lado. Como queda en `https://`, el celular también permite notificaciones y mantener la pantalla encendida.

## Antes de empezar

- Una cuenta en GitHub (gratis) y en el hosting que elijas (Render o Railway).
- Opcional: el número y la apikey de WhatsApp (CallMeBot) para que además te llegue el aviso a ti.
- NO subas tu `.env` a GitHub (el `.gitignore` ya lo evita). Los datos secretos se escriben en el panel del hosting.

## Paso 1. Subir la carpeta a GitHub

1. Crea un repositorio **privado** nuevo en GitHub.
2. Sube todos los archivos de esta carpeta (`Dockerfile`, `monitor_adviento.py`, `web_alerta.py`, `render.yaml`, etc.).

## Paso 2A. Render (tiene plan gratis, con una limitación)

1. En render.com: **New +** → **Blueprint** → conecta tu GitHub y elige el repositorio.
2. Render lee `render.yaml`, crea el servicio y genera solo la `ACCESS_KEY`. Te pide `WHATSAPP_PHONE` y `WHATSAPP_APIKEY` (puedes dejarlos vacíos).
3. Cuando termine de desplegar, copia la dirección del servicio (algo como `https://alerta-calendario.onrender.com`) y, en **Environment**, copia el valor de `ACCESS_KEY`.
4. El enlace para ella es: `https://TU-DIRECCION.onrender.com/?k=TU_ACCESS_KEY`

**Limitación del plan gratis:** según la documentación de Render, el servicio se suspende tras 15 minutos sin tráfico y tarda cerca de 60 segundos en despertar. Mientras ella tenga la página abierta, el celular consulta al servidor cada 10 segundos y eso lo mantiene despierto. Pero si nadie la tiene abierta, no revisará la tienda ni mandará WhatsApp. Además el disco es temporal y Render puede reiniciar el servicio en cualquier momento (no pasa nada grave: al reiniciar vuelve a empezar la revisión).

## Paso 2B. Railway (siempre encendido, de pago)

1. En railway.com: **New Project** → **Deploy from GitHub repo** → elige el repositorio (detecta el `Dockerfile`).
2. En **Variables**, agrega `ACCESS_KEY` (una clave larga que inventes) y, si quieres, `WHATSAPP_PHONE` y `WHATSAPP_APIKEY`.
3. En **Settings → Networking**, genera un dominio público.
4. El enlace para ella es: `https://TU-DOMINIO/?k=TU_ACCESS_KEY`

Según la documentación de Railway, el plan Hobby cuesta 5 USD al mes e incluye 5 USD de uso; existe además un plan gratuito con crédito mensual muy pequeño. Revisa los precios vigentes antes de decidir. Si el calendario se lanza pronto, un mes de Hobby es suficiente.

## Paso 3. Lo que le dices a ella

"Abre este enlace, toca el botón morado **Activar alertas** una vez, y deja la pantalla encendida con la página abierta."

Si el celular se bloquea o cambia de app, el navegador puede pausar la página. Para que no dependa de eso, deja el WhatsApp configurado como respaldo (te llega a ti).

## Alternativa sin hosting: tu propio computador

Si prefieres no subir nada: corre `python3 web_alerta.py` en tu computador (que debe estar siempre encendido) y exponlo con un túnel gratuito como Cloudflare Tunnel (`cloudflared tunnel --url http://localhost:8080`). Te da un enlace `https://...` que cambia cada vez que reinicias el túnel, así que hay que volver a mandárselo.

## Variables que acepta el servidor

- `ACCESS_KEY`: clave del enlace (obligatoria si es público).
- `WHATSAPP_PHONE`, `WHATSAPP_APIKEY`: avisos por WhatsApp (opcional).
- `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID`: avisos por Telegram (opcional).
- `KEYWORDS`: palabras que busca (por defecto `adviento,advent,calendario`).
- `WEB_CHECK_SECONDS`: cada cuánto revisa la tienda (por defecto 60, mínimo 30).
- `STORE_URL`: por defecto la web de Trendy Shop.
