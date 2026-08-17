# Pipeline del Sitio Estático

## Propósito
Documentar cómo `publish.py` convierte los JSON ya calculados en
`data/races/**` y `data/athletes/**` en el sitio HTML/CSS/JS completo que
termina en `vertlabs-web`.

## Cómo funciona

### Principio de no duplicación
El Builder (`builder/` + `publish.py`) vive en el mismo repo que el motor
de cálculo, no como un proyecto/fork separado. Las funciones nuevas del
Builder se agregan como funciones de export **dentro de `app.py`** (la tab
"🌐 Exportar a Web") en vez de como un motor paralelo — el mismo `app.py`
que se usa a diario para analizar carreras es el que alimenta los datos que
consume el Builder.

### Comando único
```bash
python publish.py
```
Regenera `output/` completo desde cero (`clean_output()` lo borra primero),
por locale (`en`, `es`, `fr` — inglés en la raíz, los otros bajo
`/es/`/`/fr/`), en este orden por locale:

1. Carga posts (`post_generator.load_posts()`) y los agrupa por
   `race_slug` para poder inyectarlos en las páginas de carrera.
2. `race_generator.generate()` — lee `data/races/**/race.json`, genera una
   página por distancia + una página "hub" por evento (agrupando
   distancias que comparten carpeta `<circuito>/<año>/`) + el índice
   `/races/`.
3. `athlete_generator.generate()` — lee `data/athletes/*/profile.json`,
   genera una página por atleta + el índice `/athletes/`.
4. `post_generator.generate()` — genera las páginas de posts, ya resueltas
   contra su carrera si tienen `race_slug`.
5. `homepage_generator.generate()` — portada.
6. `rankings_generator.generate()` — `/rankings/`.
7. `static_pages_generator.generate()` — `/about/` y `/search/`.
8. `search_generator.generate()` — `search.json` (índice liviano para
   búsqueda client-side).

Una vez, para todo el sitio (no por locale):

9. `sitemap_generator.generate()` — `sitemap.xml` + `robots.txt` con
   `hreflang` entre los 3 idiomas.
10. `copy_assets()` — copia `assets/` → `output/assets/` (CSS/JS
    compartidos, no dependen del idioma).
11. `copy_public_media()` — copia **solo** las carpetas literalmente
    llamadas `images/` o `charts/` de cada carrera/atleta/post →
    `output/media/<kind>/<slug>/`. Nunca toca `gpx/`, `results/`, ni los
    `.json` en sí.

### De `output/` a `vertlabs-web`
El paso 11 es donde se aplica por construcción la regla de seguridad de
`Claude.md` §6 (nunca debe llegar a `output/` código Python, GPX crudo,
resultados crudos, ni parámetros internos de cálculo) — no es una lista de
exclusión que haya que mantener actualizada, es que solo esas dos carpetas
con ese nombre exacto se copian, todo lo demás en `data/` queda afuera por
default.

Desde ahí, el botón "🚀 Publicar sitio" (barra lateral de `app.py`) corre
`publish.py` y mergea `output/` dentro de un checkout local de
`vertlabs-web`, commiteando y pusheando a la rama elegida (`staging` o
`main`). Ver `docs/04-infra/hosting.md` para el detalle de ese paso y el
deploy en Cloudflare Pages.

## Decisiones clave / lecciones aprendidas
- `clean_output()` borra `output/` completo antes de regenerar — evita que
  páginas/media de datos que ya no existen (slugs renombrados, carreras
  eliminadas) queden como basura huérfana indefinidamente.
- Las páginas de evento ("hub" que agrupa varias distancias) se generan
  agrupando por **carpeta física** (`<circuito>/<año>/`), no por el campo
  `name` del JSON — agrupar por texto libre rompe silenciosamente si dos
  ediciones tienen el nombre escrito con variaciones. Ver
  `docs/05-known-issues.md` para el historial de bugs relacionados con
  esto.
- `output/` está en `.gitignore` de `Vert_engine` — nunca se commitea ahí,
  siempre se regenera y se copia aparte al repo público.

## Problemas conocidos
Ver `docs/05-known-issues.md`.

## Archivos relacionados
- `publish.py` — orquestador único
- `builder/env.py` — setup de Jinja2 (`env`, `write_page`, `locale_url`,
  filtros custom)
- `builder/generators/` — un generador por tipo de página
- `builder/templates/` — templates Jinja2
- `builder/i18n.py` — traducciones EN/ES/FR
- `app.py` — `_publish_to_branch`, `_sync_output_to_web_repo` (el puente
  hacia `vertlabs-web`)
