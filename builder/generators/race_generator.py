"""
Reads data/races/**/race.json (nested under <circuito>/<año>/<distancia>/)
and generates one static page per race, plus the /races/ index.

Never imports from engine/: race.json is already the final, calculated
result. This module only reads it and renders HTML.
"""
import json
from pathlib import Path
from builder.env import env, write_page, DATA_DIR

RACES_DIR = DATA_DIR / "races"


def load_races() -> list[dict]:
    races = []
    for f in sorted(RACES_DIR.glob("**/race.json")):
        race = json.loads(f.read_text(encoding="utf-8"))
        race["_source_dir"] = f.parent
        races.append(race)
    return races


def generate() -> list[dict]:
    """Generates every race page and the /races/ index. Returns the race
    list (without the internal _source_dir key) so other generators
    (homepage, search, sitemap, publish's asset copy) can reuse it
    without re-reading the JSON."""
    template = env.get_template("race.html")
    index_template = env.get_template("races_index.html")
    races = load_races()

    for race in races:
        html = template.render(race=race)
        write_page(f"races/{race['slug']}/index.html", html)

    ordered = sorted(races, key=lambda r: (r.get("year", 0), r.get("date", "")), reverse=True)
    write_page("races/index.html", index_template.render(races=ordered))

    return races


if __name__ == "__main__":
    generate()
