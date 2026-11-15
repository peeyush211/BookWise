# Deployment guide

[Back to the README](../README.md)

## Deploy on Render's free options

The recommended production layout is:

```text
Render Static Site  →  Render Web Service  →  PostgreSQL database
        frontend             Flask API              persistent data
```

Do not deploy the production app with SQLite. Render web-service filesystems
are not a safe place for permanent user accounts, ratings, or shelves. Use a
PostgreSQL connection string for deployed data.

Render's free web services spin down after 15 minutes without traffic, so the
first request after inactivity can be slow. This is suitable for a demo,
portfolio project, or class submission, not latency-sensitive production
traffic.

### A. Create the backend Web Service

1. Push the project to GitHub.
2. In Render, choose **New → Web Service** and connect the repository.
3. Use these settings:

| Setting | Value |
|---|---|
| Root Directory | Leave blank |
| Runtime | Python 3 |
| Build Command | `pip install -r requirements.lock` |
| Start Command | `gunicorn --bind 0.0.0.0:$PORT --workers 1 --timeout 120 backend.wsgi:app` |
| Health Check Path | `/api/health` |

4. Add these environment variables:

```text
APP_ENV=production
SECRET_KEY=<generate-a-long-random-secret>
DATABASE_URL=<your-PostgreSQL-connection-string>
AUTH_TOKEN_MAX_AGE=86400
AUTH_COOKIE_SECURE=true
CORS_ORIGINS=https://bookwise-frontend-bz3e.onrender.com
```

Do not hard-code `PORT`; Render supplies it at runtime. The application binds
to `0.0.0.0:$PORT` so Render can route traffic to it.

5. Deploy and verify:

```text
https://<your-backend>.onrender.com/api/health
```

Production web workers do not initialize the database. Before serving traffic,
run `python -m backend.migrate` in an environment with the production
`DATABASE_URL` and `APP_ENV=production`. This creates the schema and synchronizes
the catalogue from `data/processed/books_clean.csv`. Run it again after schema
changes, with a database backup in place.

### B. Create the database

Create a PostgreSQL database in Render if a suitable free database is available
for your account, then copy its internal connection string into the backend's
`DATABASE_URL` environment variable. For real user data, use a database plan
with persistence and backups. Render's free Postgres offering has an expiry
period, so it should not be treated as permanent production storage.

### C. Create the frontend Static Site

1. Choose **New → Static Site** in Render and connect the same repository.
2. Use these settings:

| Setting | Value |
|---|---|
| Root Directory | `frontend` |
| Build Command | `npm ci && npm run build` |
| Publish Directory | `dist` |

3. Add this build environment variable:

```text
VITE_API_BASE_URL=https://<your-backend>.onrender.com/api
```

4. Deploy the static site.
5. Copy the final frontend URL and update the backend's `CORS_ORIGINS` to the
   exact HTTPS origin, for example:

```text
CORS_ORIGINS=https://bookwise-frontend-bz3e.onrender.com
```

6. Redeploy the backend after changing `CORS_ORIGINS`.

### D. Verify the deployed application

Check the API first:

```text
https://<your-backend>.onrender.com/api/health
```

Then open the frontend URL and test this order:

1. Register a new account.
2. Refresh the page and confirm the session is restored.
3. Open **For You** and confirm recommendations load.
4. Open **Reading Room** and create a shelf.
5. Rate a book, add it to a shelf, and reopen it after refresh.
6. Check browser DevTools for failed `/api/` requests.

If the frontend shows CORS errors, check that `CORS_ORIGINS` contains the exact
frontend origin with no trailing slash. If it shows 404 errors for discovery or
reader tools, verify that the frontend `VITE_API_BASE_URL` points to the current
backend URL and that the backend was redeployed from the same commit.

## Optional Docker deployment

The included Dockerfile is compatible with a platform-provided `PORT`:

```powershell
docker build -t bookwise-api .
docker run --rm -p 8000:10000 -e PORT=10000 bookwise-api
```

For Render, the native Python Web Service configuration above is simpler. Use
the Docker runtime only if you specifically want container-based deployment.

## Security and production notes

- Use a unique random `SECRET_KEY` in production.
- Never commit `.env`, database files, credentials, or API tokens.
- Use PostgreSQL for deployed accounts and reader data.
- Keep `AUTH_COOKIE_SECURE=true` when using HTTPS.
- Set `CORS_ORIGINS` to only the real frontend origin(s).
- Back up production data before schema changes.
- The app includes validation and rate limits, but it does not include a full
  moderation/admin workflow for public comments and reviews.
