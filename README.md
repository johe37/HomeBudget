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

Open http://localhost:8000/ and create an account. Each budget has its own name, so two budgets can describe the same calendar month. A new budget starts empty, on Indata. Månad and Översikt are separate pages for the saved result. Yellow fields are what you type, income first. Amounts group thousands with a space as you type. Write a car under costs. Mortgage interest and amortization are calculated and added when you save. Copy names the new budget automatically, and the name can be changed afterwards.

Money is rounded to öre. A person is whatever you write on a row. The mortgage is not assigned to anyone.

## Social login

Copy `.env.example` to `.env`, fill one or more providers, export the variables, then run `migrate` again.

Callback URLs for a local server:

- GitHub: `http://localhost:8000/accounts/github/login/callback/`
- Meta (Facebook): `http://localhost:8000/accounts/facebook/login/callback/`
- X: `http://localhost:8000/accounts/twitter_oauth2/login/callback/`

`python manage.py createsuperuser` opens Django admin at `/admin/` if you would rather attach the OAuth apps by hand.
