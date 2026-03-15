import time

import requests

BASE_URL = "https://api.scryfall.com"
HEADERS = {"User-Agent": "MTGCollector/1.0", "Accept": "application/json"}
_DELAY = 0.05  # 50ms between requests to stay well under the 10 req/s limit


class ScryfallError(Exception):
    pass


def _get(path: str, params: dict | None = None) -> dict:
    time.sleep(_DELAY)
    try:
        resp = requests.get(
            f"{BASE_URL}{path}", params=params, headers=HEADERS, timeout=10
        )
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        raise ScryfallError(str(exc)) from exc


def autocomplete(q: str) -> list[str]:
    if len(q) < 2:
        return []
    try:
        data = _get("/cards/autocomplete", {"q": q})
        return data.get("data", [])
    except ScryfallError:
        return []


def get_prints(name: str) -> list[dict]:
    """Return all unique printings of a card sorted newest first."""
    try:
        data = _get(
            "/cards/search",
            {"q": f'!"{name}"', "unique": "prints", "order": "released", "dir": "desc"},
        )
        return [_format_card(c) for c in data.get("data", [])]
    except ScryfallError:
        return []


def get_card_by_id(scryfall_id: str) -> dict | None:
    try:
        return _format_card(_get(f"/cards/{scryfall_id}"))
    except ScryfallError:
        return None


def get_prices(scryfall_id: str) -> dict:
    try:
        data = _get(f"/cards/{scryfall_id}")
        prices = data.get("prices", {})
        return {
            "usd": prices.get("usd"),
            "usd_foil": prices.get("usd_foil"),
            "usd_etched": prices.get("usd_etched"),
        }
    except ScryfallError:
        return {}


def _format_card(data: dict) -> dict:
    image_url = ""
    if "image_uris" in data:
        image_url = data["image_uris"].get("normal", "")
    elif "card_faces" in data and data["card_faces"]:
        face = data["card_faces"][0]
        if "image_uris" in face:
            image_url = face["image_uris"].get("normal", "")

    prices = data.get("prices", {})
    color_identity = "".join(data.get("color_identity", []))

    released = data.get("released_at", "")
    year = released[:4] if released else ""

    return {
        "scryfall_id": data["id"],
        "oracle_id": data.get("oracle_id", ""),
        "name": data["name"],
        "set_name": data.get("set_name", ""),
        "set_code": data.get("set", "").upper(),
        "collector_number": data.get("collector_number", ""),
        "type_line": data.get("type_line", ""),
        "mana_cost": data.get("mana_cost", ""),
        "oracle_text": data.get("oracle_text", ""),
        "rarity": data.get("rarity", ""),
        "color_identity": color_identity,
        "image_url": image_url,
        "scryfall_uri": data.get("scryfall_uri", ""),
        "market_price": prices.get("usd"),
        "foil_price": prices.get("usd_foil") or prices.get("usd_etched"),
        "year": year,
    }
