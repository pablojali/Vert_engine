"""
Central Jinja2 environment setup. Every generator imports `env` and
`write_page` from here instead of repeating the setup.
"""
from pathlib import Path
from datetime import datetime
from jinja2 import Environment, FileSystemLoader, select_autoescape

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

env.globals["current_year"] = datetime.now().year
env.globals["site_name"] = "Vertical Trail Labs"
env.globals["site_domain"] = "vertlabs.run"


def write_page(relative_path: str, html: str) -> None:
    """Writes an HTML page inside output/, creating folders as needed.
    relative_path example: 'races/aran-2026/index.html'"""
    target = OUTPUT_DIR / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html, encoding="utf-8")
    print(f"  ✓ {relative_path}")
