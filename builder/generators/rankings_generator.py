"""
Sorts the already-generated athlete list by career_avg VPI/DMI/ER and
renders /rankings/. This is sorting, not calculating: the averages
themselves come straight from profile.json, produced by the Engine.
"""
from builder.env import env, write_page

TOP_N = 20


def _top_by(athletes: list[dict], metric: str) -> list[dict]:
    ranked = [a for a in athletes if (a.get("career_avg") or {}).get(metric) is not None]
    ranked.sort(key=lambda a: a["career_avg"][metric], reverse=True)
    return ranked[:TOP_N]


def generate(athletes: list[dict]) -> None:
    template = env.get_template("rankings.html")
    html = template.render(
        top_vpi=_top_by(athletes, "vpi"),
        top_dmi=_top_by(athletes, "dmi"),
        top_er=_top_by(athletes, "er"),
    )
    write_page("rankings/index.html", html)


if __name__ == "__main__":
    from builder.generators.athlete_generator import load_athletes
    generate(load_athletes())
