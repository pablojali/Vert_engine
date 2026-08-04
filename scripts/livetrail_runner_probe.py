"""
Script INDEPENDIENTE (no toca utmb_checkpoints_fetcher.py ni app.py).

Explora y consume los endpoints de resultados de corredor en Livetrail,
en el mismo dominio ya confirmado para los checkpoints:

    https://api.v3.livetrail.net/api/events/points?raceId=vda            (checkpoints, confirmado)
    https://api.v3.livetrail.net/api/events/runners/{bib}                (resumen, confirmado)
    https://api.v3.livetrail.net/api/events/runners/{bib}/detail         (detalle completo, CONFIRMADO)

El endpoint /detail requiere X-Tenant COMBINADO (ej: "aranbyutmb_2026"),
no separado en X-Tenant + X-Year (eso devuelve 400).

Uso:
    # Endpoint confirmado, con tabla de passings ya parseada:
    python livetrail_runner_probe.py --detail --bib 5 --tenant aranbyutmb_2026 --race-id vda

    # JSON completo tal cual:
    python livetrail_runner_probe.py --detail --bib 5 --dump-raw

    # Endpoint de resumen (legado, sin passings detallados):
    python livetrail_runner_probe.py --bib 5 --dump-raw

    # Re-probar variantes de ruta/headers si algo cambia en el futuro:
    python livetrail_runner_probe.py --probe-detail --bib 5

Requiere: pip install requests
"""
import argparse
import json
import requests


def build_headers(tenant: str, split_tenant_year: bool = False) -> dict:
    """
    Dos esquemas posibles de headers, según lo observado:
      - Combinado (funciona en /api/events/points Y en /runners/{bib}/detail):
        X-Tenant: aranbyutmb_2026
      - Separado (visto en el bundle SSR, pero da 400 en /detail):
        X-Tenant: aranbyutmb + X-Year: 2026
    """
    subdomain = tenant.rsplit("_", 1)[0]
    base = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Origin": f"https://{subdomain}.v3.livetrail.net",
        "Referer": f"https://{subdomain}.v3.livetrail.net/",
    }
    if split_tenant_year:
        race_slug, year = tenant.rsplit("_", 1)
        base["X-Tenant"] = race_slug
        base["X-Year"] = year
    else:
        base["X-Tenant"] = tenant
    return base


# ---------------------------------------------------------------------------
# Endpoint CONFIRMADO: runner-detail (passings completos con ranking)
# ---------------------------------------------------------------------------

def fetch_runner_detail(bib: str, tenant: str, race_id: str, debug: bool = False):
    """
    GET https://api.v3.livetrail.net/api/events/runners/{bib}/detail?raceId={race_id}
    Header: X-Tenant combinado (ej: "aranbyutmb_2026").

    Devuelve diff1st, palmares, passings (pointId, dateTime, raceTime,
    ranking.scratch/sex/category, restTime), predictions, forecasts,
    penalities.
    """
    url = f"https://api.v3.livetrail.net/api/events/runners/{bib}/detail"
    headers = build_headers(tenant, split_tenant_year=False)
    resp = requests.get(url, params={"raceId": race_id}, headers=headers, timeout=15)
    if debug:
        print(f"[DEBUG] URL final: {resp.url}")
        print(f"[DEBUG] status={resp.status_code}")
    resp.raise_for_status()
    return resp.json()


def build_passings_table(detail_data: dict) -> list:
    """
    Extrae y aplana el array 'passings' de runner-detail en una lista de
    dicts lista para pandas/Excel: un row por checkpoint, con pointId,
    tiempo acumulado (raceTime en segundos -> HH:MM:SS), rankings y
    tiempo de descanso.
    """
    def _seconds_to_hms(seconds):
        if seconds is None:
            return None
        seconds = int(seconds)
        h, rem = divmod(seconds, 3600)
        m, s = divmod(rem, 60)
        return f"{h}:{m:02d}:{s:02d}"

    rows = []
    for p in detail_data.get("passings", []):
        ranking = p.get("ranking") or {}
        rows.append({
            "pointId": p.get("pointId"),
            "dateTime": p.get("dateTime"),
            "raceTime_seconds": p.get("raceTime"),
            "raceTime_hms": _seconds_to_hms(p.get("raceTime")),
            "restTime_seconds": p.get("restTime"),
            "rank_scratch": ranking.get("scratch"),
            "rank_sex": ranking.get("sex"),
            "rank_category": ranking.get("category"),
        })
    return rows


# ---------------------------------------------------------------------------
# Endpoint de resumen (legado / referencia): runners/{bib} sin /detail
# ---------------------------------------------------------------------------

def fetch_runner_summary(bib: str, tenant: str, race_id: str = None, debug: bool = False, split_headers: bool = False):
    """
    GET https://api.v3.livetrail.net/api/events/runners/{bib}
    Solo trae el resumen (bib, nombre, status, lastPassage, ranking) -
    NO trae el array completo de passings. Para eso usar fetch_runner_detail.
    """
    url = f"https://api.v3.livetrail.net/api/events/runners/{bib}"
    headers = build_headers(tenant, split_tenant_year=split_headers)
    params = {"raceId": race_id} if race_id else {}
    resp = requests.get(url, headers=headers, params=params, timeout=15)
    if debug:
        print(f"[DEBUG] URL final: {resp.url}")
        print(f"[DEBUG] status={resp.status_code}")
        print(f"[DEBUG] body (primeros 1500 chars): {resp.text[:1500]}")
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Probing (referencia histórica: cómo se encontró /detail)
# ---------------------------------------------------------------------------

RUNNER_DETAIL_CANDIDATE_TEMPLATES = [
    "https://api.v3.livetrail.net/api/events/runners/{bib}/detail",
    "https://api.v3.livetrail.net/api/events/runner-detail/{bib}",
    "https://api.v3.livetrail.net/api/events/runners/{bib}/passings",
    "https://api.v3.livetrail.net/api/events/runners/{bib}/passages",
    "https://api.v3.livetrail.net/api/events/runner-details/{bib}",
    "https://api.v3.livetrail.net/api/events/runners/detail/{bib}",
]


def probe_runner_detail_endpoints(bib: str, tenant: str, race_id: str = "vda"):
    """Prueba rutas candidatas con ambos esquemas de headers. Ya no hace
    falta correr esto normalmente: /runners/{bib}/detail + X-Tenant
    combinado ya está confirmado. Se deja para si algo cambia."""
    for template in RUNNER_DETAIL_CANDIDATE_TEMPLATES:
        url = template.format(bib=bib)
        for split in (False, True):
            headers = build_headers(tenant, split_tenant_year=split)
            scheme = "X-Tenant+X-Year separados" if split else "X-Tenant combinado"
            try:
                resp = requests.get(url, params={"raceId": race_id}, headers=headers, timeout=10)
            except requests.RequestException as e:
                print(f"[ERROR] ({scheme}) {url} -> {e}")
                continue
            print(f"[{resp.status_code}] ({scheme}) {url}?raceId={race_id}")
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    print(json.dumps(data, indent=2, ensure_ascii=False)[:1000])
                except ValueError:
                    print("  (respuesta no es JSON)")
            print("-" * 60)


def find_split_arrays(obj, path=""):
    """Busca recursivamente arrays de dicts con pinta de checkpoints/splits/passings."""
    candidates = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            candidates += find_split_arrays(v, f"{path}.{k}")
    elif isinstance(obj, list) and obj and isinstance(obj[0], dict):
        keys = set(obj[0].keys())
        hint_keys = {"pointId", "point", "id", "name", "km", "distance",
                     "checkpoint", "time", "cumulatedTime", "passing", "datetimeIn", "datetimeOut"}
        if keys & hint_keys:
            candidates.append((path, obj))
        for i, item in enumerate(obj):
            candidates += find_split_arrays(item, f"{path}[{i}]")
    return candidates


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bib", default="5", help="Número de dorsal (default: 5)")
    ap.add_argument("--tenant", default="aranbyutmb_2026", help="default: aranbyutmb_2026")
    ap.add_argument("--race-id", default=None, help="Opcional, se agrega como ?raceId=... si se pasa")
    ap.add_argument("--dump-raw", action="store_true", help="Imprime el JSON completo tal cual")
    ap.add_argument("--debug", action="store_true", help="Muestra status y URL final")
    ap.add_argument(
        "--split-headers",
        action="store_true",
        help="Usa X-Tenant + X-Year separados en vez de combinado (solo aplica al modo resumen)",
    )
    ap.add_argument(
        "--detail",
        action="store_true",
        help="Usa el endpoint CONFIRMADO runners/{bib}/detail (passings completos con ranking)",
    )
    ap.add_argument(
        "--probe-detail",
        action="store_true",
        help="Re-prueba endpoints candidatos para 'runner-detail' (ya no hace falta, referencia histórica)",
    )
    args = ap.parse_args()

    if args.detail:
        race_id = args.race_id or "vda"
        try:
            detail_data = fetch_runner_detail(args.bib, args.tenant, race_id, debug=args.debug)
        except Exception as e:
            print(f"[ERROR] La request falló: {e}")
            return

        if args.dump_raw:
            print(json.dumps(detail_data, indent=2, ensure_ascii=False))
            return

        print("== Resumen ==")
        print(f"diff1st: {detail_data.get('diff1st')}")
        print(f"Cantidad de passings: {len(detail_data.get('passings', []))}")
        print()
        print("== Tabla de passings (pointId, tiempo, rankings) ==")
        for row in build_passings_table(detail_data):
            print(row)
        return

    if args.probe_detail:
        probe_runner_detail_endpoints(args.bib, args.tenant, race_id=args.race_id or "vda")
        return

    # Modo resumen (legado)
    try:
        data = fetch_runner_summary(
            args.bib, args.tenant, race_id=args.race_id, debug=args.debug, split_headers=args.split_headers
        )
    except Exception as e:
        print(f"[ERROR] La request falló: {e}")
        return

    if args.dump_raw:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return

    print("== Claves de nivel raíz ==")
    if isinstance(data, dict):
        print(list(data.keys()))
    else:
        print(f"(la respuesta es una lista con {len(data)} elementos)")
    print()

    print("== Candidatos a lista de checkpoints/splits/pasadas ==")
    candidates = find_split_arrays(data)
    if not candidates:
        print("No se encontraron arrays con pinta de splits/pasadas. Corre con --dump-raw para ver todo.")
    for path, arr in candidates:
        print(f"\n--- {path} (primeros 3 elementos, de {len(arr)} totales) ---")
        print(json.dumps(arr[:3], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()