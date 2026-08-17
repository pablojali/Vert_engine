# VertLabs — Documentación Técnica

VertLabs es una plataforma de analítica de rendimiento para ultra-trail
running: convierte datos de carrera (splits oficiales + GPX) en tres
índices propios — VPI, DMI y ER — y publica el análisis como sitio
estático.

```
Vert_engine (privado)            vertlabs-web (público)
  Streamlit app + scraping   →     solo recibe HTML/CSS/JS
  + Builder (Jinja2)              generado por publish.py
        │                                │
        ▼                                ▼
Streamlit Community Cloud        Cloudflare Pages
  (app privada del engine)         (vertlabs.run)
```

Ver `01-architecture/overview.md` para el diagrama completo y el detalle
de cada pieza.

## Índice

### 01 — Arquitectura
- [`overview.md`](01-architecture/overview.md) — los dos repos, los tres
  índices, dónde vive cada cosa
- [`data-flow.md`](01-architecture/data-flow.md) — el camino de un dato
  desde LiveTrail hasta `vertlabs.run`, y la frontera privado/público

### 02 — Engine
- [`api-integration.md`](02-engine/api-integration.md) — integración con
  LiveTrail (y por qué UTMB Live se descartó)
- [`indices-vpi-dmi-er.md`](02-engine/indices-vpi-dmi-er.md) — metodología
  de cálculo de VPI, DMI y ER
- [`gpx-processing.md`](02-engine/gpx-processing.md) — carga del catálogo
  de carreras y procesamiento de tracks GPS
- [`segment-merging.md`](02-engine/segment-merging.md) — cómo se manejan
  los checkpoints sin tiempo registrado
- [`streamlit-app-tabs.md`](02-engine/streamlit-app-tabs.md) — qué hace
  cada una de las 8 tabs de `app.py`

### 03 — Web Builder
- [`static-site-pipeline.md`](03-web-builder/static-site-pipeline.md) —
  cómo `publish.py` genera el sitio estático
- [`data-schema.md`](03-web-builder/data-schema.md) — esquema real de
  `race.json`, `profile.json`, `post.json`
- [`blog-export.md`](03-web-builder/blog-export.md) — export del informe
  HTML completo por corredor (para Blogger)

### 04 — Infraestructura
- [`hosting.md`](04-infra/hosting.md) — Streamlit Community Cloud +
  Cloudflare Pages
- [`hetzner-vps.md`](04-infra/hetzner-vps.md) — VPS provisionado, estado y
  decisión pendiente

### 05 — Problemas Conocidos
- [`05-known-issues.md`](05-known-issues.md)

### Roadmap
- [`../ROADMAP.md`](../ROADMAP.md) — vive en la raíz del repo (no acá
  adentro) porque se actualiza con mucha más frecuencia que esta
  documentación técnica.
