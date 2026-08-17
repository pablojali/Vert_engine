# Visión General de la Arquitectura

## Propósito
VertLabs es una plataforma de analítica de rendimiento para ultra-trail
running. Convierte splits oficiales de carrera (LiveTrail) y/o el track GPS
personal de un corredor en tres índices propietarios — VPI, DMI, ER — y
publica el análisis como sitio estático en `vertlabs.run`.

## Cómo funciona
El sistema tiene dos mitades con visibilidad opuesta, ambas viviendo en el
mismo repo (`Vert_engine`) pero separadas por lo que cada una expone:

```
┌─────────────────────────────┐        ┌──────────────────────────┐
│  Vert_engine (privado)      │        │  vertlabs-web (público)  │
│  ─────────────────────      │        │  ──────────────────────  │
│  app.py (Streamlit, 8 tabs) │        │  Solo HTML/CSS/JS/JSON   │
│  scraping (LiveTrail API)   │  push  │  generados por publish.py│
│  engine/metrics/ (VPI/DMI/ER)├───────►│  Nunca contiene Python,  │
│  builder/ (Jinja2 → HTML)   │ output/│  GPX, ni fórmulas        │
│  data/ (JSON + GPX + media) │        │                          │
└──────────────┬───────────────┘        └─────────────┬────────────┘
               │ deploy                                │ deploy
               ▼                                        ▼
   Streamlit Community Cloud                    Cloudflare Pages
   (app privada del engine)                     (vertlabs.run)
```

- **`Vert_engine`** (privado): la app Streamlit (`app.py`) donde se busca,
  analiza y calcula el rendimiento de cada corredor; el motor de cálculo
  (`engine/metrics/`); y el Builder (`builder/` + `publish.py`) que convierte
  los datos ya calculados en un sitio estático completo dentro de `output/`
  (gitignored, se regenera desde cero en cada publicación).
- **`vertlabs-web`** (público): repo aparte que solo recibe el contenido de
  `output/` — nunca ve el código Python, los GPX crudos, ni los parámetros
  de cálculo. Ver `docs/01-architecture/data-flow.md` para el detalle de esa
  frontera.
- **Streamlit Community Cloud**: hosting de la app privada del engine,
  desplegada automáticamente al pushear a la rama que el deploy tiene
  configurada.
- **Cloudflare Pages**: hosting del sitio público. Dos ramas de
  `vertlabs-web` mapean a dos destinos — `staging` genera una URL de preview
  automática, `main` es lo que sirve `vertlabs.run` (ver
  `docs/04-infra/hosting.md`).

Los tres índices que calcula el motor:

| Índice | Qué mide | Unidad |
|---|---|---|
| **VPI** (Vertical Power Index) | Eficiencia de subida en tramos con pendiente ≥12% | m/h |
| **DMI** (Descent Mastery Index) | Eficiencia de bajada en tramos con pendiente ≤-12% | km/h |
| **ER** (Endurance Rating) | Decaimiento de ritmo entre la primera y segunda mitad de la carrera, medido en km de esfuerzo | Score 0-100 |

Ver `docs/02-engine/indices-vpi-dmi-er.md` para la metodología completa de
cada uno.

## Decisiones clave / lecciones aprendidas
- **Un solo repo de código, dos repos de contenido.** El Builder no es un
  proyecto aparte ni un fork del engine — vive en el mismo `Vert_engine`,
  como funciones de export dentro de `app.py` + el paquete `builder/`. Esto
  evita que el motor de cálculo se duplique o se desincronice entre "la app
  que uso todos los días" y "lo que genera la web".
- **La fuente de datos de carrera es LiveTrail, no UTMB Live.** El proyecto
  arrancó integrando la API de UTMB Live (`utmblive-api.utmb.world`), pero
  esa integración fue removida por completo: UTMB Live es una SPA en React
  que no expone los datos vía fetch directo de forma estable para todas las
  carreras, mientras que LiveTrail (`api.v3.livetrail.net`) es el proveedor
  de timing subyacente, agnóstico de marca, y funciona igual para cualquier
  carrera en esa plataforma. Ver `docs/02-engine/api-integration.md`.
- **El GPX oficial sigue siendo necesario aunque LiveTrail dé splits.**
  LiveTrail entrega tiempos por checkpoint, no la geometría del recorrido
  (pendientes punto a punto). El GPX oficial de la organización es la única
  fuente de esa geometría, y es lo que permite ubicar dónde exactamente
  ocurre cada tramo de pendiente fuerte.
- **La web nunca calcula nada.** `race.json`/`profile.json` ya traen los
  números resueltos; el Builder solo lee y renderiza.

## Problemas conocidos
Ver `docs/05-known-issues.md`.

## Archivos relacionados
- `app.py` — Streamlit app completa (motor + tabs + export)
- `engine/metrics/` — cálculo puro de VPI/DMI/ER, sin dependencia de Streamlit
- `builder/` + `publish.py` — generador del sitio estático
- `Claude.md` — documento de arquitectura original (histórico; ver nota en
  `docs/README.md` sobre qué partes siguen vigentes)
