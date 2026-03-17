import Foundation
public protocol CodeCommand: Command {}
public struct SearchRepositoryCommand: CodeCommand {
    public let id: CommandID; public let kind = "searchRepository"; public let metadata: CommandMetadata
    public let query: String; public let maxResults: Int
    public init(id: CommandID = CommandID(), metadata: CommandMetadata, query: String, maxResults: Int = 20) {
        self.id = id; self.metadata = metadata; self.query = query; self.maxResults = maxResults }
}
public struct ModifyFileCommand: CodeCommand {
    public let id: CommandID; public let kind = "modifyFile"; public let metadata: CommandMetadata
    public let filePath: String; public let patch: String
    public init(id: CommandID = CommandID(), metadata: CommandMetadata, filePath: String, patch: String) {
        self.id = id; self.metadata = metadata; self.filePath = filePath; self.patch = patch }
}
public struct RunBuildCommand: CodeCommand {
    public let id: CommandID; public let kind = "runBuild"; public let metadata: CommandMetadata
    public let workspacePath: String
    public init(id: CommandID = CommandID(), metadata: CommandMetadata, workspacePath: String) {
        self.id = id; self.metadata = metadata; self.workspacePath = workspacePath }
}
public struct RunTestsCommand: CodeCommand {
    public let id: CommandID; public let kind = "runTests"; public let metadata: CommandMetadata
    public let filter: String?
    public init(id: CommandID = CommandID(), metadata: CommandMetadata, filter: String? = nil) {
        self.id = id; self.metadata = metadata; self.filter = filter }
}
public struct ReadFileCommand: CodeCommand {
    public let id: CommandID; public let kind = "readFile"; public let metadata: CommandMetadata
    public let filePath: String
    public init(id: CommandID = CommandID(), metadata: CommandMetadata, filePath: String) {
        self.id = id; self.metadata = metadata; self.filePath = filePath }
}
