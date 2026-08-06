"""
Generates index.html from the race list already produced by
race_generator (avoids reading the JSON twice), for a given locale.
"""
from builder.env import env, write_page, out_path


def generate(races: list[dict], loc: dict, t: dict) -> None:
    template = env.get_template("index.html")
    ordered = sorted(races, key=lambda r: (r.get("year", 0), r.get("date", "")), reverse=True)
    html = template.render(races=ordered, t=t, locale=loc["code"], page_path="")
    write_page(out_path(loc["prefix"], "index.html"), html)
