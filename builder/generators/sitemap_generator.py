"""
Generates one sitemap.xml covering all three locales (with hreflang
alternates) + robots.txt.
"""
from builder.env import OUTPUT_DIR, env, locale_url
from builder.i18n import LOCALES

BASE_URL = f"https://{env.globals['site_domain']}"
# "rankings/" intentionally left out while it's hidden from the nav
# (see base.html) - the page still builds, just isn't promoted for indexing.
STATIC_PAGE_PATHS = ["", "races/", "athletes/", "about/", "search/"]


def generate(races_by_locale: dict, athletes_by_locale: dict, posts_by_locale: dict) -> None:
    # Collect the set of page_paths that exist (same across locales, since
    # every race/athlete/post slug is generated for every locale).
    en_races = races_by_locale.get("en", [])
    en_athletes = athletes_by_locale.get("en", [])
    en_posts = posts_by_locale.get("en", [])
    page_paths = list(STATIC_PAGE_PATHS)
    page_paths += [f"races/{r['slug']}/" for r in en_races]
    page_paths += [f"athletes/{a['slug']}/" for a in en_athletes]
    page_paths += [f"posts/{p['slug']}/" for p in en_posts]

    entries = []
    for page_path in page_paths:
        alt_links = "\n".join(
            f'    <xhtml:link rel="alternate" hreflang="{loc["code"]}" '
            f'href="{BASE_URL}{locale_url(loc["code"], page_path)}"/>'
            for loc in LOCALES
        )
        for loc in LOCALES:
            loc_url = f"{BASE_URL}{locale_url(loc['code'], page_path)}"
            entries.append(f"  <url>\n    <loc>{loc_url}</loc>\n{alt_links}\n  </url>")

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
        'xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
        + "\n".join(entries) +
        "\n</urlset>\n"
    )

    (OUTPUT_DIR / "sitemap.xml").write_text(xml, encoding="utf-8")
    (OUTPUT_DIR / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {BASE_URL}/sitemap.xml\n",
        encoding="utf-8",
    )
    print(f"  ✓ sitemap.xml + robots.txt ({len(entries)} URLs)")
