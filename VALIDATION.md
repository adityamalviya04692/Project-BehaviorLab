# Validation — 4 November 2026

## Passed locally

- 17 Python unit/API/transport-contract tests. Coverage includes score undo, repeated actions, capture idempotency, conflict rejection, atomic outbox capture, cross-topic out-of-order materialization, recommendations, deterministic bounded seed, workspace isolation, reset/late delivery, invalid input, source spoofing, CSRF/content-type/body limits, route/assets, acknowledgment handling, publish-failure status, private token exclusion and consumer commit/quarantine behavior.
- JavaScript syntax checks for all five modules.
- YAML parsing for both GitHub workflows and all three Compose configurations.
- Local application served with Gunicorn, one worker and eight HTTP threads.
- Browser: landing animation, pause control and sample generation work. 60 synthetic visitors produced 345 persisted/materialized events and 60 gold profiles.
- Browser: database record detail shows actual action/category/user/time/source; category routing lanes reconcile to 345 and honestly show zero Kafka publications in local mode.
- Browser: all four architecture stages work, including raw/clean/profile counts and scoring explanation.
- Browser: a real story view and bookmark generated two events and five Design points; Insights showed one real visitor and isolated those events from the synthetic cohort.
- Browser: scenario with 53 bookmarked synthetic visitors, 5% conversion and ₹1,500 order value produced ₹3,975; changing the value to ₹2,000 produced ₹5,300.
- Browser: a real visitor evidence profile showed one view, one active bookmark and five Design points.
- Responsive checks at 320px and 390px; desktop checks at 1440px. Fixed architecture grid min-content overflow and landing process-strip overflow at 320px. Data tables scroll inside their own containers.
- Reduced-motion emulation switched to Play animation (paused) and reduced visible cursors from 30 to six. Cleared the emulation and restored the original viewport after testing.
- No browser console errors observed during the tested application flows.

## Included, not executed here

- `tests/kafka_smoke.py` exercises a real Kafka deployment using HTTP, checking deduplication, broker acknowledgment, partition/offset receipt, Kafka-origin processing, profile scoring and reset.
- CI runs that smoke test against the supplied Compose stack. The image publication workflow runs it before publishing.
- No Docker runtime is installed on this machine. Actual Kafka startup, Docker image build, container volume initialization, Codespaces, GHCR publication and public HTTPS deployment remain unverified.
- Compose uses Kafka's image-provisioned `/var/lib/kafka/data` directory for the persistent volume, based on the Apache 3.9.1 Dockerfile's ownership and volume configuration.
- No load/soak test or million-user capacity claim. No real conversion or purchase outcome has been measured.

## Saved evidence

- `docs/landing-preview.png`
- `docs/architecture-preview.png`
- `docs/insights-preview.png`

The preview workspace retains 60 synthetic visitors and the two test interactions so its evidence panels are populated. Reset workspace clears that browser workspace if a clean walkthrough is preferred. The source archive excludes all SQLite databases, private cookies, local logs, virtual environments and Git internals.
