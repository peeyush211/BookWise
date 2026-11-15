# BookWise

BookWise is a full-stack book discovery and recommendation app built with a
React/Vite frontend and a Flask API. It combines catalogue search, popularity
ranking, TF-IDF content similarity, SVD collaborative filtering, a hybrid
recommender, private reader tools, ratings, shelves, and shareable lists.

**Live demo:** [bookwise-frontend-bz3e.onrender.com](https://bookwise-frontend-bz3e.onrender.com)

## Features

- Search 10,000 Goodbooks catalogue titles by title, author, keyword, or genre.
- Popular, hidden-gem, similar-book, and personalized recommendation feeds.
- Hybrid recommendation engine using popularity, content similarity, and SVD.
- A personalized **For You** feed with preference controls, feedback events,
  experiments, explanations, and reader-specific ranking signals.
- User accounts with secure password hashes and HttpOnly authentication cookies.
- Ratings, favorites, reading status, progress tracking, notes, reviews, comments,
  followed authors, custom shelves, private lists, and public share links.
- A Reading Room workspace for progress, notes, reviews, comments, shelves,
  followed authors, private lists, and shareable public list links.
- ML Dashboard model comparisons and offline evaluation metrics.
- ML Insights with ranking charts, genre prediction, K-Means reading clusters,
  and explanations for cluster-aware personalization.
- Responsive warm-ivory/gold interface with light and dark themes.

## Technology

| Layer | Technology |
|---|---|
| Frontend | React 19, Vite 8, Tailwind CSS 4, Lucide React |
| Backend | Python 3.12, Flask 3, SQLAlchemy 2 |
| Recommendation models | Popularity, TF-IDF content-based, Truncated SVD, hybrid ensemble |
| Database | SQLite for local development; PostgreSQL for persistent deployment |
| Testing | Python unittest, Vitest, Testing Library, Oxlint |
| API server | Gunicorn serving Flask via WSGI |
| Hosting | Render Static Site (frontend) + AWS EC2 (backend API) |
| Production data | PostgreSQL via `DATABASE_URL` (provider configured at deployment) |

The app does not depend on a third-party recommendation, authentication, or
reader-data SaaS. Recommendation models, authentication, reader tools, and API
routes are implemented in this repository. Render hosts the frontend, and
AWS EC2 hosts the backend. Database configuration comes from `DATABASE_URL`.

## Project structure

```text
Book Recomendation/
├── backend/
│   ├── app.py                 # Flask app factory and health endpoint
│   ├── auth.py                # Token/cookie authentication helpers
│   ├── config.py              # Environment-backed configuration
│   ├── database.py            # SQLAlchemy engine, schema creation, catalog seed
│   ├── models/                # SQLAlchemy models
│   ├── recommender/           # Recommendation algorithms and ranking logic
│   ├── routes/                # Books, users, reader, and discovery APIs
│   ├── tests/                 # Backend tests
│   └── wsgi.py                # Gunicorn entry point
├── frontend/
│   ├── src/
│   │   ├── components/        # Shared UI components
│   │   ├── pages/             # Main application pages
│   │   ├── services/          # API clients and configurable API base URL
│   │   └── test/              # Frontend tests
│   ├── package.json
│   └── vite.config.js
├── data/
│   ├── processed/             # Seed catalogue and processed ratings
│   └── raw/                   # Original dataset files
├── artifacts/                 # Evaluation and model artifacts
├── scripts/                   # Smoke tests, evaluation, and validation helpers
├── Dockerfile
├── requirements.lock
└── README.md
```

## Important configuration rule

The Vite development proxy and the Flask server must point to the same backend.
The project uses port `8000` locally by default:

```text
Frontend: http://127.0.0.1:5173
Backend:  http://127.0.0.1:8000
```

Do not commit `.env`. It is ignored by Git. Create it from `.env.example` and
replace the development secret with a strong private value.

## Local setup on Windows

Open PowerShell in the project root.

### 1. Create and activate the Python environment

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.lock
```

If PowerShell blocks activation, run this once in the same PowerShell window:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

### 2. Create local environment variables

```powershell
Copy-Item .env.example .env
```

The local `.env` should contain at least:

```dotenv
APP_ENV=development
SECRET_KEY=replace-with-a-long-random-local-secret
DATABASE_URL=sqlite:///backend/bookwise.db
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
AUTH_TOKEN_MAX_AGE=86400
PORT=8000
```

If an old shell-level `PORT=5000` overrides `.env`, clear it before starting:

```powershell
Remove-Item Env:PORT -ErrorAction SilentlyContinue
```

### 3. Initialize the database and start the backend

```powershell
python -m backend.migrate
python -m backend.app
```

The API should print:

```text
Running on http://127.0.0.1:8000
```

Verify it in a second PowerShell window:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

### 4. Install and start the frontend

```powershell
Set-Location frontend
npm ci
npm run dev
```

Open <http://127.0.0.1:5173>.

The frontend uses `/api` locally through the Vite proxy. For a separately
hosted frontend, set `VITE_API_BASE_URL` to the complete backend API base,
including `/api`, for example:

```dotenv
VITE_API_BASE_URL=https://<your-backend-domain>/api
```

## API overview

Public endpoints:

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | Service and database health |
| GET | `/api/books` | Search and paginate the catalogue |
| GET | `/api/books/<id>` | Book details |
| GET | `/api/books/<id>/similar` | Similar-book recommendations |
| GET | `/api/recommendations/popular` | Popular and hidden-gem shelves |
| GET | `/api/evaluation/metrics` | Offline model metrics |
| POST | `/api/evaluation/genre-predict` | Predict book genres from metadata |
| GET | `/api/evaluation/clusters` | Aggregate application reading clusters |
| GET | `/api/users/<id>/cluster` | Current reader's K-Means taste cluster |
| GET | `/api/reader/shared/<token>` | Public published-list payload |

Authentication endpoints:

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/auth/register` | Create an account |
| POST | `/api/auth/login` | Sign in by username or email |
| GET | `/api/auth/me` | Restore the current session |
| POST | `/api/auth/logout` | Clear the authentication cookie |

Private discovery and reader endpoints include:

- `/api/discovery/preferences`
- `/api/discovery/feed`
- `/api/discovery/events`
- `/api/discovery/experiments`
- `/api/reader/books/<id>/...`
- `/api/reader/shelves`
- `/api/reader/progress`
- `/api/reader/authors`
- `/api/reader/lists`

Private requests use the HttpOnly cookie issued by login/register. The browser
client also keeps a bearer token in memory as a fallback; it is not stored in
localStorage.

## Tests and checks

From the project root:

```powershell
python -m unittest discover -s backend/tests -p "test_*.py" -v
python -m compileall -q backend scripts
```

From `frontend/`:

```powershell
npm test
npm run lint
npm run build
```

Run the disposable browser-QA backend without touching the real database:

```powershell
# Terminal 1, from the project root
python -m scripts.smoke_server --port 8019 --frontend-port 5190

# Terminal 2, from frontend/
$env:VITE_API_PROXY_TARGET="http://127.0.0.1:8019"
npm run dev -- --host 127.0.0.1 --port 5190 --strictPort
```

## Deployment

Try the [live demo](https://bookwise-frontend-bz3e.onrender.com).
The hosting layout uses a Render Static Site for the React frontend and a
AWS EC2 instance for the Flask API. PostgreSQL is recommended for persistent
deployed data; the database provider is configured through `DATABASE_URL`.

See the [deployment guide](docs/DEPLOYMENT.md) for frontend and backend configuration,
database initialization, troubleshooting, deployment checks, and optional Docker setup.

## Security notes

- Keep `.env`, credentials, tokens, database files, and `node_modules` out of Git.
- Use a unique production `SECRET_KEY`, HTTPS cookies, and the exact frontend CORS origin.
- Use persistent database storage and back it up before schema changes.

## License and dataset note

This project uses the Goodbooks-10k dataset for development and academic
recommendation experiments. Check the dataset's own licensing and attribution
requirements before redistributing the data or deploying it commercially.
