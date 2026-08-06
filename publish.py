"""
Single entry point of the publish pipeline.

    python publish.py

Flow:
  1. generate race pages (+ /races/ index)      -> data/races/**/race.json
  2. generate athlete pages (+ /athletes/ index) -> data/athletes/*/profile.json
  3. generate homepage
  4. generate /rankings/
  5. generate /about/ and /search/
  6. generate search.json
  7. generate sitemap.xml + robots.txt
  8. copy assets/ -> output/assets/
  9. copy ONLY images/ and charts/ (public) from data/ -> output/

Security rule (see Claude.md section 6): output/ must never contain
Python code, raw GPX, raw results/, or internal calculation parameters.
Step 9 enforces this by construction - it only ever copies directories
literally named "images" or "charts", nothing else from data/.
"""
import shutil
from pathlib import Path

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
    folder into its published URL path. Never touches gpx/, results/,
    race.json/profile.json themselves, or any .py file."""
    count = 0
    for race in races:
        source_dir = race.get("_source_dir")
        if not source_dir:
            continue
        for subdir in PUBLIC_SUBDIRS:
            src = Path(source_dir) / subdir
            if src.is_dir():
                dest = OUTPUT_DIR / "races" / race["slug"] / subdir
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
                dest = OUTPUT_DIR / "athletes" / athlete["slug"] / subdir
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(src, dest)
                count += 1

    print(f"  ✓ media pública copiada ({count} carpetas images/charts)")


def main() -> None:
    print("1/9 Generando páginas de carrera...")
    races = race_generator.generate()

    print("2/9 Generando páginas de atleta...")
    athletes = athlete_generator.generate()

    print("3/9 Generando homepage...")
    homepage_generator.generate(races)

    print("4/9 Generando rankings...")
    rankings_generator.generate(athletes)

    print("5/9 Generando about/ y search/...")
    static_pages_generator.generate()

    print("6/9 Generando índice de búsqueda...")
    search_generator.generate(races, athletes)

    print("7/9 Generando sitemap y robots.txt...")
    sitemap_generator.generate(races, athletes)

    print("8/9 Copiando assets estáticos...")
    copy_assets()

    print("9/9 Copiando imágenes y charts públicos...")
    copy_public_media(races, athletes)

    print(f"\nListo. Sitio generado en: {OUTPUT_DIR}")
    print("Siguiente paso: copiar output/ al repo público vertlabs-web y pushear.")


if __name__ == "__main__":
    main()
