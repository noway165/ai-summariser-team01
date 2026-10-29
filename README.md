# AI Summariser — Lab 5 example (72ITDS30103)

A one-page web app: paste a text, click **Summarise**, get a three-sentence summary from
Google Gemini. The browser calls only this server (`POST /api/summarise`); the server calls
Gemini with a key read from the environment. No database.

| File | What it does |
|------|--------------|
| `app/main.py` | `/` (the page), `/health`, `POST /api/summarise` → 200 summary or 503 friendly message |
| `app/ai.py` | The only file that knows the AI provider: retries 429, never retries 4xx, 15 s timeout |
| `app/ui.html` | The page. Uses `textContent`, never `innerHTML` |
| `tests/` | 12 tests; the AI provider is faked, so no key is needed |
| `Dockerfile` | Reads `PORT` (Render sets it) and binds `0.0.0.0` |
| `.github/workflows/ci.yml` | Lint and test on every push and pull request |
| `extras/node/` | `ai.js` + tests for Node.js teams who want to add AI to their own project |

## Run it on your laptop (optional)

    cp .env.example .env              # then put your key after GEMINI_API_KEY=
    podman build -t ai-summariser .
    podman run --rm -p 8000:8000 --env-file .env ai-summariser
    # open http://localhost:8000

## Deploy it

Follow Option B of the Lab 5 handout: a GitHub repository, a Render web service
(Docker, Free, Health Check Path `/health`) and one environment variable, `GEMINI_API_KEY`.

Never commit `.env`. It is already listed in `.gitignore` and `.dockerignore`.
