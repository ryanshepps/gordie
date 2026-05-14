# Email Setup (Mailgun)

Gordie sends and receives email through Mailgun. The server runs fine without email configured — outbound calls log a warning and return `error: email_disabled`. Inbound webhooks return 503.

## 1. Mailgun account + domain

1. Sign up at https://signup.mailgun.com (free sandbox or paid).
2. Add and verify a domain. SPF + DKIM + MX records are required for inbound mail.
3. Copy the **Private API Key** and **Domain** from the Mailgun dashboard.

## 2. Set env vars

```bash
MAILGUN_API_KEY=...
MAILGUN_DOMAIN=mg.yourdomain.com
MAILGUN_FROM_EMAIL="Gordie <gordie@mg.yourdomain.com>"   # optional; default uses domain
MAILGUN_WEBHOOK_SIGNING_KEY=...                          # from Mailgun → Webhooks
```

## 3. Inbound routing

In Mailgun → **Receiving → Create Route**:

- **Filter expression:** `match_recipient("gordie@mg.yourdomain.com")`
- **Action:** `forward("https://your-public-host/email/webhook")`

The webhook handler verifies the Mailgun signature using `MAILGUN_WEBHOOK_SIGNING_KEY`, parses the email, and threads it to the agent.

## 4. Outbound test

```bash
uv run python -c "
from server.email_service import EmailService
r = EmailService().send_email('you@example.com', 'Test', 'Hello from Gordie.')
print(r)
"
```

Expected: `EmailResult(success=True, message_id='...')`.

## Alternatives

The code is Mailgun-specific (`server/email_service.py`). To swap in SMTP, Postmark, SES, etc., reimplement the `send_email` method against your provider's API. The rest of the system uses only `EmailResult`.
