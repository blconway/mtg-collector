from flask import Blueprint, jsonify, render_template, request
from sqlalchemy import func

from app.extensions import db
from app.models import (
    CONDITION_LABELS,
    CONDITION_OPTIONS,
    FINISH_OPTIONS,
    LANGUAGE_OPTIONS,
    Card,
)
from app.services.importer import parse_csv, parse_text_list, resolve_cards
from app.services.mtgjson import deck_to_import_list, get_deck, search_decks
from app.services.scryfall import (
    ScryfallError, autocomplete, get_card_by_id, get_card_by_id, get_prints,
    get_set_cards, search_card, search_sets,
)

api_bp = Blueprint("api", __name__, url_prefix="/api")


# ── Scryfall proxy endpoints ─────────────────────────────────────────────────

@api_bp.get("/autocomplete")
def card_autocomplete():
    q = request.args.get("q", "").strip()
    return jsonify({"results": autocomplete(q)})


@api_bp.get("/collection/stats")
def collection_stats():
    """Return collection summary stats."""
    from decimal import Decimal

    total_qty = db.session.query(func.sum(Card.quantity)).scalar() or 0
    unique_count = Card.query.count()

    # Calculate total value
    cards = Card.query.all()
    total_value = sum((c.total_value for c in cards), Decimal("0.00"))

    # Find most recent price update
    latest_update = db.session.query(func.max(Card.price_updated_at)).scalar()

    return jsonify({
        "total_cards": int(total_qty),
        "unique_cards": unique_count,
        "total_value": str(total_value),
        "price_updated_at": latest_update.isoformat() if latest_update else None,
    })


@api_bp.post("/prices/refresh")
def refresh_prices():
    """Manually trigger a price refresh for all cards."""
    import threading
    from flask import current_app

    app = current_app._get_current_object()

    def _run_refresh():
        from app.services.prices import refresh_all_prices
        refresh_all_prices(app)

    thread = threading.Thread(target=_run_refresh, daemon=True)
    thread.start()

    return jsonify({"ok": True, "message": "Price refresh started. This may take a few minutes."})


@api_bp.get("/prints")
def card_prints():
    name = request.args.get("name", "").strip()
    if not name:
        return jsonify({"results": []})
    return jsonify({"results": get_prints(name)})


@api_bp.get("/card/<scryfall_id>")
def scryfall_card_detail(scryfall_id: str):
    card = get_card_by_id(scryfall_id)
    if not card:
        return jsonify({"error": "Card not found"}), 404
    return jsonify(card)


# ── Collection API endpoints ─────────────────────────────────────────────────

COLOR_LABELS = {
    "W": "White",
    "U": "Blue",
    "B": "Black",
    "R": "Red",
    "G": "Green",
}


@api_bp.get("/groups")
def groups():
    """Return group tree for the sidebar."""
    group_by = request.args.get("group_by", "set_name").strip()

    allowed = {
        "set_name", "color_identity", "rarity", "condition",
        "finish", "type_line", "binder", "box", "tags",
    }
    if group_by not in allowed:
        group_by = "set_name"

    if group_by == "tags":
        return _groups_by_tags()

    if group_by == "color_identity":
        return _groups_by_color()

    if group_by == "condition":
        return _groups_by_condition()

    column = getattr(Card, group_by)
    rows = (
        db.session.query(column, func.sum(Card.quantity).label("count"))
        .group_by(column)
        .order_by(column.asc())
        .all()
    )

    result = []
    for value, count in rows:
        label = value if value else "(none)"
        if group_by == "finish":
            label = (value or "nonfoil").title()
        result.append({"label": label, "value": value or "", "count": int(count)})

    total = sum(g["count"] for g in result)
    return jsonify({"group_by": group_by, "total": total, "groups": result})


def _groups_by_tags():
    cards = db.session.query(Card.tags, Card.quantity).all()
    tag_counts: dict[str, int] = {}
    total = 0
    for tags_str, qty in cards:
        total += qty
        if not tags_str:
            tag_counts.setdefault("(untagged)", 0)
            tag_counts["(untagged)"] += qty
            continue
        for tag in tags_str.split(","):
            tag = tag.strip()
            if tag:
                tag_counts.setdefault(tag, 0)
                tag_counts[tag] += qty

    result = [
        {"label": tag, "value": tag, "count": count}
        for tag, count in sorted(tag_counts.items())
    ]
    return jsonify({"group_by": "tags", "total": total, "groups": result})


def _groups_by_color():
    rows = db.session.query(Card.color_identity, Card.quantity).all()
    color_counts: dict[str, int] = {}
    total = 0
    for ci, qty in rows:
        total += qty
        if not ci:
            color_counts.setdefault("Colorless", 0)
            color_counts["Colorless"] += qty
        elif len(ci) > 1:
            color_counts.setdefault("Multicolor", 0)
            color_counts["Multicolor"] += qty
        else:
            label = COLOR_LABELS.get(ci, ci)
            color_counts.setdefault(label, 0)
            color_counts[label] += qty

    # Stable color order
    order = ["White", "Blue", "Black", "Red", "Green", "Multicolor", "Colorless"]
    result = []
    for label in order:
        if label in color_counts:
            value = label
            result.append({"label": label, "value": value, "count": color_counts[label]})
    # Any extras not in order
    for label, count in sorted(color_counts.items()):
        if label not in order:
            result.append({"label": label, "value": label, "count": count})

    return jsonify({"group_by": "color_identity", "total": total, "groups": result})


def _groups_by_condition():
    rows = (
        db.session.query(Card.condition, func.sum(Card.quantity).label("count"))
        .group_by(Card.condition)
        .all()
    )
    counts = {cond: int(count) for cond, count in rows}
    result = []
    for opt in CONDITION_OPTIONS:
        if opt in counts:
            result.append({
                "label": CONDITION_LABELS[opt],
                "value": opt,
                "count": counts[opt],
            })
    total = sum(g["count"] for g in result)
    return jsonify({"group_by": "condition", "total": total, "groups": result})


def _build_card_query(group_by, group_value, q, sort):
    """Build a filtered and sorted Card query."""
    query = Card.query

    if q:
        query = query.filter(Card.name.ilike(f"%{q}%"))

    if group_value is not None:
        if group_by == "tags":
            if group_value == "(untagged)":
                query = query.filter(db.or_(Card.tags.is_(None), Card.tags == ""))
            else:
                query = query.filter(Card.tags.ilike(f"%{group_value}%"))
        elif group_by == "color_identity":
            if group_value == "Colorless":
                query = query.filter(db.or_(Card.color_identity.is_(None), Card.color_identity == ""))
            elif group_value == "Multicolor":
                query = query.filter(func.length(Card.color_identity) > 1)
            else:
                # Map label back to code
                code = next((k for k, v in COLOR_LABELS.items() if v == group_value), group_value)
                query = query.filter(Card.color_identity == code)
        else:
            column = getattr(Card, group_by, None)
            if column is not None:
                if group_value == "":
                    query = query.filter(db.or_(column.is_(None), column == ""))
                else:
                    query = query.filter(column == group_value)

    sort_map = {
        "name": Card.name.asc(),
        "value": Card.market_price.desc().nullslast(),
        "condition": Card.condition.asc(),
        "set": Card.set_name.asc(),
        "added": Card.created_at.desc(),
        "quantity": Card.quantity.desc(),
        "rarity": Card.rarity.asc(),
    }
    query = query.order_by(sort_map.get(sort, Card.name.asc()), Card.name.asc())
    return query


@api_bp.get("/cards")
def cards_list():
    """Return paginated card list as JSON."""
    group_by = request.args.get("group_by", "").strip()
    group_value = request.args.get("group_value", None)
    q = request.args.get("q", "").strip()
    sort = request.args.get("sort", "name")
    page = max(1, request.args.get("page", 1, type=int))
    per_page = 30

    query = _build_card_query(group_by, group_value, q, sort)
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "cards": [c.to_dict() for c in pagination.items],
        "total": pagination.total,
        "page": pagination.page,
        "pages": pagination.pages,
    })


@api_bp.get("/cards/<uid>")
def card_detail_json(uid: str):
    """Return full card detail as JSON."""
    card = Card.query.filter_by(uid=uid).first_or_404()
    return jsonify(card.to_dict())


@api_bp.get("/card-form")
def card_form_partial():
    """Return the add-card form HTML partial for modal injection."""
    return render_template(
        "partials/card_form_modal.html",
        card=None,
        condition_options=CONDITION_OPTIONS,
        condition_labels=CONDITION_LABELS,
        finish_options=FINISH_OPTIONS,
        language_options=LANGUAGE_OPTIONS,
    )


@api_bp.get("/card-form/<uid>")
def card_edit_form_partial(uid: str):
    """Return the edit-card form HTML partial for modal injection."""
    card = Card.query.filter_by(uid=uid).first_or_404()
    return render_template(
        "partials/card_form_modal.html",
        card=card,
        condition_options=CONDITION_OPTIONS,
        condition_labels=CONDITION_LABELS,
        finish_options=FINISH_OPTIONS,
        language_options=LANGUAGE_OPTIONS,
    )


# ── Import endpoints ─────────────────────────────────────────────────────────

@api_bp.get("/import-form")
def import_form_partial():
    """Return the import modal HTML partial."""
    return render_template("partials/import_modal.html")


@api_bp.post("/import/parse")
def import_parse():
    """Parse a text list or CSV and resolve cards via Scryfall."""
    fmt = request.form.get("format", "text")

    if fmt == "csv":
        # Accept either file upload or pasted content
        file = request.files.get("file")
        if file:
            content = file.read().decode("utf-8", errors="replace")
        else:
            content = request.form.get("content", "")
    else:
        content = request.form.get("content", "")

    if not content.strip():
        return jsonify({"ok": False, "errors": ["No content provided."]}), 400

    if fmt == "csv":
        parsed = parse_csv(content)
    else:
        parsed = parse_text_list(content)

    if not parsed:
        return jsonify({"ok": False, "errors": ["No cards found in input."]}), 400

    resolved, warnings = resolve_cards(parsed)

    return jsonify({
        "ok": True,
        "cards": resolved,
        "warnings": warnings,
        "total_parsed": len(parsed),
    })


@api_bp.post("/import/commit")
def import_commit():
    """Bulk-create cards from a resolved import list."""
    from decimal import Decimal, InvalidOperation

    data = request.get_json()
    if not data or "cards" not in data:
        return jsonify({"ok": False, "errors": ["No card data provided."]}), 400

    cards_data = data["cards"]
    imported = 0

    for entry in cards_data:
        name = entry.get("name", "").strip()
        if not name:
            continue

        def _dec(val):
            try:
                return Decimal(str(val).strip()) if val else Decimal("0.00")
            except (InvalidOperation, ValueError):
                return Decimal("0.00")

        card = Card(
            name=name,
            set_name=entry.get("set_name", ""),
            set_code=entry.get("set_code", "") or None,
            collector_number=entry.get("collector_number", "") or None,
            scryfall_id=entry.get("scryfall_id", "") or None,
            oracle_id=entry.get("oracle_id", "") or None,
            type_line=entry.get("type_line", "") or None,
            mana_cost=entry.get("mana_cost", "") or None,
            oracle_text=entry.get("oracle_text", "") or None,
            rarity=entry.get("rarity", "") or None,
            color_identity=entry.get("color_identity", "") or None,
            image_url=entry.get("image_url", "") or None,
            scryfall_uri=entry.get("scryfall_uri", "") or None,
            quantity=max(1, int(entry.get("quantity", 1))),
            condition=entry.get("condition", "near_mint"),
            finish=entry.get("finish", "nonfoil"),
            language=entry.get("language", "English"),
            purchase_price=_dec(entry.get("purchase_price")),
            market_price=_dec(entry.get("market_price")) if entry.get("market_price") else None,
            foil_price=_dec(entry.get("foil_price")) if entry.get("foil_price") else None,
            tags=entry.get("tags", "") or None,
            notes=entry.get("notes", "") or None,
        )
        db.session.add(card)
        imported += 1

    db.session.commit()
    return jsonify({"ok": True, "imported": imported})


# ── Precon / Set search endpoints ─────────────────────────────────────────────

@api_bp.get("/sets/search")
def sets_search():
    """Search for sets/precon decks by name."""
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify({"results": []})
    results = search_sets(q)
    return jsonify({"results": results})


@api_bp.get("/sets/<set_code>/cards")
def set_cards(set_code: str):
    """Fetch all cards in a set, ready for import."""
    cards = get_set_cards(set_code)
    # Add default import fields
    for card in cards:
        card["quantity"] = 1
        card["condition"] = "near_mint"
        card["finish"] = "nonfoil"
        card["language"] = "English"
        card["purchase_price"] = "0.00"
        card["tags"] = ""
        card["notes"] = ""
        card["matched"] = True
    return jsonify({"ok": True, "cards": cards, "total": len(cards)})


# ── Deck search endpoints (MTGJSON) ──────────────────────────────────────────

@api_bp.get("/decks/search")
def decks_search():
    """Search MTGJSON deck list by name."""
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify({"results": []})
    results = search_decks(q)
    return jsonify({"results": results})


@api_bp.get("/decks/<file_name>/cards")
def deck_cards(file_name: str):
    """Fetch a specific deck from MTGJSON and resolve cards via Scryfall."""
    deck = get_deck(file_name)
    if not deck:
        return jsonify({"ok": False, "errors": ["Deck not found."]}), 404

    entries = deck_to_import_list(deck)

    # Resolve each card via Scryfall for images and prices
    resolved = []
    warnings = []
    for entry in entries:
        scryfall_id = entry.get("scryfall_id", "")
        set_code = entry.get("set_code", "")
        collector_number = entry.get("collector_number", "")
        name = entry["name"]

        card_data = None

        # Try Scryfall ID first (most precise)
        if scryfall_id:
            card_data = get_card_by_id(scryfall_id)

        # Fall back to set+number
        if not card_data and set_code and collector_number:
            card_data = search_card(name, set_code, collector_number)

        # Fall back to name search
        if not card_data:
            card_data = search_card(name)

        if card_data:
            result = {**card_data}
            result["quantity"] = entry.get("quantity", 1)
            result["condition"] = "near_mint"
            result["finish"] = "nonfoil"
            result["language"] = "English"
            result["purchase_price"] = "0.00"
            result["tags"] = "commander" if entry.get("is_commander") else ""
            result["notes"] = ""
            result["matched"] = True
            resolved.append(result)
        else:
            result = {
                "name": name,
                "set_code": set_code,
                "set_name": "",
                "collector_number": collector_number,
                "quantity": entry.get("quantity", 1),
                "condition": "near_mint",
                "finish": "nonfoil",
                "language": "English",
                "purchase_price": "0.00",
                "tags": "",
                "notes": "",
                "matched": False,
                "image_url": "",
                "scryfall_id": scryfall_id,
                "oracle_id": "",
                "type_line": entry.get("type_line", ""),
                "mana_cost": entry.get("mana_cost", ""),
                "oracle_text": entry.get("oracle_text", ""),
                "rarity": entry.get("rarity", ""),
                "color_identity": entry.get("color_identity", ""),
                "scryfall_uri": "",
                "market_price": None,
                "foil_price": None,
            }
            resolved.append(result)
            warnings.append(f'Could not find "{name}" on Scryfall')

    return jsonify({
        "ok": True,
        "cards": resolved,
        "warnings": warnings,
        "deck_name": deck.get("name", ""),
        "total": len(resolved),
    })
