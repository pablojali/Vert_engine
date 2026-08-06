"""
Generates one lightweight search.json per locale with races + athletes,
each entry already pointing at the URL in that locale. At VertLabs'
scale (hundreds of athletes, dozens of races/year) one JSON file +
vanilla JS is enough - no external search engine needed.
"""
import json
from builder.env import OUTPUT_DIR, out_path


def generate(races: list[dict], athletes: list[dict], loc: dict) -> None:
    index = []

    for r in races:
        index.append({"type": "race", "title": f"{r['name']} {r['year']}", "url": r["url"]})

    for a in athletes:
        index.append({"type": "athlete", "title": a["name"], "url": a["url"]})

    target = OUTPUT_DIR / out_path(loc["prefix"], "search.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ✓ {out_path(loc['prefix'], 'search.json')} ({len(index)} entradas)")
