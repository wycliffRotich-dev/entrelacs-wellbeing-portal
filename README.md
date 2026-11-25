# Employee and HR Wellbeing Portal

A small full-stack application for the Entrelacs exercise. Employees complete a three-question wellbeing check-in. HR users see aggregate results for their own organization. The assessment is fictional and has no clinical or diagnostic meaning. All data is synthetic.

Stack: React 19 with strict TypeScript (Vite, Vitest), Python 3.12 with FastAPI, PostgreSQL 16. In Docker Compose, nginx serves the frontend and proxies `/api` to the backend.

## Quick start

You need Docker with Compose v2 and `openssl`.

```bash
git clone https://github.com/wycliffRotich-dev/entrelacs-wellbeing-portal.git
cd entrelacs-wellbeing-portal
bash scripts/gen-secrets.sh
APP_UID=$(id -u) APP_GID=$(id -g) docker compose up --build
```

Open http://localhost:8080 once the `frontend` container is running. The first start applies the database schema, then a one-shot `seed` service loads the synthetic data and prints the accounts.

- Stop with Ctrl+C. Reset everything, including the database, with `docker compose down -v`.
- Ports are bound to `127.0.0.1` only: the app on 8080 (`APP_PORT`) and Postgres on 5433 (`POSTGRES_HOST_PORT`).
- `scripts/gen-secrets.sh` creates the database password and the token signing key under `secrets/`. It never overwrites a file and never prints a value. `secrets/` is ignored by git.

## Demo accounts

The password for every account is `demo-password-123`. It is a local-only demonstration credential for synthetic accounts, not a real secret.

| Organization | Role | Sign in as | Team |
|---|---|---|---|
| Northwind Health | HR | `hr@northwind.example.test` | all teams |
| Northwind Health | Employee | `maya`, `noah`, `priya`, `liam`, `zoe`, `omar`, `hana` at `northwind.example.test` | Platform |
| Northwind Health | Employee | `ivan`, `lena`, `tariq`, `sara` at `northwind.example.test` | Support |
| Northwind Health | Employee | `kofi`, `mei`, `paul` at `northwind.example.test` | Design |
| Northwind Health | none | no employees | Ops |
| Contoso Labs | HR | `hr@contoso.example.test` | all teams |
| Contoso Labs | Employee | `amir`, `bea`, `chen`, `dara`, `eli`, `fay` at `contoso.example.test` | Engineering |
| Contoso Labs | Employee | `gus`, `hugo`, `ines` at `contoso.example.test` | Sales |

The seed data covers every case in the aggregation rules:

- Northwind Platform has exactly five respondents, so its average is shown. One employee has a repeat check-in in the month, one has a September submission that must not count, one has only a draft, and one has nothing.
- Northwind Support has three respondents, so its average is withheld.
- Northwind Design has no respondents in the month. One person has a draft and one has a November submission.
- Northwind Ops has no eligible employees.
- The Northwind organization view has 8 respondents out of 14 eligible employees (57.1%), with an average of 68.3.
- Contoso Engineering has six respondents, and Contoso Sales has two respondents and one draft.

## Reporting month

The HR dashboard uses one fixed reporting month: **October 2026**, from 2026-10-01 to the end of 2026-10-31 UTC. It is set by `reporting_month_start` in `backend/app/config.py`, and the dashboard shows it. There is no month selector.

## Behavior

Employees answer three questions from 0 to 10: how connected they feel to the people around them, how supported they feel at work, and how manageable their workload feels. Higher is more positive. An employee can save an incomplete draft, resume it after a refresh or a new sign-in, submit it, and see the submitted answers and score. Submitted check-ins cannot be edited. The employee can then start a new check-in, and the latest submitted one in the month is the one that counts.

The score is the mean of the three answers, multiplied by 10 and rounded to one decimal place. The server calculates it and validates the answers.

HR users see the organization overview and can filter by team:

- Each employee counts once, using their most recent submitted check-in in the reporting month. Drafts do not count.
- Participation is respondents divided by eligible employees. It shows "No eligible employees" when the denominator is zero.
- With fewer than five respondents, the API withholds the average and the page shows "Insufficient responses". Respondent counts and participation are still shown.
- HR responses contain no individual answers, individual scores or employee identifiers.

## API

| Method and path | Role | Purpose |
|---|---|---|
| `POST /api/auth/login` | none | exchange email and password for a token |
| `GET /api/auth/me` | any | the signed-in user |
| `GET /api/employee/check-ins/current` | employee | current draft and latest submitted check-in |
| `PUT /api/employee/check-ins/draft` | employee | save a draft, partial answers allowed |
| `POST /api/employee/check-ins/{id}/submit` | employee | submit a complete draft |
| `GET /api/employee/check-ins/{id}` | employee | read one of your own check-ins |
| `GET /api/hr/wellbeing?team_id=` | HR | aggregate for the organization or one team |
| `GET /api/hr/teams` | HR | team list for the filter |

Every error uses one envelope: `{"error": {"code", "message"}}`. Validation errors (422, code `validation_error`) add `details`, a list of `{"field", "message"}` objects.

## How access is enforced

- Identity, role, organization and team are loaded from the database on every request. A token only names the user. No request parameter or body field can choose them.
- A `team_id` from another organization returns 404, so the response does not confirm that the team exists.
- A check-in is looked up by its owner, so another employee's id returns nothing, whoever asks.
- The database backs this up: composite foreign keys keep check-ins, teams and users inside one organization, and a trigger rejects any update or delete of a submitted check-in.
- Secrets are read from files. The app refuses to start if `DB_PASSWORD` or `JWT_SECRET` is set as a plain environment variable.

## Layout

- `backend/app/domain`: check-ins, scoring, aggregation and the privacy threshold, with no framework imports.
- `backend/app/application`: services and ports.
- `backend/app/infrastructure`: PostgreSQL repositories, password hashing, tokens.
- `backend/app/presentation`: FastAPI routes, schemas, error mapping.
- `frontend/src`: the API client, session handling, the employee screen and the HR dashboard.

## Tests

Backend, which needs Python 3.12 and the database container:

```bash
docker compose up -d db
python3 -m venv .venv && . .venv/bin/activate
pip install -r backend/requirements-dev.txt
cd backend
pytest
ruff check . && mypy app tests
```

- `pytest tests/unit` needs no database.
- The first run of the API and integration tests creates a `wellbeing_test` database in the same Postgres and loads the schema into it. The tests never touch the `wellbeing` demo database. After a schema change, run `docker compose exec db dropdb -U wellbeing wellbeing_test` once, and the next run rebuilds it.

Frontend, which needs Node 20 or newer:

```bash
cd frontend
npm ci
npm test
npm run typecheck
npm run build
```

The critical user journey is `frontend/src/journey.test.tsx`. An employee signs in, submits a check-in and sees the score, then HR signs in and sees only the aggregate.

## Decisions and assumptions

- **Fixed month.** October 2026, as described above.
- **Schema setup.** Postgres applies `schema.sql` the first time it starts on an empty volume. It does not re-run, so a schema change needs `docker compose down -v`. I chose this over a migration tool because the exercise has no change history to carry.
- **Secret files and the container user.** The secret files are mode `0600`. The backend containers run as your user id (`APP_UID`, `APP_GID`) so they can read them. They also run with a read-only filesystem and no extra capabilities.
- **Foreign team ids return 404.** This avoids confirming that another organization's team exists.
- **Eligibility.** All seeded employees are eligible and team membership is fixed, as the exercise states.
- **Sessions.** Tokens last 30 minutes. The browser keeps the token for the tab only. A rejected token returns the user to the sign-in form.
- **Duplicate submissions.** The interface sends one request at a time, and the database allows only one draft per employee and rejects a second submission of the same check-in.
