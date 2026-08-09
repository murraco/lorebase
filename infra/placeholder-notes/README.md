# Placeholder

This folder exists so `docker compose up` works before you point
`LOREBASE_NOTES_DIR` at real notes.

Set it in `infra/.env`:

    LOREBASE_NOTES_DIR=/Users/you/Documents/notes

Then `docker compose up -d` (not `restart` — env changes only apply when
the container is recreated) and the folder appears in the source picker
under `external`.
