import Foundation
/// Routes a Command to the correct executor domain.
public enum CommandRouter {
    public enum Domain { case ui, code, system, unknown }
    public static func domain(for command: any Command) -> Domain {
        switch command.kind {
        case "clickElement","typeText","focusWindow","readElement": return .ui
        case "searchRepository","modifyFile","runBuild","runTests","readFile": return .code
        case "launchApp","openURL": return .system
        default: return .unknown
        }
    }
}
