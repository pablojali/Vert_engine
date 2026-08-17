# Flujo de Datos End-to-End

## Propósito
Trazar el camino completo de un dato, desde que sale de LiveTrail hasta que
aparece en `vertlabs.run`, y marcar exactamente dónde está la frontera
privado/público que nunca debe cruzarse.

## Cómo funciona

### Rama 1 — Terrain Intelligence Engine (privado, dentro de `Vert_engine`)

```
LiveTrail API (api.v3.livetrail.net)
        │  fetch_livetrail_checkpoints() / fetch_runner_by_tenant_and_bib_livetrail()
        ▼
GPX oficial (data/gpx/<carrera>/<año>/*.gpx)  +  checkpoints (data/races_registry.json)
        │  gpx_loader.py (catálogo) + análisis geométrico del GPX (app.py, tab "Race Analysis")
        ▼
DataFrames: geometría de la carrera (df_gpx) × segmentos entre checkpoints (df_segments)
        │  cruce con los splits reales del corredor (df_runner)
        ▼
engine/metrics/indices.py → calculate_runner_indices() / calculate_indices_by_segment()
        │
        ▼
VPI / DMI / ER + tablas de degradación + gráficos Plotly
        │  se muestran en la tab correspondiente de app.py (Streamlit)
        │  y opcionalmente se acumulan en st.session_state['web_export_pool']
        ▼
(sigue en la Rama 2 vía la tab "🌐 Exportar a Web")
```

### Rama 2 — Static Site Builder (público, termina en `vertlabs-web`)

```
st.session_state['web_export_pool'] (resultados ya calculados en memoria)
        │  tab "🌐 Exportar a Web" (app.py) — SOLO serializa, no recalcula nada
        ▼
data/races/<circuito>/<año>/<distancia>/race.json
data/athletes/<slug>/profile.json
        │  publish.py → builder/generators/*.py (Jinja2)
        ▼
output/  (HTML + CSS + JS + JSON públicos, por locale en/es/fr)
        │  botón "🚀 Publicar sitio" en la barra lateral →
        │  git commit + push al repo vertlabs-web (rama 'staging' o 'main')
        ▼
Cloudflare Pages
        ▼
vertlabs.run (rama 'main')  /  URL de preview (rama 'staging')
```

## Decisiones clave / lecciones aprendidas
- **La frontera dura está en `data/`, no en el código.** Todo lo que vive
  bajo una carpeta `images/` o `charts/` dentro de `data/races/**` o
  `data/athletes/**` es público (se copia a `output/media/`); todo lo demás
  en `data/` (GPX, `races_registry.json`, resultados crudos) es privado y
  `publish.py` nunca lo toca. Ver la función `copy_public_media()` en
  `publish.py`, que solo copia carpetas literalmente llamadas `images` o
  `charts` — la regla de seguridad está aplicada por construcción, no por
  una lista de exclusión que alguien podría olvidar actualizar.
- **`race.json`/`profile.json` son el contrato entre las dos ramas.** El
  Builder nunca importa nada de `engine/metrics/` ni recalcula: solo lee
  estos JSON ya resueltos. Esto significa que se puede reconstruir todo el
  sitio (`python publish.py`) sin tocar la API de LiveTrail para nada.
- **`data/races_registry.json` (privado) es distinto de
  `data/races/**/race.json` (público).** El primero es un catálogo interno
  del motor — dónde está el GPX de cada carrera/año/distancia y qué
  checkpoints tiene — usado solo por `gpx_loader.py` para poblar los
  selectores del engine. El segundo es el resultado YA calculado de una
  carrera específica, listo para publicar. Confundirlos fue la causa de más
  de un bug de "carpeta duplicada" durante el desarrollo (ver
  `docs/05-known-issues.md`).
- **El `web_export_pool` vive solo en memoria de la sesión.** Es
  `st.session_state`, no se persiste en disco — si el contenedor de
  Streamlit se reinicia (redeploy, timeout de inactividad) entre calcular
  un corredor y exportarlo, esos resultados en memoria se pierden y hay que
  recalcular. No afecta a lo que YA se exportó a `data/races/**/race.json`.

## Archivos relacionados
- `app.py` — funciones `_web_export_track_result`, `_publish_to_branch`,
  tab `tab_web_export`
- `publish.py` — `copy_public_media()`, `main()`
- `data/gpx_loader.py` — catálogo privado (`races_registry.json`)
- `builder/generators/` — lectura de `data/races/**/race.json` y
  `data/athletes/*/profile.json`
