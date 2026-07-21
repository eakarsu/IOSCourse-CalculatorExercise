import XCTest
@testable import CalculatorCore

final class CalculatorEngineTests: XCTestCase {
    func testAdditionAndChainedOperation() {
        var engine = CalculatorEngine()
        engine.inputDigit(1); engine.inputDigit(2); engine.select(.add); engine.inputDigit(3); engine.equals()
        XCTAssertEqual(engine.state.input, "15")
        engine.select(.multiply); engine.inputDigit(2); engine.equals()
        XCTAssertEqual(engine.state.input, "30")
    }

    func testSubtractionMultiplicationAndDivision() {
        var engine = CalculatorEngine()
        engine.inputDigit(9); engine.select(.subtract); engine.inputDigit(4); engine.equals()
        XCTAssertEqual(engine.state.input, "5")
        engine.select(.multiply); engine.inputDigit(8); engine.equals()
        XCTAssertEqual(engine.state.input, "40")
        engine.select(.divide); engine.inputDigit(5); engine.equals()
        XCTAssertEqual(engine.state.input, "8")
    }

    func testDecimalInputIsExactAndOnlyOneSeparatorIsAccepted() {
        var engine = CalculatorEngine()
        engine.inputDigit(1); engine.inputDecimalSeparator(); engine.inputDigit(2); engine.inputDecimalSeparator(); engine.inputDigit(5)
        engine.select(.add); engine.inputDigit(2); engine.inputDecimalSeparator(); engine.inputDigit(7); engine.inputDigit(5); engine.equals()
        XCTAssertEqual(engine.state.input, "4")
    }

    func testDivisionByZeroProducesRecoverableError() {
        var engine = CalculatorEngine()
        engine.inputDigit(8); engine.select(.divide); engine.inputDigit(0); engine.equals()
        XCTAssertEqual(engine.state.error, .divisionByZero)
        engine.inputDigit(2)
        XCTAssertNil(engine.state.error)
        XCTAssertEqual(engine.state.input, "2")
    }

    func testPercentAndToggleSign() {
        var engine = CalculatorEngine()
        engine.inputDigit(5); engine.inputDigit(0); engine.percent(); XCTAssertEqual(engine.state.input, "0.5")
        engine.toggleSign(); XCTAssertEqual(engine.state.input, "-0.5")
    }

    func testClearReturnsEmptyInitialState() {
        var engine = CalculatorEngine()
        engine.inputDigit(9); engine.select(.add); engine.inputDigit(2); engine.clear()
        XCTAssertEqual(engine.state, CalculatorState())
    }

    func testMalformedRestoredInputFailsSafely() {
        var engine = CalculatorEngine(state: CalculatorState(input: "not-a-number", startsNewInput: false))
        engine.select(.add)
        XCTAssertEqual(engine.state.error, .malformedInput)
    }

    func testInputLengthIsBounded() {
        var engine = CalculatorEngine(maximumInputLength: 3)
        engine.inputDigit(1); engine.inputDigit(2); engine.inputDigit(3); engine.inputDigit(4)
        XCTAssertEqual(engine.state.error, .inputTooLong)
    }

    func testStateRoundTripsForLifecycleRestoration() throws {
        var engine = CalculatorEngine()
        engine.inputDigit(4); engine.inputDigit(2); engine.select(.divide)
        let encoded = try JSONEncoder().encode(engine.state)
        let restored = try JSONDecoder().decode(CalculatorState.self, from: encoded)
        XCTAssertEqual(restored, engine.state)
    }

    func testUserDefaultsStoreRestoresAndClears() throws {
        let suite = "CalculatorEngineTests.\(UUID().uuidString)"
        let defaults = try XCTUnwrap(UserDefaults(suiteName: suite))
        defer { defaults.removePersistentDomain(forName: suite) }
        let store = CalculatorStateStore(defaults: defaults, key: "state")
        let state = CalculatorState(input: "17", accumulator: 17, startsNewInput: false)
        try store.save(state)
        XCTAssertEqual(store.restore(), state)
        store.clear(); XCTAssertNil(store.restore())
    }

    func testRepeatedEqualsUsesLastOperand() {
        var engine = CalculatorEngine()
        engine.inputDigit(2); engine.select(.add); engine.inputDigit(3); engine.equals(); engine.equals()
        XCTAssertEqual(engine.state.input, "8")
    }

    func testOperatorChangeDoesNotUseEmptyOperand() {
        var engine = CalculatorEngine()
        engine.inputDigit(8); engine.select(.add); engine.select(.multiply); engine.inputDigit(2); engine.equals()
        XCTAssertEqual(engine.state.input, "16")
    }

    func testDisplayFormatterUsesRequestedLocaleWithoutChangingStoredValue() {
        let formatter = CalculatorDisplayFormatter(locale: Locale(identifier: "de_DE"))
        XCTAssertEqual(formatter.string(forStorageValue: "12.5"), "12,5")
        XCTAssertEqual(formatter.string(forStorageValue: "0."), "0,")
    }
}
