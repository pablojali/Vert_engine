# =============================================================================
# INTEGRACIÓN: pestaña "🧩 Checkpoint Fetcher"
# =============================================================================
#
# 1) Agrega estas dos funciones junto a las demás funciones del motor
#    (por ejemplo, justo después de `fetch_runner_by_tenant_and_bib`).
#
# 2) Agrega `tab_checkpoints` a la línea de `st.tabs(...)`.
#
# 3) Agrega el bloque `with tab_checkpoints:` al final, junto a los demás
#    `with tab_...:`.
#
# =============================================================================


# --- 1) FUNCIONES DEL MOTOR (agregar junto a las demás funciones) ----------

def fetch_livetrail_checkpoints(race_id: str, tenant: str, url: str):
    """
    Descarga la lista de checkpoints (pointId, name, distance, elevationGain)
    desde el endpoint de Livetrail. Requiere el header X-Tenant, igual que
    el endpoint de runner de utmb.world. Origin/Referer se derivan del
    tenant (ej: "aranbyutmb_2026" -> "aranbyutmb.v3.livetrail.net"), para
    que funcione con cualquier carrera sin tocar código.
    """
    subdomain = tenant.rsplit("_", 1)[0]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Origin": f"https://{subdomain}.v3.livetrail.net",
        "Referer": f"https://{subdomain}.v3.livetrail.net/",
        "X-Tenant": tenant,
    }
    response = requests.get(url, params={"raceId": race_id}, headers=headers, timeout=15)
    response.raise_for_status()
    return response.json()


def build_registry_checkpoints_block(gpx_file: str, race_slug_api: str, points: list) -> str:
    """
    Convierte la respuesta cruda de Livetrail al bloque de texto EXACTO
    que se pega dentro de data/races_registry.json:

        {
          "gpx_file": "...",
          "race_slug_api": "...",
          "checkpoints": [
            {"id": "0", "nombre": "...", "km": 0.0},
            ...
          ]
        }

    Ordena por distancia ascendente, usa 'name' (no 'shortName'), y alinea
    las columnas del array de checkpoints al estilo ya usado a mano en el
    registry (para que el copy-paste no rompa el formato visual existente).
    """
    sorted_points = sorted(points, key=lambda p: p["distance"])
    checkpoints = [
        {
            "id": str(p["pointId"]),
            "nombre": p["name"],
            "km": round(p["distance"] / 1000, 1),
        }
        for p in sorted_points
    ]

    # Alineación estilo "tabla" (igual que el registry existente)
    id_width = max(len(f'"{cp["id"]}"') for cp in checkpoints) + 1
    nombre_width = max(len(f'"{cp["nombre"]}"') for cp in checkpoints) + 1

    lines = []
    for cp in checkpoints:
        id_str = f'"{cp["id"]}",'.ljust(id_width + 1)
        nombre_str = f'"{cp["nombre"]}",'.ljust(nombre_width + 1)
        lines.append(f'    {{"id": {id_str} "nombre": {nombre_str} "km": {cp["km"]}}}')

    checkpoints_block = ",\n".join(lines)

    return (
        "{\n"
        f'  "gpx_file": "{gpx_file}",\n'
        f'  "race_slug_api": "{race_slug_api}",\n'
        '  "checkpoints": [\n'
        f"{checkpoints_block}\n"
        "  ]\n"
        "},"
    )


# --- 2) Agregar a la línea de st.tabs(...) ----------------------------------
#
# ANTES:
#
# tab_race, tab_runner, tab_gpx, tab_comparison, tab_top, tab_methodology = st.tabs(
#     ["🗺️ Race Analysis", "🏃 Runner Metrics", "🛰️ GPX Metrics", "⚖️ UTMB vs GPX",
#      "🏆 Top Runners", "📖 Indices & Methodology"]
# )
#
# DESPUÉS:
#
# tab_race, tab_runner, tab_gpx, tab_comparison, tab_top, tab_methodology, tab_checkpoints = st.tabs(
#     ["🗺️ Race Analysis", "🏃 Runner Metrics", "🛰️ GPX Metrics", "⚖️ UTMB vs GPX",
#      "🏆 Top Runners", "📖 Indices & Methodology", "🧩 Checkpoint Fetcher"]
# )


# --- 3) BLOQUE DE LA PESTAÑA (agregar al final, junto a los demás with tab_...) ---

CHECKPOINT_FETCHER_TAB_CODE = '''
with tab_checkpoints:
    st.header("🧩 Checkpoint Fetcher (Livetrail)")
    st.caption(
        "Descarga la lista de checkpoints (id, nombre, km) de cualquier carrera que use "
        "Livetrail como proveedor de cronometraje, y genera el bloque listo para pegar "
        "en `data/races_registry.json`."
    )

    with st.form("checkpoint_fetcher_form"):
        col1, col2 = st.columns(2)
        with col1:
            cf_race_id = st.text_input(
                "Race ID (raceId)", value="vda",
                help="El slug de la carrera dentro del tenant, ej: 'vda' para Val d'Aran.",
            )
            cf_tenant = st.text_input(
                "X-Tenant", value="aranbyutmb_2026",
                help="Formato raceslug_year, ej: 'aranbyutmb_2026'.",
            )
            cf_url = st.text_input(
                "Request URL (endpoint de Livetrail)",
                value="https://api.v3.livetrail.net/api/events/points",
                help="La Request URL exacta vista en DevTools > Network (sin el query string).",
            )
        with col2:
            cf_gpx_file = st.text_input(
                "gpx_file (ruta relativa)",
                value="data/gpx/<carrera>/<anio>/<ARCHIVO>.gpx",
                help="Ruta al GPX oficial que vas a subir/ya subiste para esta carrera.",
            )
            cf_race_slug_api = st.text_input(
                "race_slug_api", value="",
                help="Normalmente igual al Race ID (se autocompleta si lo dejas vacío).",
            )

        cf_submit = st.form_submit_button("🧩 Fetch checkpoints", type="primary", use_container_width=True)

    if cf_submit:
        if not cf_race_id or not cf_tenant or not cf_url:
            st.warning("Completa al menos Race ID, X-Tenant y Request URL.")
        else:
            with st.spinner("Consultando Livetrail..."):
                try:
                    raw_points = fetch_livetrail_checkpoints(cf_race_id, cf_tenant, cf_url)
                    cf_error = None
                except Exception:
                    raw_points = None
                    cf_error = traceback.format_exc()

            if cf_error:
                st.error("❌ No se pudo obtener la lista de checkpoints.")
                with st.expander("Ver detalle técnico del error"):
                    st.code(cf_error, language="python")
            elif not raw_points:
                st.warning("⚠️ La respuesta llegó vacía. Revisa el Race ID y el X-Tenant.")
            else:
                effective_slug = cf_race_slug_api.strip() or cf_race_id

                st.success(f"✅ {len(raw_points)} checkpoints encontrados para raceId='{cf_race_id}'.")

                # Preview en tabla, ordenada por distancia
                preview_rows = [
                    {
                        "id": p["pointId"],
                        "nombre": p["name"],
                        "km": round(p["distance"] / 1000, 1),
                        "altitud (m)": p.get("altitude"),
                        "ganancia acum. (m)": p.get("elevationGain"),
                    }
                    for p in sorted(raw_points, key=lambda x: x["distance"])
                ]
                st.dataframe(preview_rows, use_container_width=True, hide_index=True)

                registry_block = build_registry_checkpoints_block(
                    cf_gpx_file, effective_slug, raw_points
                )

                st.markdown("##### 📋 Bloque listo para pegar en `races_registry.json`")
                st.code(registry_block, language="json")

                st.download_button(
                    "📥 Descargar como .json",
                    data=registry_block.encode("utf-8"),
                    file_name=f"{cf_race_id}_checkpoints.json",
                    mime="application/json",
                    use_container_width=True,
                )
'''