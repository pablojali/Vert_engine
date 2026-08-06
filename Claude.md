# Vertical Trail Labs v2 — Arquitectura y plan de trabajo

Este documento es la referencia única del proyecto. Pegalo en Claude Code
(o guardalo como `CLAUDE.md` en la raíz del repo) para que no haya que
re-explicar el contexto en cada sesión.

---

## 1. Filosofía

Vertical Trail Labs no es un blog ni un CMS. Es un motor de inteligencia
de datos (el Engine) cuyo resultado final es una web estática. La web
nunca calcula nada — solo muestra lo que el Engine ya calculó.

```
Engine (Python)  →  JSON  →  Builder (Jinja2)  →  HTML estático  →  Cloudflare Pages
```

---

## 2. Los dos repos

| Repo | Visibilidad | Contenido | Estado actual |
|---|---|---|---|
| `Vert_engine` | Privado | Streamlit en producción + Engine + Builder nuevo | Existe, en uso diario |
| `vertlabs_web` | Público | Solo el `output/` generado, HTML/CSS/JS/JSON | Creado, vacío |

`vertlabs_web` nunca contiene Python, GPX crudos, ni fórmulas. Solo el
resultado final listo para servir.

---

## 3. Estrategia de ramas — CLAVE, leer con atención

Todo el trabajo nuevo pasa en una rama nueva del repo `Vert_engine`:

```bash
git checkout -b web-builder
```

- `main` queda intacto. Streamlit Community Cloud sigue desplegando desde
  `main`, así que la app en producción no se entera de nada de esto hasta
  que decidamos mergear.
- **El Engine actual (`app.py`, scrapers, cálculo de VPI/DMI/ER) NO se
  duplica ni se copia a ningún lado.** Al ser una rama del mismo repo,
  `app.py` ya está disponible tal cual dentro de `web-builder`. Es el
  mismo código, la misma carpeta, sin fork ni copy-paste.
- Esto significa que en la rama `web-builder` podés:
  - seguir corriendo el Streamlit local o remoto exactamente igual que
    siempre (analizar carreras, calcular métricas, etc.)
  - Y en paralelo, ir construyendo `builder/`, `templates/`, `data/` al
    lado, sin que una cosa interfiera con la otra.

**No hace falta "duplicar" el Engine.** La única pieza nueva que falta es
un puente entre el Engine y el Builder: una función de exportación que,
después de que el Streamlit calcule VPI/DMI/ER de una carrera, escriba
esos resultados como `race.json` / `profile.json` dentro de `data/`, en
el formato que el Builder espera. Esa función de export es la que
"alimenta de análisis a la web" — se agrega como una pestaña o botón
más en el Streamlit existente (ej. "Exportar a Web"), no como un Engine
separado.

Cuando el v2 esté probado y listo para reemplazar por completo la
necesidad del v1 (si es que eso pasa algún día), recién ahí se mergea
`web-builder` a `main`. Hasta entonces, ambos conviven en la misma rama
de trabajo sin pisarse.

---

## 4. Estructura de carpetas a construir en `web-builder`

```
Vert_engine/
├── app.py                    ← Streamlit actual, SIN TOCAR
├── (resto del engine actual, scrapers, etc.)  ← SIN TOCAR
│
├── engine/
│   └── metrics/
│       ├── vpi.py            ← lógica de calculate_vpi portada desde app.py
│       ├── dmi.py            ← ídem DMI
│       └── er.py             ← ídem ER
│       (el Builder nunca calcula: solo lee JSON ya resuelto)
│
├── builder/
│   ├── env.py                ← setup de Jinja2 (loader, autoescape, write_page())
│   ├── templates/
│   │   ├── base.html         ← layout compartido (header, nav, footer, meta OG)
│   │   ├── race.html         ← página de carrera
│   │   ├── athlete.html      ← página de atleta
│   │   └── index.html        ← homepage
│   └── generators/
│       ├── race_generator.py     ← glob recursivo sobre data/races/**/race.json
│       ├── athlete_generator.py  ← glob sobre data/athletes/*/profile.json
│       ├── homepage_generator.py
│       ├── search_generator.py   ← genera search.json liviano
│       └── sitemap_generator.py  ← genera sitemap.xml + robots.txt
│
├── data/
│   ├── races/
│   │   └── <circuito>/<año>/<distancia>/
│   │       ├── race.json         ← PÚBLICO, resultado del Engine
│   │       ├── gpx/               ← PRIVADO, nunca se copia a output/
│   │       ├── results/           ← PRIVADO, nunca se copia a output/
│   │       ├── images/            ← PÚBLICO
│   │       └── charts/            ← PÚBLICO
│   └── athletes/
│       └── <slug>/
│           ├── profile.json       ← PÚBLICO
│           ├── images/            ← PÚBLICO
│           └── charts/            ← PÚBLICO
│
├── assets/
│   ├── css/style.css
│   └── js/search.js          ← fetch a /search.json, filtro client-side
│
├── publish.py                 ← UN SOLO comando, ver flujo abajo
└── output/                    ← gitignored, sitio completo generado
```

---

## 5. Flujo de `publish.py`

```
1. race_generator.generate()      → lee data/races/**/race.json, genera HTML, devuelve la lista
2. athlete_generator.generate()   → lee data/athletes/*/profile.json, genera HTML, devuelve la lista
3. homepage_generator.generate(races)
4. search_generator.generate(races, athletes)
5. sitemap_generator.generate(races, athletes)
6. copiar assets/ → output/assets/
7. copiar SOLO images/ y charts/ públicos de data/ → output/
```

Un comando, todo el sitio se regenera desde cero.

---

## 6. Regla de seguridad — no negociable

**Nunca debe llegar a `output/`:**
- código Python
- GPX crudos
- `results/` crudos (JSON intermedios de timing)
- fórmulas o parámetros internos de cálculo

**Solo se publica:**
- HTML, CSS, JS
- imágenes y charts ya generados
- JSON públicos (`race.json`, `profile.json`, `search.json`)

---

## 7. Preview local (antes de publicar nada)

Estamos en GitHub Codespaces, no hay nada instalado en la máquina local.

```bash
cd output
python3 -m http.server 8000
```

No usar `localhost` — abrir la pestaña **Ports** de Codespaces, ahí
aparece el puerto 8000 con una URL pública/privada para ver el sitio en
el navegador, tal como va a verse en producción.

---

## 8. Roadmap — ir en vivo (más adelante, no ahora)

1. Merge de `web-builder` a `main` (no afecta el deploy de Streamlit).
2. Copiar/pushear `output/` a `vertlabs_web`.
3. Conectar `vertlabs_web` a Cloudflare Pages (build command vacío,
   output directory `/`).
4. Probar en el subdominio `*.pages.dev` antes de tocar el dominio real.
5. En Cloudflare → DNS: eliminar los registros de Blogger
   (A records 216.239.32.21/34.21/36.21/38.21 y el CNAME `www` a
   `ghs.google.com`).
6. Agregar `vertlabs.run` como custom domain en el proyecto de Pages.
7. Verificar propagación y SSL.
8. (Opcional, más adelante) GitHub Actions para automatizar
   Engine → publish → push a `vertlabs_web` sin pasos manuales.

---

## 9. Tareas concretas para arrancar ahora

1. `git checkout -b web-builder`
2. Armar la estructura de carpetas de la sección 4
3. Portar `calculate_vpi` / `calculate_dmi` / `calculate_er` desde
   `app.py` a `engine/metrics/` como funciones puras, sin tocar el
   Streamlit original
4. Agregar una función/pestaña de "Exportar a Web" en el Streamlit
   actual que escriba `race.json` / `profile.json` en `data/` con el
   formato que espera el Builder (ver sección 4)
5. Crear 1 `race.json` y 1 `profile.json` de ejemplo a mano para probar
   el pipeline sin depender todavía del export real
6. Correr `publish.py` y confirmar que `output/` se genera sin errores
7. Levantar el preview local (sección 7) y revisar visualmente