# SpendWise Android — free, on-device edition

The default Flutter entry point is now a receipt app that does not initialize Supabase, call the backend, upload photos, or make LLM requests. The existing backend and legacy UI remain available through `--dart-define=ENABLE_LEGACY_BACKEND=true` with the original development configuration.

## Chosen implementation

- Flutter / Material 3 with ivory, charcoal and lime styling.
- Google's ML Kit document scanner: crop, rotate and clean up a single receipt; gallery supported. This requires Google Play services and may download scanner components on first use.
- Bundled ML Kit Latin text recognition: no OCR API key, no per-scan API bill, works offline including on the Import photo path.
- Deterministic Dart parser reconstructs spatial rows from OCR boxes, extracts printed prices, and keeps the raw text and original item descriptions. It does not use a cloud or on-device LLM and does not claim perfect recognition.
- Integer cents for supported two-decimal currencies (USD, CAD, AUD, EUR, GBP). Dollar symbols alone never establish currency. Slash dates are interpreted as US month/day/year and must be reviewed.
- App-private files and an atomic, versioned JSON ledger. Drafts persist before review; only reviewed receipts contribute to monthly totals. No cloud backup is enabled by this app.
- JSON export of details and recognized text through Android's system file picker. It does not include receipt photos and is not an in-app restore feature.

No paid cloud service is required. The camera scanner can download assets via Play services. A user's own network/data plan is outside the app's control. Free cloud inference is intentionally excluded: public shared quotas and financial-document privacy would undermine the offline guarantee.

## Run and test

```sh
cd mobile
flutter pub get
flutter analyze
flutter test
flutter run -d <android-device>
```

Android API 23+ is required. Use a physical phone to verify camera behavior, initial Play services download, import, OCR latency and airplane mode. This implementation targets Android; other platforms show an explanatory screen.

The `Android offline app` workflow produces an installable **debug preview APK** in its `spendwise-android-preview` artifact. It uses standard GitHub-hosted runners on this public repository, with no external paid services. It is not a production release and its debug signing identity is not a stable public update identity. Artifacts expire after 14 days.

## Stable public releases

Choose and back up a production signing key before distributing a public release. Never commit it. Release builds use the following environment variables and do not fall back to debug signing:

- `SPENDWISE_KEYSTORE_PATH` (absolute path)
- `SPENDWISE_KEYSTORE_PASSWORD`
- `SPENDWISE_KEY_ALIAS`
- `SPENDWISE_KEY_PASSWORD`

Then run `flutter build apk --release --split-per-abi`. Verify installation and upgrades using the same key, and publish the signed APKs through a GitHub Release for direct installation. Google Play publication is a separate option with its developer registration fee; it is not required for direct APK distribution. Retain the key privately for future updates.

## Quality gate before public release

Use synthetic or consenting, sanitized receipt photos with ground-truth annotations. Include at least 30–50 receipts across stores, long receipts, rotated captures, faint thermal print, discounts, quantity lines, tips and multiple tax lines. Measure merchant/date/total exact match, item-and-price recall, correction effort, and median / p95 elapsed scan time on a budget and a midrange phone. No accuracy or speed benchmark is claimed by this change.

Verify:

1. First scan with internet and first gallery import without internet.
2. Airplane-mode scan after scanner initialization.
3. Cancel scanning/import/export and retry; deny or lack Google Play services.
4. Kill/restart after a draft is created; review and save; restart again.
5. Failed storage writes preserve prior data and do not show a false success.
6. Delete both metadata and receipt photo; export details to a user-chosen file.
7. Large font sizes, narrow screens, dark receipt photos, very large source images.
8. Keep currencies separate and exclude drafts from totals.

Known limitations: heuristic item extraction cannot understand every receipt layout; source image is zoomable but individual field bounding boxes are not highlighted. Quantity/unit-price fields are editable and only explicitly detected quantity prefixes are extracted. Long receipts may require multiple separate captures. Refund/return workflows, multilingual parsing, encrypted backups/restore, synchronization and downloaded local LLMs are future work. Uninstalling or clearing app data deletes local receipts. Store only data the device owner intends to retain.
