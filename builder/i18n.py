"""
UI copy for the three supported locales. Race/athlete data (names,
locations, dates) is never translated here - only site chrome. English
is the default/canonical locale (served at the site root); Spanish and
French are served under /es/ and /fr/.
"""

LOCALES = [
    {"code": "en", "label": "EN", "name": "English", "prefix": ""},
    {"code": "es", "label": "ES", "name": "Español", "prefix": "/es"},
    {"code": "fr", "label": "FR", "name": "Français", "prefix": "/fr"},
]

TRANSLATIONS = {
    "en": {
        "nav_races": "Races",
        "nav_athletes": "Athletes",
        "nav_rankings": "Rankings",
        "nav_about": "About VTL",
        "nav_search": "Search",
        "site_tagline": "Performance Intelligence for Trail Running",
        "site_hero_sub": (
            "Independent trail running intelligence powered by proprietary "
            "performance analytics. Explore races, compare athletes, and "
            "understand performance beyond the results."
        ),
        "home_latest_posts": "Latest Posts",
        "race_latest_posts": "Latest Posts",
        "event_no_posts": "No posts yet",
        "home_stat_races": "Races Analyzed",
        "home_stat_races_sub": "Published",
        "home_stat_athletes": "Athlete Reports",
        "home_stat_athletes_sub": "In-depth profiles",
        "home_stat_metrics": "Performance Metrics",
        "home_featured_label": "Race Analysis",
        "home_featured_desc": (
            "In-depth data insights into climbing efficiency, downhill "
            "mastery and endurance performance."
        ),
        "home_featured_cta": "View Analysis",
        "carousel_prev": "Previous",
        "carousel_next": "Next",
        "race_date_label": "Date",
        "race_distance_label": "Distance",
        "race_elevation_label": "Total Elevation Gain",
        "race_winning_time_label": "Winning Time",
        "races_title": "Races",
        "athletes_title": "Athletes",
        "athletes_jump_label": "Jump to letter",
        "athletes_search_placeholder": "Search athlete...",
        "athletes_filter_all": "All",
        "athletes_filter_men": "Men",
        "athletes_filter_women": "Women",
        "athletes_all_races": "All races",
        "athletes_all_years": "All years",
        "athletes_load_more": "Load more",
        "athletes_no_results": "No athletes found",
        "rankings_title": "Rankings",
        "rankings_subtitle": (
            "Career average per athlete. Only athletes with at least one "
            "calculated metric are included."
        ),
        "rankings_top_vpi": "Top VPI",
        "rankings_top_dmi": "Top DMI",
        "rankings_top_er": "Top ER",
        "about_title": "The Engine",
        "about_meta_title": "About Vertical Trail Labs | Trail Running Performance Intelligence",
        "about_meta_description": (
            "Learn about Vertical Trail Labs, an independent trail running "
            "performance platform analyzing terrain, race data and athlete "
            "performance."
        ),
        "about_tagline": "Built by a trail runner, for trail runners.",
        "about_intro_p1": (
            "Every race tells a story hidden in its terrain. The Vertical "
            "Trail Engine transforms official race profiles and checkpoint "
            "data into objective performance intelligence, revealing how "
            "athletes truly climb, descend, and endure."
        ),
        "about_intro_p2": (
            "Our proprietary methodology goes beyond finishing times to "
            "measure performance in the context of the terrain itself."
        ),
        "about_core_p1": (
            "The final result tells us who finished first. It doesn't "
            "necessarily tell us how an athlete performed across the "
            "mountain."
        ),
        "about_core_p2": (
            "VTL analyzes race terrain and checkpoint performance to "
            "understand what happens throughout a race: climbing, "
            "descending, terrain transitions, fatigue, pacing, endurance, "
            "and performance across different sections of the course."
        ),
        "about_core_p3": (
            "The platform transforms race data into structured performance "
            "information that can be explored at race and athlete level."
        ),
        "about_vpi_title": "VPI — Vertical Power Index",
        "video_vpi_label": "Watch: how VPI works",
        "video_close": "Close video",
        "about_vpi_desc": (
            "Meters of elevation gain per hour, measured only on strong-climb "
            "segments (slope ≥12%). Measures pure climbing efficiency and "
            "specific power output on severe vertical gains."
        ),
        "about_vpi_formula": "VPI = Σ(elevation gain on segments ≥12%) / Σ(athlete time on those segments)",
        "about_dmi_title": "DMI — Descent Mastery Index",
        "about_dmi_desc": (
            "Speed (km/h) on strong-descent segments (slope ≤-12%). Measures "
            "technical downhill skill and muscular resilience against heavy "
            "eccentric loading."
        ),
        "about_dmi_formula": "DMI = Σ(distance on segments ≤-12%) / Σ(athlete time on those segments)",
        "about_er_title": "ER — Endurance Rating",
        "about_er_desc": (
            "A 0-100 score measuring pacing degradation between the first "
            "and second half of the race, measured in effort-kilometers "
            "(distance + elevation/100) instead of raw distance."
        ),
        "about_er_formula": "ER = 100 − (pacing decay % between halves)",
        "founder_title": "Founder",
        "founder_name": "Pablo Jali",
        "founder_role": "Founder · Vertical Trail Labs",
        "founder_photo_alt": "Pablo Jali — Founder, Vertical Trail Labs",
        "founder_bio_p1": (
            "Vertical Trail Labs was created by Pablo Jali, a trail runner "
            "interested in understanding what happens beyond the finish "
            "line."
        ),
        "founder_bio_p2": (
            "The idea behind VTL came from a simple observation: race "
            "results tell us who finished first, but they only tell part "
            "of the story."
        ),
        "founder_bio_p3": (
            "Mountain races are shaped by terrain, climbing, descending, "
            "pacing and fatigue. VTL was created to analyze those elements "
            "and turn them into measurable performance signals."
        ),
        "founder_bio_p4": (
            "What started as a personal project has evolved into an "
            "independent platform focused on building a structured "
            "database of trail running performance."
        ),
        "independent_title": "Independent project",
        "independent_statement": (
            "Vertical Trail Labs is an independent project and is not "
            "affiliated with UTMB, LiveTrail or any race organizer unless "
            "explicitly stated."
        ),
        "about_contact_title": "Contact",
        "about_contact_body": "Questions, collaborations, data requests or feedback?",
        "about_contact_cta": "Get in touch at",
        "share_button_label": "Share",
        "share_copy_link": "Copy link",
        "share_link_copied": "Link copied",
        "share_title_suffix": "VTL Performance Analysis",
        "search_title": "Search",
        "search_placeholder": "Race or athlete...",
        "race_performance_title": "Performance by athlete",
        "race_pos": "Pos",
        "race_bib": "Bib",
        "race_athlete": "Athlete",
        "race_time": "Time",
        "race_pace_1h": "1st Half Pace",
        "race_pace_2h": "2nd Half Pace",
        "post_see_all_prefix": "See all ",
        "post_see_all_suffix": " runners analyzed in this race →",
        "event_card_athletes_label": "athletes analyzed",
        "race_metric_note": "VPI in m/h · DMI in km/h · ER is a 0-100 score.",
        "race_how_calculated": "How is this calculated?",
        "race_runner_charts_title": "Runner Charts",
        "report_back": "Back to profile",
        "athlete_profile_title": "VTL Performance Profile",
        "athlete_profile_vpi_caption": "Climbing",
        "athlete_profile_dmi_caption": "Descending",
        "athlete_profile_er_caption": "Endurance",
        "athlete_profile_race_singular": "race analyzed",
        "athlete_profile_races_plural": "races analyzed",
        "athlete_profile_maturity_early": "Early signal",
        "athlete_profile_maturity_emerging": "Emerging profile",
        "athlete_profile_maturity_established": "Established profile",
        "athlete_profile_maturity_high_confidence": "High-confidence profile",
        "athlete_profile_empty": "Performance profile will appear once sufficient race data is available.",
        "athlete_profile_legend_short": "≤80K",
        "athlete_profile_legend_mid": "80–120K",
        "athlete_profile_legend_long": ">120K",
        "athlete_race_history": "Race History",
        "athlete_race_col": "Race",
        "athlete_year": "Year",
        "athlete_distance_col": "Distance",
        "athlete_gender_pos": "Gender Pos",
        "breadcrumb_races": "Races",
        "breadcrumb_athletes": "Athletes",
        "footer_tagline": "Trail running performance engine.",
        "notfound_title": "Page not found.",
        "notfound_body": (
            "The athlete, race or analysis you're looking for may not "
            "exist or may have moved."
        ),
        "notfound_cta_athletes": "Back to Athletes",
        "notfound_cta_races": "Explore Races",
        "notfound_cta_home": "Home",
        "analysis_meta_title": "Get Your VTL Analysis | Vertical Trail Labs",
        "analysis_meta_description": (
            "Submit your race data and GPX file to get a personal VTL "
            "performance analysis - VPI, DMI and ER for your own race."
        ),
        "analysis_title": "Get Your VTL Analysis",
        "analysis_intro_p1": "Want to see what your race tells us?",
        "analysis_intro_p2": (
            "Send us your race details and GPX file. We'll review your "
            "data and get back to you."
        ),
        "analysis_field_name": "Name",
        "analysis_field_email": "Email",
        "analysis_field_race": "Race",
        "analysis_field_distance": "Distance",
        "analysis_field_date": "Race date",
        "analysis_field_gpx": "GPX file",
        "analysis_field_message": "Message (optional)",
        "analysis_submit": "Request Analysis",
        "analysis_submitting": "Sending…",
        "analysis_success_title": "Request Received",
        "analysis_success_body": (
            "Thanks — your analysis request has been received. We'll "
            "review your race data and get back to you."
        ),
        "analysis_privacy_note": (
            "Your information and GPX file will only be used to process "
            "your VTL analysis request. We do not publish submitted "
            "personal data without permission."
        ),
        "analysis_error_generic": "Something went wrong. Please try again.",
        "analysis_error_required": "Please fill in all required fields.",
        "analysis_error_email": "Please enter a valid email address.",
        "analysis_error_gpx_type": "Please upload a .gpx file.",
        "analysis_error_gpx_size": "The GPX file is too large (max 8 MB).",
        "analysis_cta_title": "Want Your Own Analysis?",
        "analysis_cta_body": "See what your race tells us.",
        "analysis_cta_button": "Get Your Analysis",
        "home_analysis_title": "Your Race. Your Data.",
        "home_analysis_body": "Get your own VTL performance analysis based on your race data.",
    },
    "es": {
        "nav_races": "Carreras",
        "nav_athletes": "Atletas",
        "nav_rankings": "Rankings",
        "nav_about": "Acerca de VTL",
        "nav_search": "Buscar",
        "site_tagline": "Inteligencia de rendimiento para el trail running",
        "site_hero_sub": (
            "Inteligencia independiente de trail running impulsada por "
            "analítica de rendimiento propia. Explorá carreras, comparás "
            "atletas y entendé el rendimiento más allá de los resultados."
        ),
        "home_latest_posts": "Últimos Posts",
        "race_latest_posts": "Últimos Posts",
        "event_no_posts": "Todavía no hay posts",
        "home_stat_races": "Carreras Analizadas",
        "home_stat_races_sub": "Publicadas",
        "home_stat_athletes": "Perfiles de Atletas",
        "home_stat_athletes_sub": "Análisis en profundidad",
        "home_stat_metrics": "Métricas de Rendimiento",
        "home_featured_label": "Análisis de Carrera",
        "home_featured_desc": (
            "Datos en profundidad sobre eficiencia de escalada, dominio en "
            "bajada y rendimiento de resistencia."
        ),
        "home_featured_cta": "Ver análisis",
        "carousel_prev": "Anterior",
        "carousel_next": "Siguiente",
        "race_date_label": "Fecha",
        "race_distance_label": "Distancia",
        "race_elevation_label": "Desnivel Positivo Total",
        "race_winning_time_label": "Tiempo Ganador",
        "races_title": "Carreras",
        "athletes_title": "Atletas",
        "athletes_jump_label": "Saltar a letra",
        "athletes_search_placeholder": "Buscar atleta...",
        "athletes_filter_all": "Todos",
        "athletes_filter_men": "Hombres",
        "athletes_filter_women": "Mujeres",
        "athletes_all_races": "Todas las carreras",
        "athletes_all_years": "Todos los años",
        "athletes_load_more": "Cargar más",
        "athletes_no_results": "No se encontraron atletas",
        "rankings_title": "Rankings",
        "rankings_subtitle": (
            "Promedio de carrera por atleta. Solo se incluyen atletas con al "
            "menos una métrica calculada."
        ),
        "rankings_top_vpi": "Top VPI",
        "rankings_top_dmi": "Top DMI",
        "rankings_top_er": "Top ER",
        "about_title": "El Engine",
        "about_meta_title": "Acerca de Vertical Trail Labs | Inteligencia de Rendimiento en Trail Running",
        "about_meta_description": (
            "Conocé Vertical Trail Labs, una plataforma independiente de "
            "rendimiento en trail running que analiza terreno, datos de "
            "carrera y rendimiento de atletas."
        ),
        "about_tagline": "Creado por un corredor de trail, para corredores de trail.",
        "about_intro_p1": (
            "Cada carrera esconde una historia en su terreno. El Vertical "
            "Trail Engine transforma los perfiles oficiales de carrera y los "
            "datos de checkpoints en inteligencia de rendimiento objetiva, "
            "revelando cómo los atletas realmente escalan, descienden y "
            "resisten."
        ),
        "about_intro_p2": (
            "Nuestra metodología propia va más allá de los tiempos finales "
            "para medir el rendimiento en el contexto del terreno mismo."
        ),
        "about_core_p1": (
            "El resultado final nos dice quién llegó primero. No "
            "necesariamente nos dice cómo rindió un atleta a lo largo de "
            "la montaña."
        ),
        "about_core_p2": (
            "VTL analiza el terreno de la carrera y el rendimiento en los "
            "puntos de control para entender qué pasa durante la carrera: "
            "subidas, bajadas, transiciones de terreno, fatiga, ritmo, "
            "resistencia y rendimiento en las distintas secciones del "
            "recorrido."
        ),
        "about_core_p3": (
            "La plataforma transforma los datos de carrera en información "
            "de rendimiento estructurada, explorable a nivel de carrera y "
            "de atleta."
        ),
        "about_vpi_title": "VPI — Vertical Power Index",
        "video_vpi_label": "Ver: cómo funciona el VPI",
        "video_close": "Cerrar video",
        "about_vpi_desc": (
            "Metros de desnivel positivo por hora, medidos únicamente en los "
            "tramos de fuerte pendiente (≥12%). Mide la eficiencia y potencia "
            "específica en subida severa."
        ),
        "about_vpi_formula": "VPI = Σ(desnivel+ en tramos ≥12%) / Σ(tiempo del atleta en esos tramos)",
        "about_dmi_title": "DMI — Descent Mastery Index",
        "about_dmi_desc": (
            "Velocidad (km/h) en los tramos de fuerte descenso (≤-12%). Mide "
            "la habilidad técnica de bajada y la resiliencia muscular frente "
            "a la carga excéntrica."
        ),
        "about_dmi_formula": "DMI = Σ(distancia en tramos ≤-12%) / Σ(tiempo del atleta en esos tramos)",
        "about_er_title": "ER — Endurance Rating",
        "about_er_desc": (
            "Score de 0 a 100 que mide la degradación de ritmo entre la "
            "primera y la segunda mitad de la carrera, medida en kilómetros "
            "de esfuerzo (distancia + desnivel/100) en vez de kilómetros "
            "crudos."
        ),
        "about_er_formula": "ER = 100 − (decaimiento de ritmo % entre mitades)",
        "founder_title": "Fundador",
        "founder_name": "Pablo Jali",
        "founder_role": "Fundador · Vertical Trail Labs",
        "founder_photo_alt": "Pablo Jali — Fundador, Vertical Trail Labs",
        "founder_bio_p1": (
            "Vertical Trail Labs fue creado por Pablo Jali, un corredor de "
            "trail interesado en entender qué pasa más allá de la línea de "
            "meta."
        ),
        "founder_bio_p2": (
            "La idea de VTL surgió de una observación simple: los "
            "resultados de carrera nos dicen quién llegó primero, pero "
            "solo cuentan parte de la historia."
        ),
        "founder_bio_p3": (
            "Las carreras de montaña están definidas por el terreno, la "
            "subida, la bajada, el ritmo y la fatiga. VTL nació para "
            "analizar esos elementos y convertirlos en señales de "
            "rendimiento medibles."
        ),
        "founder_bio_p4": (
            "Lo que empezó como un proyecto personal evolucionó hacia una "
            "plataforma independiente enfocada en construir una base de "
            "datos estructurada de rendimiento en trail running."
        ),
        "independent_title": "Proyecto independiente",
        "independent_statement": (
            "Vertical Trail Labs es un proyecto independiente y no está "
            "afiliado a UTMB, LiveTrail ni a ningún organizador de "
            "carreras, salvo que se indique explícitamente."
        ),
        "about_contact_title": "Contacto",
        "about_contact_body": "¿Preguntas, propuestas de colaboración, correcciones de datos o feedback?",
        "about_contact_cta": "Escribinos a",
        "share_button_label": "Compartir",
        "share_copy_link": "Copiar enlace",
        "share_link_copied": "Enlace copiado",
        "share_title_suffix": "Análisis de Rendimiento VTL",
        "search_title": "Buscar",
        "search_placeholder": "Carrera o atleta...",
        "race_performance_title": "Rendimiento por corredor",
        "race_pos": "Pos",
        "race_bib": "Dorsal",
        "race_athlete": "Corredor",
        "race_time": "Tiempo",
        "race_pace_1h": "Ritmo 1ª Mitad",
        "race_pace_2h": "Ritmo 2ª Mitad",
        "post_see_all_prefix": "Ver los ",
        "post_see_all_suffix": " corredores analizados en esta carrera →",
        "event_card_athletes_label": "corredores analizados",
        "race_metric_note": "VPI en m/h · DMI en km/h · ER es un score 0-100.",
        "race_how_calculated": "¿Cómo se calculan?",
        "race_runner_charts_title": "Gráficos por corredor",
        "report_back": "Volver al perfil",
        "athlete_profile_title": "Perfil de Rendimiento VTL",
        "athlete_profile_vpi_caption": "Subida",
        "athlete_profile_dmi_caption": "Bajada",
        "athlete_profile_er_caption": "Resistencia",
        "athlete_profile_race_singular": "carrera analizada",
        "athlete_profile_races_plural": "carreras analizadas",
        "athlete_profile_maturity_early": "Señal inicial",
        "athlete_profile_maturity_emerging": "Perfil emergente",
        "athlete_profile_maturity_established": "Perfil establecido",
        "athlete_profile_maturity_high_confidence": "Perfil de alta confianza",
        "athlete_profile_empty": "El perfil de rendimiento va a aparecer cuando haya suficientes datos de carreras.",
        "athlete_profile_legend_short": "≤80K",
        "athlete_profile_legend_mid": "80–120K",
        "athlete_profile_legend_long": ">120K",
        "athlete_race_history": "Historial de carreras",
        "athlete_race_col": "Carrera",
        "athlete_year": "Año",
        "athlete_distance_col": "Distancia",
        "athlete_gender_pos": "Pos. Categoría",
        "breadcrumb_races": "Carreras",
        "breadcrumb_athletes": "Atletas",
        "footer_tagline": "Motor de análisis de rendimiento en trail running.",
        "notfound_title": "Página no encontrada.",
        "notfound_body": (
            "El atleta, la carrera o el análisis que buscás puede no "
            "existir o haberse movido."
        ),
        "notfound_cta_athletes": "Volver a Atletas",
        "notfound_cta_races": "Explorar Carreras",
        "notfound_cta_home": "Inicio",
        "analysis_meta_title": "Obtené tu Análisis VTL | Vertical Trail Labs",
        "analysis_meta_description": (
            "Enviá los datos de tu carrera y tu archivo GPX para obtener "
            "tu propio análisis de rendimiento VTL - VPI, DMI y ER."
        ),
        "analysis_title": "Obtené tu Análisis VTL",
        "analysis_intro_p1": "¿Querés ver qué te dice tu carrera?",
        "analysis_intro_p2": (
            "Envianos los detalles de tu carrera y tu archivo GPX. Vamos "
            "a revisar tus datos y responderte."
        ),
        "analysis_field_name": "Nombre",
        "analysis_field_email": "Email",
        "analysis_field_race": "Carrera",
        "analysis_field_distance": "Distancia",
        "analysis_field_date": "Fecha de la carrera",
        "analysis_field_gpx": "Archivo GPX",
        "analysis_field_message": "Mensaje (opcional)",
        "analysis_submit": "Solicitar Análisis",
        "analysis_submitting": "Enviando…",
        "analysis_success_title": "Solicitud Recibida",
        "analysis_success_body": (
            "Gracias — tu solicitud de análisis fue recibida. Vamos a "
            "revisar los datos de tu carrera y responderte."
        ),
        "analysis_privacy_note": (
            "Tu información y archivo GPX se van a usar solo para "
            "procesar tu solicitud de análisis VTL. No publicamos datos "
            "personales enviados sin permiso."
        ),
        "analysis_error_generic": "Algo salió mal. Probá de nuevo.",
        "analysis_error_required": "Completá todos los campos obligatorios.",
        "analysis_error_email": "Ingresá un email válido.",
        "analysis_error_gpx_type": "Subí un archivo .gpx.",
        "analysis_error_gpx_size": "El archivo GPX es demasiado grande (máx. 8 MB).",
        "analysis_cta_title": "¿Querés tu propio análisis?",
        "analysis_cta_body": "Mirá qué te dice tu carrera.",
        "analysis_cta_button": "Obtené tu Análisis",
        "home_analysis_title": "Tu Carrera. Tus Datos.",
        "home_analysis_body": "Obtené tu propio análisis de rendimiento VTL basado en los datos de tu carrera.",
    },
    "fr": {
        "nav_races": "Courses",
        "nav_athletes": "Athlètes",
        "nav_rankings": "Classements",
        "nav_about": "À propos de VTL",
        "nav_search": "Rechercher",
        "site_tagline": "Intelligence de performance pour le trail running",
        "site_hero_sub": (
            "Intelligence indépendante du trail running propulsée par une "
            "analyse de performance propriétaire. Explorez les courses, "
            "comparez les athlètes et comprenez la performance au-delà des "
            "résultats."
        ),
        "home_latest_posts": "Derniers Articles",
        "race_latest_posts": "Derniers Articles",
        "event_no_posts": "Pas encore d'articles",
        "home_stat_races": "Courses Analysées",
        "home_stat_races_sub": "Publiées",
        "home_stat_athletes": "Profils d'Athlètes",
        "home_stat_athletes_sub": "Analyses détaillées",
        "home_stat_metrics": "Métriques de Performance",
        "home_featured_label": "Analyse de Course",
        "home_featured_desc": (
            "Analyse approfondie de l'efficacité en montée, de la maîtrise "
            "en descente et de la performance d'endurance."
        ),
        "home_featured_cta": "Voir l'analyse",
        "carousel_prev": "Précédent",
        "carousel_next": "Suivant",
        "race_date_label": "Date",
        "race_distance_label": "Distance",
        "race_elevation_label": "Dénivelé Positif Total",
        "race_winning_time_label": "Temps Vainqueur",
        "races_title": "Courses",
        "athletes_title": "Athlètes",
        "athletes_jump_label": "Aller à la lettre",
        "athletes_search_placeholder": "Rechercher un athlète...",
        "athletes_filter_all": "Tous",
        "athletes_filter_men": "Hommes",
        "athletes_filter_women": "Femmes",
        "athletes_all_races": "Toutes les courses",
        "athletes_all_years": "Toutes les années",
        "athletes_load_more": "Charger plus",
        "athletes_no_results": "Aucun athlète trouvé",
        "rankings_title": "Classements",
        "rankings_subtitle": (
            "Moyenne de carrière par athlète. Seuls les athlètes avec au "
            "moins une métrique calculée sont inclus."
        ),
        "rankings_top_vpi": "Top VPI",
        "rankings_top_dmi": "Top DMI",
        "rankings_top_er": "Top ER",
        "about_title": "Le Moteur",
        "about_meta_title": "À propos de Vertical Trail Labs | Intelligence de Performance en Trail Running",
        "about_meta_description": (
            "Découvrez Vertical Trail Labs, une plateforme indépendante de "
            "performance en trail running qui analyse le terrain, les "
            "données de course et la performance des athlètes."
        ),
        "about_tagline": "Créé par un coureur de trail, pour les coureurs de trail.",
        "about_intro_p1": (
            "Chaque course cache une histoire dans son terrain. Le Vertical "
            "Trail Engine transforme les profils officiels de course et les "
            "données de points de contrôle en intelligence de performance "
            "objective, révélant comment les athlètes grimpent, descendent "
            "et endurent réellement."
        ),
        "about_intro_p2": (
            "Notre méthodologie propriétaire va au-delà des temps d'arrivée "
            "pour mesurer la performance dans le contexte du terrain "
            "lui-même."
        ),
        "about_core_p1": (
            "Le résultat final nous dit qui a fini premier. Il ne nous dit "
            "pas nécessairement comment un athlète a performé à travers la "
            "montagne."
        ),
        "about_core_p2": (
            "VTL analyse le terrain de la course et la performance aux "
            "points de contrôle pour comprendre ce qui se passe pendant "
            "la course : montée, descente, transitions de terrain, "
            "fatigue, gestion de l'effort, endurance, et performance sur "
            "les différentes sections du parcours."
        ),
        "about_core_p3": (
            "La plateforme transforme les données de course en "
            "informations de performance structurées, consultables au "
            "niveau de la course et de l'athlète."
        ),
        "about_vpi_title": "VPI — Vertical Power Index",
        "video_vpi_label": "Voir : comment fonctionne le VPI",
        "video_close": "Fermer la vidéo",
        "about_vpi_desc": (
            "Mètres de dénivelé positif par heure, mesurés uniquement sur "
            "les tronçons à forte pente (≥12%). Mesure l'efficacité pure en "
            "montée et la puissance spécifique sur fort dénivelé."
        ),
        "about_vpi_formula": "VPI = Σ(dénivelé+ sur tronçons ≥12%) / Σ(temps de l'athlète sur ces tronçons)",
        "about_dmi_title": "DMI — Descent Mastery Index",
        "about_dmi_desc": (
            "Vitesse (km/h) sur les tronçons à forte descente (≤-12%). "
            "Mesure la technicité en descente et la résilience musculaire "
            "face à la charge excentrique."
        ),
        "about_dmi_formula": "DMI = Σ(distance sur tronçons ≤-12%) / Σ(temps de l'athlète sur ces tronçons)",
        "about_er_title": "ER — Endurance Rating",
        "about_er_desc": (
            "Score de 0 à 100 mesurant la dégradation du rythme entre la "
            "première et la seconde moitié de la course, mesurée en "
            "kilomètres d'effort (distance + dénivelé/100) plutôt qu'en "
            "distance brute."
        ),
        "about_er_formula": "ER = 100 − (décroissance du rythme % entre les moitiés)",
        "founder_title": "Fondateur",
        "founder_name": "Pablo Jali",
        "founder_role": "Fondateur · Vertical Trail Labs",
        "founder_photo_alt": "Pablo Jali — Fondateur, Vertical Trail Labs",
        "founder_bio_p1": (
            "Vertical Trail Labs a été créé par Pablo Jali, un coureur de "
            "trail intéressé par ce qui se passe au-delà de la ligne "
            "d'arrivée."
        ),
        "founder_bio_p2": (
            "L'idée de VTL est née d'une observation simple : les "
            "résultats de course nous disent qui a fini premier, mais ils "
            "ne racontent qu'une partie de l'histoire."
        ),
        "founder_bio_p3": (
            "Les courses de montagne sont façonnées par le terrain, la "
            "montée, la descente, la gestion de l'effort et la fatigue. "
            "VTL a été créé pour analyser ces éléments et les transformer "
            "en signaux de performance mesurables."
        ),
        "founder_bio_p4": (
            "Ce qui a commencé comme un projet personnel est devenu une "
            "plateforme indépendante dédiée à la construction d'une base "
            "de données structurée de la performance en trail running."
        ),
        "independent_title": "Projet indépendant",
        "independent_statement": (
            "Vertical Trail Labs est un projet indépendant et n'est "
            "affilié à l'UTMB, LiveTrail ni à aucun organisateur de "
            "course, sauf mention explicite."
        ),
        "about_contact_title": "Contact",
        "about_contact_body": "Des questions, une collaboration, une correction de données ou un retour ?",
        "about_contact_cta": "Écrivez-nous à",
        "share_button_label": "Partager",
        "share_copy_link": "Copier le lien",
        "share_link_copied": "Lien copié",
        "share_title_suffix": "Analyse de Performance VTL",
        "search_title": "Rechercher",
        "search_placeholder": "Course ou athlète...",
        "race_performance_title": "Performance par athlète",
        "race_pos": "Pos",
        "race_bib": "Dossard",
        "race_athlete": "Athlète",
        "race_time": "Temps",
        "race_pace_1h": "Allure 1ère Moitié",
        "race_pace_2h": "Allure 2ème Moitié",
        "post_see_all_prefix": "Voir les ",
        "post_see_all_suffix": " coureurs analysés dans cette course →",
        "event_card_athletes_label": "coureurs analysés",
        "race_metric_note": "VPI en m/h · DMI en km/h · ER est un score sur 100.",
        "race_how_calculated": "Comment est-ce calculé ?",
        "race_runner_charts_title": "Graphiques par coureur",
        "report_back": "Retour au profil",
        "athlete_profile_title": "Profil de Performance VTL",
        "athlete_profile_vpi_caption": "Montée",
        "athlete_profile_dmi_caption": "Descente",
        "athlete_profile_er_caption": "Endurance",
        "athlete_profile_race_singular": "course analysée",
        "athlete_profile_races_plural": "courses analysées",
        "athlete_profile_maturity_early": "Signal initial",
        "athlete_profile_maturity_emerging": "Profil émergent",
        "athlete_profile_maturity_established": "Profil établi",
        "athlete_profile_maturity_high_confidence": "Profil haute confiance",
        "athlete_profile_empty": "Le profil de performance apparaîtra une fois que suffisamment de données de course seront disponibles.",
        "athlete_profile_legend_short": "≤80K",
        "athlete_profile_legend_mid": "80–120K",
        "athlete_profile_legend_long": ">120K",
        "athlete_race_history": "Historique des courses",
        "athlete_race_col": "Course",
        "athlete_year": "Année",
        "athlete_distance_col": "Distance",
        "athlete_gender_pos": "Pos. Catégorie",
        "breadcrumb_races": "Courses",
        "breadcrumb_athletes": "Athlètes",
        "footer_tagline": "Moteur d'analyse de performance en trail running.",
        "notfound_title": "Page introuvable.",
        "notfound_body": (
            "L'athlète, la course ou l'analyse que vous cherchez n'existe "
            "peut-être plus ou a été déplacé(e)."
        ),
        "notfound_cta_athletes": "Retour aux Athlètes",
        "notfound_cta_races": "Explorer les Courses",
        "notfound_cta_home": "Accueil",
        "analysis_meta_title": "Obtenez votre Analyse VTL | Vertical Trail Labs",
        "analysis_meta_description": (
            "Envoyez les données de votre course et votre fichier GPX "
            "pour obtenir votre analyse de performance VTL personnelle - "
            "VPI, DMI et ER."
        ),
        "analysis_title": "Obtenez votre Analyse VTL",
        "analysis_intro_p1": "Vous voulez voir ce que votre course révèle ?",
        "analysis_intro_p2": (
            "Envoyez-nous les détails de votre course et votre fichier "
            "GPX. Nous allons examiner vos données et vous répondre."
        ),
        "analysis_field_name": "Nom",
        "analysis_field_email": "Email",
        "analysis_field_race": "Course",
        "analysis_field_distance": "Distance",
        "analysis_field_date": "Date de la course",
        "analysis_field_gpx": "Fichier GPX",
        "analysis_field_message": "Message (optionnel)",
        "analysis_submit": "Demander une Analyse",
        "analysis_submitting": "Envoi…",
        "analysis_success_title": "Demande Reçue",
        "analysis_success_body": (
            "Merci — votre demande d'analyse a été reçue. Nous allons "
            "examiner les données de votre course et vous répondre."
        ),
        "analysis_privacy_note": (
            "Vos informations et votre fichier GPX ne seront utilisés "
            "que pour traiter votre demande d'analyse VTL. Nous ne "
            "publions pas les données personnelles envoyées sans "
            "autorisation."
        ),
        "analysis_error_generic": "Une erreur s'est produite. Veuillez réessayer.",
        "analysis_error_required": "Veuillez remplir tous les champs obligatoires.",
        "analysis_error_email": "Veuillez entrer une adresse email valide.",
        "analysis_error_gpx_type": "Veuillez téléverser un fichier .gpx.",
        "analysis_error_gpx_size": "Le fichier GPX est trop volumineux (max. 8 Mo).",
        "analysis_cta_title": "Vous voulez votre propre analyse ?",
        "analysis_cta_body": "Découvrez ce que votre course révèle.",
        "analysis_cta_button": "Obtenez votre Analyse",
        "home_analysis_title": "Votre Course. Vos Données.",
        "home_analysis_body": "Obtenez votre propre analyse de performance VTL basée sur les données de votre course.",
    },
}
