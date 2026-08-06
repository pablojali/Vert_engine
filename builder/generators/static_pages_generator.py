"""
Renders the pages with no per-item data: /about/ and /search/.
"""
from builder.env import env, write_page


def generate() -> None:
    write_page("about/index.html", env.get_template("about.html").render())
    write_page("search/index.html", env.get_template("search.html").render())


if __name__ == "__main__":
    generate()
