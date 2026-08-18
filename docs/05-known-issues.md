# Problemas Conocidos

Un issue por sección. `Estado` refleja la situación al momento de esta
documentación — actualizar a mano cuando cambie.

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
**Estado:** sin resolver

**Descripción:** el informe de análisis completo por corredor (HTML) se
genera correctamente en el momento del fetch (tabs "Runner Metrics" /
"Top Runners" — confirmado visible como ✅ en la columna "Informe" de la
vista previa de "Exportar a Web"), pero no queda adjuntado al exportar: el
`race.json` resultante sigue con `"report": null` para esos corredores, y
el archivo no aparece en el sitio publicado, aunque la foto y el país sí
se auto-adjuntan correctamente en el mismo export. Requiere subir el
informe a mano (mismo archivo, por el `file_uploader` de cada corredor)
como workaround.

**Impacto:** el flujo de "cargar 10 corredores de una sola vez" (tab "Top
Runners") sigue requiriendo un paso manual por corredor para el informe,
aunque el resto del proceso (foto, país, VPI/DMI/ER) ya es 100%
automático.

**Próximos pasos:** con el string del HTML ya construido en el momento del
fetch y viajando como tal (no como los objetos DataFrame/Figure crudos que
se usaban en un intento anterior) hasta `session_state`, la causa restante
no está identificada. Como no hay acceso de red a LiveTrail desde el
entorno donde se desarrolló este fix, no pudo reproducirse en vivo — el
próximo intento debería arrancar confirmando en la propia sesión de
Streamlit si `runners_pool[...]["_report_html"]` realmente tiene contenido
en el momento exacto de hacer submit del formulario de export.

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

---

<!-- Agregar nuevos issues debajo, con el mismo formato: título, Estado,
     Descripción, Impacto, Próximos pasos. -->
