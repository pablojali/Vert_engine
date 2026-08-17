# Exportación de Informes para Blog (Blogger)

## Propósito
Documentar el export de "Informe de Análisis Completo" por corredor,
pensado para pegarse directo en el editor HTML de Blogger — no es parte
del sitio estático generado por `publish.py`, es un artefacto aparte que
sale de la app Streamlit.

## Cómo funciona
`build_full_runner_report_html(runner_info, df_runner, indices, figures, df_segment_degradation, df_summary)`
(`app.py`) arma un único bloque de HTML autocontenido: tarjeta del
corredor, tabla de checkpoints/splits, métricas de VPI/DMI/ER, y los 4
gráficos (VPI, DMI, ER, curva de degradación) con interactividad completa
(zoom/hover/pan).

- **Plotly.js se carga una sola vez** vía CDN al principio del documento
  (`<script src='https://cdn.plot.ly/plotly-2.32.0.min.js'>`), y cada
  gráfico se embebe como fragmento liviano (`include_plotlyjs=False`) que
  reusa esa carga — en vez de cargar la librería completa una vez por
  gráfico.
- Las tablas usan la paleta propia de VertLabs (fondo slate oscuro, acento
  cyan: clases CSS `.vl-report`, `.vl-metric`, `table.vl-table`) definidas
  inline en un `<style>` al principio del bloque, para que combinen con el
  tema existente del blog en vez de verse como HTML sin estilo.
- Este mismo bloque se genera y se reusa en tres lugares: el botón de
  descarga individual en "Runner Metrics (LiveTrail)", el botón de
  descarga por corredor en "Top Runners" (bulk), y el auto-adjuntado al
  exportar a la web (tab "Exportar a Web") — una sola función, no hay
  versiones paralelas que puedan desincronizarse.

### Nombre de archivo de descarga
`_ascii_filename(text)` solo se ocupa de que el nombre del **archivo
descargado** no tenga tildes/caracteres no-ASCII (los navegadores pueden
fallar silenciosamente una descarga si el header `Content-Disposition` no
es ASCII puro) — nunca toca cómo se muestra el nombre del corredor
*dentro* del informe. No hay un slugifier separado de "apellido-nombre"
específico para este export; el patrón de slug usado en todo el resto del
sitio (URLs de atleta, carpetas de media) es el mismo `_slugify()`
genérico (minúsculas, guiones, sin acentos) usado en toda la app.

## Decisiones clave / lecciones aprendidas
- El informe es HTML **autocontenido** a propósito (CSS inline, sin
  dependencias de archivos externos del sitio) — puede pegarse en
  cualquier editor que acepte HTML crudo sin arrastrar hojas de estilo ni
  rutas relativas que se rompan fuera de `vertlabs.run`.
- Notas operativas sobre Blogger como destino (conocimiento general de la
  plataforma, no específico de este repo — no verificado contra código
  porque no hay código de este proyecto que hable con Blogger):
  - Las condiciones `b:if` de Blogger requieren `&&`, no la palabra
    `and`.
  - Toda referencia `b:include` necesita su `b:includable` correspondiente
    definido en el mismo theme.
  - Los errores de theme de Blogger se inyectan silenciosamente en el
    código fuente de la página — hay que inspeccionar con Ctrl+U para
    verlos, no aparecen en la vista normal.
  - Los temas gratuitos de Blogger de terceros pueden traer scripts de
    redirección ofuscados — conviene inspeccionar el HTML del theme antes
    de instalarlo.

## Problemas conocidos
Ninguno abierto específico de este export.

## Archivos relacionados
- `app.py` — `build_full_runner_report_html()`, `_ascii_filename()`,
  `chart_download_button()` (descarga de un gráfico individual, distinto
  del informe completo)
