"""
Generates index.html from the race/event/athlete/post lists already
produced by the other generators (avoids reading the JSON twice), for a
given locale.
"""
import re
from builder.env import env, write_page, out_path

CAROUSEL_SIZE = 3
EXCERPT_LENGTH = 150


def _stat(value, label, unit=None, extra_class=None):
    return {"value": value, "label": label, "unit": unit, "extra_class": extra_class}


def _excerpt(post: dict, fallback: str) -> str:
    """Short teaser for the carousel, taken from the post's first text
    block instead of a fixed line so every slide reads differently."""
    text_block = next((b for b in post.get("blocks", []) if b.get("type") == "text"), None)
    if not text_block:
        return fallback
    text = re.sub(r"\s+", " ", text_block.get("content", "")).strip()
    if not text:
        return fallback
    if len(text) <= EXCERPT_LENGTH:
        return text
    return text[:EXCERPT_LENGTH].rsplit(" ", 1)[0] + "…"


def _post_carousel_item(p: dict, t: dict) -> dict:
    stats = []
    if p.get("date"):
        stats.append(_stat(p["date"], t["race_date_label"], extra_class="carousel-stat-date"))
    return {
        "url": p["url"], "image": p.get("cover_image"), "title": p["title"],
        "eyebrow": p.get("category") or t["home_featured_label"], "cta": t["home_featured_cta"],
        "desc": _excerpt(p, t["home_featured_desc"]),
        "stats": stats, "sort_key": p.get("date") or "",
    }


def generate(races: list[dict], athletes: list[dict], posts: list[dict], loc: dict, t: dict) -> None:
    """The carousel is posts only, newest first - a post is the direct,
    specific thing someone shares/clicks into, unlike an event (which
    would need a second click to pick a distance). "Latest Posts" below
    it shows whatever real posts didn't make the carousel."""
    template = env.get_template("index.html")
    ordered_posts = sorted(posts, key=lambda p: p.get("date") or "", reverse=True)

    carousel_items = [_post_carousel_item(p, t) for p in ordered_posts[:CAROUSEL_SIZE]]
    latest_posts = ordered_posts[CAROUSEL_SIZE:CAROUSEL_SIZE + 6]

    stats = {
        "races": len(races),
        "athletes": len(athletes),
        "metrics": 3,  # VPI, DMI, ER - fixed, not derived from data
    }

    html = template.render(
        carousel_items=carousel_items, latest_posts=latest_posts,
        stats=stats, t=t, locale=loc["code"], page_path="",
    )
    write_page(out_path(loc["prefix"], "index.html"), html)
