"""
Generates a single lightweight search.json with races + athletes.
At VertLabs' scale (hundreds of athletes, dozens of races/year) one
JSON file + vanilla JS is enough - no external search engine needed.
"""
import json
from builder.env import OUTPUT_DIR


def generate(races: list[dict], athletes: list[dict]) -> None:
    index = []

    for r in races:
        index.append({
            "type": "race",
            "title": f"{r['name']} {r['year']}",
            "url": f"/races/{r['slug']}/",
        })

    for a in athletes:
        index.append({
            "type": "athlete",
            "title": a["name"],
            "url": f"/athletes/{a['slug']}/",
        })

    target = OUTPUT_DIR / "search.json"
    target.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ✓ search.json ({len(index)} entradas)")
