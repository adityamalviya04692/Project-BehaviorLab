# Behavior Lab

**Live demo:** https://behavior-lab-tum9.onrender.com — runs on Render's free plan in local-processor mode (no Kafka broker). The first request after idle can take about 50 seconds while the instance wakes, and demo data resets on restart. Run it locally (below) for the full Kafka stack.

An interactive behavioral data application. Watch an animated crowd move through a mobile app, try it yourself, inspect every pipeline layer, and explore audience interests and hypothetical sales opportunities.



## Four connected pages

| Page | Purpose |
| --- | --- |
| `/` | Original cursor-swarm animation illustrating many visitors, event registration and interest signals. Includes pause/reduced-motion support. |
| `/playground` | Clickable phone with Home, Explore, Saved, You and story details. Real clicks, likes, bookmarks and navigation become stored events. |
| `/architecture` | Inspect database records and schema, category topic routing, Kafka delivery receipts, bronze/silver/gold tables and scoring rules. |
| `/insights` | Topic cohorts, visitor evidence profiles, real/synthetic filters and an adjustable revenue scenario. |

The phone app represents **Northline Events**, a fictional Toronto-based corporate events company. Its Canadian event catalog is in `catalog.json`. Tickets, merchandise orders, meeting bookings, briefs, proposal requests, and entry are simulated within each workspace.

## Run locally

Python 3.9+ (Docker uses Python 3.12):

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python server.py
```

Open **http://127.0.0.1:8791**. Local mode runs the real event database and the same profile materializer without a broker. The UI labels this as **Local processor**. SQLite data persists in `data/behavior-events.sqlite3`.

For the production HTTP server locally:

```sh
.venv/bin/gunicorn --bind 127.0.0.1:8791 --workers 1 --threads 8 server:app
```

Keep one web worker in this demonstrator because local processing runs in an embedded thread. Kafka mode uses a separate worker service.

## Run the complete Kafka backend

Install Docker with Compose, then:

```sh
docker compose -f compose.yaml -f compose.kafka.yaml up --build -d --wait
```

This starts the Flask/Gunicorn web service, an Apache Kafka broker and a publisher/consumer worker. Kafka has nine behavior and business topics, three partitions per topic, and user IDs as partition keys. Kafka is internal to the Compose network. SQLite and broker logs use persistent volumes.

To use Docker without Kafka:

```sh
docker compose up --build -d --wait
```

Do not switch a populated deployment between modes while traffic is active: already-materialized local events are not republished to Kafka. Start a separate deployment or reset the demo workspace for a clean comparison.

## A two-minute walkthrough

1. Open the landing page and watch the cursor swarm. Its numbers are **illustrative**, not live user metrics.
2. Select **Run a 60-visitor sample**. This writes synthetic behavior and business records across 60 anonymous profiles into your workspace. Repeated clicks do not duplicate the sample.
3. Open **Architecture**. Watch captured events become bronze records, silver records and gold profiles. Inspect a row to see its ID, visitor, category, action, source and delivery metadata.
4. Explore **Route through Kafka**. In local mode, publication is correctly zero. With Compose Kafka, actual partitions and offsets appear after broker acknowledgment.
5. In **Playground**, open an event and save it. The profile gains one point for the first view and four for the active bookmark.
6. In **Insights**, select **My clicks** to isolate your actions from the synthetic audience. Inspect a visitor’s evidence, then adjust the conversion and order-value assumptions.

**Reset workspace** in the playground clears your real actions and synthetic sample. It does not affect other visitors’ workspaces. Existing browser cookies identify anonymous workspaces; there is no login or collection of names, emails or location.

## Pipeline

```text
Phone interactions
    → Flask validation + anonymous visitor identity
    → SQLite events + transactional outbox
    → Kafka category topics (or explicit local processor)
    → Bronze: raw event payload
    → Silver: normalized event + effective score contribution
    → Gold: per-visitor topic scores and active interests
    → audience cohorts, recommendations and what-if scenarios
```

The publisher only marks events published after a broker acknowledgment. The consumer commits offsets after materialization. Unique event IDs deduplicate capture and consumption. For cross-topic arrival, the profile is rebuilt in capture sequence. See [architecture details](docs/ARCHITECTURE.md).

## GitHub and deployment

This folder is ready to become the repository root. It includes:

- GitHub Actions checks for Python tests and a real Kafka end-to-end smoke test.
- A manually triggered workflow to publish a tested container to GitHub Container Registry.
- A Codespaces/devcontainer configuration with Docker support.
- Docker Compose configurations for local mode, Kafka mode and an HTTPS reverse proxy.

GitHub Pages cannot run this Python/Kafka backend. Use Codespaces to run the complete stack from GitHub, or deploy the repository on a persistent Docker host. See the exact commands in [DEPLOYMENT.md](docs/DEPLOYMENT.md). Source and case-study media are published in this repository. The public demo is deployed on Render from `render.yaml` at https://behavior-lab-tum9.onrender.com (local-processor mode, free plan).

## Validation

```sh
.venv/bin/python -m unittest -v test_pipeline.py
```

With the Kafka Compose stack running:

```sh
python tests/kafka_smoke.py
```

Read [VALIDATION.md](VALIDATION.md) for what was actually exercised and what remains unverified.

## Limits and honest interpretation

- The animated “million journeys” is a visual explanation. No million-user capacity or benchmark is claimed.
- Synthetic and real activity are labeled and independently filterable. Public visitors never receive another workspace’s rows.
- Topic scores are explainable heuristics. They are not trained AI, personality traits, confidence probabilities or purchase predictions.
- The what-if sales calculation uses eligible visitors, an assumed conversion rate and a CAD order value. Demo orders, quantities and totals are reported separately.
- SQLite, one materializer, a single broker and replication factor one are demonstration choices. Production scale needs a distributed data store, replicated Kafka, partition-aware workers, observability, retention and abuse controls.
- At-least-once transport plus idempotent writes is not an exactly-once guarantee across Kafka and SQLite.
- The original v1 `events.sqlite3`, if present, is preserved. The new schema uses `data/behavior-events.sqlite3`; v1 data is not silently migrated.

## Visual credits

The swarm concept was inspired by [DhvanilPatel/swarm-cursors](https://github.com/DhvanilPatel/swarm-cursors), which credits Joel Califa’s Swarm. This project uses an original, bounded Web Animations implementation; no extension code or animation assets were copied. The user’s normal pointer is unchanged.

## Northline demo walkthrough

Open North Summit, choose Get tickets, and place a demo order. Open Tickets to see a code for each pass and simulate entry. Use Shop to order merchandise and Workspace to book a consultation or save a brief with custom requirements. A saved brief can generate a demo proposal request. The Organizer dashboard shows event-specific tickets issued, check-ins, merchandise and ticket sales. Insights ranks clients by explicit follow-up signals and demo spend.

The event edition uses a separate database so records from the earlier story demo remain on disk. Prices are in CAD. Demo checkout creates local records and does not collect card details. Meeting and proposal actions create workspace records only.


## Case study and walkthrough

The repository includes an eight-slide editable presentation, a narrated MP4 walkthrough, captions and a PDF case study under `launch/output`.

The full Kafka CI workflow passed on 5 November 2026. See [the verified run](https://github.com/adityamalviya04692/Project-BehaviorLab/actions/runs/41978919827). The public demo is live at https://behavior-lab-tum9.onrender.com.
