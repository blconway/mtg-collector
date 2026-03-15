import csv
import io

from flask import Blueprint, Response, render_template

from app.models import Card

inventory_bp = Blueprint("inventory", __name__)


@inventory_bp.get("/")
def collection():
    return render_template("collection.html")


@inventory_bp.get("/export")
def export_csv():
    cards = Card.query.order_by(Card.name.asc(), Card.set_name.asc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Name", "Set", "Set Code", "Collector #", "Condition", "Finish",
        "Language", "Quantity", "Rarity", "Type", "Binder", "Box", "Row", "Slot",
        "Purchase Price", "Market Price", "Tags", "Notes", "Acquired", "Scryfall ID",
    ])
    for c in cards:
        writer.writerow([
            c.name, c.set_name, c.set_code or "", c.collector_number or "",
            c.condition, c.finish, c.language, c.quantity,
            c.rarity or "", c.type_line or "",
            c.binder or "", c.box or "", c.row or "", c.slot or "",
            str(c.purchase_price), str(c.market_price or ""),
            c.tags or "", c.notes or "",
            str(c.acquired_at) if c.acquired_at else "",
            c.scryfall_id or "",
        ])
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=collection.csv"},
    )
