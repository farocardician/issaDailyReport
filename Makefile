.PHONY: up seed test sync-sheets set-webhook repomix

up:
	docker compose up -d --build

seed:
	docker compose run --rm --build bot python -m app.scripts.seed

test:
	docker compose run --rm --build bot pytest

sync-sheets:
	docker compose run --rm --build sheets-sync

set-webhook:
	docker compose run --rm --build bot python -c 'import os, urllib.parse, urllib.request; token = os.environ["TELEGRAM_BOT_TOKEN"]; base_url = os.environ["WEBHOOK_BASE_URL"].rstrip("/"); path = os.environ.get("WEBHOOK_PATH", "/telegram/webhook"); secret = os.environ["WEBHOOK_SECRET"]; data = urllib.parse.urlencode({"url": f"{base_url}{path}", "secret_token": secret}).encode(); print(urllib.request.urlopen(f"https://api.telegram.org/bot{token}/setWebhook", data=data).read().decode())'

repomix:
	docker build --output type=local,dest=. -f Dockerfile.repomix .
