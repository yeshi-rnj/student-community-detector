# Deploying

The bundle includes the web page (`templates/` and `static/`).

## Docker
```bash
docker build -t community-detector .
docker run -p 8000:8000 -e APP_PASSWORD=change-me community-detector
```
Open http://localhost:8000. Health check: `/healthz`.

## Render / Railway / Heroku-style platforms
Use the included `Procfile` (`gunicorn -c gunicorn.conf.py app:app`), or point the platform at the Dockerfile. Set:

| Variable | Purpose |
|---|---|
| `PORT` | Set automatically by most platforms |
| `APP_PASSWORD` | Optional login (user `admin`, or set `APP_USER`). Leave unset for a public demo; set it to restrict access |
| `TRUST_PROXY=1` | Needed behind a platform load balancer so the host/https checks work |

## Things to know
- **One worker only.** Students live in process memory, so `gunicorn.conf.py` uses 1 worker with 8 threads. More workers would each hold a different copy of the data.
- **Data resets on every restart or redeploy.** Export a CSV first. For persistence, move storage to SQLite/Postgres.
- Serve over HTTPS (the platform or a reverse proxy normally does this); Basic auth sends the password in every request.
- Local development is unchanged: `python app.py` (add `FLASK_DEBUG=1` for debug mode; never in production).
