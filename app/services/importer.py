import csv
import io
import re

from app.services.scryfall import search_card


def parse_text_list(content: str) -> list[dict]:
    """Parse a plain text decklist into structured entries.

    Supported formats:
        2x Sol Ring
        2 Sol Ring
        Sol Ring
        1 Lightning Bolt (MH3)
        1 Aegis Angel (W16) 1
        1 Ambush Commander (DD1) 1 Foil
        2 Archangel Avacyn // Avacyn, the Purifier (SOI) 5
        // Comment or section header (ignored)
    """
    results = []

    # Format: qty name (SET) collector_number [Foil]
    # e.g. "1 Aegis Angel (W16) 1" or "1 Ambush Commander (DD1) 1 Foil"
    full_pattern = re.compile(
        r"^(\d+)\s+"                     # quantity
        r"(.+?)"                          # card name (lazy, stops at set code)
        r"\s+\(([A-Za-z0-9]+)\)"         # (SET) set code
        r"\s+(\d+[a-zA-Z]?)"             # collector number
        r"(?:\s+(Foil))?"                 # optional Foil marker
        r"\s*$",
        re.IGNORECASE,
    )

    # Format: qty[x] name [(SET)]
    # e.g. "2x Sol Ring" or "1 Lightning Bolt (MH3)"
    simple_pattern = re.compile(
        r"^(\d+)\s*x?\s+"       # quantity
        r"(.+?)"                 # card name
        r"(?:\s*\((\w+)\))?"     # optional set code in parens
        r"\s*$"
    )

    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("//") or line.startswith("#"):
            continue

        # Try full format first (qty name (SET) num [Foil])
        m = full_pattern.match(line)
        if m:
            entry = {
                "name": m.group(2).strip(),
                "quantity": int(m.group(1)),
                "set_code": m.group(3).upper(),
                "collector_number": m.group(4),
            }
            if m.group(5):
                entry["finish"] = "foil"
            results.append(entry)
            continue

        # Try simple format (qty[x] name [(SET)])
        m = simple_pattern.match(line)
        if m:
            results.append({
                "name": m.group(2).strip(),
                "quantity": int(m.group(1)),
                "set_code": m.group(3).upper() if m.group(3) else None,
            })
            continue

        # Try as bare card name, possibly with (SET) or trailing Foil
        set_match = re.match(r"^(.+?)\s*\((\w+)\)\s*(?:(\d+[a-zA-Z]?)\s*)?(?:(Foil))?\s*$", line, re.IGNORECASE)
        if set_match:
            entry = {
                "name": set_match.group(1).strip(),
                "quantity": 1,
                "set_code": set_match.group(2).upper(),
            }
            if set_match.group(3):
                entry["collector_number"] = set_match.group(3)
            if set_match.group(4):
                entry["finish"] = "foil"
            results.append(entry)
            continue

        # Bare card name
        if line:
            results.append({"name": line, "quantity": 1})

    return results


# Column name aliases for CSV import
_NAME_COLS = {"name", "card name", "card", "cardname"}
_QTY_COLS = {"quantity", "qty", "count", "amount"}
_SET_COLS = {"set", "set name", "edition", "setname"}
_SET_CODE_COLS = {"set code", "setcode", "code"}
_CONDITION_COLS = {"condition", "cond"}
_FINISH_COLS = {"finish", "foil", "printing"}
_LANGUAGE_COLS = {"language", "lang"}
_COLLECTOR_COLS = {"collector number", "collector_number", "number", "num", "collector num"}
_PRICE_COLS = {"purchase price", "purchase_price", "price", "cost"}
_TAGS_COLS = {"tags", "tag"}
_NOTES_COLS = {"notes", "note", "comment"}

CONDITION_ALIASES = {
    "mint": "mint",
    "near_mint": "near_mint",
    "lightly_played": "lightly_played",
    "moderately_played": "moderately_played",
    "heavily_played": "heavily_played",
    "damaged": "damaged",
    "nm": "near_mint",
    "near mint": "near_mint",
    "m": "mint",
    "lp": "lightly_played",
    "lightly played": "lightly_played",
    "mp": "moderately_played",
    "moderately played": "moderately_played",
    "hp": "heavily_played",
    "heavily played": "heavily_played",
    "d": "damaged",
    "dmg": "damaged",
}

FINISH_ALIASES = {
    "nonfoil": "nonfoil",
    "foil": "foil",
    "etched": "etched",
    "non-foil": "nonfoil",
    "normal": "nonfoil",
    "yes": "foil",
    "no": "nonfoil",
    "true": "foil",
    "false": "nonfoil",
}


def _find_col(headers: list[str], candidates: set[str]) -> int | None:
    """Find the index of a column matching any candidate name."""
    for i, h in enumerate(headers):
        if h.lower().strip() in candidates:
            return i
    return None


def _normalize_condition(val: str) -> str:
    return CONDITION_ALIASES.get(val.strip().lower(), "near_mint")


def _normalize_finish(val: str) -> str:
    return FINISH_ALIASES.get(val.strip().lower(), "nonfoil")


def parse_csv(content: str) -> list[dict]:
    """Parse CSV content into structured entries."""
    reader = csv.reader(io.StringIO(content))

    try:
        headers = next(reader)
    except StopIteration:
        return []

    name_idx = _find_col(headers, _NAME_COLS)
    if name_idx is None:
        return []

    qty_idx = _find_col(headers, _QTY_COLS)
    set_idx = _find_col(headers, _SET_COLS)
    set_code_idx = _find_col(headers, _SET_CODE_COLS)
    cond_idx = _find_col(headers, _CONDITION_COLS)
    finish_idx = _find_col(headers, _FINISH_COLS)
    lang_idx = _find_col(headers, _LANGUAGE_COLS)
    coll_idx = _find_col(headers, _COLLECTOR_COLS)
    price_idx = _find_col(headers, _PRICE_COLS)
    tags_idx = _find_col(headers, _TAGS_COLS)
    notes_idx = _find_col(headers, _NOTES_COLS)

    results = []
    for row in reader:
        if len(row) <= name_idx:
            continue

        name = row[name_idx].strip()
        if not name:
            continue

        entry = {"name": name, "quantity": 1}

        if qty_idx is not None and qty_idx < len(row) and row[qty_idx].strip():
            try:
                entry["quantity"] = max(1, int(row[qty_idx].strip()))
            except ValueError:
                pass

        if set_code_idx is not None and set_code_idx < len(row) and row[set_code_idx].strip():
            entry["set_code"] = row[set_code_idx].strip().upper()
        elif set_idx is not None and set_idx < len(row) and row[set_idx].strip():
            entry["set_name"] = row[set_idx].strip()

        if cond_idx is not None and cond_idx < len(row) and row[cond_idx].strip():
            entry["condition"] = _normalize_condition(row[cond_idx])

        if finish_idx is not None and finish_idx < len(row) and row[finish_idx].strip():
            entry["finish"] = _normalize_finish(row[finish_idx])

        if lang_idx is not None and lang_idx < len(row) and row[lang_idx].strip():
            entry["language"] = row[lang_idx].strip()

        if coll_idx is not None and coll_idx < len(row) and row[coll_idx].strip():
            entry["collector_number"] = row[coll_idx].strip()

        if price_idx is not None and price_idx < len(row) and row[price_idx].strip():
            entry["purchase_price"] = row[price_idx].strip()

        if tags_idx is not None and tags_idx < len(row) and row[tags_idx].strip():
            entry["tags"] = row[tags_idx].strip()

        if notes_idx is not None and notes_idx < len(row) and row[notes_idx].strip():
            entry["notes"] = row[notes_idx].strip()

        results.append(entry)

    return results


def resolve_cards(parsed: list[dict]) -> tuple[list[dict], list[str]]:
    """Look up each parsed entry on Scryfall and return resolved cards + warnings."""
    resolved = []
    warnings = []

    for entry in parsed:
        name = entry["name"]
        set_code = entry.get("set_code")

        collector_number = entry.get("collector_number")
        card_data = search_card(name, set_code, collector_number)

        if card_data:
            # Merge parsed entry with Scryfall data
            result = {**card_data}
            result["quantity"] = entry.get("quantity", 1)
            result["condition"] = entry.get("condition", "near_mint")
            result["finish"] = entry.get("finish", "nonfoil")
            result["language"] = entry.get("language", "English")
            result["purchase_price"] = entry.get("purchase_price", "0.00")
            result["tags"] = entry.get("tags", "")
            result["notes"] = entry.get("notes", "")
            result["matched"] = True
            resolved.append(result)
        else:
            # Card not found — include with basic info and a warning
            result = {
                "name": name,
                "set_code": set_code or "",
                "set_name": entry.get("set_name", ""),
                "quantity": entry.get("quantity", 1),
                "condition": entry.get("condition", "near_mint"),
                "finish": entry.get("finish", "nonfoil"),
                "language": entry.get("language", "English"),
                "purchase_price": entry.get("purchase_price", "0.00"),
                "tags": entry.get("tags", ""),
                "notes": entry.get("notes", ""),
                "matched": False,
                "image_url": "",
                "scryfall_id": "",
                "oracle_id": "",
                "type_line": "",
                "mana_cost": "",
                "oracle_text": "",
                "rarity": "",
                "color_identity": "",
                "scryfall_uri": "",
                "collector_number": entry.get("collector_number", ""),
                "market_price": None,
                "foil_price": None,
            }
            resolved.append(result)
            warnings.append(f"Could not find \"{name}\"{f' in set {set_code}' if set_code else ''} on Scryfall")

    return resolved, warnings
