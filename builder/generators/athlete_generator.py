"""
Reads data/athletes/<slug>/profile.json and generates one static page
per athlete, plus the /athletes/ index, for a given locale.
"""
import json
import unicodedata
from itertools import groupby
from builder.env import env, write_page, out_path, locale_url, DATA_DIR
from builder.generators.radar_chart import build_radar_svg

ATHLETES_DIR = DATA_DIR / "athletes"


def _surname_sort_key(name: str) -> str:
    """Names are stored as 'First Middle SURNAME(S)', with the surname in
    caps (e.g. 'Katarzyna DOMBROWSKA', 'Delbi VILLA GONGORA'). Sorts by
    that trailing all-caps block instead of the first name."""
    words = (name or "").split()
    i = len(words)
    while i > 0 and words[i - 1].isupper():
        i -= 1
    surname = " ".join(words[i:]) if i < len(words) else name
    return (surname or name or "").lower()


def _fold_ascii(text: str) -> str:
    """Strips accents (Étienne -> Etienne) so they don't get their own
    one-off bucket/miss in the index or the live search below."""
    return unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode("ascii")


def _index_letter(name: str) -> str:
    """A-Z bucket for the alphabetical athlete directory, based on the
    first character of the surname sort key. Accents are folded so they
    land in the expected letter; anything left non-alphabetic goes to '#'."""
    key = _surname_sort_key(name)
    if not key:
        return "#"
    ascii_char = _fold_ascii(key[0])
    return ascii_char.upper() if ascii_char.isalpha() else "#"


def _search_name(name: str) -> str:
    """Accent-folded, lowercased name used for the live search on
    /athletes/ - so 'esteban' still matches 'Estéban' etc."""
    return _fold_ascii(name or "").lower()


_MONTH_ABBR = {
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    "es": ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"],
    "fr": ["Janv", "Févr", "Mars", "Avr", "Mai", "Juin", "Juil", "Août", "Sept", "Oct", "Nov", "Déc"],
}


def _month_label(date_str: str | None, locale_code: str) -> str | None:
    """Abbreviated, locale-aware month name from a race's "YYYY-MM-DD"
    date - None (never raises) for a race with no date on file yet, so
    the Race History table can fall back to showing just the year."""
    if not date_str:
        return None
    parts = date_str.split("-")
    if len(parts) < 2:
        return None
    try:
        month_num = int(parts[1])
    except ValueError:
        return None
    if not 1 <= month_num <= 12:
        return None
    return _MONTH_ABBR.get(locale_code, _MONTH_ABBR["en"])[month_num - 1]


def _profile_maturity_key(race_count: int) -> str | None:
    """Sample-size label for the VTL Performance Profile - communicates
    how many analyzed races back the profile, not a statistical
    confidence interval. Thresholds are a display convention, isolated
    here so they can be tuned without touching the aggregation itself
    (which is still career_avg, computed once in the Engine at export
    time - this function never averages anything)."""
    if race_count <= 0:
        return None
    if race_count == 1:
        return "early"
    if race_count <= 3:
        return "emerging"
    if race_count <= 6:
        return "established"
    return "high_confidence"


def load_athletes() -> list[dict]:
    athletes = []
    for f in sorted(ATHLETES_DIR.glob("*/profile.json")):
        athlete = json.loads(f.read_text(encoding="utf-8"))
        athlete["_source_dir"] = f.parent
        athletes.append(athlete)
    return athletes


def generate(loc: dict, t: dict, events: list[dict]) -> list[dict]:
    template = env.get_template("athlete.html")
    report_template = env.get_template("report.html")
    index_template = env.get_template("athletes_index.html")
    athletes = load_athletes()

    # profile.json only stores each race's year (not its full date) - the
    # actual date lives on race.json, keyed by race_slug via the already-
    # built events (event["distances"] carries the same race dicts
    # race_generator.py loaded, "date" included). Looked up once here
    # instead of re-reading every race.json per athlete.
    date_by_race_slug = {
        d["slug"]: d.get("date") for event in events for d in event["distances"]
    }

    for athlete in athletes:
        athlete["url"] = locale_url(loc["code"], f"athletes/{athlete['slug']}/")
        for r in athlete.get("races", []):
            r["month"] = _month_label(date_by_race_slug.get(r["race_slug"]), loc["code"])
            if r.get("report"):
                # Render the uploaded full-analysis HTML inside our own page
                # (header/nav/footer intact, embedded via iframe) instead of
                # linking straight to the raw file - a direct link would
                # navigate away from the site entirely, losing the menu.
                report_page_path = f"athletes/{athlete['slug']}/{r['race_slug']}/"
                r["url"] = locale_url(loc["code"], report_page_path)
                report_html = report_template.render(
                    athlete=athlete, race_entry=r, t=t, locale=loc["code"], page_path=report_page_path,
                )
                write_page(out_path(loc["prefix"], f"{report_page_path}index.html"), report_html)
            else:
                r["url"] = locale_url(loc["code"], f"races/{r['race_slug']}/")
        # Most recent race by year, used for the share text/OG description
        # ("Name - Race Year | VTL") - None for an athlete with no races
        # yet, handled in the template (name-only share text).
        athlete["primary_race"] = max(
            athlete.get("races", []), key=lambda r: r.get("year") or 0, default=None
        )
        # VTL Performance Profile: one outlined triangle per eligible race
        # (all three metrics present, so the chart never plots a partial/
        # misleading shape), overlaid on the same chart and colored by
        # distance bracket - not a single averaged polygon. The displayed
        # race count always matches exactly what's plotted.
        eligible_races = [
            r for r in athlete.get("races", [])
            if r.get("vpi") is not None and r.get("dmi") is not None and r.get("er") is not None
        ]
        athlete["profile_race_count"] = len(eligible_races)
        athlete["profile_maturity_key"] = _profile_maturity_key(len(eligible_races))
        athlete["radar_svg"] = build_radar_svg(eligible_races)
        html = template.render(athlete=athlete, t=t, locale=loc["code"], page_path=f"athletes/{athlete['slug']}/")
        write_page(out_path(loc["prefix"], f"athletes/{athlete['slug']}/index.html"), html)

    for athlete in athletes:
        athlete["search_name"] = _search_name(athlete.get("name", ""))

    ordered = sorted(athletes, key=lambda a: _surname_sort_key(a.get("name", "")))
    groups = [
        (letter, list(group)) for letter, group in groupby(ordered, key=lambda a: _index_letter(a.get("name", "")))
    ]

    # Event/year options for the /athletes/ filters, grouped like the
    # /races/ hub pages (one event per real shared folder - e.g. Val
    # d'Aran's 110k and 163k are one "Val d'Aran by UTMB" event, not two
    # entries), not by race_slug or by race_name text (both would show
    # Val d'Aran / Lavaredo twice, once per distance).
    event_by_race_slug = {}
    for event in events:
        label = f"{event['name']} {event['year']}" if event.get("year") else event["name"]
        for d in event["distances"]:
            event_by_race_slug[d["slug"]] = {"slug": event["slug"], "name": label}

    for athlete in athletes:
        athlete["_event_slugs"] = sorted({
            event_by_race_slug[r["race_slug"]]["slug"]
            for r in athlete.get("races", [])
            if r.get("race_slug") in event_by_race_slug
        })

    race_options = sorted(
        {(info["slug"], info["name"]) for info in event_by_race_slug.values()},
        key=lambda pair: pair[1],
    )
    race_options = [{"slug": slug, "name": name} for slug, name in race_options]
    year_options = sorted(
        {r["year"] for a in athletes for r in a.get("races", []) if r.get("year")},
        reverse=True,
    )

    write_page(
        out_path(loc["prefix"], "athletes/index.html"),
        index_template.render(
            groups=groups, race_options=race_options, year_options=year_options,
            t=t, locale=loc["code"], page_path="athletes/",
        ),
    )

    return athletes


if __name__ == "__main__":
    from builder.i18n import LOCALES, TRANSLATIONS
    generate(LOCALES[0], TRANSLATIONS["en"], [])
