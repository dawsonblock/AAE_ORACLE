// MARK: - UICommand
import Foundation

public protocol UICommand: Command {}

public struct ClickElementCommand: UICommand {
    public let id: CommandID
    public let kind = "clickElement"
    public let metadata: CommandMetadata
    public let targetID: String
    public let applicationBundleID: String

    public init(id: CommandID = CommandID(), metadata: CommandMetadata, targetID: String, applicationBundleID: String) {
        self.id = id; self.metadata = metadata; self.targetID = targetID; self.applicationBundleID = applicationBundleID
    }
}

public struct TypeTextCommand: UICommand {
    public let id: CommandID
    public let kind = "typeText"
    public let metadata: CommandMetadata
    public let targetID: String
    public let text: String

    public init(id: CommandID = CommandID(), metadata: CommandMetadata, targetID: String, text: String) {
        self.id = id; self.metadata = metadata; self.targetID = targetID; self.text = text
    }
}

public struct FocusWindowCommand: UICommand {
    public let id: CommandID
    public let kind = "focusWindow"
    public let metadata: CommandMetadata
    public let applicationBundleID: String

    public init(id: CommandID = CommandID(), metadata: CommandMetadata, applicationBundleID: String) {
        self.id = id; self.metadata = metadata; self.applicationBundleID = applicationBundleID
    }
}

public struct ReadElementCommand: UICommand {
    public let id: CommandID
    public let kind = "readElement"
    public let metadata: CommandMetadata
    public let targetID: String

    public init(id: CommandID = CommandID(), metadata: CommandMetadata, targetID: String) {
        self.id = id; self.metadata = metadata; self.targetID = targetID
    }
}
