"""
Generates index.html from the race list already produced by
race_generator (avoids reading the JSON twice).
"""
from builder.env import env, write_page


def generate(races: list[dict]) -> None:
    template = env.get_template("index.html")
    ordered = sorted(races, key=lambda r: (r.get("year", 0), r.get("date", "")), reverse=True)
    html = template.render(races=ordered)
    write_page("index.html", html)


if __name__ == "__main__":
    from builder.generators.race_generator import load_races
    generate(load_races())
