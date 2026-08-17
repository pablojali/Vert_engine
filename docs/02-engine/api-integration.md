# Integración con LiveTrail

## Propósito
Documentar cómo el motor obtiene checkpoints y splits de corredores, y por
qué la fuente de datos es LiveTrail y no UTMB Live.

## Cómo funciona

### UTMB Live: descartado
El proyecto integró originalmente `utmblive-api.utmb.world`. Esa integración
fue removida por completo del código (funciones `extract_runner_id`,
`extract_tenant`, `fetch_runner_by_tenant_and_bib`, `scrape_runner_splits`
— ya no existen en `app.py`). Motivo: `live.utmb.world` es una SPA en React
que no expone checkpoints/km de forma estable vía la API pública, y el
endpoint de corredor de UTMB Live no trae nombres de checkpoints ni
distancia — solo campos de timing/ranking.

### LiveTrail: fuente única actual
`api.v3.livetrail.net` es el proveedor de timing subyacente que usa UTMB
Live puertas adentro, pero es agnóstico de marca: funciona igual para
cualquier carrera servida en esa plataforma, tenga o no branding UTMB. Todo
el motor usa hoy exclusivamente LiveTrail.

**Checkpoints de una carrera** — `fetch_livetrail_checkpoints(race_id, tenant, url)`:
```python
GET {url}?raceId={race_id}
Headers: X-Tenant: {tenant}, Origin/Referer: https://{subdomain}.v3.livetrail.net/
```
Devuelve la lista cruda de puntos (`pointId`, `name`, `distance`,
`elevationGain`). `url` normalmente es
`https://api.v3.livetrail.net/api/events/points`.

**Datos de un corredor** — `fetch_runner_by_tenant_and_bib_livetrail(tenant, bib, race_id)`:
requiere DOS pedidos, confirmado por descubrimiento manual del endpoint:
```python
GET /api/events/runners/{bib}?raceId={race_id}          # nombre, categoría, club, status, ranking
GET /api/events/runners/{bib}/detail?raceId={race_id}    # passings completos por checkpoint
```
Ambos con el mismo header `X-Tenant` **combinado** (ej. `"aranbyutmb_2026"`)
— la variante separada `X-Tenant`/`X-Year` devuelve 400.

**Formato del `X-Tenant`:** `{slug_de_la_url}_{año}`, ej. `aranbyutmb_2026`.
Se deriva del subdominio de la URL de LiveTrail (`https://aranbyutmb.v3.livetrail.net/...`),
**no** del campo `race_slug_api` interno de `races_registry.json` (ese campo
es un valor distinto, usado solo para otros fines del registro).

`Origin`/`Referer` se construyen como
`https://{subdomain}.v3.livetrail.net/`, donde `subdomain` es el tenant sin
el sufijo `_{año}` (`tenant.rsplit("_", 1)[0]`).

**Parseo de URLs** — `parse_livetrail_url(url)` (usado por los campos
"pegá el link" de las tabs Checkpoint Fetcher / Top Runners) extrae tenant y
race ID de varias formas de URL de LiveTrail conocidas (parámetros
`e=`/`c=`, o subdominio + año en la ruta), devolviendo `{}` cuando no
reconoce el formato — nunca un valor adivinado a medias.

**Campos adicionales del corredor** (agregados durante el desarrollo de este
sesión, no en la integración original):
- `nationality` → país en formato ISO de 2 letras (`runner_info["Country"]`)
- `picture` → un ID opaco, no una URL. La foto real se sirve desde
  Cloudinary bajo la cuenta de UTMB World:
  `https://res.cloudinary.com/utmb-world/image/upload/q_auto/f_auto/c_scale,w_300/c_fill,g_auto/v1/worldseries/Members/{picture_id}`
  (patrón confirmado contra una URL real, no documentado por LiveTrail/UTMB
  World en ningún lado público — si cambia, `_livetrail_picture_url()` es
  el único lugar a tocar).

## Decisiones clave / lecciones aprendidas
- Las llamadas van con `requests` directo (headers + `requests.get`), sin
  Playwright/Chromium ni scraping de HTML — más liviano y sin dependencias
  frágiles en Streamlit Community Cloud.
- `Speed`/`Pace` por checkpoint no están expuestos por el endpoint de
  corredor de LiveTrail (sí lo estaban en UTMB Live). No afecta a VPI/DMI/ER,
  que se calculan desde `Accumulated Time`, no desde esas columnas — quedan
  simplemente en blanco en la tabla de splits.
- **(Histórico, ya no aplica)** Con la integración de UTMB Live existía un
  `KeyError: 'Rest'` cuando un corredor no tenía descanso registrado en
  ningún checkpoint. El código actual de LiveTrail ya lee ese campo de
  forma defensiva (`p.get("restTime")`, nunca indexado directo), así que
  esta clase de error no debería reproducirse — se deja la nota por si
  aparece una variante nueva del mismo patrón en otro campo.

## Problemas conocidos
Ninguno abierto específico de esta integración. Ver `docs/05-known-issues.md`
para el estado general.

## Archivos relacionados
- `app.py` — `fetch_livetrail_checkpoints`, `fetch_runner_by_tenant_and_bib_livetrail`,
  `scrape_runner_splits_livetrail`, `parse_livetrail_url`, `_livetrail_picture_url`
- `scripts/utmb_checkpoints_fetcher.py` — snippet histórico de integración
  (instrucciones de copy-paste manual); la implementación real y viva está
  en `app.py`, este archivo no se importa desde ningún lado
