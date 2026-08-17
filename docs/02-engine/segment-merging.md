# Fusión de Segmentos (Segment Merging)

## Propósito
Documentar cómo el motor evita perder tramos enteros de carrera del
cálculo de índices cuando un checkpoint intermedio no tiene tiempo
registrado para un corredor puntual.

## Cómo funciona
Las aid stations que reparten agua/comida pero no escanean el dorsal del
corredor dejan un "agujero": el checkpoint existe en la geometría oficial
de la carrera, pero ese corredor específico no tiene una hora de paso ahí.

Sin manejo especial, esto rompería el cálculo de cualquier tramo que use
ese checkpoint como extremo — por ejemplo, un tramo P0→P12 que es una
subida real y empinada desaparecería por completo del cálculo apenas P12
no tenga tiempo, aunque el corredor SÍ tenga hora conocida en P0 y en el
siguiente checkpoint que sí registra (digamos P16).

`merge_segments_with_runner_times(df_segments, df_runner)`
(`engine/metrics/segments.py`) resuelve esto fusionando P0→P12→P16 en un
único segmento P0→P16:
1. Recorre los segmentos oficiales ordenados por km.
2. Va acumulando un "buffer" mientras el checkpoint de cierre de un
   segmento no tenga tiempo registrado para este corredor — sumando
   distancia, desnivel positivo y negativo del tramo.
3. La pendiente promedio del tramo fusionado se recalcula como un
   **promedio ponderado por distancia** de las sub-pendientes (no un
   promedio simple), para no distorsionar el peso relativo de cada
   sub-tramo.
4. En cuanto el buffer llega a un checkpoint que SÍ tiene tiempo
   registrado (y el checkpoint de inicio del buffer también lo tiene), se
   cierra ese segmento fusionado y arranca uno nuevo.
5. Un segmento que queda abierto al final sin cerrar (ej. un DNF sin
   tiempo en el último checkpoint conocido) simplemente se descarta — mismo
   comportamiento que un "segmento sin emparejar" preexistente.

`build_time_by_point(df_runner)` es el mapa auxiliar
`{checkpoint_id: tiempo_acumulado_en_horas}` que se usa tanto para decidir
qué checkpoints tienen tiempo como para el cálculo posterior — un
checkpoint sin passing para ese corredor simplemente no aparece como clave
ahí, y esa ausencia es la señal que dispara la fusión.

Este merge se aplica **antes** de calcular VPI/DMI/ER
(`calculate_runner_indices()` lo llama primero, luego cruza con el tiempo
del corredor) — el reparto por effort-share dentro del segmento fusionado
(ver `docs/02-engine/indices-vpi-dmi-er.md`) sigue funcionando igual sobre
el tramo combinado.

## Decisiones clave / lecciones aprendidas
- Fusionar en vez de descartar es la diferencia entre "esta carrera tiene
  agujeros en la tabla de segmentos porque el aid station de tal km no
  escanea dorsales" y "el índice global de VPI de este corredor está mal
  porque le faltó justo el tramo más empinado de la carrera".
- El merge es **idempotente**: si se le pasa una lista de segmentos que ya
  no tiene ningún hueco (todos los checkpoints tienen tiempo), el resultado
  es el mismo `df_segments` original sin cambios reales — por eso
  `calculate_runner_indices()` puede llamar a
  `calculate_indices_by_segment()` (que también fusiona internamente) sin
  preocuparse de estar duplicando trabajo o rompiendo algo.
- `unmatched_segments` / `merged_checkpoints` se reportan como conteos en
  el resultado (`calculate_runner_indices()`), y la UI los muestra como
  avisos informativos al usuario — no quedan silenciados.

## Problemas conocidos
Ver `docs/05-known-issues.md`.

## Archivos relacionados
- `engine/metrics/segments.py` — `merge_segments_with_runner_times()`,
  `build_time_by_point()`
- `engine/metrics/indices.py` — `calculate_runner_indices()`,
  `calculate_indices_by_segment()`
