"""
Single entry point of the publish pipeline.

    python publish.py

Flow (per locale: en at the root, es at /es/, fr at /fr/):
  1. generate race pages (+ /races/ index)      -> data/races/**/race.json
  2. generate athlete pages (+ /athletes/ index) -> data/athletes/*/profile.json
  3. generate homepage
  4. generate /rankings/
  5. generate /about/ and /search/
  6. generate search.json

Then, once for the whole site:
  7. generate sitemap.xml + robots.txt (all locales, with hreflang)
  8. copy assets/ -> output/assets/ (shared, not localized)
  9. copy ONLY images/ and charts/ (public) from data/ -> output/media/
     (shared across locales - images aren't language-dependent)

Security rule (see Claude.md section 6): output/ must never contain
Python code, raw GPX, raw results/, or internal calculation parameters.
Step 9 enforces this by construction - it only ever copies directories
literally named "images" or "charts", nothing else from data/.
"""
import shutil
from pathlib import Path

from builder.i18n import LOCALES, TRANSLATIONS
from builder.generators import (
    race_generator,
    athlete_generator,
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


def copy_public_media(races: list[dict], athletes: list[dict]) -> None:
    """Copies only images/ and charts/ out of each race/athlete's data
    folder into output/media/ - shared across every locale, since images
    aren't language-dependent. Never touches gpx/, results/,
    race.json/profile.json themselves, or any .py file."""
    count = 0
    for race in races:
        source_dir = race.get("_source_dir")
        if not source_dir:
            continue
        for subdir in PUBLIC_SUBDIRS:
            src = Path(source_dir) / subdir
            if src.is_dir():
                dest = OUTPUT_DIR / "media" / "races" / race["slug"] / subdir
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(src, dest)
                count += 1

    for athlete in athletes:
        source_dir = athlete.get("_source_dir")
        if not source_dir:
            continue
        for subdir in PUBLIC_SUBDIRS:
            src = Path(source_dir) / subdir
            if src.is_dir():
                dest = OUTPUT_DIR / "media" / "athletes" / athlete["slug"] / subdir
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(src, dest)
                count += 1

    print(f"  ✓ media pública copiada ({count} carpetas images/charts)")


def main() -> None:
    races_by_locale = {}
    athletes_by_locale = {}

    for loc in LOCALES:
        t = TRANSLATIONS[loc["code"]]
        print(f"\n=== Locale: {loc['code']} ({loc['name']}) ===")

        print("1/6 Generando páginas de carrera...")
        races = race_generator.generate(loc, t)

        print("2/6 Generando páginas de atleta...")
        athletes = athlete_generator.generate(loc, t)

        print("3/6 Generando homepage...")
        homepage_generator.generate(races, loc, t)

        print("4/6 Generando rankings...")
        rankings_generator.generate(athletes, loc, t)

        print("5/6 Generando about/ y search/...")
        static_pages_generator.generate(loc, t)

        print("6/6 Generando índice de búsqueda...")
        search_generator.generate(races, athletes, loc)

        races_by_locale[loc["code"]] = races
        athletes_by_locale[loc["code"]] = athletes

    print("\n=== Recursos compartidos ===")
    print("Generando sitemap y robots.txt...")
    sitemap_generator.generate(races_by_locale, athletes_by_locale)

    print("Copiando assets estáticos...")
    copy_assets()

    print("Copiando imágenes y charts públicos...")
    copy_public_media(races_by_locale["en"], athletes_by_locale["en"])

    print(f"\nListo. Sitio generado en: {OUTPUT_DIR}")
    print("Siguiente paso: copiar output/ al repo público vertlabs-web y pushear.")


if __name__ == "__main__":
    main()
