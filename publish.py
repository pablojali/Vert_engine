"""
Single entry point of the publish pipeline.

    python publish.py

Flow (per locale: en at the root, es at /es/, fr at /fr/):
  1. load posts metadata (just enough to know which race each is tied to)
  2. generate race pages (+ event hub pages + /races/ index) -> data/races/**/race.json
  3. generate athlete pages (+ /athletes/ index) -> data/athletes/*/profile.json
  4. generate post pages (fully resolved against their race, if any)
  5. generate homepage
  6. generate /rankings/
  7. generate /about/ and /search/
  8. generate search.json

Then, once for the whole site:
  9. generate sitemap.xml + robots.txt (all locales, with hreflang)
  10. copy assets/ -> output/assets/ (shared, not localized)
  11. copy ONLY images/ and charts/ (public) from data/ -> output/media/
      (shared across locales - images aren't language-dependent)

Security rule (see Claude.md section 6): output/ must never contain
Python code, raw GPX, raw results/, or internal calculation parameters.
Step 11 enforces this by construction - it only ever copies directories
literally named "images" or "charts", nothing else from data/.
"""
import shutil
from pathlib import Path

from builder.env import locale_url
from builder.i18n import LOCALES, TRANSLATIONS
from builder.generators import (
    race_generator,
    athlete_generator,
    post_generator,
    homepage_generator,
    rankings_generator,
    static_pages_generator,
    search_generator,
    sitemap_generator,
)

ROOT = Path(__file__).parent
ASSETS_SRC = ROOT / "assets"
OUTPUT_DIR = ROOT / "output"

PUBLIC_SUBDIRS = ("images", "charts")


def copy_assets() -> None:
    dest = OUTPUT_DIR / "assets"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(ASSETS_SRC, dest)
    print("  ✓ assets/ copiados a output/assets/")


def copy_public_media(races: list[dict], athletes: list[dict], posts: list[dict]) -> None:
    """Copies only images/ and charts/ out of each race/athlete/post's data
    folder into output/media/ - shared across every locale, since images
    aren't language-dependent. Never touches gpx/, results/,
    race.json/profile.json/post.json themselves, or any .py file."""
    count = 0
    for kind, items in (("races", races), ("athletes", athletes), ("posts", posts)):
        for item in items:
            source_dir = item.get("_source_dir")
            if not source_dir:
                continue
            for subdir in PUBLIC_SUBDIRS:
                src = Path(source_dir) / subdir
                if src.is_dir():
                    dest = OUTPUT_DIR / "media" / kind / item["slug"] / subdir
                    if dest.exists():
                        shutil.rmtree(dest)
                    shutil.copytree(src, dest)
                    count += 1

    print(f"  ✓ media pública copiada ({count} carpetas images/charts)")


def clean_output() -> None:
    """Wipes output/ before regenerating, so pages/media left over from
    data that no longer exists (renamed slugs, removed races, etc.)
    don't linger on disk indefinitely."""
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)


def _group_posts_by_race(posts: list[dict]) -> dict:
    by_race = {}
    for p in posts:
        if p.get("race_slug"):
            by_race.setdefault(p["race_slug"], []).append(p)
    for lst in by_race.values():
        lst.sort(key=lambda p: p.get("date") or "", reverse=True)
    return by_race


def main() -> None:
    clean_output()
    races_by_locale = {}
    athletes_by_locale = {}
    posts_by_locale = {}
    events_by_locale = {}

    for loc in LOCALES:
        t = TRANSLATIONS[loc["code"]]
        print(f"\n=== Locale: {loc['code']} ({loc['name']}) ===")

        print("1/8 Cargando posts...")
        posts = post_generator.load_posts()
        for p in posts:
            p["url"] = locale_url(loc["code"], f"posts/{p['slug']}/")
        posts_by_race_slug = _group_posts_by_race(posts)

        print("2/8 Generando páginas de carrera y eventos...")
        races, events = race_generator.generate(loc, t, posts_by_race_slug)
        races_by_slug = {r["slug"]: r for r in races}

        print("3/8 Generando páginas de atleta...")
        athletes = athlete_generator.generate(loc, t, events)

        print("4/8 Generando páginas de posts...")
        posts = post_generator.generate(loc, t, races_by_slug, posts)

        print("5/8 Generando homepage...")
        homepage_generator.generate(races, athletes, posts, loc, t)

        print("6/8 Generando rankings...")
        rankings_generator.generate(athletes, loc, t)

        print("7/8 Generando about/ y search/...")
        static_pages_generator.generate(loc, t)

        print("8/8 Generando índice de búsqueda...")
        search_generator.generate(races, athletes, loc)

        races_by_locale[loc["code"]] = races
        athletes_by_locale[loc["code"]] = athletes
        posts_by_locale[loc["code"]] = posts
        events_by_locale[loc["code"]] = events

    print("\n=== Recursos compartidos ===")
    print("Generando sitemap y robots.txt...")
    sitemap_generator.generate(races_by_locale, athletes_by_locale, posts_by_locale, events_by_locale)

    print("Copiando assets estáticos...")
    copy_assets()

    print("Copiando imágenes y charts públicos...")
    copy_public_media(
        races_by_locale["en"] + events_by_locale["en"], athletes_by_locale["en"], posts_by_locale["en"]
    )

    print(f"\nListo. Sitio generado en: {OUTPUT_DIR}")
    print("Siguiente paso: copiar output/ al repo público vertlabs-web y pushear.")


if __name__ == "__main__":
    main()
