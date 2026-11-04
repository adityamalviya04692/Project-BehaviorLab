# Architecture and contracts

## Capture and identity

A random 256-bit HttpOnly, SameSite=Strict cookie scopes an anonymous workspace. Each workspace has one real visitor plus an optional synthetic cohort. The server assigns IDs and `source`; a client cannot impersonate a synthetic visitor by adding fields. No personal identity data is collected. This is an anonymous demonstration boundary, not an enterprise identity system.

`POST /api/events` accepts a JSON object:

```json
{
  "id": "c7913984-5105-4f8c-8459-c41a817f072a",
  "type": "bookmark_add",
  "content_id": "c2",
  "page": "detail"
}
```

For `topic_filter`, omit content_id or send null and supply `filter_value` from the catalog topics or `All`. Navigation actions do not accept content IDs. Server validation enforces UUIDs, actions, pages and content membership. Unknown categories cannot enter scores. Body size is bounded. Cross-origin writes and non-JSON writes are rejected. A workspace is capped at 8,000 real-capture event rows; the synthetic loader can add one bounded 60-visitor cohort. These limits do not replace perimeter rate limiting for a public service.

## Tables

| Table | Important fields | Role |
| --- | --- | --- |
| users | user_id, workspace, alias, source, created_at | Anonymous identity and tenant scope |
| events | seq, event_id, workspace, user_id, event_type, content_id, category, page, filter_value, source, received_at, schema_version | Durable capture order and source record |
| outbox | event_id, topic, status, partition_id, broker_offset, published_at | Retryable delivery and broker acknowledgment |
| bronze | event_id, payload, ingested_at, transport | Raw materialized payload |
| silver | event_id, user_id, category, effective_weight, processed_at | Normalized contribution |
| gold | user_id, scores, saved, liked, viewed, updated_at | Current profile for serving |
| worker_status | name, status, detail, updated_at | Publisher, consumer or local-processor heartbeat |
| dead_letters | topic, partition_id, broker_offset, error, created_at | Quarantine receipt for malformed Kafka envelopes |

Every database connection enables foreign keys. Deleting a workspace’s users cascades through its events and derived layers. A late Kafka message referring to a deleted event is skipped, preventing resurrection. API record/export output excludes the workspace capability. Keep server databases and broker logs out of public repositories.

## Transactional outbox

Capture runs `BEGIN IMMEDIATE`; the event and its outbox row commit atomically. A repeated event ID with an identical action is accepted without another row; conflicting reuse is rejected. This prevents the classic gap where the database commit succeeds but broker publication fails.

The publisher reads pending rows in sequence, sends full event metadata excluding the private workspace token, and uses a delivery callback to persist the broker partition and offset. `acks=all` and producer idempotence are enabled. Delivery errors preserve pending state. A crash after broker delivery and before marking the outbox can resend the event; the consumer deduplicates by event ID.

## Topic semantics

- `behavior.conferences`
- `behavior.shows`
- `behavior.networking`
- `behavior.workshops`
- `behavior.navigation`
- `business.commerce`, `business.meetings`, `business.planning`, `business.attendance`

Routing uses trusted catalog metadata, not inferred preference. All stories in a category share a topic. User IDs are keys, giving stable per-user partition routing *within a topic*. Category filters are navigation events, not evidence of a content preference. A preference is computed in the materializer.

The demo creates three partitions per topic and replication factor one. The configured broker is internal and uses plaintext within the local Compose network. Managed brokers can use SASL/TLS via `KAFKA_SECURITY_PROTOCOL`, `KAFKA_SASL_MECHANISM`, `KAFKA_SASL_USERNAME` and `KAFKA_SASL_PASSWORD`; never commit those credentials. Provision production topics with a suitable replication factor and permissions.

## Consumer, layers and ordering

The consumer validates the Kafka envelope and checks its key/topic against captured metadata. Bronze and silver rows plus the gold profile update share a transaction. The existing capture record is the source of truth; this demo is not a standalone ingestion consumer for arbitrary external events.

Profiles are replayed in server capture sequence over the visitor’s currently processed records. This is deliberate: Kafka does not guarantee ordering across different topics. A late bookmark-add that preceded a remove in capture order will still produce the correct final inactive bookmark. Silver weights are recomputed alongside the profile.

Offsets commit synchronously after database success. If the process crashes between database and offset commits, replay is safe. Malformed envelopes are recorded in `dead_letters` before advancing past them. Operational/database failures are retried from the last committed offset rather than discarded.

The replay implementation is simple and inspectable, but its work grows with per-user history. At higher scale, replace it with ordered incremental keyed state, well-defined late-event handling and a distributed store. Avoid multiple independent local materializer loops against this SQLite demo.

## Scoring and decisions

First view of each unique content item = 1 point. Active like = 2. Active bookmark = 4. Undo removes the corresponding points. Repeated views and duplicate add/remove actions contribute zero. Navigation/filter actions contribute zero. Shares are topic points divided by total points. Equal leaders are shown as a tie.

Recommendations sort by topic score, then unseen status, excluding saved content. Cohort membership is nonexclusive: a visitor can show interest in several topics. “With a bookmark” is an observed behavioral segment, not a validated propensity-to-buy model. Revenue is a transparent what-if calculation, with user-adjustable assumptions.

## API surface

| Method / path | Result |
| --- | --- |
| GET /api/health | Transport mode and worker heartbeat |
| GET /api/catalog | Sample content catalog |
| GET /api/state | Current real visitor’s events, scores and recommendations |
| POST /api/events | Validate/capture; process immediately only in local mode |
| POST /api/simulate | Create the deterministic 60-visitor synthetic cohort once |
| GET /api/overview?source=all\|real\|simulated | Workspace aggregates, profiles and latest 50 event records |
| GET /api/export | All raw events in this workspace, without private workspace key |
| POST /api/reset | Clear this workspace’s real and synthetic records |

## Retention and operating boundary

Cookie access lasts 30 days; database retention is independent and currently manual. Reset clears relational data but does not delete already-published Kafka records from broker logs. Set retention and access controls before processing actual sensitive customer data. The app captures only demo catalog interactions, not arbitrary browsing history. Gunicorn access logging is separate from the behavioral dataset and may include connection metadata.

No million-user workload has been executed. The architecture page distinguishes production design concepts from this single-host demonstration. The status UI distinguishes local processing, Kafka configuration and recent worker activity rather than presenting a fake broker connection.
