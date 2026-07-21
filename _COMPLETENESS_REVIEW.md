# Completeness Review: IOSCourse-CalculatorExercise

**Review date:** 2026-07-18

## Assessment basis

Static inspection of project-owned source and configuration only; no dependency installation, build, database migration, external-service call, or runtime launch was performed. The scan considered 62 project files (2 source files), 0 manifest(s), 0 test-like file(s), and 0 CI workflow(s), excluding dependency/generated directories.

## Classification

**Prototype-demo**

This is a prototype/demo for mobile/iOS. The implemented surface is narrow: it contains 2 source files and visible routes/pages in `IOSExcersizeMyCalculator/`, `IOSExcersizeMyCalculator.xcodeproj/`, but those surfaces are not evidence of durable domain execution, verified integrations, or operational completion.

## Why it is not complete

- No recognizable project-owned automated tests were found for the main workflow.
- No checked-in CI workflow proves builds, tests, migrations, and security checks on every change.
- No environment template documents required configuration and secret boundaries.
- No clear deployment/container configuration demonstrates a reproducible production topology.

## Needed features

1. Finish the primary user journey with explicit loading, empty, error, offline, and state-restoration behavior.
2. Separate persistence/network services from views and add validated models plus accessible navigation and controls.
3. Add unit and UI tests for lifecycle, rotation, localization, malformed input, and offline recovery.
4. Create reproducible signing/build configuration, privacy disclosures, release assets, and crash/analytics policy.
5. Add risk-based unit, integration, and end-to-end tests in CI, including migration and failure-path coverage.

## Risks or launch blockers

- Regression risk is high because no recognizable project-owned automated tests cover the main path.
- No CI evidence prevents broken or insecure changes from reaching a release.

## Evidence inspected

- `IOSExcersizeMyCalculator/AppDelegate.swift`
- `IOSExcersizeMyCalculator/ViewController.swift`

## Recommended next action

Stop adding generated pages; prove one mobile/iOS workflow against real services and persistent state, with tests and measurable acceptance criteria.

## Implementation progress (2026-07-18)

All five requested implementation areas now have project-owned coverage:

1. The calculator journey is implemented as a Decimal-based state machine with explicit restoring, empty/offline-ready, ready/offline, recoverable error, and persisted-state behavior. Division by zero, malformed restored data, input limits, repeated equals, decimals, sign, percent, clear, and the four operations are handled without a network dependency.
2. `CalculatorEngine`, validated Codable state, localized display formatting, and `CalculatorStateStore` separate domain/persistence behavior from the UIKit controller. Controls and the display have localized VoiceOver labels, values, hints, traits, Dynamic Type-safe scaling, and stable UI-test identifiers.
3. The Swift package contains 13 passing unit tests. A wired XCUITest target adds five primary/failure, lifecycle restoration, malformed-state, rotation, localization, and offline journeys to the shared scheme.
4. The project now has versioned iOS 15/Swift 5 build settings, automatic-signing boundaries, a shared scheme, privacy manifest and disclosure, release runbook, and a no-crash/no-analytics policy. Final branded App Store icons/screenshots and organization signing assets still require product-owner and Apple Developer account input; they are explicitly release-gated rather than fabricated.
5. CI runs core tests, plist/XML/storyboard validation, the simulator UI suite, a Debug test build, and Release analysis. Codable round-trip and malformed-persistence tests cover migration/failure paths for this local-only topology.

Validation performed locally: 13/13 Swift package tests passed; the app sources and UI-test sources type-checked against the installed iOS Simulator SDK; both plists, both storyboards, the Xcode project, and the shared scheme passed structural validation; and `git diff --check` passed. The full simulator build/UI run could not execute on this machine because Xcode 26.6 reports an older incompatible CoreSimulator service and a missing iOS 26.5 platform. Physical-device rotation, VoiceOver, clean-install/upgrade, signing/archive, screenshot, and App Store privacy verification remain release-owner/device gates.

## Runtime and login acceptance (2026-07-20)

**NOT_APPLICABLE** for the local web-runtime and browser-login acceptance harness.

- This repository is an iOS/UIKit calculator: the supported application target is `IOSExcersizeMyCalculator.xcodeproj`, its UI is storyboard-based, and `scripts/verify.sh` uses `xcodebuild` with an iOS Simulator destination.
- `Package.swift` exposes a library used for isolated domain tests; it does not define an executable product, HTTP server, or independently supported local web application.
- The calculator is intentionally offline and has no account, authentication, or session workflow. A browser login test therefore has no applicable product surface.
- A fabricated `start.sh` would misrepresent the supported runtime. Runtime acceptance belongs in Xcode on an installed simulator or signed iOS device, subject to the CoreSimulator and signing gates recorded above.

### Campaign verification evidence (2026-07-20)

The project remains an independent native iOS app, not a web service and not a non-application repository. No `start.sh` was added: on this host a truthful launcher would have to boot, install, and launch through CoreSimulator, while `simctl` is unavailable and a build-only script would not be an application runtime. The campaign result is therefore `NOT_APPLICABLE/native_ios_no_web_login_runtime_spm_verified`, not a fabricated HTTP listener.

Direct validation passed 13/13 Swift package tests, plist/project/scheme/storyboard structural checks, and iOS Simulator SDK typechecking of the calculator domain plus UIKit application sources. The unsigned Debug `xcodebuild` attempt was honestly retained as `FAILED/native_xcodebuild_host_unavailable`: Xcode 26.6 reports CoreSimulator 1051.49.0 versus required 1051.55.0, cannot resolve a simulator destination, and reports the iOS 26.5 platform unavailable. Assigned campaign ports `55618`, `6050`, and `6051` were not used and remained released. `git diff --check` passed.
