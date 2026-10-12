# Privacy and data handling

**Status: draft for an academic project. Not a legal privacy policy, and not reviewed by a lawyer.** It describes what the software does today, including its gaps. Items marked `TODO` need a decision from the project owner. Before the app is published to any app store, this must be turned into a real privacy policy; see [Before publishing](#before-publishing).

Last verified against the code: 2026-10-10 (`backend/src/routes/ml.js`, `users.js`, `auth.js`, `services/`, `migrations/`).

## 1. What is collected

| Data | Where it is stored | Why |
|---|---|---|
| Phone number (10 digits) | `users.phone_number` | Account identity and login |
| Name, 4-digit farmer ID, language, land unit | `users` | Profile |
| State, district, total land area, irrigation type | `users` | Weather, schemes, advice |
| Field name, area, **centre latitude and longitude**, **boundary polygon**, soil type | `fields` | Weather, planting, map |
| Soil-test values (up to 12) | `soil_tests` | Fertility and crop advice |
| Plantings (crop, variety, sowing date) | `plantings` | Growth-stage rules |
| Activities, costs and notes | `interventions` | Ledger |
| Pest and disease counts, notes | `scouting_observations` | Alert rules |
| **Photos** you send for a check (leaf, soil, insect, and similar) | Server disk, `backend/uploads/ml/YYYY/MM/` | The check and your photo history |
| Result of each photo check, the request that produced it, and a SHA-256 hash of the photo | `ml_inferences` | History and audit |
| Alerts you received and how you responded | `recommendations`, `scheme_matches` | Alerts screen |
| A sign-in token (JWT) containing your user ID and phone number | On your phone | Staying signed in; valid 7 days |

The app also keeps some data on the phone itself (profile, fields, plantings) in local storage so screens load quickly.

## 2. Who else receives data

- **Open-Meteo** (weather): receives each field's latitude and longitude, and state and district, to return the forecast. No account or key is used, and there is no opt-out in the app.
- **MapTiler** (map imagery): the app requests map tiles for the field-boundary screen using a MapTiler key; tile requests reveal the area being viewed.
- **The ML service** runs on the same server as the API (localhost only). Photos and the inputs for advice (for example crop and state) are sent to it, but it has no database and does not keep them.
- No analytics, advertising or crash-reporting service is used.

## 3. Photos

- Every photo that passes basic validation is saved **unencrypted** on the server disk, **including photos where the model refused or failed**.
- A photo is discarded without being saved only if the model reports it as an invalid or oversize image. Uploads of the wrong type or over 8 MB are rejected before saving.
- The photo-history screen lists your photo checks and lets you delete them.

### The photo-training consent flag

Profile has a switch, "Allow my photos to be used to improve the checks", **off by default**, stored in `users.photo_training_consent`.

> **Today nothing reads this flag.** It is recorded and returned by the API, but no code uses or checks it, and photos are stored whether it is on or off. No farmer photo has been used to train any model; every shipped model was trained on third-party datasets.
>
> Any future export of farmer photos for training **must** filter on this flag, and the switch should not be described to users as active until that is built.

## 4. Retention and deletion

| What | Behaviour today |
|---|---|
| A photo check | `DELETE /ml/inferences/:id` (the Delete button in photo history) removes the photo file and clears its path. **The database row is kept**, with its request and result data and a `deleted_at` time. |
| Fields, plantings, activities, scouting counts | Deleting marks them `deleted_at`; **the data stays in the database**. Deleting a field or planting does not remove its soil tests, photos, alerts or history. |
| Soil tests, alerts, scheme matches | No delete option. |
| Your account | **No way to delete an account or export your data.** |
| Retention period | None. Nothing is purged automatically. `TODO: choose a retention period` |
| Sign-in | No logout on the server and no token revocation; a token stays valid until it expires after 7 days. The app's Log out clears the phone only. |

## 5. Security status

This is a development build. Do not use real farmer data until these are fixed.

- **Login is a mock.** Any phone number can sign in with the fixed code `123456`; no SMS is sent. Anyone who knows a phone number can open that account.
- No rate limiting on any endpoint.
- The server accepts requests from any origin (`CORS *`) and listens on all network interfaces.
- Traffic is plain HTTP in the default setup; there is no HTTPS.
- Photos on disk and database contents are not encrypted at rest by the application.
- The internal batch endpoints use one shared secret key.
- Errors are logged to the server console; there is no structured access log.

## 6. Children

The app is not designed for or aimed at children. `TODO: confirm intended minimum age`

## 7. Contact

`TODO: add a contact email and an owner name for privacy questions and deletion requests`

## 8. Changes

`TODO: effective date and version`

## Before publishing

App stores require a published privacy policy and a data-safety declaration. Before release, at minimum:

1. Replace the mock login with real phone verification (SMS OTP) and add rate limiting.
2. Serve everything over HTTPS and restrict CORS to the app's origins.
3. Make `photo_training_consent` enforced in code, or remove the switch.
4. Add **account deletion** and data export, and make deletion remove data, not just flag it: purge photo rows and result JSON, and cascade to a field's soil tests, history and photos.
5. Decide and implement a retention period and a purge job.
6. Add token revocation or short-lived tokens with refresh.
7. Add an in-app notice naming Open-Meteo and MapTiler as data recipients, and decide whether location sharing needs consent.
8. Fill in the `TODO` items above, then have the final policy reviewed against the privacy law that applies where you publish (for example India's Digital Personal Data Protection Act, 2023). This draft makes no claim of compliance with any law.

Related: [DISCLAIMER.md](DISCLAIMER.md), [documentation/DATABASE.md](documentation/DATABASE.md), [documentation/ARCHITECTURE.md](documentation/ARCHITECTURE.md).
