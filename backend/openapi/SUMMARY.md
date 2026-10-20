# SubTrack API contract

Generated from `/api/v1/openapi.json`. Do not edit manually.

Money is serialized as decimal strings. Dates use ISO-8601. Every business route
requires the HTTP Bearer access token. Health and register/login are public.

| Method | Route | Auth | Purpose |
| --- | --- | --- | --- |
| GET | `/api/v1/alerts` | JWT | Alerts |
| GET | `/api/v1/alerts/{alert_id}` | JWT | Alert Detail |
| POST | `/api/v1/auth/login` | Public | Login |
| GET | `/api/v1/auth/me` | JWT | Me |
| POST | `/api/v1/auth/register` | Public | Register |
| GET | `/api/v1/budget` | JWT | Budget |
| PUT | `/api/v1/budget` | JWT | Put Budget |
| GET | `/api/v1/categories/unconfirmed` | JWT | Unconfirmed |
| PATCH | `/api/v1/categories/{category_id}` | JWT | Patch Category |
| POST | `/api/v1/categories/{category_id}/suggest` | JWT | Suggest Category |
| POST | `/api/v1/chat` | JWT | Chat |
| GET | `/api/v1/chat/config` | JWT | Chat Config |
| PUT | `/api/v1/chat/config` | JWT | Chat Consent |
| DELETE | `/api/v1/chat/history` | JWT | Delete History |
| GET | `/api/v1/chat/history` | JWT | History |
| DELETE | `/api/v1/demo/data` | JWT | Remove Demo |
| POST | `/api/v1/demo/load` | JWT | Load Demo |
| GET | `/api/v1/health` | Public | Health |
| GET | `/api/v1/health/ready` | Public | Ready |
| DELETE | `/api/v1/me/data` | JWT | Delete My Data |
| GET | `/api/v1/me/export` | JWT | Export Data |
| GET | `/api/v1/recommendations` | JWT | Recommendations |
| PATCH | `/api/v1/recommendations/{recommendation_id}` | JWT | Patch Recommendation |
| GET | `/api/v1/renewals/upcoming` | JWT | Renewals |
| GET | `/api/v1/settings/alerts` | JWT | Settings |
| PUT | `/api/v1/settings/alerts` | JWT | Put Settings |
| GET | `/api/v1/subscriptions` | JWT | Subscriptions |
| GET | `/api/v1/subscriptions/{subscription_id}` | JWT | Subscription Detail |
| PATCH | `/api/v1/subscriptions/{subscription_id}` | JWT | Patch Subscription |
| GET | `/api/v1/summary` | JWT | Summary |
| GET | `/api/v1/summary/savings` | JWT | Savings |
| GET | `/api/v1/summary/trend` | JWT | Summary Trend |
| GET | `/api/v1/uploads` | JWT | Uploads |
| POST | `/api/v1/uploads` | JWT | Upload |
| POST | `/api/v1/uploads/preview` | JWT | Preview |
| DELETE | `/api/v1/uploads/previews/{preview_id}` | JWT | Cancel Statement Preview |
| GET | `/api/v1/uploads/previews/{preview_id}` | JWT | Statement Preview Status |
| GET | `/api/v1/uploads/{upload_id}` | JWT | Upload Detail |

See the JSON contract for request/response schemas, examples, filters, bounds,
pagination and error envelopes. Upload mappings are JSON encoded multipart form fields.
The asynchronous upload response is 202; poll its `id` until `done` or `failed`.
