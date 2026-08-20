# VertLabs — Roadmap

Última actualización: 2026-08-20

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
- [ ] Backfill de género: el pipeline ya captura `gender` (parseado de
      `Category`, ej. "SE H"/"SE F") para exports NUEVOS, pero los 246
      atletas ya publicados no lo tienen — necesitan reexportarse desde
      Top Runners/Runner Metrics para que el filtro Men/Women en
      `/athletes/` los incluya

## ✅ Resueltos recientemente (bugs)
- [x] Entrada duplicada de Monterosa en `races_registry.json` (dos slugs
      para el mismo evento, uno con checkpoints del 90K pisando al 120K) —
      causaba VPI/DMI/ER rotos para corredores de esa carrera; entrada mala
      + GPX huérfano eliminados, y el Checkpoint Fetcher ahora tiene un
      desplegable de "carrera existente" para que esto no se repita por
      typo de slug (ver `docs/05-known-issues.md`)
- [x] Falso positivo en "Exportar a Web": "Marathon du Mont Blanc" se
      emparejaba con la carpeta ya publicada de "Trail du Saint-Jacques"
      porque solo compartían la preposición francesa "du" - la lista de
      palabras genéricas de `_find_existing_race_folder` solo cubría
      inglés. Ahora incluye conectores de francés/italiano/español/alemán
      (ver `docs/05-known-issues.md`)

## 📋 Próximo (backlog priorizado)
- [ ] Filtrado de atletas por nacionalidad en `/athletes/` (la data ya
      está disponible - mismo patrón que género/carrera/año, que ya
      tienen su filtro)
- [ ] Decidir uso del Hetzner VPS: cron scraping de LiveTrail/UTMB o baja
      del servicio (ver `docs/04-infra/hetzner-vps.md`)

## 💡 Ideas / mejoras futuras (sin priorizar)
- [ ] (añadir según surjan)

## ✅ Completado recientemente
- [x] Búsqueda + filtros + paginación en `/athletes/` (vanilla JS, sin
      dependencias nuevas): búsqueda en vivo por nombre (con fold de
      acentos), filtro por evento (agrupado como `/races/`, no por
      distancia - 1 sola entrada para Val d'Aran, 1 sola para Lavaredo),
      por año, y por género (Men/Women). Género es dato nuevo: se parsea
      de `Category` de LiveTrail ("SE H"/"SE F" confirmado real) y se
      guarda igual que `country` - los 246 atletas ya publicados no lo
      tienen todavía, van completándose a medida que se reexportan.
      Paginación de 100 + "Load more"; los filtros muestran todos los
      resultados directo (el conjunto más grande filtrado, por evento o
      año, está bien por debajo de 100).
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
- [x] Cross-linking carrera↔atleta (5 pasos, validado en staging antes de
      producción): tabla completa de corredores en la página de carrera Y
      en la de evento (Pos/Bib/Athlete/Time/VPI/DMI/ER, reusando estilos
      del Top 10); ordenamiento por click (vanilla JS, sin dependencias);
      CTA dinámico al final de cada Top 10 en los posts ("Ver los N
      corredores analizados en esta carrera →"); conteo de corredores
      analizados en las tarjetas de `/races/`. 0 links rotos verificados
      sobre 261 referencias corredor↔carrera en las 3 locales. De paso,
      arreglado un "None · None" preexistente en el header de carrera/
      evento cuando falta location/date.
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
