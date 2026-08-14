"""
Central Jinja2 environment setup. Every generator imports `env` and
`write_page` from here instead of repeating the setup.
"""
from pathlib import Path
from datetime import datetime
from jinja2 import Environment, FileSystemLoader, select_autoescape

from .i18n import LOCALES

ROOT_DIR = Path(__file__).parent.parent
TEMPLATES_DIR = Path(__file__).parent / "templates"
OUTPUT_DIR = ROOT_DIR / "output"
DATA_DIR = ROOT_DIR / "data"

env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def locale_url(code: str, path: str = "") -> str:
    """Builds the absolute URL for `path` (e.g. 'races/aran-2026/') in the
    given locale. English is the canonical/default locale, served at the
    site root with no prefix; es/fr are served under /es/, /fr/."""
    prefix = next((l["prefix"] for l in LOCALES if l["code"] == code), "")
    if path:
        return f"{prefix}/{path}"
    return f"{prefix}/" if prefix else "/"


env.globals["current_year"] = datetime.now().year
env.globals["site_name"] = "Vertical Trail Labs"
env.globals["site_domain"] = "vertlabs.run"
env.globals["locales"] = LOCALES
env.globals["locale_url"] = locale_url


def country_flag_url(iso_code: str) -> str | None:
    """Builds a small flag image URL for a 2-letter ISO country code via the
    free flagcdn.com CDN. An <img> instead of the Unicode flag emoji
    (regional-indicator-symbol pairs), because Windows browsers don't ship
    flag glyphs by default and fall back to showing the two bare letters
    in little boxes - which reads exactly like the country code never
    changed at all. Returns None if the code isn't a plain 2-letter code."""
    if not iso_code or len(iso_code) != 2 or not iso_code.isalpha():
        return None
    return f"https://flagcdn.com/{iso_code.lower()}.svg"


env.filters["country_flag_url"] = country_flag_url


def write_page(relative_path: str, html: str) -> None:
    """Writes an HTML page inside output/, creating folders as needed.
    relative_path example: 'es/races/aran-2026/index.html'"""
    target = OUTPUT_DIR / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html, encoding="utf-8")
    print(f"  ✓ {relative_path}")


def out_path(locale_prefix: str, page_path: str) -> str:
    """Joins a locale's output prefix (e.g. '' or 'es') with a page's
    relative path (e.g. 'races/aran-2026/index.html') into the
    write_page()-relative path, without doubling slashes."""
    parts = [p for p in (locale_prefix.strip("/"), page_path.strip("/")) if p]
    return "/".join(parts)
