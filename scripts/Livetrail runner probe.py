"""
Script INDEPENDIENTE (no toca utmb_checkpoints_fetcher.py ni app.py) para
probar si Livetrail expone resultados/pasadas de un corredor específico,
en el mismo dominio que ya confirmamos para los checkpoints:

    https://api.v3.livetrail.net/api/events/points?raceId=vda   (ya confirmado)
    https://api.v3.livetrail.net/api/events/runners/5           (a probar)

Mismo esquema de headers que ya funciona (X-Tenant + Origin/Referer
derivados del tenant).

Uso:
    python livetrail_runner_probe.py --bib 5 --tenant aranbyutmb_2026 --race-id vda --dump-raw

Requiere: pip install requests
"""
import argparse
import json
import requests


def build_headers(tenant: str) -> dict:
    subdomain = tenant.rsplit("_", 1)[0]
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Origin": f"https://{subdomain}.v3.livetrail.net",
        "Referer": f"https://{subdomain}.v3.livetrail.net/",
        "X-Tenant": tenant,
    }


def fetch_runner(bib: str, tenant: str, race_id: str = None, debug: bool = False):
    """
    Prueba el endpoint https://api.v3.livetrail.net/api/events/runners/{bib}
    Si race_id se pasa, se agrega como query param ?raceId=... por si acaso
    lo requiere (igual que /points), aunque puede que no sea necesario ya
    que el bib probablemente ya identifica al corredor de forma única
    dentro del tenant.
    """
    url = f"https://api.v3.livetrail.net/api/events/runners/{bib}"
    headers = build_headers(tenant)
    params = {"raceId": race_id} if race_id else {}

    resp = requests.get(url, headers=headers, params=params, timeout=15)

    if debug:
        print(f"[DEBUG] URL final: {resp.url}")
        print(f"[DEBUG] status={resp.status_code}")
        print(f"[DEBUG] response headers: {dict(resp.headers)}")
        print(f"[DEBUG] body (primeros 1500 chars): {resp.text[:1500]}")
        print("-" * 60)

    resp.raise_for_status()
    return resp.json()


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
    ap.add_argument("--debug", action="store_true", help="Muestra status, headers y body crudo")
    args = ap.parse_args()

    try:
        data = fetch_runner(args.bib, args.tenant, race_id=args.race_id, debug=args.debug)
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