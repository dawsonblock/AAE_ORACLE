// RuntimeEventBus.swift — Event-driven communication backbone for the runtime.
//
// All subsystems publish structured events rather than calling one another
// directly.  This decouples planner, executor, critic, and world-model while
// keeping a single ordered event stream that can be observed, replayed, or
// fed to an evaluation engine.

import Foundation
import Dispatch

// MARK: - Event Definitions

/// A structured event emitted by any runtime subsystem.
public enum RuntimeEvent: Sendable {
    case taskCreated(TaskEvent)
    case taskStarted(TaskEvent)
    case taskCompleted(TaskEvent)
    case taskFailed(TaskEvent)
    case actionExecuted(ActionEvent)
    case artifactGenerated(ArtifactEvent)
    case stateUpdated(StateUpdateEvent)
    case evaluationFinished(EvaluationEvent)
    case plannerFeedback(PlannerFeedbackEvent)
}

/// Metadata common to every event.
public struct EventMetadata: Sendable {
    public let id: String
    public let timestamp: Date
    public let source: String

    public init(source: String) {
        self.id = UUID().uuidString
        self.timestamp = Date()
        self.source = source
    }
}

public struct TaskEvent: Sendable {
    public let metadata: EventMetadata
    public let taskID: String
    public let taskName: String
    public let status: String

    public init(taskID: String, taskName: String, status: String, source: String) {
        self.metadata = EventMetadata(source: source)
        self.taskID = taskID
        self.taskName = taskName
        self.status = status
    }
}

public struct ActionEvent: Sendable {
    public let metadata: EventMetadata
    public let actionName: String
    public let success: Bool
    public let durationMs: Int

    public init(actionName: String, success: Bool, durationMs: Int, source: String) {
        self.metadata = EventMetadata(source: source)
        self.actionName = actionName
        self.success = success
        self.durationMs = durationMs
    }
}

public struct ArtifactEvent: Sendable {
    public let metadata: EventMetadata
    public let artifactType: String
    public let taskID: String
    public let location: String

    public init(artifactType: String, taskID: String, location: String, source: String) {
        self.metadata = EventMetadata(source: source)
        self.artifactType = artifactType
        self.taskID = taskID
        self.location = location
    }
}

public struct StateUpdateEvent: Sendable {
    public let metadata: EventMetadata
    public let domain: String
    public let changeDescription: String

    public init(domain: String, changeDescription: String, source: String) {
        self.metadata = EventMetadata(source: source)
        self.domain = domain
        self.changeDescription = changeDescription
    }
}

public struct EvaluationEvent: Sendable {
    public let metadata: EventMetadata
    public let taskID: String
    public let score: Double
    public let outcome: String

    public init(taskID: String, score: Double, outcome: String, source: String) {
        self.metadata = EventMetadata(source: source)
        self.taskID = taskID
        self.score = score
        self.outcome = outcome
    }
}

public struct PlannerFeedbackEvent: Sendable {
    public let metadata: EventMetadata
    public let taskID: String
    public let recommendation: String

    public init(taskID: String, recommendation: String, source: String) {
        self.metadata = EventMetadata(source: source)
        self.taskID = taskID
        self.recommendation = recommendation
    }
}

// MARK: - Event Bus

/// Thread-safe, in-process event bus.
///
/// Subsystems register subscribers for specific event types and the bus
/// delivers events asynchronously without coupling producers to consumers.
public final class RuntimeEventBus: @unchecked Sendable {

    public typealias Subscriber = @Sendable (RuntimeEvent) -> Void

    // The handler is stored as @Sendable which the compiler enforces at the
    // call-site.  @unchecked Sendable is safe here because Registration is only
    // read under the bus's NSLock.
    private struct Registration: @unchecked Sendable {
        let id: String
        let handler: Subscriber
    }

    private let lock = NSLock()
    private var registrations: [Registration] = []
    private var eventLog: [RuntimeEvent] = []
    private let maxLogSize: Int
    private let deliveryQueue = DispatchQueue(label: "RuntimeEventBus.deliveryQueue")

    public init(maxLogSize: Int = 1000) {
        // Clamp to a non-negative value to avoid runtime traps when trimming the log.
        self.maxLogSize = max(0, maxLogSize)
    }

    /// Subscribe to all events.  Returns an opaque ID used to unsubscribe.
    @discardableResult
    public func subscribe(_ handler: @escaping Subscriber) -> String {
        let reg = Registration(id: UUID().uuidString, handler: handler)
        lock.lock()
        registrations.append(reg)
        lock.unlock()
        return reg.id
    }

    /// Remove a previously registered subscriber.
    public func unsubscribe(id: String) {
        lock.lock()
        registrations.removeAll { $0.id == id }
        lock.unlock()
    }

    /// Publish an event to all subscribers and append to the event log.
    public func publish(_ event: RuntimeEvent) {
        lock.lock()
        eventLog.append(event)
        if eventLog.count > maxLogSize {
            eventLog.removeFirst(eventLog.count - maxLogSize)
        }
        let current = registrations
        lock.unlock()

        deliveryQueue.sync {
            for reg in current {
                reg.handler(event)
            }
        }
    }

    /// Returns recent events (most recent last), up to `maxLogSize`.
    public func recentEvents() -> [RuntimeEvent] {
        lock.lock()
        defer { lock.unlock() }
        return eventLog
    }
}
