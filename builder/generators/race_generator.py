"""
Reads data/races/**/race.json (nested under <circuito>/<año>/<distancia>/)
and generates one static page per race, plus the /races/ index, for a
given locale.

Never imports from engine/: race.json is already the final, calculated
result. This module only reads it and renders HTML.
"""
import json
from builder.env import env, write_page, out_path, locale_url, DATA_DIR

RACES_DIR = DATA_DIR / "races"


def load_races() -> list[dict]:
    races = []
    for f in sorted(RACES_DIR.glob("**/race.json")):
        race = json.loads(f.read_text(encoding="utf-8"))
        race["_source_dir"] = f.parent

        blocks_path = f.parent / "analysis_blocks.json"
        legacy_path = f.parent / "analysis.html"
        if blocks_path.exists():
            race["analysis_blocks"] = json.loads(blocks_path.read_text(encoding="utf-8")).get("blocks", [])
        elif legacy_path.exists():
            # Pre-block-editor races: treat the old single HTML blob as one
            # raw-HTML block so nothing written before is lost.
            race["analysis_blocks"] = [{"type": "html", "content": legacy_path.read_text(encoding="utf-8")}]
        else:
            race["analysis_blocks"] = []

        races.append(race)
    return races


def generate(loc: dict, t: dict) -> list[dict]:
    """Generates every race page and the /races/ index for one locale.
    Returns the race list (still carrying _source_dir) so other
    generators (homepage, search, sitemap, publish's asset copy) can
    reuse it without re-reading the JSON."""
    template = env.get_template("race.html")
    index_template = env.get_template("races_index.html")
    races = load_races()

    for race in races:
        race["url"] = locale_url(loc["code"], f"races/{race['slug']}/")
        for a in race.get("athletes", []):
            a["url"] = locale_url(loc["code"], f"athletes/{a['slug']}/")

        athletes_by_slug = {a["slug"]: a for a in race.get("athletes", [])}
        for block in race["analysis_blocks"]:
            if block.get("type") == "top10":
                block["entries"] = [
                    athletes_by_slug[slug] for slug in block.get("slugs", []) if slug in athletes_by_slug
                ]

        html = template.render(race=race, t=t, locale=loc["code"], page_path=f"races/{race['slug']}/")
        write_page(out_path(loc["prefix"], f"races/{race['slug']}/index.html"), html)

    ordered = sorted(races, key=lambda r: (r.get("year", 0), r.get("date", "")), reverse=True)
    write_page(
        out_path(loc["prefix"], "races/index.html"),
        index_template.render(races=ordered, t=t, locale=loc["code"], page_path="races/"),
    )

    return races


if __name__ == "__main__":
    from builder.i18n import LOCALES, TRANSLATIONS
    generate(LOCALES[0], TRANSLATIONS["en"])
