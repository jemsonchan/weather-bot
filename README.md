# weather-bot

Automated weather bots for both Malta and Roatan. Posts to X, LinkedIn and Nostr
on a schedule via GitHub Actions (`.github/workflows/weather_bot.yml`).

## Run behaviour

Each channel is attempted independently. The run fails (exit 1) only if **every**
channel failed — a single dead channel is reported as a workflow warning
annotation so the other posts still count as a success.

## LinkedIn tokens

LinkedIn access tokens expire after **60 days**. If the app is enrolled for
programmatic refresh, store the refresh token and the bot renews the access token
on every run automatically (refresh tokens last ~365 days).

Re-authorize with:

```bash
python linkedin_auth.py --account bcm    --client-id XXX --client-secret YYY
python linkedin_auth.py --account roatan --client-id XXX --client-secret YYY
```

Add `http://localhost:8080/callback` to the app's *Authorized redirect URLs*
(LinkedIn developer portal → your app → Auth) first. The script prints the
`gh secret set` commands to run.

## Secrets

| Secret | Notes |
| --- | --- |
| `OWM_API_KEY` | OpenWeatherMap |
| `BCM_X_API_KEY` / `_API_SECRET` / `_ACCESS_TOKEN` / `_ACCESS_SECRET` | X, Malta |
| `ROA_X_API_KEY` / `_API_SECRET` / `_ACCESS_TOKEN` / `_ACCESS_SECRET` | X, Roatan |
| `BCM_LI_ACCESS_TOKEN`, `BCM_LI_AUTHOR_URN` | LinkedIn, Malta |
| `ROA_LI_ACCESS_TOKEN`, `ROA_LI_AUTHOR_URN` | LinkedIn, Roatan |
| `{BCM,ROA}_LI_REFRESH_TOKEN` / `_CLIENT_ID` / `_CLIENT_SECRET` | optional; enables auto-refresh |
| `NOSTR_NSEC` | Nostr, both accounts |
