# Meridiano – Guías de viaje por Europa

Demo de portafolio: web + PWA de guías de viaje para público latino.

## Qué incluye
- Sitio y guías por destino (París, Roma, Lisboa, Praga, Santorini, Viena) con itinerario, gastronomía y consejos
- Precios en USD, MXN, ARS, COP, CLP y PEN
- Guías gratis y de pago (pasarela simulada: tarjeta, PayPal, Przelewy24, SEPA)
- Guardado sin conexión, instalable como app (manifest + service worker)
- Subida de fotos de usuarios con panel de moderación
- Panel CMS de demostración (destinos, moderación, pedidos)
- Diseño responsive pensado para celular, con modo oscuro

## Archivos
- `index.html`: toda la app (HTML, CSS, JS y fotos incrustadas)
- `manifest.webmanifest`, `sw.js`, `icon-192.png`, `icon-512.png`: PWA

## Probar en local
```
python3 -m http.server 8080
```
Abre http://localhost:8080 (el service worker necesita http o https, no file://).

## Publicar
Sube la carpeta a Netlify, Vercel o GitHub Pages (HTTPS incluido).

## Limitaciones (es una demo)
- Los datos viven en el navegador (localStorage); no hay base de datos ni login real.
- El pago es una simulación; no se conecta con ninguna pasarela.
- Los tipos de cambio son aproximados y fijos.
- Los presupuestos y textos de las guías son de ejemplo.

## Siguiente paso hacia producción
Next.js + Payload CMS + PostgreSQL, almacenamiento de medios en S3/R2, login con roles, pagos reales (Stripe, Mercado Pago, Przelewy24) y tipos de cambio por API.
