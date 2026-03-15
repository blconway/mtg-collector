from datetime import date
from decimal import Decimal, InvalidOperation

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for

from app.extensions import db
import json

from app.models import (
    CONDITION_OPTIONS,
    FINISH_OPTIONS,
    LANGUAGE_OPTIONS,
    Card,
    ChangeLog,
)
from app.services.scryfall import get_card_by_id

cards_bp = Blueprint("cards", __name__)


def _wants_json() -> bool:
    return (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or request.accept_mimetypes.best == "application/json"
    )


def _parse_decimal(val: str) -> Decimal:
    try:
        return Decimal(val.strip()) if val.strip() else Decimal("0.00")
    except InvalidOperation:
        return Decimal("0.00")


def _parse_date(val: str) -> date | None:
    if not val or not val.strip():
        return None
    try:
        return date.fromisoformat(val.strip())
    except ValueError:
        return None


def _apply_form(card: Card) -> list[str]:
    """Apply form POST data to a Card instance. Returns list of validation errors."""
    errors: list[str] = []

    card.name = request.form.get("name", "").strip()
    card.set_name = request.form.get("set_name", "").strip()
    card.set_code = request.form.get("set_code", "").strip() or None
    card.collector_number = request.form.get("collector_number", "").strip() or None
    card.scryfall_id = request.form.get("scryfall_id", "").strip() or None
    card.oracle_id = request.form.get("oracle_id", "").strip() or None
    card.type_line = request.form.get("type_line", "").strip() or None
    card.mana_cost = request.form.get("mana_cost", "").strip() or None
    card.oracle_text = request.form.get("oracle_text", "").strip() or None
    card.rarity = request.form.get("rarity", "").strip() or None
    card.color_identity = request.form.get("color_identity", "").strip() or None
    card.image_url = request.form.get("image_url", "").strip() or None
    card.scryfall_uri = request.form.get("scryfall_uri", "").strip() or None

    if not card.name:
        errors.append("Card name is required.")

    condition = request.form.get("condition", "near_mint")
    if condition not in CONDITION_OPTIONS:
        errors.append("Invalid condition.")
    card.condition = condition

    finish = request.form.get("finish", "nonfoil")
    if finish not in FINISH_OPTIONS:
        errors.append("Invalid finish.")
    card.finish = finish

    card.language = request.form.get("language", "English")

    try:
        qty = int(request.form.get("quantity", "1"))
        if qty < 1:
            raise ValueError
        card.quantity = qty
    except (ValueError, TypeError):
        errors.append("Quantity must be a positive number.")

    card.purchase_price = _parse_decimal(request.form.get("purchase_price", ""))

    market_raw = request.form.get("market_price", "").strip()
    card.market_price = Decimal(market_raw) if market_raw else card.market_price

    foil_raw = request.form.get("foil_price", "").strip()
    card.foil_price = Decimal(foil_raw) if foil_raw else card.foil_price

    card.binder = request.form.get("binder", "").strip() or None
    card.box = request.form.get("box", "").strip() or None
    card.row = request.form.get("row", "").strip() or None
    card.slot = request.form.get("slot", "").strip() or None
    card.notes = request.form.get("notes", "").strip() or None
    card.tags = request.form.get("tags", "").strip() or None
    card.acquired_at = _parse_date(request.form.get("acquired_at", ""))

    return errors


@cards_bp.get("/cards/add")
def add_card():
    return render_template(
        "card_form.html",
        card=None,
        condition_options=CONDITION_OPTIONS,
        finish_options=FINISH_OPTIONS,
        language_options=LANGUAGE_OPTIONS,
        prefill={},
    )


@cards_bp.post("/cards/add")
def add_card_post():
    card = Card()
    errors = _apply_form(card)
    if errors:
        if _wants_json():
            return jsonify({"ok": False, "errors": errors}), 400
        for e in errors:
            flash(e, "error")
        return redirect(url_for("cards.add_card"))
    db.session.add(card)
    db.session.flush()
    log = ChangeLog(
        action="add",
        description=f"Added {card.name}",
        card_data=json.dumps([card.to_dict()]),
    )
    db.session.add(log)
    db.session.commit()
    if _wants_json():
        return jsonify({"ok": True, "card": card.to_dict(), "message": f"Added {card.name}."})
    flash(f"Added {card.name}.", "success")
    return redirect(url_for("inventory.collection"))


@cards_bp.get("/cards/<uid>/edit")
def edit_card(uid: str):
    card = Card.query.filter_by(uid=uid).first_or_404()
    return render_template(
        "card_form.html",
        card=card,
        condition_options=CONDITION_OPTIONS,
        finish_options=FINISH_OPTIONS,
        language_options=LANGUAGE_OPTIONS,
        prefill={},
    )


@cards_bp.post("/cards/<uid>/edit")
def edit_card_post(uid: str):
    card = Card.query.filter_by(uid=uid).first_or_404()
    errors = _apply_form(card)
    if errors:
        if _wants_json():
            return jsonify({"ok": False, "errors": errors}), 400
        for e in errors:
            flash(e, "error")
        return redirect(url_for("cards.edit_card", uid=uid))
    db.session.commit()
    if _wants_json():
        return jsonify({"ok": True, "card": card.to_dict(), "message": f"Saved {card.name}."})
    flash(f"Saved {card.name}.", "success")
    return redirect(url_for("inventory.collection"))


@cards_bp.post("/cards/<uid>/delete")
def delete_card(uid: str):
    card = Card.query.filter_by(uid=uid).first_or_404()
    name = card.name
    log = ChangeLog(
        action="delete",
        description=f"Deleted {name}",
        card_data=json.dumps([card.to_dict()]),
    )
    db.session.add(log)
    db.session.delete(card)
    db.session.commit()
    if _wants_json():
        return jsonify({"ok": True, "message": f"Deleted {name}."})
    flash(f"Deleted {name}.", "success")
    return redirect(url_for("inventory.collection"))
