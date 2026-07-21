// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "CalculatorCore",
    platforms: [.macOS(.v13), .iOS(.v15)],
    products: [.library(name: "CalculatorCore", targets: ["CalculatorCore"])],
    targets: [
        .target(name: "CalculatorCore"),
        .testTarget(name: "CalculatorCoreTests", dependencies: ["CalculatorCore"]),
    ]
)
