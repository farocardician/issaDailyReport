# Deploying to a VPS

This guide moves the stack (Postgres + bot + Cloudflare Tunnel) from your local
Docker Compose setup to a VPS, carrying over the real database (submitted
reports, live-added admin/store records) rather than starting from a fresh
seed.

## Before you start

1. **Push your code.** `origin/main` may be behind your local branch. The VPS
   deploys by cloning from GitHub, so nothing reaches it until you push and
   merge to `main`:
   ```bash
   git add -A
   git commit -m "..."
   git push -u origin <your-branch>
   # merge that branch into main (PR + merge, or locally) and push main
   ```
2. **Decide: migrate the DB or start fresh.** If you have real submitted
   reports or stores/users added live through the bot's admin menus (not in
   `Reference/*.csv`), migrate the actual database (Phase 6 below) instead of
   just running `make seed` on the VPS — a fresh seed will not bring any of
   that over.

## Phase 1 — provision the VPS

Any provider (DigitalOcean, Hetzner, Vultr, Contabo, ...) — pick **Ubuntu
22.04 or 24.04 LTS**. 1–2 vCPU / 2GB RAM is enough for this stack. Note the
VPS IP address, then SSH in:

```bash
ssh root@<your-vps-ip>
```

## Phase 2 — install Docker on the VPS

```bash
curl -fsSL https://get.docker.com | sh
docker compose version   # verify the compose plugin is present
```

## Phase 3 — firewall

`cloudflared` only makes **outbound** connections, so no inbound web port
needs to be open — not even 80/443.

```bash
ufw allow OpenSSH
ufw enable
ufw status   # should show only 22/tcp allowed
```

## Phase 4 — get the code

```bash
git clone git@github.com:farocardician/issaDailyReport.git /opt/dailyreport
cd /opt/dailyreport
git checkout main   # or whichever branch you deployed
```

If the repo is private and you don't want to copy your personal SSH key to
the VPS, generate a deploy key there instead:

```bash
ssh-keygen -t ed25519 -C "vps-deploy"
```

Add the printed public key under GitHub repo → Settings → Deploy keys.

## Phase 5 — recreate `.env` on the VPS

Create `/opt/dailyreport/.env` with the same keys as `.env.example`. Values
are gitignored and do **not** transfer via git — copy them over SSH only,
never paste secrets into chat/tickets:

```bash
scp .env root@<your-vps-ip>:/opt/dailyreport/.env
```

Required keys:

```
TELEGRAM_BOT_TOKEN=
ADMIN_CHAT_ID=
DATABASE_URL=postgresql://spg:spg@db:5432/spg
BOT_MODE=webhook
WEBHOOK_BASE_URL=
WEBHOOK_PATH=/telegram/webhook
WEBHOOK_SECRET=
WEBHOOK_LISTEN_PORT=8080
DEFAULT_RADIUS_METER=100
ACTIVE_STATUS=Aktif
SESSION_TTL_MINUTES=30
APP_TZ=Asia/Jakarta
CLOUDFLARE_TUNNEL_TOKEN=
POSTGRES_USER=
POSTGRES_PASSWORD=
POSTGRES_DB=
```

Decide here:

- **Reuse the same** `CLOUDFLARE_TUNNEL_TOKEN` / `WEBHOOK_BASE_URL` — simplest,
  the public hostname doesn't change, you're just relocating which machine
  runs the tunnel connector.
- **Create a new Cloudflare Tunnel** for the VPS (Zero Trust dashboard →
  Networks → Tunnels → Create, route the public hostname to
  `http://bot:8080`, copy the new token). If you do this, update
  `WEBHOOK_BASE_URL` and re-run `make set-webhook` in Phase 8.

## Phase 6 — migrate the database

On your **local machine**:

```bash
docker compose exec -T db pg_dump -U faro -d storeDailyReport -F c -f /tmp/dailyreport.dump
docker compose cp db:/tmp/dailyreport.dump ./dailyreport.dump
scp ./dailyreport.dump root@<your-vps-ip>:/opt/dailyreport/
```

On the **VPS**:

```bash
cd /opt/dailyreport
docker compose up -d db          # start only Postgres first
docker compose exec -T db pg_isready -U <POSTGRES_USER>   # wait until ready
docker compose cp dailyreport.dump db:/dailyreport.dump
docker compose exec -T db pg_restore -U <POSTGRES_USER> -d <POSTGRES_DB> --clean --if-exists /dailyreport.dump
```

## Phase 7 — bring up the full stack

```bash
make up                          # builds bot image, starts db + bot + cloudflared
docker compose ps                # all 3 should be Up/healthy
docker compose logs -f bot       # watch for startup errors, Ctrl+C when satisfied
```

`bootstrap_schema` runs automatically on bot startup and is idempotent, so
it's safe to run against the restored database.

## Phase 8 — point the webhook (only if you created a new tunnel)

```bash
make set-webhook
```

Skip this if you reused the same tunnel/hostname — Telegram's webhook URL
hasn't changed, only which machine answers it.

## Phase 9 — verify end-to-end

- Send `/start` to the bot in Telegram, confirm it replies.
- `docker compose logs -f bot` on the VPS should show the update coming in.
- Submit one test report through the full flow.

## Phase 10 — decommission local

Once the VPS is confirmed working — especially if you reused the same tunnel
token, since two live connectors racing to handle the same webhook causes
confusing double-processing:

```bash
# on your local machine
docker compose down
```

Keep the local `pgdata` volume/dump around for a few days as a safety net
before deleting anything.

## Follow-up: backups

Once live on the VPS, there's no backup story for the database sitting on a
single disk. Set up a daily `pg_dump` cron job on the VPS and copy the
dump off-box (e.g. `scp` to your local machine or a storage bucket).
