# Problemas Conocidos

Un issue por sección. `Estado` refleja la situación al momento de esta
documentación — actualizar a mano cuando cambie.

---

## "Exportar a Web" se perdía si el Engine se reiniciaba antes de Publicar
**Estado:** resuelto (2026-09-01)

**Descripción:** se cargaron 20 corredores de CCC vía "Top Runners" y se
exportaron con "🌐 Exportar a Web" (con sus informes HTML) de la forma
habitual. El Engine (Streamlit Community Cloud) se reinició después del
export pero antes de tocar "🚀 Publicar a Producción". Al publicar más
tarde, el log mostró "Sin cambios en data/ - nada para respaldar" desde
la primera línea, y ninguno de los 20 corredores llegó a GitHub.

Causa raíz: el disco de Streamlit Community Cloud es efímero — un
reinicio del Engine re-clona el repo desde GitHub en un contenedor
nuevo, descartando cualquier archivo modificado en disco que no se haya
commiteado todavía. "Exportar a Web" escribía `race.json`/`profile.json`
correctamente en el filesystem local, pero el único lugar que
commiteaba+pusheaba `data/` a GitHub (`_backup_engine_data()`) corría
exclusivamente dentro de "Publicar a Producción". Si el reinicio caía
entre el export y el publish, el export quedaba solo en el contenedor
viejo (ya descartado) y jamás llegaba a git — indistinguible, para
`_backup_engine_data()`, de "no cambió nada".

**Impacto:** pérdida silenciosa y total de un export (corredores +
informes HTML) sin ningún mensaje de error en ningún paso — ni al
exportar (que sí escribió bien en su momento) ni al publicar (que
correctamente no encontró nada que respaldar, dado el estado del disco
en ese momento).

**Fix:** `tab_web_export` ahora llama a `_backup_engine_data()`
inmediatamente después de un export exitoso, en vez de esperar al botón
de Publicar. El export queda commiteado y pusheado a GitHub apenas se
escribe, así que un reinicio posterior del Engine — sin importar cuándo
ocurra — ya no puede borrarlo. Si el respaldo automático falla (ej. sin
red), se lo avisa explícitamente en pantalla con instrucción de no
reiniciar el Engine hasta resolverlo.

**Próximos pasos:** ninguno — los 20 corredores de CCC originales no son
recuperables (nunca llegaron a disco de forma persistente) y deben
volver a cargarse desde LiveTrail.

---

## Lavaredo 80K — checkpoint inicial sin datos
**Estado:** sin resolver
<!-- TODO: verificar — este item viene de contexto provisto directamente,
     no se pudo confirmar contra el código ni contra los datos actuales
     del repo en esta pasada de documentación (no hay evidencia de este
     comportamiento específico en las sesiones de trabajo registradas
     sobre Lavaredo). Confirmar si sigue siendo reproducible y con qué
     carrera/checkpoint exacto antes de investigar. -->

**Descripción:** el primer checkpoint de la carrera "Lavaredo 80K" no
tendría datos; el motor solo mostraría resultados a partir del tercer
checkpoint, saltándose los datos del km26.

**Impacto:** tabla de segmentos incompleta para esta carrera específica.

**Próximos pasos:** confirmar si el problema persiste con los datos
actuales de `data/races_registry.json` / el GPX de Lavaredo antes de
investigar la causa.

---

## Auto-adjuntado del informe HTML en "Exportar a Web" no funciona
**Estado:** resuelto (2026-08-20)

**Descripción:** el informe de análisis completo por corredor (HTML) se
generaba correctamente en el momento del fetch (tabs "Runner Metrics" /
"Top Runners" — confirmado visible como ✅ en la columna "Informe" de la
vista previa de "Exportar a Web"), pero no quedaba adjuntado al exportar:
el `race.json` resultante seguía con `"report": null` para esos
corredores, aunque la foto y el país sí se auto-adjuntaban correctamente
en el mismo export. Requería subir el informe a mano (mismo archivo, por
el `file_uploader` de cada corredor) como workaround.

**Causa real:** `build_full_runner_report_html` (`app.py`) devolvía
`bytes` (`.encode("utf-8")` al final), pero el código de auto-adjuntado en
"Exportar a Web" llama a `Path.write_text(report_html, ...)`, que exige
`str` - cada intento lanzaba `TypeError: data must be str, not bytes`,
atrapado en silencio por el `try/except` alrededor (el conteo de fallos SÍ
se mostraba, pero dentro de un `st.expander` colapsado, fácil de pasar por
alto) y `report_path` quedaba en `None` siempre. La columna "Informe ✅"
solo revisa que el valor sea truthy - bytes también lo es, por eso el
diagnóstico "parecía" confirmar que todo estaba listo. Los botones de
descarga manual (`st.download_button`) nunca pisaron este bug porque
aceptan bytes o str indistinto - por eso el workaround de subir el archivo
a mano siempre funcionó, y por eso costó tanto encontrarlo.

**Fix:** se sacó el `.encode("utf-8")` - la función devuelve `str` ahora.
Reproducido el `TypeError` exacto offline (bytes vs. str a `write_text`) y
confirmado que con `str` escribe bien. Ningún otro call site necesitó
cambios (los dos usos de `download_button(data=...)` ya funcionaban igual
con str).

**Impacto:** el flujo de "cargar 10 corredores de una sola vez" (tab "Top
Runners") ahora adjunta el informe automáticamente.

**Confirmado en producción (2026-08-20):** el primer export real después
del fix (carrera "Trail Verbier St-Bernard 140K", 20 corredores) llegó con
los 20 `report.html` escritos en disco y linkeados correctamente en
`race.json` - visto directo en los datos que el botón "Publicar" subió al
repo, sin necesidad de acceso a LiveTrail desde este entorno.

---

## "Promover a Producción" parecía colgarse sin feedback
**Estado:** mitigado (2026-08-20)

**Descripción:** después de un export grande, el botón "✅ Promover a
Producción" se quedaba con la pantalla oscurecida (comportamiento normal
de `st.spinner` de Streamlit durante un script largo) sin ningún mensaje
de progreso intermedio durante varios minutos, indistinguible de un
cuelgue real.

**Causa de fondo (robustez, no de este caso puntual):** ninguna llamada a
`git` en `app.py` (`_run_git`, `_ensure_web_repo`) tenía timeout. Si
`GITHUB_TOKEN` faltara/venciera, el remoto cae a una URL HTTPS sin
credenciales embebidas, que en un contexto sin terminal puede bloquearse
esperando un prompt que nunca llega - sin timeout, esto colgaría la app
entera indefinidamente.

**Verificado en este caso puntual:** comparando el build regenerado
contra lo que ya estaba en `main` de `vertlabs-web`, el export SÍ se había
publicado correctamente - no era un cuelgue real, sino un push de ~1600
archivos sin ninguna señal de progreso intermedia.

**Fix:** `GIT_TERMINAL_PROMPT=0` (falla al toque en vez de bloquear
esperando un prompt) + timeout de 5 minutos en cada llamada a `git`,
como red de seguridad ante un cuelgue real futuro (no como límite de
rendimiento - un push grande y lento pero funcionando tiene margen de
sobra). Queda pendiente, de menor prioridad, agregar feedback de progreso
paso a paso durante la publicación.

---

## ER da valores inflados (>100) en carreras con perfil "subida concentrada + tramo fácil"
**Estado:** causa identificada, sin corregir (decisión del usuario: dejarlo así por ahora)

**Descripción:** el índice ER (`calculate_runner_indices` en `app.py`) parte
la carrera en "primera mitad" y "segunda mitad" por **km de esfuerzo**
(distancia + desnivel/100), no por tiempo transcurrido. En un perfil de
carrera típico de trail (una subida fuerte concentrada en una parte del
recorrido, tramo llano/fácil en otra), esa conversión fija de "100m de
desnivel = 1km extra de esfuerzo" subestima el costo real de subir (en la
práctica el ritmo real en subida puede ser 3-4x más lento que en llano, no
2x). El resultado: la "segunda mitad" calculada cae en el tramo fácil del
recorrido aunque el corredor no haya cambiado su rendimiento real, e
infla el ER por encima de 100 - y esto le pasa a **cualquier** corredor en
una carrera con ese tipo de perfil, no solo a quienes de verdad hicieron
negative split.

Confirmado offline (sin acceso a LiveTrail desde este entorno)
reconstruyendo `calculate_runner_indices` verbatim y alimentándola con un
corredor inventado de ritmo real CONSTANTE (20 min/km en subida, 6 min/km
en llano - sin fatiga ni mejora real): dio ER=123.5.

**Impacto:** el ER es potencialmente engañoso en cualquier carrera con
este tipo de perfil (subida concentrada + tramo fácil hacia el final),
no solo en "Engine Live" - ahí se notó primero porque muestra el campo
completo a la vez (100+ corredores) en vez de un puñado en Top Runners.

**Próximos pasos (cuando se retome):** la opción evaluada y recomendada es
cambiar el corte de "primera/segunda mitad" para que sea por TIEMPO
transcurrido del corredor en vez de por km de esfuerzo del recorrido, así
el ER mide fatiga real del corredor sin que el perfil de la carrera meta
ruido. Alternativa: recalibrar el factor de conversión de desnivel (hoy
100m = 1km extra) - afecta también VPI/DMI, que usan la misma noción de
"km de esfuerzo".

---

## Colisión de slug/carpeta entre distintas carreras del mismo año
**Estado:** resuelto (patrón recurrente, mitigado — no eliminado
estructuralmente)

**Descripción:** al exportar una carrera nueva, la sugerencia automática de
carpeta/slug puede coincidir con la de otra carrera real distinta si
comparten año y distancia redonda (ej. dos eventos distintos con una
distancia "120K" el mismo año), o si el nombre de la carrera se escribió
ligeramente distinto entre sesiones (ej. "Lavaredo Ultra Trail" vs.
"Lavaredo Ultra Trail by UTMB"). El síntoma típico: una carrera se exporta
sobre la carpeta/slug de otra, un evento aparece duplicado en el listado
de `/races/`, o el "hub" de un evento pisa la página de una de sus propias
distancias.

**Impacto:** Top10/posts de una distancia dejaban de verse en el sitio
público; corredores de una carrera aparecían mezclados con los de otra.

**Próximos pasos:** el emparejamiento automático de carpeta existente
ahora exige coincidencia de año + distancia **y** al menos una palabra no
genérica en común entre nombres (`_find_existing_race_folder` en `app.py`)
— reduce la probabilidad de colisión cruzada, pero sigue siendo texto
libre comparado por heurística, no un identificador único de evento. Ver
`docs/03-web-builder/data-schema.md` para el porqué estructural (slug como
clave de unión textual).

**Caso real confirmado (2026-08-19) — mismo patrón, en `races_registry.json`
en vez de en el export al sitio:** el registry tenía dos entradas de nivel
superior para el mismo evento, `"MonteRosa"` (correcta, checkpoints y GPX
reales tanto para 90K como 120K) y `"monterosa-walserwaeg-by-utmb"`
(duplicada por typo de slug al cargar/actualizar la carrera una segunda
vez - probablemente al sumar una distancia o reemplazar el GPX). La
duplicada tenía **ambas** distancias (90 y 120) apuntando por error al GPX
y a los checkpoints del 90K. Como las dos entradas comparten el mismo
"nombre visible", en los desplegables aparecían dos opciones idénticas sin
forma de distinguirlas - cuando el motor cargó la de 120K desde la entrada
duplicada, usó los checkpoints de otra distancia, y eso rompió VPI/DMI/ER
para cualquier corredor analizado desde ahí (síntoma reportado: casi todos
los checkpoints de un corredor sin "Time" - no eran datos faltantes de
LiveTrail, eran los IDs de checkpoint equivocados).

Entrada duplicada + su carpeta GPX huérfana (`data/gpx/monterosa-walserwaeg-by-utmb/`)
eliminadas. Mitigación estructural agregada en el "🧩 Checkpoint Fetcher"
(`app.py`): un desplegable para elegir una carrera YA EXISTENTE (en vez de
volver a tipear nombre/slug de memoria) que autocompleta nombre y slug y
bloquea el campo de slug para edición manual mientras esa carrera esté
seleccionada - así sumar una distancia nueva o actualizar el GPX de un
evento existente no puede volver a crear una entrada duplicada por un
slug ligeramente distinto.

**Segundo caso real confirmado (2026-08-19) — mismo patrón, pero en la
dirección opuesta (falso positivo, no duplicado):** al exportar "Marathon
du Mont Blanc" en "Exportar a Web", el guard de `_find_existing_race_folder`
la emparejó con la carpeta ya publicada `trail-du-saint-jacques-by-utmb`
- dos eventos completamente distintos. Causa: `_GENERIC_RACE_WORDS` (las
palabras que se descartan antes de comparar nombres) solo tenía palabras
genéricas en inglés (`by, utmb, ultra, trail, race, the, of`); "du"
(preposición francesa) no estaba filtrada, y era la ÚNICA palabra que
"Marathon **du** Mont Blanc" y "Trail **du** Saint-Jacques" tenían en
común. Con la mayoría de las carreras del catálogo nombradas en francés/
italiano, cualquier par de nombres que solo compartiera un conector así
(du, de, la, el, di, und, etc.) se emparejaba por error.

**Corregido:** `_GENERIC_RACE_WORDS` ahora incluye conectores gramaticales
de francés, italiano, español y alemán además de los de inglés. Verificado
offline que el par Marathon/Saint-Jacques ya no comparte tokens, y que el
caso real que motivó el guard original (Lavaredo Ultra Trail vs. Lavaredo
Ultra Trail by UTMB) sigue emparejando correctamente.

---

## Slug de `race.json` sin distancia colisiona con otra distancia o con el event hub
**Estado:** detectado y advertido en build (2026-08-21), sin corregir — pendiente para más adelante (decisión del usuario)

**Descripción:** distinto del issue de "Colisión de slug/carpeta" de arriba
(ese es sobre el emparejamiento de carpeta en "Exportar a Web"/el registry;
este es sobre el campo `"slug"` que ya quedó grabado dentro de un
`race.json` publicado). `race_generator.py` arma la URL de cada página de
carrera directamente desde `race["slug"]` tal como viene en el JSON, sin
verificar que sea único. Cuando dos distancias del mismo evento (o una
distancia y el "event hub" que las agrupa, cuyo slug se calcula como
`nombre-año`) terminan con el mismo slug, la página que se escribe último
pisa a la anterior en el mismo path de salida — sin error, sin warning
(hasta este fix), simplemente la primera queda inalcanzable.

**Detectado auditando el sitemap de producción** (ver
`docs/03-web-builder/` para el generador): de 22 páginas candidatas de
carrera/evento, solo 13 URLs únicas sobreviven — **9 quedan pisadas**.
Afecta a 6 carreras: Eiger Ultra Trail 2026 (101k pisado por su propio
event hub, un solo-distancia), Marathon du Mont Blanc 2026 (42k y 90k
comparten slug entre sí Y con el event hub — 3 páginas, 1 sobrevive),
Monterosa Walserwaeg 90k (pisado por el event hub — el 120k está bien,
tiene slug distinto), Trail du Saint-Jacques 2026 (86k pisado por su
propio event hub), Trail Verbier St-Bernard (77k y 140k comparten el
mismo slug entre sí y con el event hub), UTMB Mont Blanc 2025 (100k y
174k). Confirmado en el HTML real: `/races/eiger-ultra-trail-2026/`
sirve el event hub, no el análisis del 101k.

**Por qué no se corrige acá:** las páginas de atleta ya tienen embebido
ese mismo `race_slug` (colisionado) desde el export — reescribir el slug
solo en `race_generator.py` rompería los links atleta → carrera en vez de
arreglarlos (apuntarían a la URL equivocada). El fix real es en el paso
de exportación del Engine: darle a cada distancia un slug que incluya la
distancia, como ya hacen bien las carreras que sí están OK (ej. Val
d'Aran: `val-d-aran-by-utmb-2026-110k` / `-163k`, Monterosa 120k:
`monterosa-walserwaeg-120k`).

**Mitigación agregada mientras tanto:** `race_generator.generate()` ahora
imprime un `⚠ WARNING` en consola durante `python3 publish.py` cada vez
que detecta que dos rutas van a pisarse, nombrando el slug y las páginas
en conflicto — para que una colisión nueva se note al toque en vez de
descubrirse después como una URL "perdida". `sitemap_generator.py`
tampoco lista una URL dos veces aunque haya colisión (dedupe defensivo,
no arregla el contenido pisado).

**Próximos pasos (cuando se retome, según el usuario):** revisar el paso
de exportación en `app.py`/Engine para que el slug sugerido por distancia
incluya siempre la distancia, y re-exportar (o corregir a mano) las 6
carreras afectadas para recuperar las 9 páginas perdidas.

---

## VPI/DMI inflado en tramos con terreno corto e irregular (subida/bajada corta escondida en un tramo largo)
**Estado:** causa identificada y mitigada con un flag visual (2026-08-31) — no corregido de raíz

**Descripción:** mismo mecanismo de fondo que el issue de arriba ("ER da
valores inflados"), pero en el VPI/DMI **por tramo** (el gráfico
interactivo del informe de cada corredor, `calculate_indices_by_segment`
en `app.py`). Entre dos checkpoints no se sabe en qué punto exacto
empezó/terminó una subida o bajada real — el motor lo **estima**
repartiendo el tiempo del corredor en ese tramo proporcional al
"esfuerzo" (distancia + desnivel/100) de la parte empinada vs. el tramo
completo. Cuando la parte empinada es corta pero con desnivel
concentrado, comparada con la distancia total del tramo, esa porción de
tiempo estimada se vuelve chica y termina dividiendo por muy poco tiempo
- inflando el VPI/DMI de ese tramo puntual sin que el corredor haya
hecho nada extraordinario ahí.

**Confirmado offline** (sin acceso a LiveTrail) reconstruyendo
`calculate_indices_by_segment` verbatim y probándola con un tramo
sintético de checkpoint (6.9km) con una subida corta y empinada seguida
de una bajada larga y suave — el mismo patrón que un usuario reportó
viendo en un informe real (tramo con VPI ≈1875 m/h, muy por encima del
resto de la carrera). Variando solo qué tan corta/concentrada es la
subida sintética, el VPI del tramo escala de ~500 m/h (razonable) a
~1600+ m/h (implausible) sin cambiar el desnivel real ganado - confirma
que es un artefacto del método de estimación, no la performance real
del corredor.

**Impacto:** el VPI/DMI **global** de toda la carrera es bastante más
robusto (promedia muchos tramos), pero el valor de un tramo puntual en
el gráfico puede estar inflado - visualmente se veía como un pico
aislado sin ninguna indicación de que ese punto es menos confiable que
el resto.

**Mitigación implementada (v1, revisada):** la primera versión marcaba
un tramo como no confiable usando un umbral fijo ("effort-share < 15%"
o un techo absoluto de m/h). En la práctica, en carreras con checkpoints
espaciados, es NORMAL que la porción empinada de un tramo sea una parte
chica del tramo total - ese umbral terminaba marcando casi la mitad de
los tramos de una carrera real, sin ninguna capacidad de distinguir el
outlier real del resto (feedback del usuario: "si todos los puntos
tienen rombos... no da confiabilidad").

**Versión actual:** `calculate_indices_by_segment` marca un tramo como
no confiable de forma **relativa al propio corredor**, no contra un
número fijo: compara el VPI/DMI de cada tramo contra la MEDIANA de los
demás tramos de ESE MISMO corredor en ESA MISMA carrera
(`_flag_relative_outliers`), y solo marca cuando supera
`VPI_OUTLIER_MULTIPLIER`/`DMI_OUTLIER_MULTIPLIER` (1.5x esa mediana) -
así se adapta automáticamente a cómo es el terreno/los checkpoints de
cada carrera en particular, en vez de un corte universal. Con menos de
`MIN_SEGMENTS_FOR_OUTLIER_CHECK` (4) tramos válidos no se marca nada
(una mediana con tan poca data no significa nada). Verificado offline
con una carrera sintética de 15 tramos normales (460-590 m/h) + 1 tramo
anómalo (subida corta escondida, ~1600 m/h): la versión anterior hubiera
marcado varios de los 15 normales; la actual marca exactamente 1 de 16.

Los tramos marcados se resaltan en el gráfico
(`build_runner_analysis_bundle`) con un punto en otro color (rombo rojo)
y un tooltip: "Approximate value — short/irregular terrain within this
checkpoint segment". Como `build_full_runner_report_html` usa las
mismas figuras, el resaltado también aparece en el informe HTML público
(embebido en el sitio vía iframe), no solo en la vista de Streamlit.

**Próximos pasos (si se retoma):** la corrección de raíz sería usar el
GPX propio del corredor (con timestamp real por punto, ya hay
scaffolding parcial en `process_runner_gpx_with_time`/
`build_runner_slope_windows`) en vez de estimar por reparto de tiempo -
elimina la necesidad de estimar del todo para quien suba su GPX personal
(conecta directo con el formulario "Get Your VTL Analysis" del sitio
público). El multiplicador (`VPI_OUTLIER_MULTIPLIER`/
`DMI_OUTLIER_MULTIPLIER`, hoy 1.5x) es ajustable sin tocar el resto de
la lógica si en la práctica marca de más/de menos.

---

<!-- Agregar nuevos issues debajo, con el mismo formato: título, Estado,
     Descripción, Impacto, Próximos pasos. -->
