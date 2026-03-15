from datetime import UTC, datetime, date
from decimal import Decimal
from uuid import uuid4

from app.extensions import db


def _uid() -> str:
    return str(uuid4())


CONDITION_OPTIONS = [
    "mint",
    "near_mint",
    "lightly_played",
    "moderately_played",
    "heavily_played",
    "damaged",
]

CONDITION_LABELS = {
    "mint": "Mint",
    "near_mint": "Near Mint",
    "lightly_played": "Lightly Played",
    "moderately_played": "Moderately Played",
    "heavily_played": "Heavily Played",
    "damaged": "Damaged",
}

FINISH_OPTIONS = ["nonfoil", "foil", "etched"]

LANGUAGE_OPTIONS = [
    "English",
    "Japanese",
    "German",
    "French",
    "Spanish",
    "Italian",
    "Portuguese",
    "Korean",
    "Russian",
    "Chinese Simplified",
    "Chinese Traditional",
]


class Card(db.Model):
    __tablename__ = "cards"

    id = db.Column(db.Integer, primary_key=True)
    uid = db.Column(db.String(36), nullable=False, unique=True, index=True, default=_uid)

    # Scryfall identity
    scryfall_id = db.Column(db.String(64), index=True)
    oracle_id = db.Column(db.String(64), index=True)
    name = db.Column(db.String(200), nullable=False, index=True)
    set_name = db.Column(db.String(200), nullable=False, default="")
    set_code = db.Column(db.String(10), index=True)
    collector_number = db.Column(db.String(20))

    # Card details from Scryfall
    type_line = db.Column(db.String(255))
    mana_cost = db.Column(db.String(100))
    oracle_text = db.Column(db.Text)
    rarity = db.Column(db.String(50), index=True)
    color_identity = db.Column(db.String(20))  # e.g. "WUB"
    image_url = db.Column(db.String(500))
    scryfall_uri = db.Column(db.String(500))

    # Physical attributes
    quantity = db.Column(db.Integer, nullable=False, default=1)
    condition = db.Column(db.String(50), nullable=False, default="near_mint", index=True)
    finish = db.Column(db.String(50), nullable=False, default="nonfoil", index=True)
    language = db.Column(db.String(50), nullable=False, default="English")

    # Storage location
    binder = db.Column(db.String(100), index=True)
    box = db.Column(db.String(100), index=True)
    row = db.Column(db.String(100))
    slot = db.Column(db.String(100))

    # Financial
    purchase_price = db.Column(db.Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    market_price = db.Column(db.Numeric(10, 2))
    foil_price = db.Column(db.Numeric(10, 2))
    price_updated_at = db.Column(db.DateTime(timezone=True))

    # Meta
    notes = db.Column(db.Text)
    tags = db.Column(db.String(500))
    acquired_at = db.Column(db.Date)
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    @property
    def current_price(self) -> Decimal:
        if self.finish == "foil" and self.foil_price:
            return self.foil_price
        if self.finish == "etched" and self.foil_price:
            return self.foil_price
        return self.market_price or Decimal("0.00")

    @property
    def total_value(self) -> Decimal:
        return self.current_price * self.quantity

    @property
    def condition_label(self) -> str:
        return CONDITION_LABELS.get(self.condition, self.condition)

    @property
    def tag_list(self) -> list[str]:
        if not self.tags:
            return []
        return [t.strip() for t in self.tags.split(",") if t.strip()]
