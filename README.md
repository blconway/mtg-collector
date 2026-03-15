# MTG Collector

A self-hosted Magic: The Gathering physical card collection manager inspired by [Tellico](https://tellico-project.org/). Built with Flask, PostgreSQL, and Docker.

Track your physical MTG cards with Scryfall integration, automatic price updates, and a Tellico-style 3-pane interface.

## Features

### Collection Management
- **3-pane layout** — group sidebar, card list, and detail panel
- **Group by** set, color, rarity, condition, finish, type, storage location, or tag
- **List and grid views** with resizable panes
- **Full card detail** with Scryfall images, oracle text, prices, and storage location
- **Add cards** via Scryfall search with autocomplete and printing selection
- **Track physical attributes** — condition, finish, language, quantity, storage location (binder/box/row/slot)
- **Tags and notes** on every card
- **Keyboard navigation** — arrow keys to browse, Escape to close modals

### Import
- **Paste a text list** — supports common formats:
  - `2x Sol Ring`
  - `1 Lightning Bolt (MH3)`
  - `1 Aegis Angel (W16) 1 Foil`
  - Split cards: `2 Archangel Avacyn // Avacyn, the Purifier (SOI) 5`
- **Upload CSV** — auto-detects columns (Name, Quantity, Set, Condition, Finish, etc.). Compatible with exports from Deckbox, Moxfield, and TCGPlayer.
- **Precon deck search** — search MTGJSON's database of 2,600+ precon decks by name, load the full deck list with Scryfall data, and import
- **Set search** — import all cards from any Scryfall set
- **Preview before importing** — review matched cards, remove unwanted entries, then commit

### Pricing
- **Automatic daily price refresh** via Scryfall (runs in background via APScheduler)
- **Manual price refresh** button in the sidebar
- **Collection value display** — total cards, unique count, and market value at a glance
- Per-card market price, foil price, and purchase price tracking

### Export
- **CSV export** of entire collection

## Quick Start

### Requirements
- Docker and Docker Compose

### Run

```bash
git clone https://github.com/blconway/mtg-collector.git
cd mtg-collector
docker-compose up
```

Open **http://localhost:5002**

That's it. The database is created automatically on first startup.

### Local Development (without Docker)

```bash
# Requires PostgreSQL running with a 'mtg_collector' database
pip install -r requirements.txt
export DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/mtg_collector"
python run.py
# Open http://localhost:5000
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Flask 3.1, SQLAlchemy 2.0 |
| Database | PostgreSQL 16 |
| Card Data | Scryfall API, MTGJSON API |
| Background Jobs | APScheduler |
| Frontend | Vanilla JS, custom CSS (dark theme) |
| Container | Docker, Docker Compose |
| Python | 3.13 |

## Configuration

Environment variables (defaults are set for development in `docker-compose.yml`):

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+psycopg://postgres:postgres@db:5432/mtg_collector` | PostgreSQL connection string |
| `SECRET_KEY` | `dev` | Flask secret key (change in production) |

## Project Structure

```
mtg-collector/
├── app/
│   ├── __init__.py              # Flask app factory
│   ├── config.py                # Configuration
│   ├── extensions.py            # SQLAlchemy init
│   ├── models.py                # Card model
│   ├── routes/
│   │   ├── api.py               # JSON API + import/export endpoints
│   │   ├── cards.py             # Card CRUD
│   │   └── inventory.py         # Collection view + CSV export
│   ├── services/
│   │   ├── importer.py          # Text/CSV parsers
│   │   ├── mtgjson.py           # MTGJSON deck list client
│   │   ├── prices.py            # Background price refresh
│   │   └── scryfall.py          # Scryfall API client
│   ├── static/
│   │   ├── collection.js        # 3-pane UI application
│   │   └── styles.css           # Dark theme styles
│   └── templates/
│       ├── base.html
│       ├── collection.html      # 3-pane layout shell
│       ├── card_form.html       # Standalone add/edit form
│       └── partials/
│           ├── card_form_modal.html
│           └── import_modal.html
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── run.py
```

## API Endpoints

### Scryfall Proxy
- `GET /api/autocomplete?q=` — card name autocomplete
- `GET /api/prints?name=` — all printings of a card
- `GET /api/card/<scryfall_id>` — card details by Scryfall ID

### Collection
- `GET /api/collection/stats` — total cards, unique count, value, last price update
- `GET /api/groups?group_by=` — group tree for sidebar
- `GET /api/cards?group_by=&group_value=&sort=&q=&page=` — paginated card list
- `GET /api/cards/<uid>` — single card detail
- `POST /cards/add` — create card
- `POST /cards/<uid>/edit` — update card
- `POST /cards/<uid>/delete` — delete card

### Import
- `POST /api/import/parse` — parse text list or CSV, resolve via Scryfall
- `POST /api/import/commit` — bulk-create cards from parsed data
- `GET /api/decks/search?q=` — search MTGJSON precon decks
- `GET /api/decks/<fileName>/cards` — fetch and resolve a precon deck
- `GET /api/sets/search?q=` — search Scryfall sets
- `GET /api/sets/<code>/cards` — fetch all cards in a set

### Pricing
- `POST /api/prices/refresh` — trigger manual price refresh

### Export
- `GET /export` — download collection as CSV

## License

MIT
