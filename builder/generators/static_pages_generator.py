"""
Renders the pages with no per-item data: /about/ and /search/, for a
given locale.
"""
from builder.env import env, write_page, out_path


def generate(loc: dict, t: dict) -> None:
    write_page(
        out_path(loc["prefix"], "about/index.html"),
        env.get_template("about.html").render(t=t, locale=loc["code"], page_path="about/"),
    )
    write_page(
        out_path(loc["prefix"], "search/index.html"),
        env.get_template("search.html").render(t=t, locale=loc["code"], page_path="search/"),
    )
