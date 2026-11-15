# Deployment guide

[Back to the README](../README.md)

## Hosting

The frontend runs on a Render Static Site. The Flask backend runs on AWS EC2.
Database configuration is supplied through `DATABASE_URL`; no database hosting
provider is assumed here.

## Backend on AWS EC2

Install dependencies from the project root:

```sh
pip install -r requirements.lock
```

Configure these environment variables on the backend:

```text
APP_ENV=production
SECRET_KEY=<generate-a-long-random-secret>
DATABASE_URL=<your-database-connection-string>
AUTH_TOKEN_MAX_AGE=86400
AUTH_COOKIE_SECURE=true
CORS_ORIGINS=https://bookwise-frontend-bz3e.onrender.com
```

Before serving traffic, initialize or update the database:

```sh
python -m backend.migrate
```

Production web workers do not initialize the database. The migration command
creates the schema and synchronizes the catalogue from
`data/processed/books_clean.csv`. Back up existing data before schema changes.

The application's Gunicorn entry point is `backend.wsgi:app`. Use your EC2
process configuration to run it, and expose the API through an HTTPS endpoint.
The backend domain and instance process configuration are deployment-specific.

## Frontend on Render

1. Choose **New → Static Site** in Render and connect the same repository.
2. Use these settings:

| Setting | Value |
|---|---|
| Root Directory | `frontend` |
| Build Command | `npm ci && npm run build` |
| Publish Directory | `dist` |

3. Add this build environment variable:

```text
VITE_API_BASE_URL=https://<your-backend-domain>/api
```

4. Deploy the static site.
5. Copy the final frontend URL and update the backend's `CORS_ORIGINS` to the
   exact HTTPS origin, for example:

```text
CORS_ORIGINS=https://bookwise-frontend-bz3e.onrender.com
```

6. Redeploy the backend after changing `CORS_ORIGINS`.

## Verify the deployed application

Check the API first:

```text
https://<your-backend-domain>/api/health
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

Docker is optional; use it only if your EC2 deployment runs the API in a container.

## Security and production notes

- Use a unique random `SECRET_KEY` in production.
- Never commit `.env`, database files, credentials, or API tokens.
- Use PostgreSQL for deployed accounts and reader data.
- Keep `AUTH_COOKIE_SECURE=true` when using HTTPS.
- Set `CORS_ORIGINS` to only the real frontend origin(s).
- Back up production data before schema changes.
- The app includes validation and rate limits, but it does not include a full
  moderation/admin workflow for public comments and reviews.
