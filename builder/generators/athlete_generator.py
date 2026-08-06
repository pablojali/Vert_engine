"""
Reads data/athletes/<slug>/profile.json and generates one static page
per athlete, plus the /athletes/ index.
"""
import json
from builder.env import env, write_page, DATA_DIR

ATHLETES_DIR = DATA_DIR / "athletes"


def load_athletes() -> list[dict]:
    athletes = []
    for f in sorted(ATHLETES_DIR.glob("*/profile.json")):
        athlete = json.loads(f.read_text(encoding="utf-8"))
        athlete["_source_dir"] = f.parent
        athletes.append(athlete)
    return athletes


def generate() -> list[dict]:
    template = env.get_template("athlete.html")
    index_template = env.get_template("athletes_index.html")
    athletes = load_athletes()

    for athlete in athletes:
        html = template.render(athlete=athlete)
        write_page(f"athletes/{athlete['slug']}/index.html", html)

    ordered = sorted(athletes, key=lambda a: a.get("name", ""))
    write_page("athletes/index.html", index_template.render(athletes=ordered))

    return athletes


if __name__ == "__main__":
    generate()
