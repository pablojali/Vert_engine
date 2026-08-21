"""
Renders the pages with no per-item data: /about/ and /search/, for a
given locale.
"""
from builder.env import env, write_page, out_path, ROOT_DIR

# Drop a file at one of these paths (assets/img/) to put a real founder
# photo on the About page - no code change needed, about.html falls back
# to a placeholder monogram when none of them exist.
_FOUNDER_PHOTO_CANDIDATES = ["founder-pablo.jpg", "founder-pablo.jpeg", "founder-pablo.png", "founder-pablo.webp"]


def _founder_photo_url() -> str | None:
    assets_img = ROOT_DIR / "assets" / "img"
    for name in _FOUNDER_PHOTO_CANDIDATES:
        if (assets_img / name).exists():
            return f"/assets/img/{name}"
    return None


def generate(loc: dict, t: dict) -> None:
    write_page(
        out_path(loc["prefix"], "about/index.html"),
        env.get_template("about.html").render(
            t=t, locale=loc["code"], page_path="about/", founder_photo=_founder_photo_url(),
        ),
    )
    write_page(
        out_path(loc["prefix"], "search/index.html"),
        env.get_template("search.html").render(t=t, locale=loc["code"], page_path="search/"),
    )
