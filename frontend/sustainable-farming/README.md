# Chiguru Nele — mobile app

Expo / React Native client for the Sustainable Farming system. Display name "Chiguru Nele", slug `sustainable-farming`, URL scheme `agrosense`. For the whole-system picture see the [root README](../../README.md).

## Stack

- Expo SDK 54, React Native 0.81, React 19, TypeScript 5.9
- Routing: expo-router 6 (file-based, typed routes)
- Styling: NativeWind 4 on Tailwind 3
- Animation: react-native-reanimated 4
- i18n: i18next + react-i18next (10 locales)
- Other: react-native-svg, expo-location, expo-image-picker, expo-image-manipulator, AsyncStorage, datetimepicker
- Tests: jest with jest-expo

The intended workflow is **Expo Go**, so only libraries bundled in Expo Go are used (no native modules needing a dev build).

## Setup

Prerequisites: Node ≥ 20, the backend running (see [backend/README-ops.md](../../backend/README-ops.md)), and Expo Go or an emulator.

```bash
npm install
```

Create `.env` in this folder for the optional map key or an API URL override:

```
EXPO_PUBLIC_MAP_TILER_API_KEY=<your MapTiler key>
```

When running in Expo Go, the API defaults to the current Expo dev-server host
on port 8000, so a changing PC LAN IP does not need a `.env` update. Set
`EXPO_PUBLIC_API_BASE_URL` only to override that default.

| `EXPO_PUBLIC_API_BASE_URL` for | Value |
|---|---|
| Physical phone, same Wi-Fi as the PC | Detected from the Expo dev-server host |
| Android emulator | `http://10.0.2.2:8000` |
| iOS simulator | `http://localhost:8000` |
| Phone on mobile data | a tunnel URL, e.g. from `npx localtunnel --port 8000` |

`EXPO_PUBLIC_*` variables are inlined at bundle time and must keep that prefix. Restart with `npx expo start -c` after changing them.

## Scripts

| Script | Does |
|---|---|
| `npm start` | `expo start` (scan the QR code with Expo Go) |
| `npm run android` | Start and open on Android |
| `npm run ios` | Start and open on iOS |
| `npm run web` | Start for web (backend CORS must allow the origin) |
| `npm test` | Run jest |

**Dev login:** any phone number with OTP `123456` (the backend's `MOCK_OTP`).

## Project layout

```
app/              expo-router screens
  (auth)/           login, otp
  (onboarding)/     step-1 … step-5
  (tabs)/           home, fields, log, schemes, profile
  alert/ scheme/ ledger/ planting/   detail screens (planting has diseases + photo-check)
  modals/           add-field, add-planting, add-soil-test, log-scouting, quick-log
  market.tsx  photo-history.tsx
components/       AlertCard, SchemeCard, WeatherWidget, FieldBoundaryMap, AnimatedSplash, ml/*, ui/*
services/         API calls per feature (go through lib/apiClient.ts)
store/            appStore.ts — app state + persistence
hooks/            e.g. useRefreshTriggers (refetch on foreground and on a timer)
lib/ utils/ types/ context/ data/ theme.ts
locales/          en hi kn ta te ml bn gu pa mni (.json)
```

## State and data flow

- `store/appStore.ts` holds app state in memory and persists a **whitelist** of keys to AsyncStorage as a versioned envelope with a migration chain (`SCHEMA_VERSION`). Add a migration whenever the persisted shape changes; `store/__tests__/appStore.migration.test.ts` covers the chain.
- The store tracks `dataOrigin` (empty, demo or live) so demo data is never mistaken for the farmer's own.
- The app is **online-only**. There is no offline write queue; a failed create shows a toast. (An earlier WatermelonDB-style sync design was dropped to keep Expo Go working.)
- ML features (photo checks, disease Q&A, yield outlook) go through the backend's `/api/v1/ml` routes. When the ML sidecar is down they receive `503 ml_unavailable` and should degrade gracefully.

## Internationalisation

Strings live in `locales/<code>.json`. When adding a key, add it to **all 10 locale files** so key sets stay in step. Manipuri (`mni`) translations are machine-generated and **unverified**; some recently added keys may be missing there.

## Presenting ML output

Follow the rules the ML layer enforces (see [ml/README.md](../../ml/README.md)): show confidence only as the categorical label (`ConfidencePill`), show yield as a percentile band, never invent probabilities, and keep caveat text (`CaveatText`, `ModelNotice`) visible next to model output.

## Tests

```bash
npm test
```

Current suites: `store/__tests__/appStore.migration.test.ts`, `services/__tests__/ml.test.ts`, `services/__tests__/scouting.test.ts`.

## Notes

- Expo SDK 54 docs apply; see `AGENTS.md` / `CLAUDE.md` in this folder for contributor guidance.
- The "nearby vendors" list is a hard-coded mock.
