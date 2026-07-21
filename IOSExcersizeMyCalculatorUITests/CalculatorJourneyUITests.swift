import XCTest

final class CalculatorJourneyUITests: XCTestCase {
    private var app: XCUIApplication!

    override func setUp() {
        super.setUp()
        continueAfterFailure = false
        app = XCUIApplication()
        app.launchArguments = ["-reset-calculator-state"]
    }

    private var displayValue: String? {
        app.staticTexts["calculator.display"].value as? String
    }

    func testPrimaryJourneyAndDivisionByZeroRecovery() {
        app.launch()
        XCTAssertEqual(displayValue, "0")
        app.buttons["8"].tap()
        app.buttons["Divide"].tap()
        app.buttons["0"].tap()
        app.buttons["Equals"].tap()
        XCTAssertEqual(displayValue, "Cannot divide by zero")
        app.buttons["2"].tap()
        XCTAssertEqual(displayValue, "2")
    }

    func testLifecycleRestoresLocalStateWithoutNetwork() {
        app.launch()
        app.buttons["4"].tap()
        app.buttons["2"].tap()
        XCTAssertEqual(displayValue, "42")
        app.terminate()
        app.launchArguments = []
        app.launch()
        XCTAssertEqual(displayValue, "42")
    }

    func testMalformedStoredStateFallsBackToEmptyState() {
        app.launchArguments = ["-inject-malformed-calculator-state"]
        app.launch()
        XCTAssertEqual(displayValue, "0")
    }

    func testLayoutSurvivesRotation() {
        app.launch()
        XCUIDevice.shared.orientation = .landscapeLeft
        XCTAssertTrue(app.staticTexts["calculator.display"].waitForExistence(timeout: 2))
        XCUIDevice.shared.orientation = .portrait
        XCTAssertTrue(app.buttons["Equals"].isHittable)
    }

    func testGermanLocaleUsesLocalizedDecimalSeparator() {
        app.launchArguments += ["-AppleLanguages", "(de)", "-AppleLocale", "de_DE"]
        app.launch()
        app.buttons["1"].tap()
        app.buttons["Decimal separator"].tap()
        app.buttons["5"].tap()
        XCTAssertEqual(displayValue, "1,5")
    }
}
