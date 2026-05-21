# AW Client Report Portal — FastAPI Backend

Backend for the Windbrook Solutions client report portal.  
Accepts client profiles and quarterly balances, runs all SACS/TCC calculations, and generates polished PDF reports.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Health check |
| GET | `/clients` | List all clients (dashboard view) |
| POST | `/clients` | Create client with accounts |
| GET | `/clients/{id}` | Full client detail |
| PUT | `/clients/{id}` | Update client + replace accounts |
| DELETE | `/clients/{id}` | Delete client |
| GET | `/clients/{id}/reports` | Report history for a client |
| POST | `/reports` | Create report → runs all calculations |
| GET | `/reports/{id}` | Get report + calculations |
| DELETE | `/reports/{id}` | Delete report |
| GET | `/reports/{id}/pdf/sacs` | Download SACS PDF |
| GET | `/reports/{id}/pdf/tcc` | Download TCC PDF |

Interactive docs available at `/docs` (Swagger UI) and `/redoc`.

---

## Calculation Rules

All rules sourced directly from the client meeting transcript:

```
# SACS
excess                    = inflow – outflow
private_reserve_target    = client.private_reserve_target  OR  6 × monthly_expense_budget

# TCC
client1_retirement_total  = sum of client1 retirement account balances
client2_retirement_total  = sum of client2 retirement account balances
non_retirement_total      = sum of non_retirement balances  ← does NOT include trust
grand_total               = c1_retirement + c2_retirement + non_retirement + trust
liabilities_total         = sum of liability balances       ← NOT subtracted from net worth
```

---

## Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run dev server (auto-reload)
uvicorn main:app --reload --port 8000

# API docs
open http://localhost:8000/docs
```

---

## Deploying to Railway

### One-click deploy

1. Push this folder to a GitHub repo.
2. In Railway → **New Project** → **Deploy from GitHub repo** → select the repo.
3. Railway auto-detects `railway.toml` and runs `uvicorn main:app --host 0.0.0.0 --port $PORT`.

### Persistent SQLite (required for production)

By default Railway's filesystem is **ephemeral** — the DB is wiped on every redeploy.

To persist data:

1. Railway Dashboard → your service → **Volumes** → **Add Volume**
2. Mount path: `/data`
3. Set env var: `DATABASE_URL=sqlite:////data/portal.db`

### Environment Variables

| Variable | Default | Notes |
|----------|---------|-------|
| `DATABASE_URL` | `sqlite:///./portal.db` | Set to `/data/portal.db` with volume |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins for production |
| `PORT` | Set by Railway | Do not set manually |

---

## Project Structure

```
portal/
├── main.py           # FastAPI app + all routes
├── models.py         # SQLAlchemy ORM models
├── schemas.py        # Pydantic schemas (mirrors TypeScript interfaces)
├── database.py       # DB engine + session factory
├── calculations.py   # Pure calculation functions (SACS + TCC math)
├── pdf_sacs.py       # ReportLab SACS PDF generator (2-page cashflow diagram)
├── pdf_tcc.py        # ReportLab TCC PDF generator (net worth circle chart)
├── requirements.txt
├── railway.toml      # Railway deployment config
├── Procfile          # Fallback start command
└── .env.example      # Environment variable template
```

---

## Known Gaps / V2 Notes

- **No authentication** — add API key middleware or OAuth before sharing the URL externally.
- **Canva export** — PRD lists this as a nice-to-have. Requires `CANVA_API_KEY` env var and a separate endpoint.
- **Dropbox auto-save** — discussed but not confirmed. Can be added as a post-PDF-generation webhook.
- **RightCapital / Schwab / Zillow integrations** — explicitly deferred to V2 per Rebecca and Maryann.
- **TCC layout** — the bubble chart uses a grid layout. For clients with 6+ accounts per spouse, consider switching to a landscape page.
