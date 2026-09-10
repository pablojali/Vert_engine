# Problemas Conocidos

Un issue por sección. `Estado` refleja la situación al momento de esta
documentación — actualizar a mano cuando cambie.

---

## "Exportar a Web" no quedaba respaldado en GitHub hasta el próximo Publish
**Estado:** resuelto (2026-09-01)

**Descripción:** el disco de Streamlit Community Cloud es efímero — un
reinicio del Engine re-clona el repo desde GitHub en un contenedor
nuevo, descartando cualquier archivo modificado en disco que no se haya
commiteado todavía. "Exportar a Web" escribía `race.json`/`profile.json`
correctamente en el filesystem local, pero el único lugar que
commiteaba+pusheaba `data/` a GitHub (`_backup_engine_data()`) corría
exclusivamente dentro de "Publicar a Producción". Si el Engine se
reiniciaba entre un export y el próximo publish, ese export se perdía
por completo, sin ningún error visible en ningún paso (ni al exportar,
que sí escribió bien en su momento, ni al publicar, que correctamente no
encontraba nada que respaldar dado el estado del disco en ese momento).

Nota: se investigó originalmente como posible causa de que a 20
corredores de CCC no se les haya generado/adjuntado el informe HTML
(ver issue siguiente), pero el usuario confirmó que en ese caso el
reinicio fue *antes* de cargar los corredores, y que `race.json`/
`profile.json` sí llegaron a producción correctamente — así que esta
issue no es la causa de ese caso puntual. Sigue siendo un gap real y
vale la pena tenerlo cerrado igual, para el caso general.

**Fix:** `tab_web_export` ahora llama a `_backup_engine_data()`
inmediatamente después de un export exitoso, en vez de esperar al botón
de Publicar. El export queda commiteado y pusheado a GitHub apenas se
escribe, así que un reinicio posterior del Engine ya no puede borrarlo.
Si el respaldo automático falla, se lo avisa explícitamente en pantalla.

---

## Informe HTML no generado/adjuntado para corredores de CCC (Top Runners)
**Estado:** resuelto (2026-09-01) — la causa real NO era la generación del informe

**Descripción:** se cargaron 20 corredores de CCC vía "🏆 Top Runners".
`race.json`/`profile.json` se generaron y publicaron correctamente (los
corredores aparecen en el listado de la carrera y en cada perfil), pero
el informe HTML completo de cada corredor no llegó a `vertlabs-web`.

Se investigó primero como una posible excepción silenciada en
`build_full_runner_report_html` (ver el fix de visibilidad de errores
más abajo, que sigue siendo válido en general) - pero el usuario
confirmó que reintentando el fetch **no aparecía ningún error**, y que
tampoco funcionaba subiendo el informe a mano en "Exportar a Web". Eso
descartó la generación del informe: los 20 `report.html` SÍ se estaban
generando y escribiendo bien en `data/` (confirmado inspeccionando el
repo directamente - 20 archivos de ~98KB cada uno, con contenido real).

**Causa real:** colisión de slug - ver "Slug de `race.json` sin
distancia colisiona con otra distancia o con el event hub" más abajo.
CCC es la distancia 100k del evento UTMB Mont Blanc 2026, que terminó
con el mismo slug público que la distancia 148k del mismo evento. Al
publicar, la copia de media de la carrera generada después borraba
(`shutil.rmtree`) la carpeta `charts/` completa de la generada antes -
los 20 `report.html` de CCC existían en Vert_engine pero nunca
sobrevivían el paso a `vertlabs-web`.

**Impacto:** informes de rendimiento completos ausentes en producción
para corredores por lo demás correctamente publicados, sin ningún
indicio en pantalla de qué falló ni por qué.

**Fix:** ver el issue de colisión de slug más abajo - renombrado el
slug de CCC y agregada una validación en "Exportar a Web" que bloquea
un export si el slug elegido ya lo usa otra carrera.

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
**Estado:** resuelto (2026-09-02) — el guard de "Exportar a Web" del
2026-09-01 tenía un agujero real (ver actualización 2026-09-02 abajo),
ya cerrado

**Actualización (2026-09-02) - el guard no cubría colisión con el event
hub:** una nueva distancia (UTMB Mont Blanc 2026, 174k) exportada
DESPUÉS del fix del 2026-09-01 volvió a colisionar - esta vez con su
propio event hub, no con una distancia hermana. Causa: `_find_slug_collision()`
solo comparaba el slug candidato contra el campo `"slug"` de otros
`race.json` en disco. El event hub, en cambio, nunca se guarda como su
propio `race.json` - `race_generator._build_events()` calcula su slug al
vuelo, a partir de nombre+año de la distancia con el `distance_km` más
chico dentro de la misma carpeta de año. Una distancia nueva puede
colisionar con esa identidad calculada sin tocar el slug de ninguna otra
distancia existente, y el guard no tenía forma de detectarlo.

**Fix:** `_find_slug_collision()` ahora replica ese mismo cálculo
(nombre+año de la distancia con `distance_km` mínimo, incluyendo la
carrera que se está por exportar en esa comparación - no solo las que ya
están en disco) y lo suma como una fuente más de colisión. Verificado
con 4 casos unitarios (distancia nueva grande con slug sin desambiguar →
colisión; misma distancia con slug desambiguado → sin colisión;
re-exportar una carrera ya publicada con su propio slug → sin colisión;
una distancia nueva que legítimamente pasa a ser la más chica → sin
colisión, es la identidad correcta del hub). El UTMB 174k afectado se
corrigió a mano igual que los casos anteriores
(`utmb-mont-blanc-2026-174k`).

**Histórico (2026-09-01):** las 7 carreras afectadas originalmente
corregidas y republicadas, guard estructural agregado por primera vez.

**Actualización (2026-09-01):** esto dejó de ser un riesgo teórico. Los
20 corredores de CCC exportados vía "Top Runners" quedaron guardados
correctamente en `data/` (VPI/DMI, race.json, profile.json, los 20
`report.html` - todo perfecto en disco y en el repo de Vert_engine), pero
sus informes HTML nunca llegaron a `vertlabs-web`. Causa: CCC es la
distancia "100k" del evento UTMB Mont Blanc 2026, y tanto esa distancia
como la de 148k del mismo evento calcularon el mismo slug por defecto
(`utmb-mont-blanc-2026`, de nombre+año sin distancia) - exactamente el
mecanismo descripto abajo. Al publicar, la carrera de 148k se generó
después y su `copy_public_media()` hizo `shutil.rmtree()` sobre
`output/media/races/utmb-mont-blanc-2026/charts/` antes de copiar la
suya, borrando los 20 `report.html` de CCC que ya estaban ahí - sin
ningún error en ningún paso. `race.json`/`profile.json` de CCC sí
sobrevivieron porque los datos de los atletas viven en sus propios
`data/athletes/<slug>/profile.json`, ajenos a esta colisión de media.

**Fix de CCC:** renombrado SOLO el slug a `utmb-mont-blanc-2026-ccc`
(sigue bajo la carpeta `data/races/utmb-mont-blanc/`, vinculada al
evento UTMB como corresponde) - `race.json` y los 20 `profile.json`
actualizados, republicado y verificado: ambas distancias ahora generan
página y media propias sin pisarse.

El nombre visible se dejó igual ("UTMB - Mont Blanc", el mismo que el
148k) a propósito: un primer intento de mostrar "CCC by UTMB" como
nombre propio requería cambiar de qué distancia toma su identidad el
"event hub" (`_build_events()` en `race_generator.py`, que hasta ahora
siempre usaba la distancia más chica) - y ese cambio, aunque resolvía
CCC, además le cambiaba en silencio el slug/URL a los event hubs de
Lavaredo y Monterosa (que no tenían nada que ver con este bug y
funcionaban bien). Revertido antes de publicar por ese efecto
colateral - si más adelante se quiere que CCC muestre su propio nombre,
hay que resolver primero de qué distancia toma identidad el event hub
cuando sus distancias tienen nombres distintos (no solo "la más chica"
ni "la más grande" a ciegas).

**Fix estructural en "Exportar a Web":** implementado el fix que ya
estaba recomendado más abajo, pero nunca se había hecho. Ahora hay una
función `_find_slug_collision()` que:
1. Al abrir el formulario, si el slug sugerido por defecto ya lo usa
   otra carrera (carpeta/año/distancia distinta), sugiere uno
   desambiguado (agregando la distancia) en su lugar, con un aviso.
2. Al tocar "Exportar", vuelve a chequear el slug que quedó cargado - si
   sigue colisionando con otra carrera, **bloquea el export** con un
   error explícito en vez de dejarlo pisar la otra carrera en silencio.

**Las 6 carreras restantes, corregidas (2026-09-01):** mismo tratamiento
que CCC - slug propio con la distancia agregada, `race.json` +
`profile.json` de cada atleta actualizados, republicado y verificado con
un rebuild completo (cero warnings de colisión, cada distancia y cada
event hub generan su propia página/media intactas):
- Eiger Ultra Trail 101k → `eiger-ultra-trail-2026-101k`
- Marathon du Mont Blanc 42k/90k → `marathon-du-mont-blanc-2026-42k` /
  `-90k` (era colisión triple: entre sí Y con el event hub)
- Monterosa Walserwaeg 90k → `monterosa-walserwaeg-90k` (mismo patrón
  que el 120k, que ya estaba bien)
- Trail du Saint-Jacques by UTMB 86k → `trail-du-saint-jacques-by-utmb-2026-86k`
- Trail Verbier St-Bernard 77k/140k → `-77k` / `-140k`
- UTMB Mont Blanc 2025 100k/174k → `-100k` / `-174k`
- UTMB Mont Blanc 2026 148k → `-148k` (una séptima colisión, expuesta
  recién al arreglar CCC - antes quedaba tapada por la colisión más
  grande entre 148k y CCC/100k)

El guard en "Exportar a Web" (arriba) evita que una carrera nueva vuelva
a caer en esto.

---

### Detalle original (2026-08-21)
**Estado:** resuelto, ver arriba (2026-09-01) — quedó documentado igual
como referencia de las 9 páginas originalmente pisadas y del porqué del
fix elegido

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
**Estado:** caso extremo (repecho/contra-repecho corto y ruidoso) corregido de raíz (2026-09-10, refinado el mismo día) — resto del problema sigue mitigado con flag visual, no corregido de raíz

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

**Caso extremo corregido de raíz (2026-09-10):** un corredor real
(Florian Descamps, Monterosa Walserwaeg by UTMB) reportó un tramo con
pendiente promedio **-10.5%** (tramo puramente de bajada, km 107→112)
apareciendo como su **BEST CLIMB** de toda la carrera con VPI 1206 m/h -
y de forma simétrica, un tramo de **+11.5%** apareciendo como BEST
DESCENT. El flag de outlier relativo (arriba) no lo atrapaba porque
compara contra la mediana del propio corredor, y ese tramo no era
necesariamente un outlier estadístico frente a sus otros tramos - el
problema no es que el valor sea inusualmente alto para ese corredor,
sino que es **conceptualmente imposible**: no puede haber una "tasa de
subida" (VPI) real para un tramo que, en conjunto, bajó.

Causa: dentro de un tramo con pendiente promedio negativa puede haber
igual algún punto GPS puntual con pendiente ≥12% (un repecho corto
dentro de una bajada larga). El método de reparto de tiempo por esfuerzo
(ver Descripción arriba) no tiene piso: a medida que ese repecho
representa una porción cada vez más chica del esfuerzo total del tramo,
la tasa estimada **no tiende a cero** - converge a un techo
(~100 × esfuerzo_total_km / tiempo_tramo_h) que fácilmente supera
1000+ m/h sin importar cuán chico sea el repecho. Confirmado
reconstruyendo el caso exacto (checkpoint sintético con el mismo patrón:
tramo neto -10.5% con un repecho corto embebido) offline.

**Primer intento (revertido el mismo día):** gatear el VPI de un tramo a
que la pendiente promedio del tramo (`Average Slope (%)`) sea positiva
(y el DMI a que sea negativa) - un tramo cuya pendiente promedio va en
el sentido contrario al índice no produciría ningún valor. Corregía el
caso de Florian Descamps, pero era demasiado estricto: feedback directo
del usuario tras probarlo fue "ahora casi que me quede sin valores
jajajaja" - también suprimía subidas/bajadas REALES y sustanciales que
ocurren dentro de un tramo cuyo balance general va para el otro lado
(ej. un repecho real de varios cientos de metros dentro de un tramo que,
en conjunto, es una bajada). El signo promedio del tramo completo no es
lo que distingue el caso inválido del válido.

**Corrección aplicada (versión final):** lo que en realidad distingue un
repecho/contra-repecho REAL de un artefacto de GPS/estimación no es la
dirección general del tramo, sino si el terreno que califica (≥12% de
pendiente) forma una racha **continua** de longitud real, o son solo
puntos GPS sueltos/ruido. `calculate_indices_by_segment` ahora exige
(`_max_contiguous_run_km`, `MIN_QUALIFYING_RUN_KM = 0.2`) que exista al
menos una racha ININTERRUMPIDA de ≥200m de terreno calificado dentro del
tramo para calcular ese índice - sin importar el signo de la pendiente
promedio del tramo completo. Si esa racha existe, el VPI/DMI SÍ se
calcula (aunque el tramo en general vaya para el otro lado); si no
existe ninguna racha de esa longitud (el caso real de Florian Descamps:
el "repecho" eran unos pocos puntos GPS sueltos de ~30m), el índice
queda en `None`. Una racha calificada corta/al límite del umbral no se
suprime - queda capturada por el flag de outlier relativo existente
(el rombo), tal como pidió el usuario ("si la muestra es muy pequeña...
lo marca con un rombo").

Verificado con tres escenarios sintéticos: (1) un tramo genuino de +15%
sigue calculando VPI normalmente (sin regresión), (2) el caso real
reportado (tramo neto -10.5% con un repecho de ~30m) sigue sin producir
VPI, y (3) un tramo neto -8% con un repecho REAL de 300m a pendiente
local alta SÍ produce VPI - confirmando que ya no se pierden subidas o
bajadas reales por el signo del tramo completo.

Al corregirse en `app.py` (la fuente), se propaga automáticamente a la
tabla de degradación, el gráfico interactivo, el informe HTML y el PDF
(`pdf_reports/data_mapper.py`'s `_segment_role_rows` ya descarta filas
con `VPI Raw (m/h)`/`DMI Raw (km/h)` nulas antes de elegir BEST/WORST
CLIMB/DESCENT, así que un tramo sin racha calificada simplemente deja de
ser candidato). El flag de outlier relativo (mitigación v2, arriba)
sigue activo como red de seguridad para el resto de los casos - tramos
con una racha calificada válida pero igual inusualmente altos frente al
resto de ese mismo corredor.

---

## Gráficos del PDF: perfil de elevación no coincidía con la carrera real, y los picos de VPI/DMI se veían "estirados" a lo largo de todo el tramo
**Estado:** resuelto (2026-09-10)

**Descripción:** dos problemas de UI/visualización relacionados, ambos
reportados por el usuario mirando el mismo informe (Monterosa Walserwaeg,
Florian Descamps) justo después de corregir el bug de VPI/DMI de arriba:

1. **Perfil de elevación equivocado en el PDF.** El fondo gris (silueta
   del terreno) de los gráficos de VPI/DMI/Pace y de la curva de
   degradación (`pdf_reports/make_charts.py`) se armaba en
   `data_mapper.py` tomando la elevación SOLO en el "End Km" de cada
   tramo oficial - es decir, un punto por checkpoint (tan pocos como
   8-10 puntos para una carrera de 100km+). Eso perdía picos y valles
   reales entre checkpoints, y podía distorsionar tanto la forma que el
   perfil del PDF no se parecía al perfil real de la carrera (el mismo
   que sí se ve bien en el dashboard interactivo). Feedback del usuario:
   "el pdf no tiene el mismo perfil que la carrera, entonces parece que
   esta bajando".

   **Fix:** nueva `_resample_elevation_profile()` en `data_mapper.py`
   que remuestrea el GPX COMPLETO de la carrera cada 200m (mismo
   step_m que ya usa `app.py`'s `resample_for_chart`/
   `add_elevation_background` para el dashboard interactivo),
   independiente de cuántos tramos/checkpoints tenga esa carrera en
   particular. Nuevas claves `elevation_profile_km`/`elevation_profile_m`
   en `degradation_index` (reemplazan la vieja `elevation_m`, atada 1:1
   a la cantidad de tramos). Verificado comparando ambos métodos sobre
   un GPX sintético con 3 picos/valles reales: el remuestreo denso
   produce ~150 puntos que preservan la forma real, contra 8 puntos del
   método viejo.

2. **VPI/DMI se graficaban en el extremo del tramo oficial, no donde
   realmente está la subida/bajada.** Al corregir el bug de arriba (la
   racha continua de ≥200m), el usuario confirmó que el pico en km
   111-112 era correcto (hay una subida real de +12% ahí) - pero como
   ese valor se graficaba en el "End Km" del tramo OFICIAL completo
   (que puede ser mucho más largo, sobre todo tras fusionar tramos sin
   tiempo registrado - `merge_segments_with_runner_times`), visualmente
   el pico parecía "estirar" la subida a lo largo de todo el tramo en
   vez de mostrarla localizada donde realmente ocurre.

   **Fix:** `calculate_indices_by_segment` ahora devuelve, además del
   valor, la ubicación real de la racha calificada más larga
   (`_longest_run_km_bounds`, que ya existía para el filtro de longitud
   mínima - ahora también reporta DÓNDE está, no solo cuánto mide):
   columnas nuevas `VPI Run Start/End Km` y `DMI Run Start/End Km`
   (`None` cuando no hay racha calificada), más `VPI/DMI Plot Km` (el
   punto medio de esa racha, o el `End Km` del tramo como respaldo
   cuando no hay racha - listo para graficar directamente). El gráfico
   interactivo (`build_runner_analysis_bundle`'s `fig_vpi`/`fig_dmi`) y
   la progresión del PDF (`data_mapper._segment_progression`, con
   `km_col="VPI Plot Km"`/`"DMI Plot Km"`) ahora anclan cada punto ahí
   en vez de en el `End Km` del tramo oficial. La tabla "Key Segments"
   del PDF (`_segment_role_rows`) también muestra el rango real de la
   subida/bajada (ej. "12.2 - 12.5") en vez del tramo oficial completo
   (ej. "9.8 - 15.8") para BEST/WORST CLIMB/DESCENT.

   Verificado reconstruyendo el caso exacto (tramo neto -8% con una
   subida real de 300m embebida cerca del km 12.2-12.5, dentro de un
   tramo oficial que va de 9.8 a 15.8km): el punto ahora se grafica en
   ~12.3km, no en 15.8km, y la tabla de segmentos muestra "12.2 - 12.5"
   en vez de "9.8 - 15.8".

**Impacto:** ambos afectaban solo la presentación visual, no los
valores de VPI/DMI en sí (que ya estaban bien calculados desde el fix
anterior) - pero juntos hacían que un valor correcto se viera
inconsistente con el terreno real, generando dudas de confiabilidad
sobre datos que sí eran válidos.

---

<!-- Agregar nuevos issues debajo, con el mismo formato: título, Estado,
     Descripción, Impacto, Próximos pasos. -->
