# Calculator release runbook

The calculator is local-only: it has no network service, account, database, tracking, advertising, crash reporter, or analytics SDK. `CalculatorState` is a versioned Codable record stored in the app's UserDefaults container. Failure to decode old or malformed state returns the safe empty state, so no database migration is required; the 13 core tests and five UI journeys provide state migration, failure, restoration, rotation, localization, and offline coverage for this topology.

Before release:

1. Run `scripts/verify.sh` using the pinned CI Xcode runner and review all compiler, storyboard, analyzer, and unit-test output.
2. Set the release bundle identifier and development team in an uncommitted or organization-managed signing configuration. Never commit signing certificates or provisioning profiles.
3. Increment `MARKETING_VERSION` and `CURRENT_PROJECT_VERSION`; archive Release in Xcode and validate the archive before upload.
4. Supply and visually verify final App Store icon files and screenshots for every required device size, light/dark appearance, Dynamic Type, portrait, and landscape. The catalog currently declares icon slots but final branded binaries require owner approval.
5. Run VoiceOver, Switch Control, Dynamic Type, rotation, interruption/background restoration, malformed-state, low-storage, and clean-install/upgrade tests on supported iOS devices.
6. Confirm `PrivacyInfo.xcprivacy` and the App Store privacy answers still match the binary, then obtain product/release approval.

The application makes no network call, so its explicit offline state is always ready. If networking, analytics, or crash reporting is added, it requires a new consent/privacy review, failure UI, retention/deletion design, and tests before release.
