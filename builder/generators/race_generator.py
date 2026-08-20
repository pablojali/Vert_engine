"""
Reads data/races/**/race.json (nested under <circuito>/<año>/<distancia>/)
and generates:
  - one page per distance/race (unchanged URL scheme: /races/<race-slug>/)
  - one "event" hub page per (name, year) group, at /races/<event-slug>/,
    listing its distances side by side with each distance's posts
  - the /races/ index, now listing events instead of individual distances

Never imports from engine/: race.json is already the final, calculated
result. This module only reads it and renders HTML.
"""
import json
import re
import unicodedata
from builder.env import env, write_page, out_path, locale_url, DATA_DIR

RACES_DIR = DATA_DIR / "races"


def _slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text or "event"


def load_races() -> list[dict]:
    races = []
    for f in sorted(RACES_DIR.glob("**/race.json")):
        race = json.loads(f.read_text(encoding="utf-8"))
        race["_source_dir"] = f.parent
        races.append(race)
    return races


def _find_event_icon(year_dir, event_slug: str):
    """The event icon is uploaded once (Exportar a Web, shared by every
    distance under that event) and lives one level up from any single
    distance folder - e.g. data/races/val-d-aran-by-utmb/2026/images/icon.*,
    a sibling of the 110k/ and 163k/ distance folders."""
    images_dir = year_dir / "images"
    for ext in (".jpg", ".jpeg", ".png"):
        if (images_dir / f"icon{ext}").exists():
            return f"/media/races/{event_slug}/images/icon{ext}"
    return None


def _build_events(races: list[dict], loc: dict) -> list[dict]:
    """Groups distances that share the same <circuito>/<año> data folder
    into one event - e.g. Val d'Aran by UTMB 2026's 110k and 163k become
    two "distances" under one "Val d'Aran by UTMB 2026" event, instead of
    two unrelated top-level races. Grouping by folder (not by name/year
    text) avoids silently splitting an event over a typo/casing mismatch."""
    groups: dict = {}
    for race in races:
        year_dir = race["_source_dir"].parent
        groups.setdefault(year_dir, []).append(race)

    events = []
    for year_dir, distances in groups.items():
        distances = sorted(distances, key=lambda r: r.get("distance_km") or 0)
        name = distances[0].get("name", "")
        year = distances[0].get("year", 0)
        slug = _slugify(f"{name}-{year}")
        icon = _find_event_icon(year_dir, slug)
        events.append({
            "slug": slug,
            "name": name,
            "year": year,
            "location": next((r.get("location") for r in distances if r.get("location")), None),
            "date": next((r.get("date") for r in distances if r.get("date")), None),
            "hero_image": icon or next((r.get("hero_image") for r in distances if r.get("hero_image")), None),
            "distances": distances,
            "url": locale_url(loc["code"], f"races/{slug}/"),
            "_source_dir": year_dir,
        })
    return events


def generate(loc: dict, t: dict, posts_by_race_slug: dict | None = None) -> tuple[list[dict], list[dict]]:
    """Generates every distance page, every event hub page, and the
    /races/ index for one locale. Returns (races, events) - races still
    carry _source_dir so other generators (homepage, search, sitemap,
    publish's asset copy) can reuse them without re-reading the JSON."""
    template = env.get_template("race.html")
    event_template = env.get_template("event.html")
    index_template = env.get_template("races_index.html")
    races = load_races()
    posts_by_race_slug = posts_by_race_slug or {}

    # Events are grouped up front (before rendering distance pages) so
    # each distance page's breadcrumb can link back through its event.
    events = _build_events(races, loc)
    event_by_race_slug = {}
    for event in events:
        for d in event["distances"]:
            event_by_race_slug[d["slug"]] = event

    for race in races:
        race["url"] = locale_url(loc["code"], f"races/{race['slug']}/")
        race["distance_label"] = race["_source_dir"].name
        race["posts"] = posts_by_race_slug.get(race["slug"], [])
        event = event_by_race_slug.get(race["slug"])
        race["event_name"] = event["name"] if event else None
        race["event_year"] = event["year"] if event else None
        race["event_url"] = event["url"] if event else None
        for a in race.get("athletes", []):
            a["url"] = locale_url(loc["code"], f"athletes/{a['slug']}/")
        # Full-field roster on the race page, ordered by real finish
        # position (not the curated Top 10 order) - unranked/DNF entries
        # (no position yet) sort to the end instead of erroring.
        race["athletes"] = sorted(race.get("athletes", []), key=lambda a: a.get("position") if a.get("position") is not None else float("inf"))

        html = template.render(race=race, t=t, locale=loc["code"], page_path=f"races/{race['slug']}/")
        write_page(out_path(loc["prefix"], f"races/{race['slug']}/index.html"), html)

    for event in sorted(events, key=lambda e: (e.get("year") or 0, e.get("date") or ""), reverse=True):
        html = event_template.render(event=event, t=t, locale=loc["code"], page_path=f"races/{event['slug']}/")
        write_page(out_path(loc["prefix"], f"races/{event['slug']}/index.html"), html)

    ordered_events = sorted(events, key=lambda e: (e.get("year") or 0, e.get("date") or ""), reverse=True)
    write_page(
        out_path(loc["prefix"], "races/index.html"),
        index_template.render(events=ordered_events, t=t, locale=loc["code"], page_path="races/"),
    )

    return races, events


if __name__ == "__main__":
    from builder.i18n import LOCALES, TRANSLATIONS
    generate(LOCALES[0], TRANSLATIONS["en"])
