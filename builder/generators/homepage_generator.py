"""
Generates index.html from the race/event/athlete/post lists already
produced by the other generators (avoids reading the JSON twice), for a
given locale.
"""
from builder.env import env, write_page, out_path


def _stat(value, label, unit=None, extra_class=None):
    return {"value": value, "label": label, "unit": unit, "extra_class": extra_class}


def _post_carousel_item(p: dict, t: dict) -> dict:
    stats = []
    if p.get("date"):
        stats.append(_stat(p["date"], t["race_date_label"], extra_class="carousel-stat-date"))
    return {
        "url": p["url"], "image": p.get("cover_image"), "title": p["title"],
        "eyebrow": p.get("category") or t["home_featured_label"], "cta": t["home_featured_cta"],
        "stats": stats, "sort_key": p.get("date") or "",
    }


def generate(
    races: list[dict], events: list[dict], athletes: list[dict], posts: list[dict], loc: dict, t: dict
) -> None:
    """The carousel is posts only, newest first - a post is the direct,
    specific thing someone shares/clicks into, unlike an event (which
    would need a second click to pick a distance). "Latest Analyses"
    below it stays event-grouped for browsing; "Latest Posts" shows
    whatever didn't make the carousel's top 5."""
    template = env.get_template("index.html")
    ordered_events = sorted(events, key=lambda e: (e.get("year", 0), e.get("date", "")), reverse=True)
    ordered_posts = sorted(posts, key=lambda p: p.get("date") or "", reverse=True)

    carousel_items = [_post_carousel_item(p, t) for p in ordered_posts[:5]]
    latest_posts = ordered_posts[5:11]

    stats = {
        "races": len(races),
        "athletes": len(athletes),
        "metrics": 3,  # VPI, DMI, ER - fixed, not derived from data
    }

    html = template.render(
        carousel_items=carousel_items, events=ordered_events, latest_posts=latest_posts,
        stats=stats, t=t, locale=loc["code"], page_path="",
    )
    write_page(out_path(loc["prefix"], "index.html"), html)
