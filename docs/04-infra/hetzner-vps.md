# Hetzner VPS

<!-- TODO: el contenido de este documento es contexto operativo/de
     infraestructura provisto directamente (no hay ningún código en este
     repo que referencie Hetzner, SSH, ni cron jobs de scraping), así que
     no pudo verificarse contra código real como el resto de la
     documentación. Confirmar que sigue vigente antes de tomar decisiones
     sobre esto. -->

## Propósito
Registrar el estado y la decisión pendiente sobre el VPS de Hetzner
provisionado para el proyecto, para no perder el contexto de por qué existe
y qué se evaluó hacer con él.

## Cómo funciona
- Instancia Hetzner CX23, datacenters de Nuremberg/Falkenstein (baja
  latencia desde el sur de Francia).
- Facturación por hora — no hay costo hundido en mantenerlo apagado, ni en
  darlo de baja si se decide no usarlo.
- Provisionado inicialmente pensando que sería necesario para hostear la
  app Streamlit. Resultó innecesario para ese propósito: Streamlit
  Community Cloud soporta apps privadas de forma nativa (ver
  `docs/04-infra/hosting.md`), sin necesitar un VPS ni túnel SSH para eso.

## Decisiones clave / lecciones aprendidas
- Valor potencial actual: correr cron jobs 24/7 de scraping de
  LiveTrail/UTMB, ya que Streamlit Community Cloud no soporta jobs
  persistentes en background (la app solo corre mientras hay actividad/el
  contenedor está despierto).
- Nota de red: la red de la oficina bloquea el puerto 22 (SSH); dado el
  firewall corporativo, no conviene usar workarounds (túnel por el puerto
  443, Tailscale) en el portátil de trabajo — usar un hotspot móvil para
  conectarse por SSH en su lugar.

## Problemas conocidos
- Decisión pendiente: mantener el VPS y usarlo para cron scraping, o darlo
  de baja. Ver `ROADMAP.md`.

## Archivos relacionados
Ninguno en este repo — infraestructura externa, sin integración de código
todavía.
