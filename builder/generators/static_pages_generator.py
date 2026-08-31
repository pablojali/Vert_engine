"""
Renders the pages with no per-item data: /about/, /search/ and
/analysis/, for a given locale.
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
    write_page(
        out_path(loc["prefix"], "analysis/index.html"),
        env.get_template("analysis.html").render(t=t, locale=loc["code"], page_path="analysis/"),
    )
    # Bare "404.html" (not a folder/index.html) so Cloudflare Pages picks it
    # up as this locale's not-found page - it walks up from the missing
    # path looking for one, so /es/404.html covers /es/*, /fr/404.html
    # covers /fr/*, and this root one covers everything else.
    write_page(
        out_path(loc["prefix"], "404.html"),
        env.get_template("404.html").render(t=t, locale=loc["code"], page_path="404.html"),
    )
