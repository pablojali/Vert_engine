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


def country_flag(iso_code: str) -> str:
    """Converts a 2-letter ISO country code (e.g. 'FR') into its flag emoji
    via the Unicode regional-indicator-symbol trick. Returns the input
    unchanged if it doesn't look like a plain 2-letter code."""
    if not iso_code or len(iso_code) != 2 or not iso_code.isalpha():
        return iso_code
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in iso_code.upper())


env.filters["country_flag"] = country_flag


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
