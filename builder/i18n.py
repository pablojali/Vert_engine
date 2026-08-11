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
        "nav_about": "Engine",
        "nav_search": "Search",
        "site_tagline": "Performance Intelligence for Trail Running",
        "site_hero_sub": (
            "Independent trail running intelligence powered by proprietary "
            "performance analytics. Explore races, compare athletes, and "
            "understand performance beyond the results."
        ),
        "home_latest_races": "Latest Analyses",
        "home_see_all": "See all →",
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
        "race_date_label": "Date",
        "race_distance_label": "Distance",
        "race_elevation_label": "Total Elevation Gain",
        "race_winning_time_label": "Winning Time",
        "races_title": "Races",
        "athletes_title": "Athletes",
        "athletes_jump_label": "Jump to letter",
        "rankings_title": "Rankings",
        "rankings_subtitle": (
            "Career average per athlete. Only athletes with at least one "
            "calculated metric are included."
        ),
        "rankings_top_vpi": "Top VPI",
        "rankings_top_dmi": "Top DMI",
        "rankings_top_er": "Top ER",
        "about_title": "The Engine",
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
        "about_vpi_title": "VPI — Vertical Power Index",
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
        "search_title": "Search",
        "search_placeholder": "Race or athlete...",
        "race_performance_title": "Performance by athlete",
        "race_pos": "Pos",
        "race_bib": "Bib",
        "race_athlete": "Athlete",
        "race_time": "Time",
        "race_pace_1h": "1st Half Pace",
        "race_pace_2h": "2nd Half Pace",
        "race_metric_note": "VPI in m/h · DMI in km/h · ER is a 0-100 score.",
        "race_how_calculated": "How is this calculated?",
        "race_runner_charts_title": "Runner Charts",
        "report_back": "Back to profile",
        "athlete_career_avg": "Career Averages",
        "athlete_race_history": "Race History",
        "athlete_race_col": "Race",
        "athlete_year": "Year",
        "athlete_distance_col": "Distance",
        "breadcrumb_races": "Races",
        "breadcrumb_athletes": "Athletes",
        "footer_tagline": "Trail running performance engine.",
    },
    "es": {
        "nav_races": "Carreras",
        "nav_athletes": "Atletas",
        "nav_rankings": "Rankings",
        "nav_about": "El Engine",
        "nav_search": "Buscar",
        "site_tagline": "Inteligencia de rendimiento para el trail running",
        "site_hero_sub": (
            "Inteligencia independiente de trail running impulsada por "
            "analítica de rendimiento propia. Explorá carreras, comparás "
            "atletas y entendé el rendimiento más allá de los resultados."
        ),
        "home_latest_races": "Últimos análisis",
        "home_see_all": "Ver todas →",
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
        "race_date_label": "Fecha",
        "race_distance_label": "Distancia",
        "race_elevation_label": "Desnivel Positivo Total",
        "race_winning_time_label": "Tiempo Ganador",
        "races_title": "Carreras",
        "athletes_title": "Atletas",
        "athletes_jump_label": "Saltar a letra",
        "rankings_title": "Rankings",
        "rankings_subtitle": (
            "Promedio de carrera por atleta. Solo se incluyen atletas con al "
            "menos una métrica calculada."
        ),
        "rankings_top_vpi": "Top VPI",
        "rankings_top_dmi": "Top DMI",
        "rankings_top_er": "Top ER",
        "about_title": "El Engine",
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
        "about_vpi_title": "VPI — Vertical Power Index",
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
        "search_title": "Buscar",
        "search_placeholder": "Carrera o atleta...",
        "race_performance_title": "Rendimiento por corredor",
        "race_pos": "Pos",
        "race_bib": "Dorsal",
        "race_athlete": "Corredor",
        "race_time": "Tiempo",
        "race_pace_1h": "Ritmo 1ª Mitad",
        "race_pace_2h": "Ritmo 2ª Mitad",
        "race_metric_note": "VPI en m/h · DMI en km/h · ER es un score 0-100.",
        "race_how_calculated": "¿Cómo se calculan?",
        "race_runner_charts_title": "Gráficos por corredor",
        "report_back": "Volver al perfil",
        "athlete_career_avg": "Promedios de carrera",
        "athlete_race_history": "Historial de carreras",
        "athlete_race_col": "Carrera",
        "athlete_year": "Año",
        "athlete_distance_col": "Distancia",
        "breadcrumb_races": "Carreras",
        "breadcrumb_athletes": "Atletas",
        "footer_tagline": "Motor de análisis de rendimiento en trail running.",
    },
    "fr": {
        "nav_races": "Courses",
        "nav_athletes": "Athlètes",
        "nav_rankings": "Classements",
        "nav_about": "Le Moteur",
        "nav_search": "Rechercher",
        "site_tagline": "Intelligence de performance pour le trail running",
        "site_hero_sub": (
            "Intelligence indépendante du trail running propulsée par une "
            "analyse de performance propriétaire. Explorez les courses, "
            "comparez les athlètes et comprenez la performance au-delà des "
            "résultats."
        ),
        "home_latest_races": "Dernières analyses",
        "home_see_all": "Voir tout →",
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
        "race_date_label": "Date",
        "race_distance_label": "Distance",
        "race_elevation_label": "Dénivelé Positif Total",
        "race_winning_time_label": "Temps Vainqueur",
        "races_title": "Courses",
        "athletes_title": "Athlètes",
        "athletes_jump_label": "Aller à la lettre",
        "rankings_title": "Classements",
        "rankings_subtitle": (
            "Moyenne de carrière par athlète. Seuls les athlètes avec au "
            "moins une métrique calculée sont inclus."
        ),
        "rankings_top_vpi": "Top VPI",
        "rankings_top_dmi": "Top DMI",
        "rankings_top_er": "Top ER",
        "about_title": "Le Moteur",
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
        "about_vpi_title": "VPI — Vertical Power Index",
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
        "search_title": "Rechercher",
        "search_placeholder": "Course ou athlète...",
        "race_performance_title": "Performance par athlète",
        "race_pos": "Pos",
        "race_bib": "Dossard",
        "race_athlete": "Athlète",
        "race_time": "Temps",
        "race_pace_1h": "Allure 1ère Moitié",
        "race_pace_2h": "Allure 2ème Moitié",
        "race_metric_note": "VPI en m/h · DMI en km/h · ER est un score sur 100.",
        "race_how_calculated": "Comment est-ce calculé ?",
        "race_runner_charts_title": "Graphiques par coureur",
        "report_back": "Retour au profil",
        "athlete_career_avg": "Moyennes de carrière",
        "athlete_race_history": "Historique des courses",
        "athlete_race_col": "Course",
        "athlete_year": "Année",
        "athlete_distance_col": "Distance",
        "breadcrumb_races": "Courses",
        "breadcrumb_athletes": "Athlètes",
        "footer_tagline": "Moteur d'analyse de performance en trail running.",
    },
}
