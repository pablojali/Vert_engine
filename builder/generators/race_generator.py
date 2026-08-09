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

        blocks_path = f.parent / "analysis_blocks.json"
        legacy_path = f.parent / "analysis.html"
        if blocks_path.exists():
            race["analysis_blocks"] = json.loads(blocks_path.read_text(encoding="utf-8")).get("blocks", [])
        elif legacy_path.exists():
            # Pre-block-editor races: treat the old single HTML blob as one
            # raw-HTML block so nothing written before is lost.
            race["analysis_blocks"] = [{"type": "html", "content": legacy_path.read_text(encoding="utf-8")}]
        else:
            race["analysis_blocks"] = []

        races.append(race)
    return races


def _build_events(races: list[dict], loc: dict) -> list[dict]:
    """Groups distances that share the same (name, year) into one event -
    e.g. Val d'Aran by UTMB 2026's 110k and 163k become two "distances"
    under one "Val d'Aran by UTMB 2026" event, instead of two unrelated
    top-level races."""
    groups: dict[tuple, list[dict]] = {}
    for race in races:
        key = (race.get("name", ""), race.get("year", 0))
        groups.setdefault(key, []).append(race)

    events = []
    for (name, year), distances in groups.items():
        distances = sorted(distances, key=lambda r: r.get("distance_km") or 0)
        slug = _slugify(f"{name}-{year}")
        events.append({
            "slug": slug,
            "name": name,
            "year": year,
            "location": next((r.get("location") for r in distances if r.get("location")), None),
            "date": next((r.get("date") for r in distances if r.get("date")), None),
            "hero_image": next((r.get("hero_image") for r in distances if r.get("hero_image")), None),
            "distances": distances,
            "url": locale_url(loc["code"], f"races/{slug}/"),
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
        race["posts"] = posts_by_race_slug.get(race["slug"], [])
        event = event_by_race_slug.get(race["slug"])
        race["event_name"] = event["name"] if event else None
        race["event_year"] = event["year"] if event else None
        race["event_url"] = event["url"] if event else None
        for a in race.get("athletes", []):
            a["url"] = locale_url(loc["code"], f"athletes/{a['slug']}/")

        athletes_by_slug = {a["slug"]: a for a in race.get("athletes", [])}
        for block in race["analysis_blocks"]:
            if block.get("type") == "top10":
                block["entries"] = [
                    athletes_by_slug[slug] for slug in block.get("slugs", []) if slug in athletes_by_slug
                ]

        html = template.render(race=race, t=t, locale=loc["code"], page_path=f"races/{race['slug']}/")
        write_page(out_path(loc["prefix"], f"races/{race['slug']}/index.html"), html)

    for event in sorted(events, key=lambda e: (e.get("year", 0), e.get("date", "")), reverse=True):
        html = event_template.render(event=event, t=t, locale=loc["code"], page_path=f"races/{event['slug']}/")
        write_page(out_path(loc["prefix"], f"races/{event['slug']}/index.html"), html)

    ordered_events = sorted(events, key=lambda e: (e.get("year", 0), e.get("date", "")), reverse=True)
    write_page(
        out_path(loc["prefix"], "races/index.html"),
        index_template.render(events=ordered_events, t=t, locale=loc["code"], page_path="races/"),
    )

    return races, events


if __name__ == "__main__":
    from builder.i18n import LOCALES, TRANSLATIONS
    generate(LOCALES[0], TRANSLATIONS["en"])
