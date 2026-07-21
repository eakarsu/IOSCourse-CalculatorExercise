import Foundation

public enum CalculatorOperator: String, Codable, CaseIterable {
    case add, subtract, multiply, divide
}

public enum CalculatorError: String, Codable, Error, Equatable {
    case divisionByZero
    case malformedInput
    case inputTooLong
}

public struct CalculatorState: Codable, Equatable {
    public var input: String
    public var accumulator: Decimal?
    public var pendingOperator: CalculatorOperator?
    public var lastOperand: Decimal?
    public var error: CalculatorError?
    public var startsNewInput: Bool

    public init(
        input: String = "0",
        accumulator: Decimal? = nil,
        pendingOperator: CalculatorOperator? = nil,
        lastOperand: Decimal? = nil,
        error: CalculatorError? = nil,
        startsNewInput: Bool = true
    ) {
        self.input = input
        self.accumulator = accumulator
        self.pendingOperator = pendingOperator
        self.lastOperand = lastOperand
        self.error = error
        self.startsNewInput = startsNewInput
    }
}

public struct CalculatorEngine {
    public private(set) var state: CalculatorState
    public let maximumInputLength: Int

    public init(state: CalculatorState = CalculatorState(), maximumInputLength: Int = 18) {
        self.state = state
        self.maximumInputLength = maximumInputLength
    }

    public mutating func inputDigit(_ digit: Int) {
        guard (0...9).contains(digit) else { return }
        recoverFromErrorIfNeeded()
        let next = state.startsNewInput || state.input == "0" ? String(digit) : state.input + String(digit)
        guard next.count <= maximumInputLength else { return fail(.inputTooLong) }
        state.input = next
        state.startsNewInput = false
    }

    public mutating func inputDecimalSeparator() {
        recoverFromErrorIfNeeded()
        if state.startsNewInput {
            state.input = "0."
            state.startsNewInput = false
        } else if !state.input.contains(".") {
            guard state.input.count < maximumInputLength else { return fail(.inputTooLong) }
            state.input += "."
        }
    }

    public mutating func select(_ operation: CalculatorOperator) {
        recoverFromErrorIfNeeded()
        guard let value = decimalValue else { return fail(.malformedInput) }
        if let pending = state.pendingOperator, !state.startsNewInput, let lhs = state.accumulator {
            guard let computed = calculate(lhs, value, pending) else { return }
            state.accumulator = computed
            state.input = Self.storageString(computed)
        } else if state.accumulator == nil || !state.startsNewInput {
            state.accumulator = value
        }
        state.pendingOperator = operation
        state.startsNewInput = true
        state.lastOperand = nil
    }

    public mutating func equals() {
        recoverFromErrorIfNeeded()
        guard let operation = state.pendingOperator, let lhs = state.accumulator else { return }
        let rhs: Decimal
        if state.startsNewInput, let repeated = state.lastOperand {
            rhs = repeated
        } else if let value = decimalValue {
            rhs = value
            state.lastOperand = value
        } else {
            return fail(.malformedInput)
        }
        guard let computed = calculate(lhs, rhs, operation) else { return }
        state.accumulator = computed
        state.input = Self.storageString(computed)
        state.startsNewInput = true
    }

    public mutating func toggleSign() {
        recoverFromErrorIfNeeded()
        guard let value = decimalValue else { return fail(.malformedInput) }
        state.input = Self.storageString(-value)
        state.startsNewInput = false
    }

    public mutating func percent() {
        recoverFromErrorIfNeeded()
        guard let value = decimalValue else { return fail(.malformedInput) }
        state.input = Self.storageString(value / 100)
        state.startsNewInput = false
    }

    public mutating func clear() { state = CalculatorState() }

    public var displayStorageValue: String { state.error?.rawValue ?? state.input }

    private var decimalValue: Decimal? { Decimal(string: state.input, locale: Locale(identifier: "en_US_POSIX")) }

    private mutating func calculate(_ lhs: Decimal, _ rhs: Decimal, _ operation: CalculatorOperator) -> Decimal? {
        switch operation {
        case .add: return lhs + rhs
        case .subtract: return lhs - rhs
        case .multiply: return lhs * rhs
        case .divide:
            guard rhs != 0 else { fail(.divisionByZero); return nil }
            return lhs / rhs
        }
    }

    private mutating func recoverFromErrorIfNeeded() {
        if state.error != nil { clear() }
    }

    private mutating func fail(_ error: CalculatorError) {
        state.error = error
        state.input = "0"
        state.accumulator = nil
        state.pendingOperator = nil
        state.lastOperand = nil
        state.startsNewInput = true
    }

    private static func storageString(_ value: Decimal) -> String {
        NSDecimalNumber(decimal: value).stringValue
    }
}

public struct CalculatorStateStore {
    private let defaults: UserDefaults
    private let key: String

    public init(defaults: UserDefaults = .standard, key: String = "calculator.state.v1") {
        self.defaults = defaults
        self.key = key
    }

    public func save(_ state: CalculatorState) throws {
        defaults.set(try JSONEncoder().encode(state), forKey: key)
    }

    public func restore() -> CalculatorState? {
        guard let data = defaults.data(forKey: key) else { return nil }
        return try? JSONDecoder().decode(CalculatorState.self, from: data)
    }

    public func clear() { defaults.removeObject(forKey: key) }
}

public struct CalculatorDisplayFormatter {
    private let formatter: NumberFormatter

    public init(locale: Locale = .current) {
        let formatter = NumberFormatter()
        formatter.locale = locale
        formatter.numberStyle = .decimal
        formatter.usesGroupingSeparator = false
        formatter.maximumFractionDigits = 16
        self.formatter = formatter
    }

    public func string(forStorageValue storage: String) -> String {
        let storageLocale = Locale(identifier: "en_US_POSIX")
        if let value = Decimal(string: storage, locale: storageLocale),
           !storage.hasSuffix("."),
           let localized = formatter.string(from: NSDecimalNumber(decimal: value)) {
            return localized
        }
        return storage.replacingOccurrences(of: ".", with: formatter.decimalSeparator)
    }
}
