import os

from django.db.models.signals import post_migrate
from django.db.utils import OperationalError, ProgrammingError
from django.dispatch import receiver

SOCIAL_PROVIDERS = (
    ("github", "GitHub", "GITHUB_CLIENT_ID", "GITHUB_CLIENT_SECRET"),
    ("facebook", "Meta", "FACEBOOK_CLIENT_ID", "FACEBOOK_CLIENT_SECRET"),
    ("twitter_oauth2", "X", "X_CLIENT_ID", "X_CLIENT_SECRET"),
)


@receiver(post_migrate)
def configure_site_and_social(sender, **kwargs):
    if getattr(sender, "label", "") != "socialaccount":
        return
    try:
        ensure_site()
        ensure_social_apps()
    except (OperationalError, ProgrammingError):
        return


def ensure_site():
    from django.contrib.sites.models import Site

    Site.objects.update_or_create(
        id=1,
        defaults={"domain": "localhost:8000", "name": "Hushållskalkyl"},
    )


def ensure_social_apps():
    from allauth.socialaccount.models import SocialApp
    from django.contrib.sites.models import Site

    site = Site.objects.get(id=1)
    for provider, name, id_key, secret_key in SOCIAL_PROVIDERS:
        client_id = os.environ.get(id_key, "").strip()
        secret = os.environ.get(secret_key, "").strip()
        if not client_id or not secret:
            continue
        app = SocialApp.objects.filter(provider=provider).first()
        if app is None:
            app = SocialApp(provider=provider)
        app.name = name
        app.client_id = client_id
        app.secret = secret
        app.save()
        app.sites.add(site)
