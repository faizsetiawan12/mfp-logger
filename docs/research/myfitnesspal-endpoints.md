# MyFitnessPal Endpoint Findings

Status: unofficial, observed behavior only  
Observed: 2026-08-29  
Source: sanitized Firefox network capture from a manual diary entry

## Safety

The original capture contained live account credentials and must not be retained.
Do not commit or log HAR files, request headers, browser cookies, bearer tokens,
CSRF tokens, Cloudflare values, device identifiers, or MyFitnessPal user IDs.

Authentication must remain inside a dedicated browser profile. Endpoint calls
must execute from that authenticated browser context rather than from copied
credentials. Login, reauthentication, CAPTCHA, and 2FA require manual handling.

## Add Diary Entry

An authenticated MyFitnessPal web session added an existing food with:

```http
POST https://www.myfitnesspal.com/food/add
Content-Type: application/x-www-form-urlencoded; charset=UTF-8
Accept: application/json
```

The form body contained:

| Field | Meaning | Observed format |
| --- | --- | --- |
| `food_entry[food_id]` | Existing MyFitnessPal food | Opaque numeric identifier |
| `food_entry[date]` | Diary date | `YYYY-MM-DD` |
| `food_entry[quantity]` | Number of servings | Decimal number |
| `food_entry[weight_id]` | Serving-size choice for the food | Opaque numeric identifier |
| `food_entry[meal_id]` | Target meal category | Opaque numeric identifier |
| `ajax` | Request mode | `true` |

The browser also supplied current same-origin authentication, anti-forgery, and
client-context data. Their names and values are intentionally not reproduced
because they are security-sensitive and may change.

### Observed Success

- HTTP status: `204 No Content`
- Response body: empty
- The response rotated the browser session cookie.
- A `204` proves the request was accepted but does not identify the new diary
  entry and is not sufficient proof that exactly one correct entry exists.

The integration must reload the target diary after submission and verify the
date, meal category, food, serving, quantity, and exactly-one-entry condition.

## Required Preconditions

Before calling the add endpoint, the integration must have:

- A manually authenticated MyFitnessPal browser session.
- A selected existing MyFitnessPal `food_id`.
- A `weight_id` that belongs to that food and represents the confirmed serving.
- A verified mapping from the intended meal category to `meal_id`.
- The confirmed diary date and quantity.
- A duplicate preflight result for the target date and meal.

Identifiers captured for one food, serving, user, or session must not be treated
as global constants.

## Failure And Retry Rules

- Submit a confirmed operation at most once.
- Treat a timeout or interrupted response as `uncertain`, not failed.
- Inspect the diary before retrying an uncertain operation.
- Stop on redirects to login, authentication challenges, CAPTCHA, unexpected
  status codes, changed response behavior, or missing verification evidence.
- Never automatically rediscover or guess changed endpoint contracts.
- Never report success based only on the `204` response.

## Unrelated Capture Traffic

Requests to `cdn.privacy-mgmt.com` handled consent configuration. They did not
create the diary entry and are not part of the MFP Logger integration contract.

## Unknown Contracts

These behaviors still require separate, sanitized investigation:

- Searching MyFitnessPal foods and obtaining candidate food identifiers.
- Obtaining valid serving choices and `weight_id` values for a selected food.
- Mapping breakfast, lunch, dinner, and snack categories to `meal_id` values.
- Creating a private custom food when no acceptable match exists.
- Reading the diary in a stable form suitable for duplicate checks and
  post-submit verification.
- Identifying, editing, or deleting the exact entry during corrections.
- Authentication and anti-forgery token lifecycle inside the browser context.

## Stability And Terms

This is an undocumented endpoint used by MyFitnessPal's normal web application,
not a supported public API. Its URL, fields, authentication requirements, and
behavior may change without notice. MyFitnessPal's terms may restrict automated
access. The integration must not bypass authentication, CAPTCHA, access controls,
or anti-automation measures.
