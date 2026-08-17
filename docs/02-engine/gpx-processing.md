# Procesamiento de GPX

## Propósito
Documentar cómo el motor carga y valida el catálogo de carreras/GPX
oficiales, y cómo procesa tracks GPS personales de corredores.

## Cómo funciona

### Catálogo de carreras — `data/gpx_loader.py`
Capa de acceso de solo lectura sobre `data/races_registry.json` (privado,
distinto de `data/races/**/race.json`, ver
`docs/01-architecture/data-flow.md`). Jerarquía: **carrera → año →
distancia** — el año se elige antes que la distancia porque la oferta de
distancias cambia de edición en edición (ej. una carrera puede ofrecer
80K+120K un año y 100K+160K al siguiente).

Funciones principales:
- `load_registry()` — carga y cachea en memoria (`@lru_cache(maxsize=1)`)
  todo `races_registry.json`; el registro solo cambia entre deploys, no
  dentro de una sesión.
- `get_carreras()` / `get_anios(slug)` / `get_distancias(slug, año)` —
  listas para poblar los selectores en cascada.
- `get_carrera_info(slug, año, distancia)` — el bloque completo
  (`gpx_file`, `race_slug_api`, `checkpoints`) para esa combinación exacta;
  lanza `KeyError` con mensaje claro si no existe.
- `get_gpx_path(...)` — ruta absoluta al GPX, lista para `gpxpy.parse()`;
  lanza `FileNotFoundError` si el registro apunta a un archivo que no está
  commiteado.
- `build_cascading_selector(st, key_prefix)` — helper de UI que arma los 3
  `st.selectbox` encadenados (única función de este módulo que toca
  Streamlit directamente).

### Claves de distancia deben ser numéricas
`get_distancias()` ordena las distancias con
`sorted(distancias, key=lambda d: float(d), reverse=True)`. Una clave de
distancia no numérica en el registro (ej. escribir el `race_slug_api` por
error en el campo "Distancia (clave)" del tab Checkpoint Fetcher, algo como
`"SDV120"` en vez de `"120"`) hace que `float(d)` lance `ValueError` y
rompe el selector para **toda** esa carrera/año, no solo esa distancia —
porque el sort falla antes de poder filtrar. No hay validación explícita en
el punto de entrada (el tab Checkpoint Fetcher) que impida guardar una
clave así; el error solo aparece después, al intentar listar distancias.

### Análisis geométrico del GPX oficial (tab "Race Analysis")
Parsea el GPX con `gpxpy`, calcula distancia acumulada/elevación/pendiente
punto a punto, y clasifica cada punto en categorías de pendiente (fuerte
subida/bajada ≥12%/≤-12%, moderada 5-12%, llano) y de altitud. Esta
clasificación geométrica es la base que después se cruza con los splits
del corredor para calcular VPI/DMI (ver
`docs/02-engine/indices-vpi-dmi-er.md`).

### Track GPS personal (tab "GPX Metrics")
`process_runner_gpx_with_time(file)` parsea un GPX personal (con
timestamps reales, ej. exportado de un reloj Garmin/COROS) en una tabla
punto a punto de distancia acumulada / elevación / tiempo transcurrido real.
A diferencia del GPX oficial, **no** calcula pendiente punto a punto aquí
mismo — eso se hace después con ventanas de distancia fija
(`build_runner_slope_windows`, ver
`docs/02-engine/indices-vpi-dmi-er.md#windowing-en-datos-gps-de-alta-frecuencia`),
porque un track a ~1 muestra/segundo está dominado por ruido de
altímetro/GPS si se calcula punto a punto. Si el GPX no tiene ningún punto
con `<time>`, lanza `ValueError` con un mensaje explícito pidiendo un track
grabado (no un archivo de ruta/curso sin timestamps).

## Decisiones clave / lecciones aprendidas
- El registro cachea con `lru_cache` — si se edita `races_registry.json`
  por fuera de la tab Checkpoint Fetcher (a mano, o vía git pull) dentro de
  la misma sesión de Streamlit ya corriendo, hace falta
  `gpx_loader.load_registry.cache_clear()` para que el cambio se vea sin
  reiniciar la app (la tab Checkpoint Fetcher ya llama a esto después de
  guardar).
- El análisis geométrico del GPX oficial y el procesamiento del GPX
  personal son dos pipelines separados con distinta granularidad de
  pendiente (punto a punto vs. ventaneado) — no comparten la misma función
  de cálculo de slope, aunque ambos alimentan finalmente el mismo cálculo
  de VPI/DMI.

## Problemas conocidos
- Claves de distancia no numéricas en `races_registry.json` rompen el
  selector de esa carrera/año completo (ver arriba). Sin validación en el
  punto de carga. Ver `docs/05-known-issues.md`.

## Archivos relacionados
- `data/gpx_loader.py`
- `app.py` — `process_runner_gpx_with_time`, `build_runner_slope_windows`,
  análisis geométrico en la tab `tab_race`
- `data/races_registry.json` — catálogo privado
