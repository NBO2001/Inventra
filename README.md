# Inventra

Receipt-based grocery spending and next-trip planning for Manaus. The agreed product scope is in [RFC 001](docs/RFC-001-manaus-receipt-assistant.md).

## Project layout

| Directory | Purpose |
| --- | --- |
| `inventra-web/` | Next.js interface: private dashboard, receipt import, list planning, sharing settings, and public product-price pages. |
| `inventra-api/` | Flask/SQLite API: SEFAZ-AM NFC-e import, monthly totals, replenishment, sharing, and price comparisons. |
| `inventra-collector/` | Existing Kafka-based receipt collector. It remains separate from the web/API prototype. |

## Run the local prototype

Requires Python 3.12+, [uv](https://docs.astral.sh/uv/), and Node.js 20.9+.

Terminal 1:

```bash
cd inventra-api
uv sync
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

This prototype has no login, so use a trusted network while it is running.

The API stores local data at `inventra-api/instance/receipts.sqlite3`, which is ignored by Git. The private receipts supplied in the earlier workspace were **not** copied into this repository.

## Checks

```bash
cd inventra-api && uv run pytest -q
cd ../inventra-collector && uv run pytest -q
cd ../inventra-web && npm run build
```

## Current limits

This is a single-user local prototype. It is not ready for public deployment: account isolation, production security/privacy controls, item correction, category reports, and product/branch matching remain to be built. A QR link can import a SEFAZ-AM page; a 44-digit key alone may require the user to open the official page through CAPTCHA and upload the saved HTML. The existing Kafka collector is not yet connected to the Flask API. Price plans use observations from the last 30 days and exclude travel cost.

