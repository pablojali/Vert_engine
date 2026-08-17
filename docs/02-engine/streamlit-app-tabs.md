# Estructura de `app.py` — Tabs de Streamlit

## Propósito
Mapear las 8 tabs reales de la app Streamlit: qué hace cada una, qué le
pide al usuario, qué claves de `session_state` usa, y qué funciones
invoca — como referencia rápida para no tener que releer 4000+ líneas de
`app.py` cada vez.

## Cómo funciona
Definidas en una sola línea:
```python
tab_race, tab_runner_lt, tab_gpx, tab_comparison, tab_top, tab_checkpoints, tab_web_export, tab_posts = st.tabs(
    ["🗺️ Race Analysis", "🏃 Runner Metrics (LiveTrail)", "🛰️ GPX Metrics",
     "⚖️ UTMB vs GPX", "🏆 Top Runners", "🧩 Checkpoint Fetcher",
     "🌐 Exportar a Web", "📰 Posts"]
)
```

### 1. 🗺️ Race Analysis (`tab_race`)
Análisis geométrico del GPX oficial: selector en cascada
carrera/año/distancia (`build_cascading_selector`), botón "Use this race
for analysis" que fija `session_state["active_race_tab1"]`, y desde ahí
renderiza distancia total, desnivel, clasificación por pendiente y por
altitud, y gráficos. Al analizar, guarda el resultado en
`session_state["saved_races"][pool_key]` (dict con `df`, `df_segments`,
`total_km`) — esa es la "biblioteca de carreras cargadas" que consumen
todas las demás tabs (Runner Metrics, GPX Metrics, Top Runners).

### 2. 🏃 Runner Metrics (LiveTrail) (`tab_runner_lt`)
Pega un link de LiveTrail de un corredor → `scrape_runner_splits_livetrail()`
→ cruza contra la carrera activa (`build_runner_analysis_bundle()`) → VPI,
DMI, ER, gráficos de degradación, y botón de descarga del informe completo
(`build_full_runner_report_html()`). El resultado se acumula
automáticamente en `session_state["web_export_pool"]` vía
`_web_export_track_result()`, listo para la tab "Exportar a Web".
`session_state` claves propias: `runner_metrics_df_lt`, `runner_info_lt`,
`lt_fetch_error`/`lt_fetch_warning`, `estimated_degradation_df_lt`,
`estimated_degradation_race_lt`, `estimated_global_indices_lt`.

### 3. 🛰️ GPX Metrics (`tab_gpx`)
Mismos índices que la tab anterior, pero medidos directamente desde el GPX
personal del corredor (con timestamps reales) en vez de estimarlos por
checkpoint — no necesita ningún link de LiveTrail.
`session_state`: `gpx_error`/`gpx_warning`, `real_degradation_df`,
`real_metrics_race`, `real_global_indices`.

### 4. ⚖️ UTMB vs GPX (`tab_comparison`)
**No pide ningún input propio.** Compara lado a lado lo que ya calcularon
las tabs 2 y 3 para el mismo corredor/carrera (lee
`estimated_*`/`real_*` de `session_state`) — pide cargar ambas primero si
falta alguna, o si son de carreras distintas.

### 5. 🏆 Top Runners (`tab_top`)
Fetch masivo: pega un link de LiveTrail (autocompleta tenant/race ID) + una
lista de dorsales (uno por línea o separados por coma) → trae y calcula
VPI/DMI/ER/foto/país de cada uno en un solo paso. Muestra:
- Tabla rápida de copiar/pegar (foto, tiempo, país, VPI/DMI/ER, ritmo 1ra/2da
  mitad) lista para pegar en Excel.
- Un botón de descarga del informe completo por corredor (no un zip).
- Excel combinado (geometría de carrera compartida + columnas de cada
  corredor lado a lado).
- 3 gráficos de progresión (posición, VPI, DMI) a lo largo de la carrera.

Cada corredor fetcheado entra automáticamente al `web_export_pool`.
`session_state`: `top_tenant_input`, `top_race_id_input`, `top_warning`,
`top_errors`, `top_results`, `top_reports`, `top_bibs_requested`,
`top_race_used`, `top_race_data_used`.

### 6. 🧩 Checkpoint Fetcher (`tab_checkpoints`)
Da de alta una carrera/año/distancia nueva (o corrige una existente) en
`data/races_registry.json` — el catálogo privado que usan las tabs de
análisis. Pega un link de resultados en vivo → autocompleta Race ID/Tenant
→ botón "Fetch checkpoints" trae la lista real → completa
nombre/slug/año/distancia → guarda en el registry + crea la carpeta del
GPX (subida opcional ahí mismo). **Solo escribe en el disco local del
contenedor** — no hace commit/push por sí sola, eso lo hace el botón
"Publicar" de la barra lateral (ver `docs/04-infra/hosting.md`).
`session_state`: `cf_tenant_input`, `cf_race_id_input`,
`cf_carrera_slug_input`, `cf_raw_points`, `cf_fetch_error`.

### 7. 🌐 Exportar a Web (`tab_web_export`)
El puente entre el Engine y el Builder. **No recalcula nada**: toma todo
lo que ya se acumuló en `session_state["web_export_pool"]` (desde las tabs
2 y 5) y lo serializa como `data/races/<carpeta>/<año>/<distancia>/race.json`
+ `data/athletes/<slug>/profile.json`, con merge no destructivo contra lo
que ya exista en disco (una carrera se puede re-exportar con más corredores
sin perder los que ya estaban). También adjunta automáticamente el
informe HTML completo y la foto de cada corredor (ver
`docs/03-web-builder/static-site-pipeline.md`).

### 8. 📰 Posts (`tab_posts`)
Editor de bloques (texto/HTML/imagen/Top 10) para artículos del blog
(pre-race analysis, race analysis, etc.), enlazados opcionalmente a una
carrera vía `race_slug`. Guarda en `data/posts/<slug>/post.json`.
`session_state`: `post_title_input`, `post_slug_input`, más las claves de
`_init_block_order`/`_render_block_editor_ui` (editor de bloques
compartido con la Exportar a Web para el "Análisis" de carrera).

## Decisiones clave / lecciones aprendidas
- Las tabs 2 (LiveTrail estimado) y 3 (GPX medido) son deliberadamente
  independientes — cada una calcula con su propia función y guarda en sus
  propias claves de `session_state` (`estimated_*` vs `real_*`) — para que
  la tab 4 pueda comparar una contra la otra sin que una pise a la otra.
- Toda tab que muestra resultados calculados los renderiza a partir de
  `session_state`, nunca condicionado solo a "¿se acaba de clickear el
  botón de fetch?" — necesario porque cualquier otro botón en pantalla
  (incluidos los de descarga) dispara un rerun completo de Streamlit, y
  si el render dependiera del flag transitorio del click, los resultados
  desaparecerían al clickear cualquier otra cosa.
- `_web_export_track_result()` es el único punto de entrada al
  `web_export_pool`, llamado desde las tabs 2 y 5 — mantiene ese
  diccionario en un solo formato consistente sin importar de qué tab vino
  el corredor.

## Problemas conocidos
Ver `docs/05-known-issues.md`.

## Archivos relacionados
- `app.py` — todo lo anterior vive en este único archivo, en bloques
  `with tab_x:` claramente delimitados con comentarios `# TAB N: ...`
