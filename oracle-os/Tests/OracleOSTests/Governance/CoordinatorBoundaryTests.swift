import Foundation
import Testing
@testable import OracleOS

@Suite("Coordinator Boundary")
struct CoordinatorBoundaryTests {

    // MARK: - DecisionCoordinator does not directly execute actions

    @Test("DecisionCoordinator does not reference execution machinery")
    func decisionCoordinatorDoesNotExecute() throws {
        let url = sourcesRoot().appendingPathComponent(
            "Runtime/Coordinators/DecisionCoordinator.swift",
            isDirectory: false
        )
        let content = try String(contentsOf: url, encoding: .utf8)
        let codeWithoutComments = strippingComments(from: content)
        #expect(
            !content.contains("executionDriver"),
            "DecisionCoordinator must not reference executionDriver"
        )
        #expect(
            !content.contains("Process()"),
            "DecisionCoordinator must not spawn processes"
        )
        #expect(
            !codeWithoutComments.contains("VerifiedActionExecutor"),
            "DecisionCoordinator must not reference VerifiedActionExecutor"
        )
    }

    // MARK: - LearningCoordinator does not directly call the planner

    @Test("LearningCoordinator does not reference planning machinery")
    func learningCoordinatorDoesNotPlan() throws {
        let url = sourcesRoot().appendingPathComponent(
            "Runtime/Coordinators/LearningCoordinator.swift",
            isDirectory: false
        )
        let content = try String(contentsOf: url, encoding: .utf8)
        #expect(
            !content.contains("MainPlanner("),
            "LearningCoordinator must not instantiate Planner"
        )
        #expect(
            !content.contains("PlanGenerator("),
            "LearningCoordinator must not instantiate PlanGenerator"
        )
        #expect(
            !content.contains("DecisionCoordinator("),
            "LearningCoordinator must not instantiate DecisionCoordinator"
        )
    }

    // MARK: - StateCoordinator does not directly call memory stores for recording

    @Test("StateCoordinator does not record to memory stores")
    func stateCoordinatorDoesNotRecordToMemory() throws {
        let url = sourcesRoot().appendingPathComponent(
            "Runtime/Coordinators/StateCoordinator.swift",
            isDirectory: false
        )
        let content = try String(contentsOf: url, encoding: .utf8)
        #expect(
            !content.contains(".recordSuccess"),
            "StateCoordinator must not call .recordSuccess on memory stores"
        )
        #expect(
            !content.contains(".recordFailure"),
            "StateCoordinator must not call .recordFailure on memory stores"
        )
        #expect(
            !content.contains(".recordStrategy"),
            "StateCoordinator must not call .recordStrategy on memory stores"
        )
    }

    // MARK: - No coordinator imports AppKit or SwiftUI

    @Test("No coordinator file imports AppKit or SwiftUI")
    func coordinatorFilesDoNotImportUI() throws {
        let coordinatorsDir = sourcesRoot()
            .appendingPathComponent("Runtime")
            .appendingPathComponent("Coordinators")
        let files = try swiftFiles(in: coordinatorsDir)

        let banned = ["import AppKit", "import SwiftUI"]
        for file in files {
            let content = try String(contentsOf: file, encoding: .utf8)
            let filename = file.lastPathComponent
            for pattern in banned {
                #expect(
                    !content.contains(pattern),
                    "Coordinator file \(filename) must not contain '\(pattern)'"
                )
            }
        }
    }

    // MARK: - Helpers

    private func swiftFiles(in directory: URL) throws -> [URL] {
        guard FileManager.default.fileExists(atPath: directory.path) else { return [] }
        return try FileManager.default.contentsOfDirectory(
            at: directory,
            includingPropertiesForKeys: nil
        ).filter { $0.pathExtension == "swift" }
    }

    /// Returns the given Swift source string with all `//` and `/* */` comments removed.
    private func strippingComments(from source: String) -> String {
        let pattern = #"//.*|/\*[\s\S]*?\*/"#
        guard let regex = try? NSRegularExpression(pattern: pattern, options: []) else {
            return source
        }
        let range = NSRange(source.startIndex..., in: source)
        return regex.stringByReplacingMatches(
            in: source,
            options: [],
            range: range,
            withTemplate: ""
        )
    }

    private func sourcesRoot() -> URL {
        var url = URL(fileURLWithPath: #filePath).deletingLastPathComponent()
        let fileManager = FileManager.default

        while true {
            let packageManifestURL = url.appendingPathComponent("Package.swift")
            if fileManager.fileExists(atPath: packageManifestURL.path) {
                return url.appendingPathComponent("Sources/OracleOS", isDirectory: true)
            }

            let parent = url.deletingLastPathComponent()
            if parent.path == url.path {
                return url.appendingPathComponent("Sources/OracleOS", isDirectory: true)
            }

            url = parent
        }
    }

}
