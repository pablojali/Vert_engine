# Esquema de Datos Públicos

## Propósito
Documentar la forma real de los JSON públicos que el Builder consume:
`race.json`, `profile.json` y `post.json`, con ejemplos tomados
directamente del repo (no inventados).

## Cómo funciona

### `data/races/<circuito>/<año>/<distancia>/race.json`
```json
{
  "slug": "val-d-aran-by-utmb-2026-163k",
  "name": "Val d'Aran by UTMB",
  "year": 2026,
  "distance_km": 160.05165725143127,
  "elevation_gain_m": 11441.0,
  "date": "2026-07-03",
  "location": "Vielha",
  "hero_image": "/media/races/val-d-aran-by-utmb-2026/images/hero.jpg",
  "elevation_profile_image": "/media/races/val-d-aran-by-utmb-2026/charts/elevation_profile.html",
  "athletes": [
    {
      "slug": "santos-gabriel-rueda",
      "name": "Santos Gabriel RUEDA",
      "bib": 5,
      "finish_time": "21:32:05",
      "position": 1,
      "gender_rank": 1,
      "vpi": 976.5,
      "dmi": 11.22,
      "er": 75.8,
      "pace_first_half": null,
      "pace_second_half": null,
      "report": "/media/races/val-d-aran-by-utmb-2026/charts/runners/santos-gabriel-rueda/report.html",
      "charts": [
        {
          "label": "Santos Gabriel Rueda Livetrail Full Analysis",
          "file": "/media/races/val-d-aran-by-utmb-2026/charts/runners/santos-gabriel-rueda/santos-gabriel-rueda-livetrail-full-analysis.html"
        }
      ]
    }
  ]
}
```
Notas de campos:
- `slug` define la URL pública de esa distancia (`/races/<slug>/`) **y** es
  la carpeta que usa `copy_public_media()` para nombrar
  `output/media/races/<slug>/` — si dos exports terminan con `slug`
  distinto para el mismo evento real, sus rutas de media divergen aunque
  vivan en la misma carpeta de disco. Ver `docs/05-known-issues.md`.
- `athletes[].report` / `athletes[].charts[].file` son rutas ya resueltas
  bajo `/media/races/<slug>/charts/runners/<athlete_slug>/...` — el
  Builder no las reconstruye, las toma tal cual vienen del export.
- `gender_rank`, `pace_first_half`, `pace_second_half` son opcionales
  (pueden faltar en exports más viejos).

### `data/athletes/<slug>/profile.json`
```json
{
  "slug": "santos-gabriel-rueda",
  "name": "Santos Gabriel RUEDA",
  "country": "AR",
  "portrait": "/media/athletes/santos-gabriel-rueda/images/portrait.jpg",
  "races": [
    {
      "race_slug": "val-d-aran-by-utmb-2026-163k",
      "race_name": "Val d'Aran by UTMB",
      "year": 2026,
      "distance_km": 160.05165725143127,
      "position": 1,
      "gender_rank": 1,
      "finish_time": "21:32:05",
      "vpi": 976.5,
      "dmi": 11.22,
      "er": 75.8,
      "report": "/media/races/val-d-aran-by-utmb-2026/charts/runners/santos-gabriel-rueda/report.html"
    }
  ],
  "career_avg": { "vpi": 931.6, "dmi": 11.4, "er": 74.9 }
}
```
Notas de campos:
- `country` es el código ISO de 2 letras que trae LiveTrail
  (`runner_info["Country"]`), se renderiza como bandera (imagen, no
  emoji) tanto en el perfil individual como en el listado general de
  `/athletes/` — ver `builder/env.py` (`country_flag_url`).
- `races[].race_slug` **debe coincidir exactamente** con el `slug` del
  `race.json` correspondiente — es la clave de unión entre ambos archivos,
  usada por el Builder para armar el link "ver carrera" desde el perfil.
- `career_avg` se recalcula en cada export como promedio simple de todas
  las carreras que el atleta tiene cargadas en `races[]` hasta ese momento
  (no un promedio ponderado por distancia/dificultad).

### `data/posts/<slug>/post.json`
```json
{
  "slug": "monterosa-walserwaeg-120k-pre-race",
  "title": "Monterosa Walserwaeg - 120k -  Pre-Race",
  "date": "2026-08-13",
  "category": "Pre-Race",
  "race_slug": "monterosa-walserwaeg-120k",
  "cover_image": "/media/posts/monterosa-walserwaeg-120k-pre-race/images/cover.png",
  "blocks": [
    { "type": "text", "title": "Race Overview", "content": "..." },
    { "type": "html", "title": "Optional heading", "content": "..." },
    { "type": "image", "src": "...", "caption": "..." },
    { "type": "top10", "...": "..." }
  ]
}
```
`race_slug` es opcional (un post puede ser independiente, sin carrera
asociada); cuando está presente debe coincidir con el `slug` del
`race.json` de esa distancia, igual que en `profile.json`. `blocks[]` es
una lista ordenada de bloques de contenido de 4 tipos: `text`, `html`,
`image`, `top10` — el mismo editor de bloques que usa la tab "Posts" y la
tab "Exportar a Web" (análisis de carrera).

**`html.title` (opcional, agregado 2026-09-02):** igual que `text.title`,
renderiza como un `<h2>` antes del HTML embebido. Antes de esto, poner un
título arriba de un gráfico/HTML embebido requería un bloque `text` aparte
solo para el título (contenido vacío, únicamente el título) — un bloque
extra que reordenar/borrar junto con el de `html` cada vez. Con
`html.title` alcanza un solo bloque. Retrocompatible: un `html` sin
`title` (todo el contenido existente) sigue renderizando exactamente igual
que antes (el `<h2>` es condicional). Ver `app.py` -
`_render_block_editor_ui()` / `_collect_blocks_from_state()`, y
`builder/templates/_blocks.html`.

## Decisiones clave / lecciones aprendidas
- **No hay un esquema JSON formal (JSON Schema) ni validación automática**
  de estos archivos — la única "validación" es que el código de
  `builder/generators/` asume ciertos campos y falla si faltan de forma
  inesperada. Cualquier cambio de forma en estos JSON debe revisarse contra
  los generators que los leen.
- `race_slug`/`slug` como clave de unión textual (no un ID numérico ni una
  referencia por carpeta) es la causa raíz de varios bugs de "carrera
  duplicada" o "link roto" documentados en `docs/05-known-issues.md` — dos
  exports del mismo evento real con un `slug` ligeramente distinto (por un
  nombre reescrito entre sesiones) generan silenciosamente una segunda
  identidad para el mismo evento.

## Problemas conocidos
Ver `docs/05-known-issues.md`.

## Archivos relacionados
- `builder/generators/race_generator.py`, `athlete_generator.py`,
  `post_generator.py` — lectura de estos JSON
- `app.py` — tab "Exportar a Web" (escritura de `race.json`/`profile.json`),
  tab "Posts" (escritura de `post.json`)
