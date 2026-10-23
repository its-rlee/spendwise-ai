# SpendWise AI — Order 5: Free-tier release preparation

This branch prepares a **test/public-preview deployment**, not a certified
production financial service. You must connect your own services, configure
secrets, run a full end-to-end smoke test, and resolve the launch blockers below.

## Cost reality

| Component | Suggested route | Important limit |
| --- | --- | --- |
| Android APK | GitHub Actions artifact, then a GitHub Release | No Play Store required; testers must allow installs from outside Play |
| Google Play | Optional later | Google charges a **US$25 one-time developer registration fee** |
| Web preview | GitHub Pages (public repository) | GitHub-hosted static site, subpath /spendwise-ai/ |
| FastAPI | Render **Free** web service | Sleeps after 15 min idle; wake-up ~1 min; 750 free instance hours/month; **not recommended for production** by Render |
| Database/Auth | Existing Supabase Free project | Size/activity/bandwidth limits; inactive free projects can be paused |
| Receipt storage | Private Supabase Storage S3-compatible bucket | 1 GB storage on Free; configure S3 protocol credentials server-side |
| LLM | Existing Google Gemini API project | A free allowance can change or be exhausted; check use/privacy terms |

An app serving everybody **cannot be promised always free**: quotas, terms,
user volume and paid registration requirements make that impossible at scale.
Do not enable paid upgrades or attach billing without understanding the risks.
A signed APK hosted on GitHub is not automatic installation or auto-update.

## 0. Prerequisites

- Orders 1/2/4 are included in `main`. Order 3 is a separate branch and is
  not integrated into this release branch yet.
- Test with fictional data first, not real financial documents.
- Ensure `backend/migrations/20261021_add_receipt_item_provenance.sql`
  and all required database tables are applied.
- Verify `FINANCE_AI_PROVIDER=gemini` and
  `RECEIPT_AI_PROVIDER=gemini` in the server.
- Do **not** put `GEMINI_API_KEY`, PostgreSQL passwords, Storage S3 secret
  keys, or Supabase service-role keys into Flutter, GitHub Variables, or Git.
- The Supabase **publishable** key is intended for client apps, but RLS/ownership
  and backend authentication must still be enforced.

## 1. Private receipt storage without AWS S3 billing

The backend still uses `boto3`, but its endpoint is now configurable.

1. In the Supabase dashboard, create a **private** Storage bucket, such as
   `spendwise-receipts`. Do NOT mark it public.
2. In Storage settings, enable S3 protocol access and generate an S3 access key
   and secret. Treat these as highly privileged **backend-only** credentials.
3. Record your project's actual region and S3 endpoint from its dashboard.
   Example **pattern**, not a real endpoint:
   `https://PROJECT_REF.storage.supabase.co/storage/v1/s3`.
4. Configure these values in Render's private environment variables:

   ```dotenv
   AWS_REGION=YOUR_SUPABASE_STORAGE_REGION
   AWS_S3_BUCKET=spendwise-receipts
   AWS_S3_ENDPOINT_URL=https://YOUR_PROJECT_REF.storage.supabase.co/storage/v1/s3
   AWS_ACCESS_KEY_ID=YOUR_SUPABASE_S3_ACCESS_KEY
   AWS_SECRET_ACCESS_KEY=YOUR_SUPABASE_S3_SECRET
   AWS_EC2_METADATA_DISABLED=true
   ```

5. Uploaded files from an earlier AWS bucket **remain in AWS**. Switching
   the endpoint does not migrate those bytes. Either migrate existing S3
   objects safely while preserving keys and hashes, or keep the original AWS
   endpoint for existing accounts until a migration is complete. Never
   silently point an existing production account to an empty storage bucket.
6. Storage quotas are small; monitor usage and plan retention/deletion before
   broad public distribution.

You can also continue with AWS S3 by leaving `AWS_S3_ENDPOINT_URL` unset,
but AWS usage may incur charges. The Render blueprint uses Supabase Storage.

## 2. Deploy the HTTPS backend (Render)

1. In Render, use **New → Blueprint**, connect your own GitHub repository,
   and select the branch containing `render.yaml`. The Blueprint creates
   one `plan: free` Docker web service; it does not create a paid database.
2. Enter the secret variables prompted by Render. The main required values:

   ```dotenv
   DATABASE_URL=postgresql+psycopg://...YOUR_SUPABASE_POOLER_CONNECTION...
   SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
   SUPABASE_PUBLISHABLE_KEY=YOUR_PUBLISHABLE_KEY
   GEMINI_API_KEY=YOUR_SERVER_SIDE_GEMINI_KEY
   CORS_ALLOWED_ORIGINS=https://its-rlee.github.io
   ```

   Use your **actual** Supabase pooler URL (with SSL), and keep passwords
   server-side. Enter the Storage variables from section 1 too.

3. Wait for a successful deployment. Verify:

   ```
   https://YOUR_SERVICE.onrender.com/health
   https://YOUR_SERVICE.onrender.com/ready
   ```

   `/ready` queries the DB. Do not paste server environment values, full
   Docker inspection output, or Authorization headers into issues.
4. Render Free services sleep after inactivity. The first request may take
   about a minute to wake; the default 30-second GET timeout in the Flutter
   client may show a transient error. This tier is suitable for testing, **not**
   a reliable public service.
5. The backend stores no persistent files in the container; database rows are
   in Supabase and receipts are in private object storage.

## 3. Configure GitHub Actions Variables (public app configuration)

Under **GitHub → Repository Settings → Secrets and variables → Actions → Variables**,
add:

| Name | Value |
| --- | --- |
| `API_BASE_URL` | `https://YOUR_SERVICE.onrender.com` (no trailing slash) |
| `SUPABASE_URL` | `https://YOUR_PROJECT_REF.supabase.co` |
| `SUPABASE_PUBLISHABLE_KEY` | Your **publishable**, not service-role, key |

These values are **embedded in the released Flutter binary/web JavaScript**;
they are not secret. Never put `GEMINI_API_KEY`, DB connection strings or
Supabase S3 access keys here.

In Supabase Auth URL configuration, add the actual GitHub Pages address to
allowed redirect URLs, such as
`https://its-rlee.github.io/spendwise-ai/`. Configure your desired site URL.
Ensure `CORS_ALLOWED_ORIGINS` lists browser **origins** only
(`https://its-rlee.github.io`, without the project path).
For a phone APK, CORS does not apply, but TLS still does.

## 4. Free static web preview (GitHub Pages)

1. In **Settings → Pages**, select **Source: GitHub Actions**.
2. Under **Actions**, manually run **Publish SpendWise Web Preview**
   from the branch containing this workflow.
3. GitHub compiles Flutter Web using `--base-href /spendwise-ai/` and deploys
   to a repo-scoped HTTPS URL. You must **confirm the actual published URL**
   shown in the Actions run.
4. Test login, receipt upload, transaction review, and question answering.
   The browser camera experience in the current `image_picker` screen is
   **not yet a guaranteed live webcam preview**. On desktop browsers it may
   use the file picker; implementing `camera`/`camera_web` is separate.
5. If Pages is inappropriate for your eventual application, deploy
   `mobile/build/web` to Cloudflare Pages Free instead. Build with
   `--base-href /` for a root-hosted domain and update CORS/auth origins.

## 5. Prepare a correctly signed Android APK

The Android package ID is `com.itsrlee.spendwise`. Choose the permanent ID
before public release; changing it later makes Android treat the APK as a
different app.

In **PowerShell**, create a keystore and back it up safely:

```powershell
keytool -genkeypair -v -keystore "$env:USERPROFILE\spendwise-release.jks" `
  -storetype PKCS12 -keyalg RSA -keysize 3072 -validity 10000 -alias spendwise
```

Do not commit or upload this file to public GitHub. Keep an encrypted backup
of the keystore and passwords; losing them may prevent future app updates.

Create these **GitHub Actions Secrets**:

| Secret | Value |
| --- | --- |
| `ANDROID_KEYSTORE_BASE64` | `[Convert]::ToBase64String([IO.File]::ReadAllBytes("$env:USERPROFILE\spendwise-release.jks"))` output — **paste only into Secrets UI** |
| `ANDROID_STORE_PASSWORD` | Keystore password |
| `ANDROID_KEY_PASSWORD` | Key password |
| `ANDROID_KEY_ALIAS` | `spendwise` |

Run **Actions → Build Signed Android APK → Run workflow** from the release
branch. If it succeeds, download the `spendwise-android-signed` artifact.
The artifact expires after 14 days; do not assume permanent distribution.

After testing installation and login on a real device, you may create a
versioned **GitHub Release** and attach the signed APK. This is free APK
distribution, **not** a Google Play listing. Avoid auto-publishing a build
that has not been reviewed and consented to.

For a local signed Android build, create `mobile/android/key.properties`:

```properties
storePassword=YOUR_STORE_PASSWORD
keyPassword=YOUR_KEY_PASSWORD
keyAlias=spendwise
storeFile=upload-keystore.jks
```

Copy the keystore to `mobile/android/app/upload-keystore.jks`
(ignored by Git), then run:

```powershell
cd mobile
flutter build apk --release `
  --dart-define="API_BASE_URL=https://YOUR_SERVICE.onrender.com" `
  --dart-define="SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co" `
  --dart-define="SUPABASE_PUBLISHABLE_KEY=YOUR_PUBLIC_KEY"
```

**No debug signing is used for the release variant.** GitHub Actions
creates `key.properties` temporarily; the files are not committed.

## 6. Test before showing real users

- Backend `/ready` succeeds cold and warm; HTTPS certificates are valid.
- Web login and email redirects work using the hosted origin.
- Android app opens on a real device, camera/gallery captures a receipt,
  upload succeeds, and human review/approval persists without missing columns.
- Reinstall/update with an APK signed by the **same release key**.
- One account cannot read, change, or delete another account's records.
- Model timeout/503 errors never silently mark incomplete receipts approved.
- All sensitive server secrets are rotated if previously exposed.
- Test slow network, permission denial, large image rejection, quota exhaustion,
  duplicate receipt, item subtotal mismatch, account deletion, and recovery.
- Verify your billing/usage dashboards remain inside free limits.

### NOT production ready until resolved

- Add explicit receipt-image and financial chat privacy disclosure/consent
  appropriate for your jurisdiction, and a genuine account/data/receipt
  deletion workflow (including stored images). Current UI does not fully
  implement these controls.
- Implement bounded Gemini retries/fallback and saved-scan recovery.
- Validate transaction/item accounting and quantity handling, improve
  transaction-review UI, and establish human support/contact information.
- Replace free-tier sleeping backend with hosting meeting uptime requirements
  if you promise reliable always-on service.
- Confirm Google AI service free-tier data-processing terms permit the type
  of receipt data and usage you intend; use synthetic/non-sensitive data
  while validating the prototype.
- Complete integration of Order 3 dashboard if you want it in launch.
- Replace generic Flutter launcher/PWA icon artwork with your own assets.
  The metadata is branded, but the existing icons are still the defaults.
- Create a truthful privacy policy, terms and support process before accepting
  real users' financial documents.

### References

- [Render Free Web Services](https://render.com/docs/free)
- [Supabase S3 compatibility](https://supabase.com/docs/guides/storage/s3/compatibility)
- [Supabase S3 authentication](https://supabase.com/docs/guides/storage/s3/authentication)
- [Flutter Android signing](https://docs.flutter.dev/deployment/android)
- [Google Play developer fee](https://support.google.com/googleplay/android-developer/answer/6112435)
- [GitHub Pages](https://docs.github.com/en/pages)
