import Foundation
public protocol SystemCommand: Command {}
public struct LaunchAppCommand: SystemCommand {
    public let id: CommandID; public let kind = "launchApp"; public let metadata: CommandMetadata
    public let bundleID: String
    public init(id: CommandID = CommandID(), metadata: CommandMetadata, bundleID: String) {
        self.id = id; self.metadata = metadata; self.bundleID = bundleID }
}
public struct OpenURLCommand: SystemCommand {
    public let id: CommandID; public let kind = "openURL"; public let metadata: CommandMetadata
    public let url: URL
    public init(id: CommandID = CommandID(), metadata: CommandMetadata, url: URL) {
        self.id = id; self.metadata = metadata; self.url = url }
}
