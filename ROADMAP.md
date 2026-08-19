# VertLabs — Roadmap

Última actualización: 2026-08-19

## 🔥 En progreso
- [ ] Auto-adjuntado del informe HTML al exportar corredores (tab "Exportar
      a Web") — la foto y el país ya se auto-adjuntan, el informe todavía
      no (detalle en `docs/05-known-issues.md`)

## 🐛 Bugs conocidos
- [ ] ER inflado (>100) en carreras con subida concentrada + tramo fácil —
      causa identificada, corrección pendiente (decisión: dejarlo por
      ahora), ver `docs/05-known-issues.md`
- [ ] Auto-adjuntado del informe HTML — ver arriba y
      `docs/05-known-issues.md`
- [ ] Lavaredo 80K — posible checkpoint inicial sin datos (sin confirmar
      contra el estado actual del repo, ver `docs/05-known-issues.md`)

## ✅ Resueltos recientemente (bugs)
- [x] Entrada duplicada de Monterosa en `races_registry.json` (dos slugs
      para el mismo evento, uno con checkpoints del 90K pisando al 120K) —
      causaba VPI/DMI/ER rotos para corredores de esa carrera; entrada mala
      + GPX huérfano eliminados, y el Checkpoint Fetcher ahora tiene un
      desplegable de "carrera existente" para que esto no se repita por
      typo de slug (ver `docs/05-known-issues.md`)

## 📋 Próximo (backlog priorizado)
- [ ] Filtrado de atletas por nacionalidad en `/athletes/` (la data
      — código de país por atleta — ya está disponible desde el export
      automático; falta la UI/lógica de filtro en el Builder)
- [ ] Decidir uso del Hetzner VPS: cron scraping de LiveTrail/UTMB o baja
      del servicio (ver `docs/04-infra/hetzner-vps.md`)
- [ ] Endurecer el emparejamiento de carpeta/slug al exportar una carrera,
      para reducir aún más el riesgo de colisión entre eventos distintos
      (ver "Colisión de slug/carpeta" en `docs/05-known-issues.md`)

## 💡 Ideas / mejoras futuras (sin priorizar)
- [ ] (añadir según surjan)

## ✅ Completado recientemente
- [x] Pipeline completo del Static Site Builder (Python → JSON → Jinja2 →
      HTML → Cloudflare Pages), en uso diario
- [x] Migración completa de UTMB Live a LiveTrail como única fuente de
      datos de carrera (checkpoints + splits de corredor)
- [x] Automatización de "Top Runners": fetch masivo de dorsales con VPI/DMI/ER,
      foto (Cloudinary/LiveTrail) y país (bandera) auto-adjuntados,
      tabla de copiar/pegar lista para Excel
- [x] Tab "Engine Live": análisis de campo completo (rango de bib, hasta
      1000) con Movers, top VPI/DMI/ER y abandonos con buen rendimiento;
      fetch paralelizado (10 bibs a la vez) en vez de secuencial
- [x] Checkpoint Fetcher: desplegable de carrera existente (autocompleta
      nombre/slug y bloquea el slug para edición manual) para sumar una
      distancia o actualizar el GPX sin arriesgar una entrada duplicada
- [x] i18n EN/ES/FR en todo el sitio público
- [x] Rediseño visual: header centrado, paleta cyan/verde/naranja,
      carrusel de posts con ajuste de imagen por altura + navegación
- [x] Guard contra carpetas de carrera duplicadas al exportar (matching
      por año + distancia + nombre, ver `docs/05-known-issues.md`)
- [x] Estructura de documentación técnica (`docs/` + este `ROADMAP.md`)

---

*Este archivo vive en la raíz del repo (no dentro de `docs/`) porque se
espera que se actualice con mucha más frecuencia que la documentación
técnica — cada sesión de trabajo debería dejarlo reflejando el estado
real.*
