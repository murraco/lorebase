# ADR 0003 — Local filesystem storage instead of S3

**Status:** Accepted

## Context

Lorebase caches original files (uploaded PDFs, via `Document.original_file`)
so a citation can point back to a real source artifact, not just re-parsed
text. The design doc originally sketched a custom `StorageProvider`
abstraction (§4.6) to keep this swappable between local disk and an
S3-compatible object store.

## Decision

Use Django's own built-in, pluggable storage API (the `STORAGES` setting +
`django.core.files.storage`) with the local filesystem backend — no custom
`StorageProvider` class, and no S3/MinIO/Garage dependency for now
(`docs/roadmap.md`, "Hallazgos previos al plan", finding 8). MinIO was
additionally ruled out on its own merits: it stopped being maintained in
2026.

## Consequences

**Gains:**
- Zero code written for something Django already solves. A hand-rolled
  `StorageProvider` interface would have re-implemented what `STORAGES`
  already provides, for no functional gain.
- Zero infrastructure for a personal-scale deployment — no object storage
  service to run, secure, or pay for.
- The swap to S3-compatible storage later is a configuration change
  (`django-storages` + a `STORAGES` setting update), not new code, because
  the abstraction boundary Django already ships is the one being used.

**Costs / accepted limitations:**
- Original files live on whatever disk the `backend`/`worker` containers
  mount, not in redundant, geographically-distributed object storage — a
  real durability trade-off for a personal deployment, mitigated by
  `infra/scripts/backup.sh` covering the database but *not* currently
  these cached originals (a gap worth closing before this ever holds
  data that matters more than personal notes already backed up
  elsewhere).
- Doesn't scale to multiple backend replicas sharing one filesystem
  without a shared volume, which local disk doesn't provide across
  machines.

**Migration trigger:** multi-instance deployment (several backend
replicas needing shared access to the same files), or a real durability
requirement beyond what host-level backups cover. Migrate to Garage
(self-hosted, S3-compatible) or S3 itself — `django-storages` plus a
`STORAGES` setting change, not a rewrite.
