// DomainEvent.swift — Core event protocol for Oracle OS event-sourcing runtime
//
// This file defines the core protocol for all domain events in the system.
// Event sourcing provides durable history where correctness matters,
// allowing reconstruction of committed state from event log.
//
// Core principles:
// - Events are immutable facts about what happened
// - Events are append-only (never modified after creation)
// - State changes derive from applying events through reducers
// - Projections provide queryable views from event stream

import Foundation

/// Base protocol for all domain events in the system.
/// 
/// Domain events represent authoritative facts about state changes.
/// They are the single source of truth for runtime state.
public protocol DomainEvent: Sendable, Codable {
    /// Unique type identifier for the event (e.g., "ActionExecuted")
    var eventType: String { get }
    
    /// Aggregate ID this event belongs to (task ID, session ID, etc.)
    var aggregateId: String { get }
    
    /// Timestamp when the event occurred
    var timestamp: Date { get }
    
    /// Correlation ID links related events in a flow
    var correlationId: UUID { get }
    
    /// Causation ID links to the event that caused this event
    var causationId: UUID? { get }
}

// MARK: - Common Event Types

/// Events emitted during action execution lifecycle
public struct ActionAuthorized: DomainEvent, Sendable, Codable {
    public let aggregateId: String
    public let timestamp: Date
    public let correlationId: UUID
    public let causationId: UUID?
    
    public let intentId: String
    public let actionType: String
    public let target: String?
    public let policyDecision: String
    
    public var eventType: String { "ActionAuthorized" }
    
    public init(
        aggregateId: String,
        correlationId: UUID,
        causationId: UUID? = nil,
        intentId: String,
        actionType: String,
        target: String?,
        policyDecision: String
    ) {
        self.aggregateId = aggregateId
        self.timestamp = Date()
        self.correlationId = correlationId
        self.causationId = causationId
        self.intentId = intentId
        self.actionType = actionType
        self.target = target
        self.policyDecision = policyDecision
    }
}

public struct PreStateObserved: DomainEvent, Sendable, Codable {
    public let aggregateId: String
    public let timestamp: Date
    public let correlationId: UUID
    public let causationId: UUID?
    
    public let observationHash: String
    public let planningStateId: String
    
    public var eventType: String { "PreStateObserved" }
    
    public init(
        aggregateId: String,
        correlationId: UUID,
        causationId: UUID? = nil,
        observationHash: String,
        planningStateId: String
    ) {
        self.aggregateId = aggregateId
        self.timestamp = Date()
        self.correlationId = correlationId
        self.causationId = causationId
        self.observationHash = observationHash
        self.planningStateId = planningStateId
    }
}

public struct ActionExecuted: DomainEvent, Sendable, Codable {
    public let aggregateId: String
    public let timestamp: Date
    public let correlationId: UUID
    public let causationId: UUID?
    
    public let actionType: String
    public let target: String?
    public let method: String
    public let success: Bool
    public let latencyMs: Int
    public let error: String?
    
    public var eventType: String { "ActionExecuted" }
    
    public init(
        aggregateId: String,
        correlationId: UUID,
        causationId: UUID? = nil,
        actionType: String,
        target: String?,
        method: String,
        success: Bool,
        latencyMs: Int,
        error: String? = nil
    ) {
        self.aggregateId = aggregateId
        self.timestamp = Date()
        self.correlationId = correlationId
        self.causationId = causationId
        self.actionType = actionType
        self.target = target
        self.method = method
        self.success = success
        self.latencyMs = latencyMs
        self.error = error
    }
}

public struct PostStateObserved: DomainEvent, Sendable, Codable {
    public let aggregateId: String
    public let timestamp: Date
    public let correlationId: UUID
    public let causationId: UUID?
    
    public let observationHash: String
    public let planningStateId: String
    
    public var eventType: String { "PostStateObserved" }
    
    public init(
        aggregateId: String,
        correlationId: UUID,
        causationId: UUID? = nil,
        observationHash: String,
        planningStateId: String
    ) {
        self.aggregateId = aggregateId
        self.timestamp = Date()
        self.correlationId = correlationId
        self.causationId = causationId
        self.observationHash = observationHash
        self.planningStateId = planningStateId
    }
}

public struct PostconditionVerified: DomainEvent, Sendable, Codable {
    public let aggregateId: String
    public let timestamp: Date
    public let correlationId: UUID
    public let causationId: UUID?
    
    public let postconditions: [String]
    public let allPassed: Bool
    public let failedChecks: [String]
    
    public var eventType: String { "PostconditionVerified" }
    
    public init(
        aggregateId: String,
        correlationId: UUID,
        causationId: UUID? = nil,
        postconditions: [String],
        allPassed: Bool,
        failedChecks: [String] = []
    ) {
        self.aggregateId = aggregateId
        self.timestamp = Date()
        self.correlationId = correlationId
        self.causationId = causationId
        self.postconditions = postconditions
        self.allPassed = allPassed
        self.failedChecks = failedChecks
    }
}

public struct PostconditionFailed: DomainEvent, Sendable, Codable {
    public let aggregateId: String
    public let timestamp: Date
    public let correlationId: UUID
    public let causationId: UUID?
    
    public let failedConditions: [String]
    public let error: String
    
    public var eventType: String { "PostconditionFailed" }
    
    public init(
        aggregateId: String,
        correlationId: UUID,
        causationId: UUID? = nil,
        failedConditions: [String],
        error: String
    ) {
        self.aggregateId = aggregateId
        self.timestamp = Date()
        self.correlationId = correlationId
        self.causationId = causationId
        self.failedConditions = failedConditions
        self.error = error
    }
}

public struct StateDriftDetected: DomainEvent, Sendable, Codable {
    public let aggregateId: String
    public let timestamp: Date
    public let correlationId: UUID
    public let causationId: UUID?
    
    public let expectedState: String
    public let actualState: String
    public let driftDescription: String
    
    public var eventType: String { "StateDriftDetected" }
    
    public init(
        aggregateId: String,
        correlationId: UUID,
        causationId: UUID? = nil,
        expectedState: String,
        actualState: String,
        driftDescription: String
    ) {
        self.aggregateId = aggregateId
        self.timestamp = Date()
        self.correlationId = correlationId
        self.causationId = causationId
        self.expectedState = expectedState
        self.actualState = actualState
        self.driftDescription = driftDescription
    }
}

public struct ArtifactProduced: DomainEvent, Sendable, Codable {
    public let aggregateId: String
    public let timestamp: Date
    public let correlationId: UUID
    public let causationId: UUID?
    
    public let artifactType: String
    public let artifactPath: String
    public let sizeBytes: Int?
    
    public var eventType: String { "ArtifactProduced" }
    
    public init(
        aggregateId: String,
        correlationId: UUID,
        causationId: UUID? = nil,
        artifactType: String,
        artifactPath: String,
        sizeBytes: Int? = nil
    ) {
        self.aggregateId = aggregateId
        self.timestamp = Date()
        self.correlationId = correlationId
        self.causationId = causationId
        self.artifactType = artifactType
        self.artifactPath = artifactPath
        self.sizeBytes = sizeBytes
    }
}

public struct ExecutionFailed: DomainEvent, Sendable, Codable {
    public let aggregateId: String
    public let timestamp: Date
    public let correlationId: UUID
    public let causationId: UUID?
    
    public let failureType: String
    public let error: String
    public let recoveryRequired: Bool
    
    public var eventType: String { "ExecutionFailed" }
    
    public init(
        aggregateId: String,
        correlationId: UUID,
        causationId: UUID? = nil,
        failureType: String,
        error: String,
        recoveryRequired: Bool = true
    ) {
        self.aggregateId = aggregateId
        self.timestamp = Date()
        self.correlationId = correlationId
        self.causationId = causationId
        self.failureType = failureType
        self.error = error
        self.recoveryRequired = recoveryRequired
    }
}

public struct CommandTimedOut: DomainEvent, Sendable, Codable {
    public let aggregateId: String
    public let timestamp: Date
    public let correlationId: UUID
    public let causationId: UUID?
    
    public let commandType: String
    public let timeoutSeconds: Double
    
    public var eventType: String { "CommandTimedOut" }
    
    public init(
        aggregateId: String,
        correlationId: UUID,
        causationId: UUID? = nil,
        commandType: String,
        timeoutSeconds: Double
    ) {
        self.aggregateId = aggregateId
        self.timestamp = Date()
        self.correlationId = correlationId
        self.causationId = causationId
        self.commandType = commandType
        self.timeoutSeconds = timeoutSeconds
    }
}

// MARK: - Recovery Events

public struct RecoveryStarted: DomainEvent, Sendable, Codable {
    public let aggregateId: String
    public let timestamp: Date
    public let correlationId: UUID
    public let causationId: UUID?
    
    public let failureEventId: UUID
    public let recoveryStrategy: String
    
    public var eventType: String { "RecoveryStarted" }
    
    public init(
        aggregateId: String,
        correlationId: UUID,
        causationId: UUID? = nil,
        failureEventId: UUID,
        recoveryStrategy: String
    ) {
        self.aggregateId = aggregateId
        self.timestamp = Date()
        self.correlationId = correlationId
        self.causationId = causationId
        self.failureEventId = failureEventId
        self.recoveryStrategy = recoveryStrategy
    }
}

public struct RecoveryActionExecuted: DomainEvent, Sendable, Codable {
    public let aggregateId: String
    public let timestamp: Date
    public let correlationId: UUID
    public let causationId: UUID?
    
    public let action: String
    public let success: Bool
    public let error: String?
    
    public var eventType: String { "RecoveryActionExecuted" }
    
    public init(
        aggregateId: String,
        correlationId: UUID,
        causationId: UUID? = nil,
        action: String,
        success: Bool,
        error: String? = nil
    ) {
        self.aggregateId = aggregateId
        self.timestamp = Date()
        self.correlationId = correlationId
        self.causationId = causationId
        self.action = action
        self.success = success
        self.error = error
    }
}

public struct RecoverySucceeded: DomainEvent, Sendable, Codable {
    public let aggregateId: String
    public let timestamp: Date
    public let correlationId: UUID
    public let causationId: UUID?
    
    public let attempts: Int
    public let finalState: String
    
    public var eventType: String { "RecoverySucceeded" }
    
    public init(
        aggregateId: String,
        correlationId: UUID,
        causationId: UUID? = nil,
        attempts: Int,
        finalState: String
    ) {
        self.aggregateId = aggregateId
        self.timestamp = Date()
        self.correlationId = correlationId
        self.causationId = causationId
        self.attempts = attempts
        self.finalState = finalState
    }
}

public struct RecoveryEscalated: DomainEvent, Sendable, Codable {
    public let aggregateId: String
    public let timestamp: Date
    public let correlationId: UUID
    public let causationId: UUID?
    
    public let reason: String
    public let escalationLevel: Int
    
    public var eventType: String { "RecoveryEscalated" }
    
    public init(
        aggregateId: String,
        correlationId: UUID,
        causationId: UUID? = nil,
        reason: String,
        escalationLevel: Int
    ) {
        self.aggregateId = aggregateId
        self.timestamp = Date()
        self.correlationId = correlationId
        self.causationId = causationId
        self.reason = reason
        self.escalationLevel = escalationLevel
    }
}

// MARK: - Critic Events

public struct CriticApprovedStep: DomainEvent, Sendable, Codable {
    public let aggregateId: String
    public let timestamp: Date
    public let correlationId: UUID
    public let causationId: UUID?
    
    public let score: Double
    public let reasoning: String
    
    public var eventType: String { "CriticApprovedStep" }
    
    public init(
        aggregateId: String,
        correlationId: UUID,
        causationId: UUID? = nil,
        score: Double,
        reasoning: String
    ) {
        self.aggregateId = aggregateId
        self.timestamp = Date()
        self.correlationId = correlationId
        self.causationId = causationId
        self.score = score
        self.reasoning = reasoning
    }
}

public struct CriticRejectedStep: DomainEvent, Sendable, Codable {
    public let aggregateId: String
    public let timestamp: Date
    public let correlationId: UUID
    public let causationId: UUID?
    
    public let reason: String
    public let suggestion: String?
    
    public var eventType: String { "CriticRejectedStep" }
    
    public init(
        aggregateId: String,
        correlationId: UUID,
        causationId: UUID? = nil,
        reason: String,
        suggestion: String? = nil
    ) {
        self.aggregateId = aggregateId
        self.timestamp = Date()
        self.correlationId = correlationId
        self.causationId = causationId
        self.reason = reason
        self.suggestion = suggestion
    }
}

public struct ReplanRequested: DomainEvent, Sendable, Codable {
    public let aggregateId: String
    public let timestamp: Date
    public let correlationId: UUID
    public let causationId: UUID?
    
    public let reason: String
    public let previousPlanId: String?
    
    public var eventType: String { "ReplanRequested" }
    
    public init(
        aggregateId: String,
        correlationId: UUID,
        causationId: UUID? = nil,
        reason: String,
        previousPlanId: String? = nil
    ) {
        self.aggregateId = aggregateId
        self.timestamp = Date()
        self.correlationId = correlationId
        self.causationId = causationId
        self.reason = reason
        self.previousPlanId = previousPlanId
    }
}

// MARK: - AAE Planning Events (Phase 2: Planning Authority Normalization)

/// Emitted when Oracle asks AAE for advisory candidates
public struct AAEAdviceRequested: DomainEvent, Sendable, Codable {
    public let aggregateId: String
    public let timestamp: Date
    public let correlationId: UUID
    public let causationId: UUID?
    
    /// Goal ID being planned
    public let goalId: String
    
    /// The objective/description of the goal
    public let objective: String
    
    /// Source marker indicating the planning context
    public let sourceMarker: String
    
    /// Number of candidates requested
    public let maxCandidates: Int
    
    public var eventType: String { "AAEAdviceRequested" }
    
    public init(
        aggregateId: String,
        correlationId: UUID,
        causationId: UUID? = nil,
        goalId: String,
        objective: String,
        sourceMarker: String = "oracle_native",
        maxCandidates: Int = 5
    ) {
        self.aggregateId = aggregateId
        self.timestamp = Date()
        self.correlationId = correlationId
        self.causationId = causationId
        self.goalId = goalId
        self.objective = objective
        self.sourceMarker = sourceMarker
        self.maxCandidates = maxCandidates
    }
}

/// Emitted when AAE responds with advisory candidates
public struct AAEAdviceReceived: DomainEvent, Sendable, Codable {
    public let aggregateId: String
    public let timestamp: Date
    public let correlationId: UUID
    public let causationId: UUID?
    
    /// Goal ID that was requested
    public let goalId: String
    
    /// Number of candidates received
    public let candidateCount: Int
    
    /// Candidate IDs received from AAE
    public let candidateIds: [String]
    
    /// Highest predicted score among candidates
    public let highestPredictedScore: Double
    
    /// Source marker from the request
    public let sourceMarker: String
    
    /// Whether validation passed
    public let validationPassed: Bool
    
    /// Number of candidates that passed validation
    public let validCandidateCount: Int
    
    public var eventType: String { "AAEAdviceReceived" }
    
    public init(
        aggregateId: String,
        correlationId: UUID,
        causationId: UUID? = nil,
        goalId: String,
        candidateCount: Int,
        candidateIds: [String],
        highestPredictedScore: Double,
        sourceMarker: String = "oracle_native",
        validationPassed: Bool = true,
        validCandidateCount: Int? = nil
    ) {
        self.aggregateId = aggregateId
        self.timestamp = Date()
        self.correlationId = correlationId
        self.causationId = causationId
        self.goalId = goalId
        self.candidateCount = candidateCount
        self.candidateIds = candidateIds
        self.highestPredictedScore = highestPredictedScore
        self.sourceMarker = sourceMarker
        self.validationPassed = validationPassed
        self.validCandidateCount = validCandidateCount ?? candidateCount
    }
}

/// Emitted when an AAE candidate is selected for execution
public struct AAECandidateAccepted: DomainEvent, Sendable, Codable {
    public let aggregateId: String
    public let timestamp: Date
    public let correlationId: UUID
    public let causationId: UUID?
    
    /// Goal ID for this planning
    public let goalId: String
    
    /// The candidate ID that was accepted
    public let candidateId: String
    
    /// Source marker (aae_advised, oracle_aae_hybrid, etc.)
    public let sourceMarker: String
    
    /// The predicted score of the accepted candidate
    public let predictedScore: Double
    
    /// The fused final score
    public let finalScore: Double
    
    /// Target path hint (if provided)
    public let targetPathHint: String?
    
    /// Recommended test command (if provided)
    public let recommendedTestCommand: String?
    
    public var eventType: String { "AAECandidateAccepted" }
    
    public init(
        aggregateId: String,
        correlationId: UUID,
        causationId: UUID? = nil,
        goalId: String,
        candidateId: String,
        sourceMarker: String,
        predictedScore: Double,
        finalScore: Double,
        targetPathHint: String? = nil,
        recommendedTestCommand: String? = nil
    ) {
        self.aggregateId = aggregateId
        self.timestamp = Date()
        self.correlationId = correlationId
        self.causationId = causationId
        self.goalId = goalId
        self.candidateId = candidateId
        self.sourceMarker = sourceMarker
        self.predictedScore = predictedScore
        self.finalScore = finalScore
        self.targetPathHint = targetPathHint
        self.recommendedTestCommand = recommendedTestCommand
    }
}

/// Emitted when an AAE candidate is rejected
public struct AAECandidateRejected: DomainEvent, Sendable, Codable {
    public let aggregateId: String
    public let timestamp: Date
    public let correlationId: UUID
    public let causationId: UUID?
    
    /// Goal ID for this planning
    public let goalId: String
    
    /// The candidate ID that was rejected
    public let candidateId: String
    
    /// Source marker from the request
    public let sourceMarker: String
    
    /// Reason for rejection
    public let reason: RejectionReason
    
    /// Additional details about the rejection
    public let details: String?
    
    public var eventType: String { "AAECandidateRejected" }
    
    /// Reasons for rejecting an AAE candidate
    public enum RejectionReason: String, Codable, Sendable {
        case validationFailed = "validation_failed"
        case belowThreshold = "below_threshold"
        case noValidCandidates = "no_valid_candidates"
        case unsupportedCandidate = "unsupported_candidate"
        case safetyConcern = "safety_concern"
        case ambiguousObjective = "ambiguous_objective"
        case targetPathMismatch = "target_path_mismatch"
        case oraclePreserved = "oracle_preserved"
    }
    
    public init(
        aggregateId: String,
        correlationId: UUID,
        causationId: UUID? = nil,
        goalId: String,
        candidateId: String,
        sourceMarker: String,
        reason: RejectionReason,
        details: String? = nil
    ) {
        self.aggregateId = aggregateId
        self.timestamp = Date()
        self.correlationId = correlationId
        self.causationId = causationId
        self.goalId = goalId
        self.candidateId = candidateId
        self.sourceMarker = sourceMarker
        self.reason = reason
        self.details = details
    }
}

// MARK: - Phase 3: Path Resolution Events

/// Emitted when the system resolves a target path for skill execution
/// Tracks how path hints flow from AAE → planning → execution
public struct PathResolutionEvent: DomainEvent, Sendable, Codable {
    public let aggregateId: String
    public let timestamp: Date
    public let correlationId: UUID
    public let causationId: UUID?
    
    /// Goal ID for this resolution
    public let goalId: String
    
    /// Source of the path resolution
    /// - "aae_hint": Path came from AAE candidate
    /// - "oracle_query": Path derived from Oracle code query
    /// - "fallback": Fallback path used
    public let source: PathSource
    
    /// What was requested (AAE target path or query)
    public let requestedPath: String?
    
    /// What was actually used after resolution
    public let resolvedPath: String?
    
    /// Resolution status
    /// - "success": Path found and used
    /// - "file_not_found": Requested path doesn't exist, fell back
    /// - "fallback_used": No AAE hints, used Oracle query or fallback
    public let resolutionStatus: ResolutionStatus
    
    /// Candidate ID if from AAE
    public let candidateId: String?
    
    /// Skill name that requested the path
    public let skillName: String?
    
    public var eventType: String { "PathResolutionEvent" }
    
    /// Source of the path resolution
    public enum PathSource: String, Codable, Sendable {
        case aaeHint = "aae_hint"
        case oracleQuery = "oracle_query"
        case fallback = "fallback"
    }
    
    /// Resolution status
    public enum ResolutionStatus: String, Codable, Sendable {
        case success = "success"
        case fileNotFound = "file_not_found"
        case fallbackUsed = "fallback_used"
    }
    
    public init(
        aggregateId: String,
        correlationId: UUID,
        causationId: UUID? = nil,
        goalId: String,
        source: PathSource,
        requestedPath: String?,
        resolvedPath: String?,
        resolutionStatus: ResolutionStatus,
        candidateId: String? = nil,
        skillName: String? = nil
    ) {
        self.aggregateId = aggregateId
        self.timestamp = Date()
        self.correlationId = correlationId
        self.causationId = causationId
        self.goalId = goalId
        self.source = source
        self.requestedPath = requestedPath
        self.resolvedPath = resolvedPath
        self.resolutionStatus = resolutionStatus
        self.candidateId = candidateId
        self.skillName = skillName
    }
}

// MARK: - Phase 6: Observability Fields

/// Shared observability fields for AAE-related events
/// Enables full traceability between Oracle and AAE systems
public struct AAERelatedFields: Codable, Sendable {
    /// Unique ID for the bridge request (correlates Oracle ↔ AAE)
    public let bridgeRequestID: String
    
    /// Goal ID being worked on
    public let goalID: String
    
    /// AAE engine version
    public let aaeEngineVersion: String
    
    /// Candidate being processed
    public let candidateID: String?
    
    /// Source of the selected candidate
    /// - "oracle_native": Oracle's own plan
    /// - "aae_advised": AAE-suggested candidate
    /// - "oracle_aae_hybrid": Fused plan
    public let selectedCandidateSource: String?
    
    /// Execution result
    /// - "success": Candidate executed successfully
    /// - "failure": Execution failed
    /// - "partial": Partial success
    public let executionResult: String?
    
    /// Final fused score after combining Oracle and AAE scores
    public let finalPlanScore: Double?
    
    /// Why candidate was rejected (if applicable)
    public let rejectionReason: String?
    
    public init(
        bridgeRequestID: String,
        goalID: String,
        aaeEngineVersion: String = "1.0.0",
        candidateID: String? = nil,
        selectedCandidateSource: String? = nil,
        executionResult: String? = nil,
        finalPlanScore: Double? = nil,
        rejectionReason: String? = nil
    ) {
        self.bridgeRequestID = bridgeRequestID
        self.goalID = goalID
        self.aaeEngineVersion = aaeEngineVersion
        self.candidateID = candidateID
        self.selectedCandidateSource = selectedCandidateSource
        self.executionResult = executionResult
        self.finalPlanScore = finalPlanScore
        self.rejectionReason = rejectionReason
    }
}

/// Emitted when AAE experiment results are received back from Oracle
/// (Phase 4: Experiment Results Flow)
public struct AAEExperimentResultReceived: DomainEvent, Sendable, Codable {
    public let aggregateId: String
    public let timestamp: Date
    public let correlationId: UUID
    public let causationId: UUID?
    
    /// Goal ID for this experiment
    public let goalId: String
    
    /// Experiment ID
    public let experimentId: String
    
    /// Candidate ID that was tested
    public let candidateId: String
    
    /// Whether the experiment passed (tests succeeded)
    public let experimentPassed: Bool
    
    /// Actual score achieved
    public let actualScore: Double
    
    /// Lift compared to baseline (if available)
    public let scoreLift: Double?
    
    /// Failure classification (if failed)
    public let failureClassification: String?
    
    /// AAE observability fields for correlation
    public let aaeFields: AAERelatedFields?
    
    public var eventType: String { "AAEExperimentResultReceived" }
    
    public init(
        aggregateId: String,
        correlationId: UUID,
        causationId: UUID? = nil,
        goalId: String,
        experimentId: String,
        candidateId: String,
        experimentPassed: Bool,
        actualScore: Double,
        scoreLift: Double? = nil,
        failureClassification: String? = nil,
        aaeFields: AAERelatedFields? = nil
    ) {
        self.aggregateId = aggregateId
        self.timestamp = Date()
        self.correlationId = correlationId
        self.causationId = causationId
        self.goalId = goalId
        self.experimentId = experimentId
        self.candidateId = candidateId
        self.experimentPassed = experimentPassed
        self.actualScore = actualScore
        self.scoreLift = scoreLift
        self.failureClassification = failureClassification
        self.aaeFields = aaeFields
    }
}

/// Emitted when planning decision is made with AAE integration
/// Full observability of the fused planning decision
public struct PlanningDecisionMade: DomainEvent, Sendable, Codable {
    public let aggregateId: String
    public let timestamp: Date
    public let correlationId: UUID
    public let causationId: UUID?
    
    /// Goal ID for this planning
    public let goalId: String
    
    /// Objective being planned
    public let objective: String
    
    /// The decided plan ID
    public let planId: String
    
    /// Source of the plan (oracle_native, aae_advised, hybrid)
    public let planSource: String
    
    /// Oracle's native score for the plan
    public let oracleScore: Double
    
    /// AAE's predicted score (if available)
    public let aaePredictedScore: Double?
    
    /// Final fused score
    public let finalScore: Double
    
    /// Whether AAE advice was used
    public let aaeAdviceUsed: Bool
    
    /// Whether fallback to Oracle-native was required
    public let fallbackUsed: Bool
    
    /// AAE observability fields
    public let aaeFields: AAERelatedFields?
    
    public var eventType: String { "PlanningDecisionMade" }
    
    public init(
        aggregateId: String,
        correlationId: UUID,
        causationId: UUID? = nil,
        goalId: String,
        objective: String,
        planId: String,
        planSource: String,
        oracleScore: Double,
        aaePredictedScore: Double? = nil,
        finalScore: Double,
        aaeAdviceUsed: Bool,
        fallbackUsed: Bool = false,
        aaeFields: AAERelatedFields? = nil
    ) {
        self.aggregateId = aggregateId
        self.timestamp = Date()
        self.correlationId = correlationId
        self.causationId = causationId
        self.goalId = goalId
        self.objective = objective
        self.planId = planId
        self.planSource = planSource
        self.oracleScore = oracleScore
        self.aaePredictedScore = aaePredictedScore
        self.finalScore = finalScore
        self.aaeAdviceUsed = aaeAdviceUsed
        self.fallbackUsed = fallbackUsed
        self.aaeFields = aaeFields
    }
}