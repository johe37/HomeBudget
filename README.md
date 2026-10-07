# Hushållskalkyl

A small Django app for a monthly household budget.

You log in, write one month and save it. The next month is a new plan. The mortgage and the cars are two separate calculations.

Login is an account on this app. GitHub, Meta and X show up on the login page once their OAuth keys are set.

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Open http://localhost:8000/ and create an account. A new month starts empty. Yellow fields are what you type. Mortgage interest and amortization are one calculation. Each car's loan, insurance and fuel are another. Both are added to the month when you save.

Money is rounded to öre. A new household is one person, Person 1, plus the shared name Gemensam. Add another person under Hushåll if you share the home. Calculated rows follow the names. Rows you typed keep the name they were saved with.

## Social login

Copy `.env.example` to `.env`, fill one or more providers, export the variables, then run `migrate` again.

Callback URLs for a local server:

- GitHub: `http://localhost:8000/accounts/github/login/callback/`
- Meta (Facebook): `http://localhost:8000/accounts/facebook/login/callback/`
- X: `http://localhost:8000/accounts/twitter_oauth2/login/callback/`

`python manage.py createsuperuser` opens Django admin at `/admin/` if you would rather attach the OAuth apps by hand.
