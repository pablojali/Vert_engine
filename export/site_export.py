"""
Bridge between the private Engine and the public vertlabs-web site.

This module is the ONLY thing that is meant to cross from this private
repo into the public one: final, already-computed numbers (VPI/DMI/ER,
finish time, position). It never exports GPX geometry, checkpoint
coordinates, scraped raw payloads, or the formulas themselves - those stay
in this repo. vertlabs-web's builder only ever reads the JSON this module
writes.

Usage (after computing a result with calculate_runner_indices /
calculate_global_real_indices from app.py):

    from export.site_export import export_result

    export_result(
        output_dir="../vertlabs-web/data",
        race_meta={
            "slug": "aran-2026", "name": "Val d'Aran by UTMB", "year": 2026,
            "distance_km": 163.0, "elevation_gain_m": 11441,
            "date": "2026-07-11", "location": "Vielha, España",
        },
        athlete_meta={"name": "Santos Gabriel Rueda", "country": "ARG"},
        result={"bib": 1, "finish_time": "21:32:05", "position": 1,
                "VPI": 812.4, "DMI": 14.2, "ER": 96.8},
    )
"""
import json
import re
import unicodedata
from pathlib import Path

RACE_META_FIELDS = ("slug", "name", "year", "distance_km", "elevation_gain_m", "date", "location")


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()


def _load(path: Path) -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _career_avg(races: list[dict], key: str):
    values = [r[key] for r in races if r.get(key) is not None]
    return round(sum(values) / len(values), 1) if values else None


def export_result(output_dir, race_meta: dict, athlete_meta: dict, result: dict) -> tuple[Path, Path]:
    """Merges one runner's result for one race into
    data/races/<race_slug>.json and data/athletes/<athlete_slug>.json under
    output_dir, creating either file the first time it's needed. Safe to
    call repeatedly (e.g. once per new result scraped): re-exporting the
    same athlete+race overwrites just that entry instead of duplicating it.

    result: {"bib", "finish_time", "position", "VPI", "DMI", "ER"} - pass
    the dict returned by calculate_runner_indices/calculate_global_real_indices
    straight through (keys are matched case-insensitively).
    """
    output_dir = Path(output_dir)
    races_dir = output_dir / "races"
    athletes_dir = output_dir / "athletes"

    athlete_slug = slugify(athlete_meta["name"])
    vpi = result.get("VPI", result.get("vpi"))
    dmi = result.get("DMI", result.get("dmi"))
    er = result.get("ER", result.get("er"))

    race_entry = {
        "slug": athlete_slug,
        "name": athlete_meta["name"],
        "bib": result.get("bib"),
        "finish_time": result.get("finish_time"),
        "position": result.get("position"),
        "vpi": vpi,
        "dmi": dmi,
        "er": er,
    }

    race_path = races_dir / f"{race_meta['slug']}.json"
    race_json = _load(race_path) or {
        **{field: race_meta[field] for field in RACE_META_FIELDS},
        "hero_image": f"/assets/images/races/{race_meta['slug']}/hero.jpg",
        "elevation_profile_image": f"/assets/images/races/{race_meta['slug']}/elevation_profile.png",
        "athletes": [],
    }
    race_json["athletes"] = [a for a in race_json["athletes"] if a["slug"] != athlete_slug]
    race_json["athletes"].append(race_entry)
    race_json["athletes"].sort(key=lambda a: (a["position"] is None, a["position"]))
    _save(race_path, race_json)

    athlete_race_entry = {
        "race_slug": race_meta["slug"],
        "race_name": race_meta["name"],
        "year": race_meta["year"],
        "position": result.get("position"),
        "finish_time": result.get("finish_time"),
        "vpi": vpi,
        "dmi": dmi,
        "er": er,
    }

    athlete_path = athletes_dir / f"{athlete_slug}.json"
    athlete_json = _load(athlete_path) or {
        "slug": athlete_slug,
        "name": athlete_meta["name"],
        "country": athlete_meta.get("country"),
        "portrait": f"/assets/images/athletes/{athlete_slug}/portrait.jpg",
        "races": [],
        "career_avg": {},
    }
    athlete_json["races"] = [r for r in athlete_json["races"] if r["race_slug"] != race_meta["slug"]]
    athlete_json["races"].append(athlete_race_entry)
    athlete_json["races"].sort(key=lambda r: r["year"], reverse=True)
    athlete_json["career_avg"] = {
        "vpi": _career_avg(athlete_json["races"], "vpi"),
        "dmi": _career_avg(athlete_json["races"], "dmi"),
        "er": _career_avg(athlete_json["races"], "er"),
    }
    _save(athlete_path, athlete_json)

    return race_path, athlete_path
