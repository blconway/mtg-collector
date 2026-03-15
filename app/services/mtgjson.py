import time

import requests

BASE_URL = "https://mtgjson.com/api/v5"
HEADERS = {"User-Agent": "MTGCollector/1.0", "Accept": "application/json"}
_DELAY = 0.05

# Cache the deck list so we don't re-fetch it on every search
_deck_list_cache: list[dict] | None = None


class MTGJSONError(Exception):
    pass


def _get(path: str) -> dict:
    time.sleep(_DELAY)
    try:
        resp = requests.get(f"{BASE_URL}{path}", headers=HEADERS, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        raise MTGJSONError(str(exc)) from exc


def get_deck_list() -> list[dict]:
    """Fetch and cache the full MTGJSON deck list."""
    global _deck_list_cache
    if _deck_list_cache is not None:
        return _deck_list_cache
    try:
        data = _get("/DeckList.json")
        _deck_list_cache = data.get("data", [])
        return _deck_list_cache
    except MTGJSONError:
        return []


def search_decks(query: str) -> list[dict]:
    """Search MTGJSON deck list by name."""
    decks = get_deck_list()
    q = query.lower()
    results = []
    for d in decks:
        name = d.get("name", "").lower()
        code = d.get("code", "").lower()
        deck_type = d.get("type", "").lower()
        if q in name or q == code:
            results.append({
                "code": d.get("code", ""),
                "fileName": d.get("fileName", ""),
                "name": d.get("name", ""),
                "releaseDate": d.get("releaseDate", ""),
                "type": d.get("type", ""),
            })
    # Sort by release date descending (newest first)
    results.sort(key=lambda d: d["releaseDate"], reverse=True)
    return results[:30]


def get_deck(file_name: str) -> dict | None:
    """Fetch a specific deck by its fileName."""
    try:
        data = _get(f"/decks/{file_name}.json")
        deck = data.get("data", data)
        return deck
    except MTGJSONError:
        return None


def deck_to_import_list(deck: dict) -> list[dict]:
    """Convert an MTGJSON deck to a list of card entries for import."""
    cards = []

    # Process commander(s) + mainboard + sideboard
    sections = [
        ("commander", deck.get("commander", [])),
        ("mainBoard", deck.get("mainBoard", [])),
        ("sideBoard", deck.get("sideBoard", [])),
    ]

    for section_name, section_cards in sections:
        for c in section_cards:
            name = c.get("name", "")
            if not name:
                continue

            identifiers = c.get("identifiers", {})
            scryfall_id = identifiers.get("scryfallId", "")
            set_code = c.get("setCode", "")
            collector_number = c.get("number", "")
            color_identity = "".join(c.get("colorIdentity", []))

            entry = {
                "name": name,
                "quantity": c.get("count", 1),
                "set_code": set_code,
                "collector_number": collector_number,
                "scryfall_id": scryfall_id,
                "type_line": c.get("type", ""),
                "mana_cost": c.get("manaCost", ""),
                "oracle_text": c.get("text", ""),
                "rarity": c.get("rarity", ""),
                "color_identity": color_identity,
                "is_commander": section_name == "commander",
            }
            cards.append(entry)

    return cards
