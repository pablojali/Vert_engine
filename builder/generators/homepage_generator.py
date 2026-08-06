"""
Generates index.html from the race/athlete lists already produced by
race_generator/athlete_generator (avoids reading the JSON twice), for a
given locale.
"""
from builder.env import env, write_page, out_path


def generate(races: list[dict], athletes: list[dict], loc: dict, t: dict) -> None:
    template = env.get_template("index.html")
    ordered = sorted(races, key=lambda r: (r.get("year", 0), r.get("date", "")), reverse=True)

    stats = {
        "races": len(races),
        "athletes": len(athletes),
        "metrics": 3,  # VPI, DMI, ER - fixed, not derived from data
        "circuits": len({r["circuit"] for r in races if r.get("circuit")}),
    }

    html = template.render(races=ordered, stats=stats, t=t, locale=loc["code"], page_path="")
    write_page(out_path(loc["prefix"], "index.html"), html)
