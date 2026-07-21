#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"
swift test
plutil -lint IOSExcersizeMyCalculator/Info.plist IOSExcersizeMyCalculator/PrivacyInfo.xcprivacy
xmllint --noout IOSExcersizeMyCalculator.xcodeproj/xcshareddata/xcschemes/IOSExcersizeMyCalculator.xcscheme
ibtool --errors --warnings --notices --minimum-deployment-target 15.0 IOSExcersizeMyCalculator/Base.lproj/Main.storyboard >/dev/null
calculator_destination="${IOS_CALCULATOR_DESTINATION:-platform=iOS Simulator,name=iPhone 16 Pro}"
xcodebuild -project IOSExcersizeMyCalculator.xcodeproj -scheme IOSExcersizeMyCalculator -destination "$calculator_destination" -configuration Debug CODE_SIGNING_ALLOWED=NO test
xcodebuild -project IOSExcersizeMyCalculator.xcodeproj -scheme IOSExcersizeMyCalculator -sdk iphonesimulator -configuration Release CODE_SIGNING_ALLOWED=NO analyze
