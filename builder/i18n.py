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
        "home_latest_races": "Latest Races",
        "home_see_all": "See all →",
        "races_title": "Races",
        "athletes_title": "Athletes",
        "rankings_title": "Rankings",
        "rankings_subtitle": (
            "Career average per athlete. Only athletes with at least one "
            "calculated metric are included."
        ),
        "rankings_top_vpi": "Top VPI",
        "rankings_top_dmi": "Top DMI",
        "rankings_top_er": "Top ER",
        "about_title": "The Engine",
        "about_intro": (
            "Vertical Trail Labs is not a blog or a CMS. It's a data "
            "intelligence engine whose final output is this static website: "
            "the site never calculates anything, it only shows what the "
            "Engine already computed from each race's official GPX and "
            "checkpoint split times."
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
        "about_flow_title": "Data Flow",
        "about_flow": "Engine (Python) → JSON → Builder (Jinja2) → Static HTML → Cloudflare Pages",
        "search_title": "Search",
        "search_placeholder": "Race or athlete...",
        "race_performance_title": "Performance by athlete",
        "race_pos": "Pos",
        "race_athlete": "Athlete",
        "race_time": "Time",
        "race_metric_note": "VPI in m/h · DMI in km/h · ER is a 0-100 score.",
        "race_how_calculated": "How is this calculated?",
        "athlete_career_avg": "Career Averages",
        "athlete_race_history": "Race History",
        "athlete_race_col": "Race",
        "athlete_year": "Year",
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
        "home_latest_races": "Últimas carreras",
        "home_see_all": "Ver todas →",
        "races_title": "Carreras",
        "athletes_title": "Atletas",
        "rankings_title": "Rankings",
        "rankings_subtitle": (
            "Promedio de carrera por atleta. Solo se incluyen atletas con al "
            "menos una métrica calculada."
        ),
        "rankings_top_vpi": "Top VPI",
        "rankings_top_dmi": "Top DMI",
        "rankings_top_er": "Top ER",
        "about_title": "El Engine",
        "about_intro": (
            "Vertical Trail Labs no es un blog ni un CMS. Es un motor de "
            "inteligencia de datos cuyo resultado final es esta web estática: "
            "el sitio nunca calcula nada, solo muestra lo que el Engine ya "
            "calculó a partir del GPX oficial de cada carrera y los tiempos "
            "de paso por checkpoint."
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
        "about_flow_title": "Flujo de datos",
        "about_flow": "Engine (Python) → JSON → Builder (Jinja2) → HTML estático → Cloudflare Pages",
        "search_title": "Buscar",
        "search_placeholder": "Carrera o atleta...",
        "race_performance_title": "Rendimiento por corredor",
        "race_pos": "Pos",
        "race_athlete": "Corredor",
        "race_time": "Tiempo",
        "race_metric_note": "VPI en m/h · DMI en km/h · ER es un score 0-100.",
        "race_how_calculated": "¿Cómo se calculan?",
        "athlete_career_avg": "Promedios de carrera",
        "athlete_race_history": "Historial de carreras",
        "athlete_race_col": "Carrera",
        "athlete_year": "Año",
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
        "home_latest_races": "Dernières courses",
        "home_see_all": "Voir tout →",
        "races_title": "Courses",
        "athletes_title": "Athlètes",
        "rankings_title": "Classements",
        "rankings_subtitle": (
            "Moyenne de carrière par athlète. Seuls les athlètes avec au "
            "moins une métrique calculée sont inclus."
        ),
        "rankings_top_vpi": "Top VPI",
        "rankings_top_dmi": "Top DMI",
        "rankings_top_er": "Top ER",
        "about_title": "Le Moteur",
        "about_intro": (
            "Vertical Trail Labs n'est ni un blog ni un CMS. C'est un moteur "
            "d'intelligence de données dont le résultat final est ce site "
            "statique : le site ne calcule jamais rien, il affiche uniquement "
            "ce que le Moteur a déjà calculé à partir du GPX officiel de "
            "chaque course et des temps de passage aux points de contrôle."
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
        "about_flow_title": "Flux de données",
        "about_flow": "Moteur (Python) → JSON → Builder (Jinja2) → HTML statique → Cloudflare Pages",
        "search_title": "Rechercher",
        "search_placeholder": "Course ou athlète...",
        "race_performance_title": "Performance par athlète",
        "race_pos": "Pos",
        "race_athlete": "Athlète",
        "race_time": "Temps",
        "race_metric_note": "VPI en m/h · DMI en km/h · ER est un score sur 100.",
        "race_how_calculated": "Comment est-ce calculé ?",
        "athlete_career_avg": "Moyennes de carrière",
        "athlete_race_history": "Historique des courses",
        "athlete_race_col": "Course",
        "athlete_year": "Année",
        "breadcrumb_races": "Courses",
        "breadcrumb_athletes": "Athlètes",
        "footer_tagline": "Moteur d'analyse de performance en trail running.",
    },
}
