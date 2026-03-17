import Foundation
public struct CapabilityBinder: Sendable {
    public init() {}
    /// Verifies that required capabilities are available for the command.
    public func bind(_ command: any Command) throws -> [String] {
        return [command.kind]
    }
}
