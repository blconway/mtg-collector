import time
from datetime import UTC, datetime
from decimal import Decimal


def refresh_all_prices(app) -> None:
    """Background job: refresh market prices for all cards that have a scryfall_id."""
    from app.extensions import db
    from app.models import Card
    from app.services.scryfall import ScryfallError, get_prices

    with app.app_context():
        cards = Card.query.filter(Card.scryfall_id.isnot(None)).all()
        for card in cards:
            try:
                prices = get_prices(card.scryfall_id)
                usd = prices.get("usd")
                usd_foil = prices.get("usd_foil") or prices.get("usd_etched")
                card.market_price = Decimal(usd) if usd else card.market_price
                card.foil_price = Decimal(usd_foil) if usd_foil else card.foil_price
                card.price_updated_at = datetime.now(UTC)
                time.sleep(0.1)
            except (ScryfallError, Exception):
                continue
        db.session.commit()
