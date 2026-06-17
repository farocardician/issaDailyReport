# Instructions for AI or Human Reviewers

This repository implements the SPG Daily Store Reporting Telegram bot described in `PLAN.md`.

Use `PLAN.md` as the product and architecture source of truth. Do not invent new behavior unless the requested task explicitly changes the plan.

Important project rules:

- Run implementation, test, seed, and app commands through Docker Compose.
- Keep `src/app/domain/` pure: no Telegram imports and no database imports.
- Keep SQL access in `src/app/repositories/`.
- Keep Telegram orchestration in `src/app/bot/flow.py`.
- Preserve the Bahasa Indonesia message flow from `Reference/message_template.csv`.
- Do not commit real `.env` values, Telegram tokens, Cloudflare tunnel tokens, personal contact changes, or production database dumps.
- `Reference/user_master.csv` is intentionally omitted from the Repomix handoff because it can contain personal contact data. Use `src/app/scripts/seed.py` and `sql/schema.sql` for the user CSV shape.
- For verification, run `make test` and, when database behavior changes, run `make seed` against the Docker Compose database.
