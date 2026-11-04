# Run and deploy from GitHub

The repository contains everything needed to build the application and its Kafka demonstration. Hosting requires a running Python/container environment; GitHub Pages only serves static content and cannot host the backend.

## 1. Put the project in your repository

Use `behavior-lab` as the repository root, not its parent resume folder. Add only the project files; `.gitignore` excludes virtual environments, local databases, logs and `.env` files. The prepared source archive also excludes these private/runtime artifacts.

If creating a new repository through the GitHub UI, upload/extract the source files at the repository root, including `.github`, `.devcontainer`, the Dockerfiles and Compose files. If using Git locally, add your repository URL as `origin` and push the main branch.

No remote has been created or pushed as part of preparing this project.

## 2. Validate in GitHub Actions

`Validate application and Kafka pipeline` runs on pushes, pull requests and manual dispatch. It:

1. Installs Python dependencies and runs unit/API/transport tests.
2. Builds the app and starts Kafka, web and worker with Compose.
3. Runs `tests/kafka_smoke.py`, which submits a real HTTP event twice and verifies one capture, a broker acknowledgment, a Kafka-origin silver record, a gold profile, and reset.
4. Prints container logs and removes test containers/volumes.

The CI workflow is included but cannot be called “passed” until it actually runs in your repository.

## 3. Try the full stack in Codespaces

Create a Codespace from the repository. The devcontainer installs Python dependencies and provides Docker-in-Docker. Then run:

```sh
docker compose -f compose.yaml -f compose.kafka.yaml up --build -d --wait
```

Open forwarded port **8791**. Keep port visibility private while testing. A Codespace is a development environment that can stop when idle, not permanent production hosting.

For a quicker broker-free preview in Codespaces:

```sh
HOST=0.0.0.0 python server.py
```

## 4. Persistent deployment on a Docker host

On your chosen Linux host, install Git and Docker Compose. Clone your repository, enter its root and run:

```sh
docker compose -f compose.yaml -f compose.kafka.yaml up --build -d --wait
```

The app binds to host loopback port 8791. Kafka is not exposed to the host. Named volumes retain the application database and broker log when containers restart. Do not use `down -v` on a deployment whose data you want to keep.

For HTTPS, point a DNS name at that host, allow inbound 80/443, and put `DOMAIN=your.actual.domain` in `.env`. Then:

```sh
docker compose -f compose.yaml -f compose.kafka.yaml -f compose.deploy.yaml up --build -d --wait
```

Caddy terminates HTTPS and reverse-proxies to the web service. The deployment overlay enables Secure cookies. Do not enable Secure cookies for a plain-HTTP localhost preview. Caddy must be able to reach the public certificate authority and the domain must resolve to the host.

To update after pushing a change:

```sh
git pull --ff-only
docker compose -f compose.yaml -f compose.kafka.yaml -f compose.deploy.yaml up --build -d --wait
```

For a private demonstration, keep access behind your host’s existing access control or private network. Before opening an anonymous public demo broadly, add perimeter request limiting and an explicit data-retention policy. The per-workspace sample cap is not protection against someone creating many workspaces.

## 5. Publish a versioned container to GitHub Container Registry

Run **Publish container to GitHub** manually in Actions. It runs unit tests and the real Kafka smoke test before publishing:

- `ghcr.io/<owner>/<repository>:latest`
- `ghcr.io/<owner>/<repository>:<commit-sha>`

It uses `GITHUB_TOKEN` with package write permission. No registry password belongs in the repository. A registry image is a build artifact, not a hosted web endpoint. The Compose files build locally from the repository by default; to use GHCR, set the `image` of both `web` and `worker` in a deployment override and run with `--no-build` after pulling the chosen immutable tag.

## Environment settings

| Variable | Default | Use |
| --- | --- | --- |
| PIPELINE_MODE | local | local or kafka; no silent fallback |
| BEHAVIOR_DB | data/behavior-events.sqlite3 | Persistent SQLite path |
| HOST / PORT | 127.0.0.1 / 8791 | Development server only; Gunicorn binding is in Docker CMD |
| COOKIE_SECURE | 0 | Set 1 behind HTTPS |
| KAFKA_BOOTSTRAP_SERVERS | localhost:9092 | Worker broker addresses; Compose uses kafka:9092 |
| KAFKA_GROUP_ID | behavior-lab-events-v1 | Consumer group; use a distinct group per separate deployment |
| KAFKA_REPLICATION_FACTOR | 1 | Topic creation factor; increase only with enough brokers |
| KAFKA_SECURITY_PROTOCOL | client default | SASL_SSL for an appropriately configured managed broker |
| KAFKA_SASL_MECHANISM / USERNAME / PASSWORD | unset | Managed broker credentials supplied as secrets |
| DOMAIN | unset | Public hostname for the HTTPS overlay |

## Verified scope

Local Python/Gunicorn operation and browser workflows have been tested. This machine has no Docker runtime, so Compose startup, the actual broker, GHCR publication, Codespaces and public HTTPS deployment remain unverified here. The included CI smoke test makes broker validation a prerequisite of publishing the image.

## References

- [GitHub Pages is static hosting](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages)
- [Publishing Docker images with GitHub Actions](https://docs.github.com/en/actions/tutorials/publish-packages/publish-docker-images)
- [Flask deployment with Gunicorn](https://flask.palletsprojects.com/en/stable/deploying/gunicorn/)
- [Apache Kafka Docker example](https://github.com/apache/kafka/blob/trunk/docker/examples/docker-compose-files/single-node/plaintext/docker-compose.yml)
- [Confluent Kafka Python client](https://docs.confluent.io/kafka-clients/python/current/overview.html)
