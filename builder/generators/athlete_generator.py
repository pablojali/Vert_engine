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


def load_athletes() -> list[dict]:
    athletes = []
    for f in sorted(ATHLETES_DIR.glob("*/profile.json")):
        athlete = json.loads(f.read_text(encoding="utf-8"))
        athlete["_source_dir"] = f.parent
        avg = athlete.get("career_avg") or {}
        athlete["radar_svg"] = build_radar_svg(avg.get("vpi"), avg.get("dmi"), avg.get("er"))
        athletes.append(athlete)
    return athletes


def generate(loc: dict, t: dict) -> list[dict]:
    template = env.get_template("athlete.html")
    report_template = env.get_template("report.html")
    index_template = env.get_template("athletes_index.html")
    athletes = load_athletes()

    for athlete in athletes:
        athlete["url"] = locale_url(loc["code"], f"athletes/{athlete['slug']}/")
        for r in athlete.get("races", []):
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
        html = template.render(athlete=athlete, t=t, locale=loc["code"], page_path=f"athletes/{athlete['slug']}/")
        write_page(out_path(loc["prefix"], f"athletes/{athlete['slug']}/index.html"), html)

    for athlete in athletes:
        athlete["search_name"] = _search_name(athlete.get("name", ""))

    ordered = sorted(athletes, key=lambda a: _surname_sort_key(a.get("name", "")))
    groups = [
        (letter, list(group)) for letter, group in groupby(ordered, key=lambda a: _index_letter(a.get("name", "")))
    ]

    # Race/year options for the /athletes/ filters - derived from the
    # same race history every athlete already carries, not a separate
    # source, so a filter option always corresponds to races that
    # actually have at least one analyzed athlete. Keyed by slug (not by
    # (slug, name) pair): race_name has been saved slightly differently
    # across export sessions for the same race in some cases (e.g. "Val
    # d'Aran by UTMB" vs "Val d'Aran by UTMB - CDH 110k" for the same
    # slug) - deduping by slug keeps one option per real race instead of
    # showing near-duplicates that filter identically.
    race_name_by_slug = {}
    for a in athletes:
        for r in a.get("races", []):
            slug = r.get("race_slug")
            if slug and slug not in race_name_by_slug:
                race_name_by_slug[slug] = r.get("race_name") or slug
    race_options = [
        {"slug": slug, "name": race_name_by_slug[slug]}
        for slug in sorted(race_name_by_slug, key=lambda s: race_name_by_slug[s])
    ]
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
    generate(LOCALES[0], TRANSLATIONS["en"])
