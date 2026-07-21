import UIKit

final class ViewController: UIViewController {
    private enum AvailabilityState { case restoring, emptyOffline, readyOffline, error }
    @IBOutlet private weak var outputLbl: UILabel!

    private let store = CalculatorStateStore()
    private var engine = CalculatorEngine()
    private let displayFormatter = CalculatorDisplayFormatter()

    override func viewDidLoad() {
        super.viewDidLoad()
        applyAvailability(.restoring)
        applyTestLaunchStateIfRequested()
        if let restored = store.restore() { engine = CalculatorEngine(state: restored) }
        outputLbl.adjustsFontSizeToFitWidth = true
        outputLbl.minimumScaleFactor = 0.35
        outputLbl.isAccessibilityElement = true
        outputLbl.accessibilityLabel = NSLocalizedString("display.accessibility.label", comment: "Calculator display")
        outputLbl.accessibilityHint = NSLocalizedString("offline.accessibility.hint", comment: "Offline behavior")
        outputLbl.accessibilityIdentifier = "calculator.display"
        view.accessibilityIdentifier = "calculator.ready.offline"
        configureAccessibility(in: view)
        NotificationCenter.default.addObserver(self, selector: #selector(saveState), name: UIApplication.didEnterBackgroundNotification, object: nil)
        render()
        applyAvailability(engine.state == CalculatorState() ? .emptyOffline : .readyOffline)
    }

    deinit { NotificationCenter.default.removeObserver(self) }

    @IBAction private func numberPressed(_ button: UIButton) { engine.inputDigit(button.tag); renderAndSave() }
    @IBAction private func onDecimalPressed(_ sender: Any) { engine.inputDecimalSeparator(); renderAndSave() }
    @IBAction private func onClearPressed(_ sender: Any) { engine.clear(); store.clear(); render() }
    @IBAction private func onMinusPressed(_ sender: Any) { engine.toggleSign(); renderAndSave() }
    @IBAction private func onPercentPressed(_ sender: Any) { engine.percent(); renderAndSave() }
    @IBAction private func onDividePressed(_ sender: Any) { select(.divide) }
    @IBAction private func onMultiplyPressed(_ sender: Any) { select(.multiply) }
    @IBAction private func onSubtractPressed(_ sender: Any) { select(.subtract) }
    @IBAction private func onAddPressed(_ sender: Any) { select(.add) }
    @IBAction private func onEqualPressed(_ sender: Any) { engine.equals(); renderAndSave() }

    private func select(_ operation: CalculatorOperator) { engine.select(operation); renderAndSave() }

    private func renderAndSave() { render(); saveState() }

    private func render() {
        if let error = engine.state.error {
            applyAvailability(.error)
            outputLbl.text = NSLocalizedString("error.\(error.rawValue)", comment: "Calculator error")
            outputLbl.accessibilityValue = outputLbl.text
            UIAccessibility.post(notification: .announcement, argument: outputLbl.text)
            return
        }
        let storage = engine.displayStorageValue
        outputLbl.text = displayFormatter.string(forStorageValue: storage)
        outputLbl.accessibilityValue = outputLbl.text
        applyAvailability(engine.state == CalculatorState() ? .emptyOffline : .readyOffline)
    }

    private func applyAvailability(_ state: AvailabilityState) {
        switch state {
        case .restoring: view.accessibilityIdentifier = "calculator.restoring"
        case .emptyOffline: view.accessibilityIdentifier = "calculator.empty.offline"
        case .readyOffline: view.accessibilityIdentifier = "calculator.ready.offline"
        case .error: view.accessibilityIdentifier = "calculator.error"
        }
    }

    private func applyTestLaunchStateIfRequested() {
        let arguments = ProcessInfo.processInfo.arguments
        if arguments.contains("-reset-calculator-state") { store.clear() }
        if arguments.contains("-inject-malformed-calculator-state") {
            UserDefaults.standard.set(Data("malformed".utf8), forKey: "calculator.state.v1")
        }
    }

    private func configureAccessibility(in root: UIView) {
        for case let button as UIButton in root.subviews {
            let actions = button.actions(forTarget: self, forControlEvent: .touchUpInside) ?? []
            let selector = actions.first ?? ""
            if selector.contains("numberPressed") {
                button.accessibilityLabel = String(button.tag)
            } else {
                let key: String?
                if selector.contains("onAdd") { key = "button.add" }
                else if selector.contains("onSubtract") { key = "button.subtract" }
                else if selector.contains("onMultiply") { key = "button.multiply" }
                else if selector.contains("onDivide") { key = "button.divide" }
                else if selector.contains("onEqual") { key = "button.equals" }
                else if selector.contains("onClear") { key = "button.clear" }
                else if selector.contains("onMinus") { key = "button.toggleSign" }
                else if selector.contains("onPercent") { key = "button.percent" }
                else if selector.contains("onDecimal") { key = "button.decimal" }
                else { key = nil }
                if let key { button.accessibilityLabel = NSLocalizedString(key, comment: "Calculator button") }
            }
            button.accessibilityTraits.insert(.button)
        }
        root.subviews.filter { !($0 is UIButton) }.forEach { configureAccessibility(in: $0) }
    }

    @objc private func saveState() { try? store.save(engine.state) }
}
