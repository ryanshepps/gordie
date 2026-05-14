# SMS Setup (Sinch)

SMS is optional. With Sinch env vars unset, `SmsService` boots in disabled mode and `send_sms` returns `error: sms_disabled`. The signup flow falls back to email-only.

## 1. Sinch account

1. Sign up at https://dashboard.sinch.com
2. Provision a long code or toll-free number in your target country.
3. Copy:
   - **Service Plan ID**
   - **API Token**
   - **From Number** (E.164 format, e.g. `+12025550100`)
4. (Optional) Create an inbound webhook secret if you want to verify incoming SMS signatures.

## 2. Set env vars

```bash
SINCH_SERVICE_PLAN_ID=...
SINCH_API_TOKEN=...
SINCH_FROM_NUMBER=+12025550100
SINCH_WEBHOOK_TOKEN=...
```

## 3. Inbound webhook

In Sinch dashboard, set the inbound SMS callback URL to:

```
https://your-public-host/sms/webhook
```

Signature is verified against `SINCH_WEBHOOK_TOKEN` (see `server/webhook_verification.py`).

## Swapping for Twilio

`server/sms_service.py` is the only Sinch-specific file. To swap to Twilio: keep the public surface (`SmsService.send_sms` returning `SmsResult`), and replace the request body + base URL inside. Inbound webhook would need a corresponding signature-verification swap.
