"""
Generates index.html from the race/athlete/post lists already produced
by the other generators (avoids reading the JSON twice), for a given
locale.
"""
from builder.env import env, write_page, out_path


def _stat(value, label, unit=None, extra_class=None):
    return {"value": value, "label": label, "unit": unit, "extra_class": extra_class}


def _race_carousel_item(r: dict, t: dict) -> dict:
    stats = []
    if r.get("date"):
        stats.append(_stat(r["date"], t["race_date_label"], extra_class="carousel-stat-date"))
    if r.get("distance_km"):
        stats.append(_stat(round(r["distance_km"], 1), t["race_distance_label"], unit="km"))
    if r.get("elevation_gain_m"):
        stats.append(_stat(round(r["elevation_gain_m"]), t["race_elevation_label"], unit="m+"))
    winner = next((a for a in r.get("athletes", []) if a.get("position") == 1), None)
    if winner:
        stats.append(_stat(winner["finish_time"], t["race_winning_time_label"]))
    return {
        "url": r["url"], "image": r.get("hero_image"), "title": f"{r['name']} {r['year']}",
        "eyebrow": t["home_featured_label"], "cta": t["home_featured_cta"],
        "stats": stats, "sort_key": r.get("date") or "",
    }


def _post_carousel_item(p: dict, t: dict) -> dict:
    stats = []
    if p.get("date"):
        stats.append(_stat(p["date"], t["race_date_label"], extra_class="carousel-stat-date"))
    return {
        "url": p["url"], "image": p.get("cover_image"), "title": p["title"],
        "eyebrow": p.get("category") or t["home_featured_label"], "cta": t["home_featured_cta"],
        "stats": stats, "sort_key": p.get("date") or "",
    }


def generate(races: list[dict], athletes: list[dict], posts: list[dict], loc: dict, t: dict) -> None:
    template = env.get_template("index.html")
    ordered = sorted(races, key=lambda r: (r.get("year", 0), r.get("date", "")), reverse=True)

    carousel_items = (
        [_race_carousel_item(r, t) for r in races]
        + [_post_carousel_item(p, t) for p in posts if p.get("placement") == "carousel"]
    )
    carousel_items.sort(key=lambda i: i["sort_key"], reverse=True)
    carousel_items = carousel_items[:5]

    other_posts = sorted(
        (p for p in posts if p.get("placement") != "carousel"),
        key=lambda p: p.get("date") or "", reverse=True,
    )

    stats = {
        "races": len(races),
        "athletes": len(athletes),
        "metrics": 3,  # VPI, DMI, ER - fixed, not derived from data
    }

    html = template.render(
        carousel_items=carousel_items, races=ordered, other_posts=other_posts,
        stats=stats, t=t, locale=loc["code"], page_path="",
    )
    write_page(out_path(loc["prefix"], "index.html"), html)
