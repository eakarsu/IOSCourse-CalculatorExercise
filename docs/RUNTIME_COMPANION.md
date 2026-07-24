# Runtime-verification companion

The supported product in this repository remains the offline UIKit calculator in
`IOSExcersizeMyCalculator.xcodeproj`. The root `start.sh` does not launch an iOS
simulator and does not pretend that the native app is a web application. It launches a
small, standard-library-only local companion so automated runtime acceptance can prove
credential handling, durable persistence, and an approved OpenRouter boundary without
changing the calculator target.

The ignored root `.env` supplies two distinct loopback ports, an absolute SQLite path,
one bootstrap administrator, and the approved OpenRouter key/model/base. The committed
`.env.example` contains no usable secret. Bare `./start.sh` fails closed when either port
is missing, duplicated, invalid, or already occupied.

The companion exposes:

- API health/readiness and credential login/identity/logout on the API port.
- An authenticated `POST /api/ai/calculator-safety-review` route that calls only the
  canonical `https://openrouter.ai/api/v1` base.
- An authenticated durable interaction read route. SQLite stores password hashes,
  bearer-token digests, provider request receipts, model metadata, and output.
- A separate UI port with functional credential login, identity, logout, and governed
  AI review forms. The page explicitly labels itself as verification support rather
  than the UIKit calculator and keeps its bearer token only in page memory.

Run `scripts/verify-companion.sh` for companion tests, compile/lint gates, a strict audit
of its empty third-party dependency set, shell syntax, and diff checks. Run
`scripts/verify.sh` for the native gates on a host with a compatible iOS platform and
CoreSimulator installation. `swift test` remains the portable native-domain gate.

On the July 24, 2026 verification host, all 13 Swift package tests passed and the app
sources type-checked against the installed iPhoneOS SDK. Xcode 26.6 could enumerate the
project and scheme, but Interface Builder and simulator execution were blocked because
the host had CoreSimulator 1051.49.0 while Xcode required 1051.55.0 and reported the iOS
26.5 platform unavailable to Interface Builder. No simulator or native application
launch was claimed.
