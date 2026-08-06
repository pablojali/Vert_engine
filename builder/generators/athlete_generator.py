"""
Reads data/athletes/<slug>/profile.json and generates one static page
per athlete, plus the /athletes/ index, for a given locale.
"""
import json
from builder.env import env, write_page, out_path, locale_url, DATA_DIR

ATHLETES_DIR = DATA_DIR / "athletes"


def load_athletes() -> list[dict]:
    athletes = []
    for f in sorted(ATHLETES_DIR.glob("*/profile.json")):
        athlete = json.loads(f.read_text(encoding="utf-8"))
        athlete["_source_dir"] = f.parent
        athletes.append(athlete)
    return athletes


def generate(loc: dict, t: dict) -> list[dict]:
    template = env.get_template("athlete.html")
    index_template = env.get_template("athletes_index.html")
    athletes = load_athletes()

    for athlete in athletes:
        athlete["url"] = locale_url(loc["code"], f"athletes/{athlete['slug']}/")
        for r in athlete.get("races", []):
            r["url"] = locale_url(loc["code"], f"races/{r['race_slug']}/")
        html = template.render(athlete=athlete, t=t, locale=loc["code"], page_path=f"athletes/{athlete['slug']}/")
        write_page(out_path(loc["prefix"], f"athletes/{athlete['slug']}/index.html"), html)

    ordered = sorted(athletes, key=lambda a: a.get("name", ""))
    write_page(
        out_path(loc["prefix"], "athletes/index.html"),
        index_template.render(athletes=ordered, t=t, locale=loc["code"], page_path="athletes/"),
    )

    return athletes


if __name__ == "__main__":
    from builder.i18n import LOCALES, TRANSLATIONS
    generate(LOCALES[0], TRANSLATIONS["en"])
