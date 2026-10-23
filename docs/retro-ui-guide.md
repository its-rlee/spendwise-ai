# SpendWise — Retro Instrument UI

## Design direction

Original neon-green retro-science console design inspired by early CRT
instruments and the user's supplied reference photo. No copyrighted Fallout
mascot, logos, typefaces or screenshots are redistributed.

| Token | Hex | Role |
| --- | --- | --- |
| Background | `#06110C` | dark instrument body |
| Panel | `#0D2016` | displays and dialogs |
| Raised | `#143021` | cards and controls |
| Phosphor | `#B7FFAB` | luminous lines and primary actions |
| Bright | `#E0FFE0` | high-contrast text |
| Soft | `#79C991` | secondary information |
| Amber | `#FFD17A` | safety/status highlights |
| Danger | `#FF9686` | invalid fields and errors |

Theming, logo, sweep line, animated bars and buttons are pure Flutter.
No paid image assets, paid fonts, or extra rendering packages are required.

## Platform behavior

- **Android:** after login opens the scanner; tapping scan provides a live
  native camera preview. Camera permission is requested by the device. Camera
  can be switched if more than one is available.
- **Web:** after login opens the dashboard (no unsolicited camera prompts).
  Users press **Scan receipt → Activate live camera**, which requests browser
  permission and renders the webcam. HTTPS or local development `localhost`
  is required by browser camera security rules.
- **Both:** users can import an image if camera access fails. Both platforms
  use the same authenticated `DocumentReviewScreen` upload/prepare/approve
  pipeline. Return to dashboard refreshes approved spending.

At widths >=1120 logical pixels, dashboard and Ask AI become side-by-side;
at smaller widths they stack and remain scrollable. The scanner uses
side-by-side camera and controls at widths >=880; the login screen uses a
split-screen layout at widths >=860. Dialogs keep native scroll behavior.

Animations use built-in controllers (logo radar pulse, HUD scan sweep, loading
bars, chart transitions, hover/tap feedback). Animations stop or become
instant when `MediaQuery.disableAnimations` is enabled. The global scanline
layer is decorative, pointer-transparent and excluded from semantics.

## Development

```powershell
cd D:\Devs\AI\spendwise-ai
git fetch origin
git switch --track origin/feat/retro-terminal-ui

cd mobile
flutter pub get
flutter analyze
flutter test

# Browser / webcam preview
flutter run -d chrome --web-port=5173 --dart-define-from-file=config/dev.json

# Physical Android USB test (from another terminal)
adb reverse tcp:8000 tcp:8000
flutter run -d YOUR_DEVICE_ID --dart-define-from-file=config/dev.json `
  --dart-define=API_BASE_URL=http://127.0.0.1:8000
```

## Premerge checklist

- Desktop Chrome and Edge on localhost show the live webcam preview after
  an explicit camera activation gesture; denied/no webcam shows an import
  option, not a blank screen.
- Chrome Android and native Android capture a readable receipt; the
  resulting image uploads, extracts, reviews and approves normally.
- Browser width ~390, 768, 1280+; rotate an Android device and verify no
  RenderFlex overflow in charts, forms, menus, or transaction detail lists.
- Sign-in, sign-out, transaction approval, and chat history work unchanged.
- Check keyboard navigation and zoom to 200% on web.
- On devices with Reduce Motion enabled, moving scan sweep and repeating
  logo animations are disabled.
- Confirm text legibility and error visibility under different display
  brightness conditions.

**Reminder:** this redesign does not solve cloud Gemini outages, permanent
storage/account deletion, or privacy consent. Test those separately before a
real financial-data public launch.
