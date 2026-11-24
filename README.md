# Inventra

Receipt-based grocery spending and next-trip planning for Manaus. The agreed product scope is in [RFC 001](docs/RFC-001-manaus-receipt-assistant.md).

## Project layout

| Directory | Purpose |
| --- | --- |
| `inventra-web/` | Next.js interface: private dashboard, receipt import, list planning, sharing settings, and public product-price pages. |
| `inventra-api/` | Flask/PostgreSQL API: SEFAZ-AM NFC-e import, monthly totals, replenishment, sharing, and price comparisons. |
| `inventra-collector/` | Existing Kafka-based receipt collector. It remains separate from the web/API prototype. |

## Run the local prototype

Requires Python 3.12+, [uv](https://docs.astral.sh/uv/), Node.js 20.9+, and Docker Compose.

Start PostgreSQL and apply schema migrations:

```bash
make setup
```

Terminal 1:

```bash
cd inventra-api
uv run python app.py
```

Terminal 2:

```bash
cd inventra-web
npm install
npm run dev
```

Open <http://127.0.0.1:3000> on the computer, or `http://<YOUR_LAN_IP>:3000` on a phone connected to the same Wi-Fi. `npm run dev` uses Next.js's default network binding. The web app forwards `/api/*` to the API at `127.0.0.1:5000`. To try receipt import without personal data, upload `inventra-collector/mock-pages/page-mock.html` in **Adicionar nota**.

For phone development, set `INVENTRA_DEV_ORIGIN` in `inventra-web/.env` to your computer's LAN IP (no `http://` or port). Copy `inventra-web/.env.example` if the file does not exist. The local `.env` file is ignored by Git.

On a phone, **Escanear QR com a câmera** opens the camera to photograph the NFC-e QR code. The page decodes the image locally and fills the SEFAZ link; then tap **Conferir nota**. This photo capture approach works on the local HTTP address, where browsers do not allow a continuous camera stream. On some phones the button may open a camera/gallery chooser.

If QR capture fails, the browser logs the decoding attempts and sends the failed photo to the local API. The API saves the image and a JSON report in `inventra-api/instance/qr-debug/` (ignored by Git), logs the report ID and reason, and shows the ID on the phone. The JSON report records the failure stage and attempted image sizes without storing the decoded URL. Set `QR_DEBUG_DIR` to change the local directory; remove old reports when debugging is complete. A successfully decoded image stays on the phone.

This prototype has no login, so use a trusted network while it is running.

The API connects through `DATABASE_URL` (default: `postgresql://inventra:inventra@127.0.0.1:5432/inventra`). PostgreSQL data lives in the `postgres_data` Docker volume. The old SQLite file is not deleted. To transfer existing receipts, run `uv run python import_sqlite.py instance/receipts.sqlite3` from `inventra-api/` after starting PostgreSQL. The importer skips receipts already transferred, so it can be rerun.

From the repository root, use `make api` and `make web` in separate terminals. `make migrate` applies pending schema changes, `make db-stop` stops PostgreSQL, and `make import-sqlite` transfers the default old SQLite file. Set `SQLITE_FILE=/path/to/receipts.sqlite3` to import a different file. Use `make help` to list commands.

## Checks

```bash
cd inventra-api && uv run pytest -q
cd ../inventra-collector && uv run pytest -q
cd ../inventra-web && npm run build
```

## Current limits

This is a single-user local prototype. It is not ready for public deployment: account isolation, production security/privacy controls, item correction, category reports, and product/branch matching remain to be built. A QR link can import a SEFAZ-AM page; a 44-digit key alone may require the user to open the official page through CAPTCHA and upload the saved HTML. The existing Kafka collector is not yet connected to the Flask API. Price plans use observations from the last 30 days and exclude travel cost.

