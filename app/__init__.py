import atexit
import os

from flask import Flask

from app.config import Config
from app.extensions import db
from app.routes.api import api_bp
from app.routes.cards import cards_bp
from app.routes.inventory import inventory_bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    app.register_blueprint(inventory_bp)
    app.register_blueprint(cards_bp)
    app.register_blueprint(api_bp)

    with app.app_context():
        db.create_all()

    # Background price refresh every 24 hours
    if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.interval import IntervalTrigger
        from app.services.prices import refresh_all_prices

        scheduler = BackgroundScheduler()
        scheduler.add_job(
            func=refresh_all_prices,
            trigger=IntervalTrigger(hours=24),
            args=[app],
            id="refresh_prices",
            replace_existing=True,
        )
        scheduler.start()
        atexit.register(scheduler.shutdown)

    return app
