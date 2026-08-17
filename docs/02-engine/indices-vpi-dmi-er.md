# VPI / DMI / ER — Metodología de Cálculo

## Propósito
Documentar la lógica real de cálculo de los tres índices propietarios,
incluyendo las decisiones de diseño que evitan tablas vacías y datos
diluidos — no solo la fórmula final, sino el porqué de cada paso intermedio.

## Cómo funciona

### Definiciones

| Índice | Criterio geométrico | Fuente de datos | Unidad |
|---|---|---|---|
| **VPI** — Vertical Power Index | Pendiente ≥ 12% | GPX oficial segmentado por checkpoints | m/h (VAM) |
| **DMI** — Descent Mastery Index | Pendiente ≤ -12% | GPX oficial segmentado por checkpoints | km/h |
| **ER** — Endurance Rating | Split al 50% del total de km de esfuerzo (Km_E) | Splits oficiales + perfil GPX maestro | Score 0-100 |

`STRONG_SLOPE_THRESHOLD = 12` (`engine/metrics/segments.py`) es la única
constante que define "pendiente fuerte" en todo el sistema.

### Fórmulas
```
VPI = Σ(desnivel+ en tramos con pendiente ≥12%) / Σ(tiempo del corredor en esos tramos)
DMI = Σ(distancia en tramos con pendiente ≤-12%) / Σ(tiempo del corredor en esos tramos)

Total_Km_E   = Distancia_total_km + (Desnivel+_total_m / 100)
Effort_Pace  = Tiempo_transcurrido_min / (Distancia_tramo_km + Desnivel+_tramo_m/100)
Decaimiento% = ((Effort_Pace_2da_mitad / Effort_Pace_1ra_mitad) - 1) * 100
ER           = 100 - (Decaimiento% * coeficiente_de_ponderación_por_distancia)
```

### El problema que resuelve el "effort-share": tablas vacías
Con checkpoints espaciados varios km, la pendiente *promedio* de un tramo
completo casi nunca supera ±12%, aunque ese tramo contenga un muro
empinado real mezclado con terreno más llano — exigir que el promedio del
tramo entero califique deja la tabla de degradación casi vacía.

La solución (`calculate_indices_by_segment()` en `engine/metrics/indices.py`)
reparte el tiempo del corredor en el tramo **proporcionalmente al esfuerzo**
de cada punto del GPX dentro de ese tramo (mismo concepto de km de esfuerzo
que usa ER: distancia + desnivel+/100), no a la distancia cruda. Los puntos
de subida empinada pesan más por km que los llanos, así que esto no es solo
un promedio disfrazado: estima cuánto del tiempo del corredor en ese tramo
se gastó plausiblemente en el terreno que sí califica, y calcula una
velocidad/VAM real solo sobre esa porción.

El VPI/DMI global de toda la carrera se reconstruye **sumando** las
contribuciones de cada tramo así calculadas (`calculate_runner_indices()`),
no filtrando tramos completos por su pendiente media — un tramo fusionado
(ver `docs/02-engine/segment-merging.md`) que combina una subida real
seguida de una bajada puede tener una pendiente promedio muy por debajo de
12% aunque contenga una subida genuina; filtrar por ese promedio diluido
la haría desaparecer del cálculo global.

### Normalización 0-100 para el gráfico de degradación
`normalize_segment_index()` (`engine/metrics/segments.py`) expresa cada
serie (VPI o DMI por tramo) contra su primer valor válido = 100, para que
la curva de degradación se pueda leer en una escala comparable
independientemente del ritmo absoluto del corredor.

### Windowing en datos GPS de alta frecuencia
Para tracks personales muestreados a alta frecuencia (ej. ~1 muestra/seg de
un reloj GPS), el cálculo GPS-medido (`build_runner_slope_windows()`, usado
por la tab "GPX Metrics") agrupa el track en ventanas de distancia fija
—**500m por defecto**, rango estable entre 250m y 2000m según los propios
hallazgos de VertLabs sobre el GPX oficial— y calcula, por ventana, el
cambio de elevación neto (cancela el ruido punto a punto del altímetro) y
el tiempo real transcurrido en esa ventana, antes de aplicar los umbrales
de pendiente fuerte.

## Decisiones clave / lecciones aprendidas
- La constante de pendiente fuerte (12%) es única y centralizada — cambiar
  el criterio geométrico es un solo lugar, no buscar el número repetido en
  varios archivos.
- El coeficiente de ponderación por distancia de ER (`distance_weighting_coef`)
  existe como parámetro en todas las funciones de cálculo, pero **ningún
  caller actual lo pasa distinto de `1.0`** (confirmado en `app.py` y
  `engine/metrics/`) — queda ahí como punto de extensión ya modelado, sin
  usarse todavía para ponderar carreras cortas vs. largas de forma distinta.
- Los checkpoints sin tiempo registrado para un corredor puntual (aid
  stations que no escanean dorsal) no se filtran silenciosamente — se
  fusionan con los tramos vecinos primero. Ver
  `docs/02-engine/segment-merging.md`.

## Problemas conocidos
Ver `docs/05-known-issues.md`.

## Archivos relacionados
- `engine/metrics/indices.py` — `calculate_runner_indices()`,
  `calculate_indices_by_segment()`
- `engine/metrics/segments.py` — `STRONG_SLOPE_THRESHOLD`,
  `merge_segments_with_runner_times()`, `normalize_segment_index()`
- `engine/metrics/vpi.py`, `dmi.py`, `er.py` — accesores finos sobre
  `calculate_runner_indices()` (no reimplementan el cálculo)
- `trail_metrics_config.py` — definiciones/fórmulas en formato de
  documentación para mostrar en la UI (`INDEX_CONFIG`), separado del
  cálculo real
- `app.py` — `build_runner_analysis_bundle()` (punto de entrada compartido
  por las tabs "Runner Metrics" y "Top Runners")
