# CONTEXT.md — MFP Logger

## Domain

Single-user meal logging tool for OpenClaw. Users submit food photos or text descriptions via Telegram, receive itemized estimates with confidence & nutritional evidence, explicitly confirm or correct proposals, and have them written to MyFitnessPal via an authenticated browser context.

## Ubiquitous Language & Glossary

- **Meal Input**: Raw photo attachment or natural-language description from Telegram.
- **Evidence Source**: Ranked data source (`nutrition_label` > `verified_restaurant` > `confirmed_personal_recipe` > `mfp_match` > `ingredient_calculation` > `vision_estimate`).
- **Confidence Level**: `high`, `medium`, or `low`. Low confidence blocks confirmation until clarified.
- **Proposed Meal / Meal Preview**: Itemized breakdown with inferred/overridden date, meal category, food items, macro breakdowns, confidence, and preview expiration.
- **Workflow State**: `prepared`, `awaiting_confirmation`, `confirmed`, `submitting`, `verifying`, `succeeded`, `pending`, `failed`, `uncertain`.
- **Custom Food**: Private MyFitnessPal food created for missing items, dated and marked as AI estimate.
- **Duplicate Preflight**: Checking target diary date & meal prior to submission to prevent duplicates.
- **Post-Submit Verification**: Re-reading diary after submission to verify exactly one matching entry exists.
