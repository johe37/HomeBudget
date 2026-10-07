# Hushållskalkyl

A small Django app for a monthly household budget.

You log in and save a named monthly budget. Make several and compare them in the list. Income is entered first. A car is an ordinary cost. Mortgage interest and amortization are calculated.

Login is an account on this app. GitHub, Meta and X show up on the login page once their OAuth keys are set.

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Open http://localhost:8000/ and create an account. Each budget has its own name, so two budgets can describe the same calendar month. A new budget starts empty, on Indata. Månad and Översikt are separate pages for the saved result. The fields are what you type, income first. Amounts group thousands with a space as you type. Write a car under costs. Mortgage interest and amortization are calculated and added when you save. Copy names the new budget automatically, and the name can be changed afterwards. The list exports and imports budgets as a semicolon-separated UTF-8 csv. Mortgage interest and amortization are calculated again on import.

Money is rounded to öre. A person is whatever you write on a row. The mortgage is not assigned to anyone.

## Docker

Copy `.env.example` to `.env` and set `DJANGO_SECRET_KEY` to a long random value. The container refuses `change-me`.

```bash
docker compose up -d --build
```

Open http://localhost:8000/. The sqlite database stays in the `homebudget-data` volume. `docker compose down` stops the app and keeps the database.

GitHub Actions builds `linux/amd64` and `linux/arm64` on every push and pull request. Pushing a git tag publishes `johe37/homebudget:<tag>` and `:latest` to Docker Hub. Add a `DOCKERHUB_TOKEN` repository secret (a Docker Hub access token for `johe37`). The compose file uses that image name and builds it from this directory when it is missing.

Behind a reverse proxy, set `DJANGO_BEHIND_PROXY=1`, `DJANGO_ACCOUNT_PROTOCOL=https`, `DJANGO_SITE_DOMAIN` to the public host, and `DJANGO_CSRF_TRUSTED_ORIGINS` to the public origin, for example `https://budget.example.com`, in `.env`. OAuth keys are the same variables as in `.env.example`.

## Social login

Copy `.env.example` to `.env`, fill one or more providers, export the variables, then run `migrate` again.

Callback URLs for a local server:

- GitHub: `http://localhost:8000/accounts/github/login/callback/`
- Meta (Facebook): `http://localhost:8000/accounts/facebook/login/callback/`
- X: `http://localhost:8000/accounts/twitter_oauth2/login/callback/`

`python manage.py createsuperuser` opens Django admin at `/admin/` if you would rather attach the OAuth apps by hand.
