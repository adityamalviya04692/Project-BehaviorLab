# Northline Events validation

The 17 pipeline tests and all JavaScript syntax checks passed. A separate API smoke check reconciled CAD 330 from two tickets and one tote, then verified meeting booking, brief creation, proposal requests, check-in deduplication, workspace isolation, and processing into silver.

In the browser, stepping the replay from Checkout to Tickets registered ticket_purchase. A demo ticket purchase and entry appeared in the organizer dashboard and Insights as one issued ticket, one check-in, and CAD 149 in demo sales.

Kafka topics and container configuration are included. Live Kafka and public deployment were outside this local check.

## GitHub CI verification

On 5 November 2026, GitHub Actions run 41978919827 passed all 17 tests and the real-broker smoke test. The smoke verified capture, duplicate retries, Kafka acknowledgments, consumer materialization and reset.

https://github.com/adityamalviya04692/Project-BehaviorLab/actions/runs/41978919827
