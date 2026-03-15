from flask import Blueprint, jsonify, request

from app.services.scryfall import ScryfallError, autocomplete, get_card_by_id, get_prints

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.get("/autocomplete")
def card_autocomplete():
    q = request.args.get("q", "").strip()
    return jsonify({"results": autocomplete(q)})


@api_bp.get("/prints")
def card_prints():
    name = request.args.get("name", "").strip()
    if not name:
        return jsonify({"results": []})
    return jsonify({"results": get_prints(name)})


@api_bp.get("/card/<scryfall_id>")
def card_detail(scryfall_id: str):
    card = get_card_by_id(scryfall_id)
    if not card:
        return jsonify({"error": "Card not found"}), 404
    return jsonify(card)
