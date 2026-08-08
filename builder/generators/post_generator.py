"""
Reads data/posts/<slug>/post.json and generates one standalone page per
post, for a given locale. A post can optionally reference a race (for
top10 blocks and the breadcrumb) but always lives at its own /posts/<slug>/
URL - it's never nested under a race, so it can exist before a race has
any results (pre-race previews) or cover something unrelated to any one
race entirely.
"""
import json
from builder.env import env, write_page, out_path, locale_url, DATA_DIR

POSTS_DIR = DATA_DIR / "posts"


def load_posts() -> list[dict]:
    posts = []
    for f in sorted(POSTS_DIR.glob("*/post.json")):
        post = json.loads(f.read_text(encoding="utf-8"))
        post["_source_dir"] = f.parent
        posts.append(post)
    return posts


def generate(loc: dict, t: dict, races_by_slug: dict) -> list[dict]:
    """races_by_slug: {race_slug: race_dict} from this same locale's
    race_generator.generate() call, already carrying .url on the race and
    its athletes - reused here to resolve top10 blocks and link back to
    the race, instead of re-reading race.json."""
    template = env.get_template("post.html")
    posts = load_posts()

    for post in posts:
        post["url"] = locale_url(loc["code"], f"posts/{post['slug']}/")
        race = races_by_slug.get(post.get("race_slug"))
        post["race"] = race

        athletes_by_slug = {a["slug"]: a for a in (race or {}).get("athletes", [])}
        for block in post.get("blocks", []):
            if block.get("type") == "top10":
                block["entries"] = [
                    athletes_by_slug[slug] for slug in block.get("slugs", []) if slug in athletes_by_slug
                ]

        html = template.render(post=post, t=t, locale=loc["code"], page_path=f"posts/{post['slug']}/")
        write_page(out_path(loc["prefix"], f"posts/{post['slug']}/index.html"), html)

    return posts


if __name__ == "__main__":
    from builder.i18n import LOCALES, TRANSLATIONS
    generate(LOCALES[0], TRANSLATIONS["en"], {})
