import csv
import io
from decimal import Decimal

from flask import Blueprint, Response, render_template, request

from app.extensions import db
from app.models import (
    CONDITION_LABELS,
    CONDITION_OPTIONS,
    FINISH_OPTIONS,
    Card,
)

inventory_bp = Blueprint("inventory", __name__)


@inventory_bp.get("/")
def index():
    total_cards = db.session.query(db.func.sum(Card.quantity)).scalar() or 0
    unique_cards = Card.query.count()
    total_value = sum((c.total_value for c in Card.query.all()), Decimal("0.00"))

    # Breakdown by condition
    by_condition = {}
    for opt in CONDITION_OPTIONS:
        count = db.session.query(db.func.sum(Card.quantity)).filter(Card.condition == opt).scalar() or 0
        if count:
            by_condition[CONDITION_LABELS[opt]] = count

    # Breakdown by finish
    by_finish: dict[str, int] = {}
    for finish in FINISH_OPTIONS:
        count = db.session.query(db.func.sum(Card.quantity)).filter(Card.finish == finish).scalar() or 0
        if count:
            by_finish[finish.title()] = count

    # Top sets by card count
    from sqlalchemy import func
    top_sets = (
        db.session.query(Card.set_name, func.sum(Card.quantity).label("qty"))
        .group_by(Card.set_name)
        .order_by(func.sum(Card.quantity).desc())
        .limit(8)
        .all()
    )

    recent = Card.query.order_by(Card.created_at.desc()).limit(8).all()

    return render_template(
        "index.html",
        total_cards=total_cards,
        unique_cards=unique_cards,
        total_value=total_value,
        by_condition=by_condition,
        by_finish=by_finish,
        top_sets=top_sets,
        recent=recent,
    )


@inventory_bp.get("/inventory")
def inventory():
    q = request.args.get("q", "").strip()
    condition_f = request.args.get("condition", "").strip()
    finish_f = request.args.get("finish", "").strip()
    set_f = request.args.get("set_name", "").strip()
    rarity_f = request.args.get("rarity", "").strip()
    location_f = request.args.get("location", "").strip()
    tag_f = request.args.get("tag", "").strip()
    sort = request.args.get("sort", "name")
    page = max(1, request.args.get("page", 1, type=int))
    per_page = 50

    query = Card.query

    if q:
        query = query.filter(Card.name.ilike(f"%{q}%"))
    if condition_f:
        query = query.filter(Card.condition == condition_f)
    if finish_f:
        query = query.filter(Card.finish == finish_f)
    if set_f:
        query = query.filter(Card.set_name == set_f)
    if rarity_f:
        query = query.filter(Card.rarity == rarity_f)
    if location_f:
        query = query.filter(
            db.or_(Card.binder == location_f, Card.box == location_f)
        )
    if tag_f:
        query = query.filter(Card.tags.ilike(f"%{tag_f}%"))

    sort_map = {
        "name": Card.name.asc(),
        "value": Card.market_price.desc().nullslast(),
        "condition": Card.condition.asc(),
        "set": Card.set_name.asc(),
        "added": Card.created_at.desc(),
        "quantity": Card.quantity.desc(),
    }
    query = query.order_by(sort_map.get(sort, Card.name.asc()), Card.set_name.asc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    # Filter options for dropdowns
    sets = [r[0] for r in db.session.query(Card.set_name).distinct().order_by(Card.set_name).all() if r[0]]
    locations = sorted(set(
        r for r in
        [r[0] for r in db.session.query(Card.binder).distinct().all() if r[0]] +
        [r[0] for r in db.session.query(Card.box).distinct().all() if r[0]]
    ))

    return render_template(
        "inventory.html",
        pagination=pagination,
        cards=pagination.items,
        q=q,
        condition_f=condition_f,
        finish_f=finish_f,
        set_f=set_f,
        rarity_f=rarity_f,
        location_f=location_f,
        tag_f=tag_f,
        sort=sort,
        sets=sets,
        locations=locations,
        condition_options=CONDITION_OPTIONS,
        condition_labels=CONDITION_LABELS,
        finish_options=FINISH_OPTIONS,
        total_results=pagination.total,
    )


@inventory_bp.get("/inventory/export")
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
