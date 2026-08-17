# Hosting

## Propósito
Documentar dónde vive cada mitad del sistema y cómo se despliega cada una.

## Cómo funciona

### Streamlit Community Cloud — motor privado
Hostea la app Streamlit (`app.py`, este mismo repo `Vert_engine`). Soporta
apps privadas de forma nativa (control de acceso propio de Streamlit
Cloud) — no requiere VPS ni túnel SSH para mantenerla fuera del acceso
público. Deploy automático al pushear a la rama que el proyecto de
Streamlit Cloud tenga configurada como fuente.

Mecanismo de push desde la propia app hacia GitHub (botón "🚀 Publicar
sitio" en la barra lateral):
- Si existe un secret `GITHUB_TOKEN` (Settings → Secrets en el dashboard de
  Streamlit Cloud), se usa para autenticar `git push` embebiéndolo en la
  URL remota (`_authed_github_url`) — necesario porque un contenedor
  fresco de Streamlit Cloud no tiene credenciales de git ambientales (a
  diferencia de un Codespace, que sí las trae).
- Los commits automáticos ("Backup de datos desde el botón Publicar",
  "Publish desde el Engine...") usan una identidad de git fija
  (`user.name=VertLabs Engine`, `user.email=engine@vertlabs.run`) pasada
  por flag (`-c user.name=... -c user.email=...`), sin depender de
  `git config --global` — funciona igual en un contenedor que nunca tuvo
  git configurado.
- El token nunca se imprime en los logs que se muestran en la UI —
  `_redact_token()` lo reemplaza por `***` en cualquier salida de git antes
  de mostrarla.

### Cloudflare Pages — sitio público
Hostea el contenido de `output/` una vez copiado al repo `vertlabs-web`.
Dos ramas de `vertlabs-web`, dos destinos:

| Rama de `vertlabs-web` | Botón en `app.py` | Destino |
|---|---|---|
| `staging` | "📤 Publicar a Staging" | URL de preview automática que genera Cloudflare Pages |
| `main` | "✅ Promover a Producción" (requiere tildar una confirmación) | `vertlabs.run` |

Free tier de Cloudflare Pages con límite de 20k archivos por sitio —
suficiente para la escala real de VertLabs (~150-300 atletas de élite,
~30 carreras/año). <!-- TODO: el límite de 20k archivos es un dato de
plataforma externa, no verificable desde este repo; confirmar contra la
documentación vigente de Cloudflare Pages si se acerca a ese volumen. -->

## Decisiones clave / lecciones aprendidas
- El botón "Promover a Producción" exige tildar explícitamente "Confirmo
  publicar en PRODUCCIÓN" antes de habilitarse — sin eso el botón queda
  deshabilitado (`disabled=not confirm_prod`), para que no sea posible
  promover a `vertlabs.run` por error de un solo click.
- `_sync_output_to_web_repo()` mergea `output/` dentro del checkout local
  copiando/sobreescribiendo primero y borrando lo obsoleto después (nunca
  al revés) — si el proceso se corta a mitad de camino (contenedor que se
  cuelga, pestaña cerrada), el working tree queda con contenido viejo+nuevo
  mezclado en vez de medio borrado sin nada que lo reemplace.

## Problemas conocidos
Ver `docs/05-known-issues.md`.

## Archivos relacionados
- `app.py` — `_publish_to_branch`, `_sync_output_to_web_repo`,
  `_github_token`, `_configure_git_push_auth`, `_run_git`, `_redact_token`,
  bloque `with st.sidebar:`
