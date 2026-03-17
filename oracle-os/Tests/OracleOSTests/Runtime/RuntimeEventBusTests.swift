import Testing
import Foundation
@testable import OracleOS

/// Thread-safe container using NSLock for testing concurrent access
final class LockedBox<T>: @unchecked Sendable {
    private let lock = NSLock()
    private var _value: T
    
    init(_ value: T) {
        self._value = value
    }
    
    func withValue<R>(_ action: (inout T) -> R) -> R {
        lock.lock()
        defer { lock.unlock() }
        return action(&_value)
    }
}

@Suite("Runtime Event Bus")
struct RuntimeEventBusTests {

    @Test("Subscriber receives published events")
    func basicPubSub() {
        let bus = RuntimeEventBus()
        let receivedBox = LockedBox<[RuntimeEvent]>([])

        bus.subscribe { event in
            receivedBox.withValue { received in
                received.append(event)
            }
        }

        bus.publish(.taskCreated(TaskEvent(
            taskID: "t1", taskName: "Test", status: "created", source: "test"
        )))
        bus.publish(.actionExecuted(ActionEvent(
            actionName: "click", success: true, durationMs: 42, source: "test"
        )))

        let receivedCount = receivedBox.withValue { $0.count }
        #expect(receivedCount == 2)
    }

    @Test("Unsubscribed handler stops receiving")
    func unsubscribe() {
        let bus = RuntimeEventBus()
        let countBox = LockedBox<Int>(0)

        let id = bus.subscribe { _ in
            countBox.withValue { count in
                count += 1
            }
        }
        bus.publish(.stateUpdated(StateUpdateEvent(
            domain: "test", changeDescription: "init", source: "test"
        )))
        let count1 = countBox.withValue { $0 }
        #expect(count1 == 1)

        bus.unsubscribe(id: id)
        bus.publish(.stateUpdated(StateUpdateEvent(
            domain: "test", changeDescription: "second", source: "test"
        )))
        let count2 = countBox.withValue { $0 }
        #expect(count2 == 1)
    }

    @Test("Event log respects max size")
    func eventLogMaxSize() {
        let bus = RuntimeEventBus(maxLogSize: 3)
        for i in 0..<5 {
            bus.publish(.taskCreated(TaskEvent(
                taskID: "t\(i)", taskName: "T\(i)", status: "created", source: "test"
            )))
        }
        #expect(bus.recentEvents().count == 3)
    }

    @Test("EventMetadata populates correctly")
    func metadataFields() {
        let meta = EventMetadata(source: "unit-test")
        #expect(!meta.id.isEmpty)
        #expect(meta.source == "unit-test")
    }

    @Test("Multiple subscribers all receive the same event")
    func multipleSubscribers() {
        let bus = RuntimeEventBus()
        let aBox = LockedBox<Int>(0)
        let bBox = LockedBox<Int>(0)

        bus.subscribe { _ in aBox.withValue { a in a += 1 } }
        bus.subscribe { _ in bBox.withValue { b in b += 1 } }

        bus.publish(.evaluationFinished(EvaluationEvent(
            taskID: "t1", score: 0.9, outcome: "success", source: "test"
        )))

        let finalA = aBox.withValue { $0 }
        let finalB = bBox.withValue { $0 }
        #expect(finalA == 1)
        #expect(finalB == 1)
    }
}
