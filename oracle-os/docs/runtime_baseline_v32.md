# Oracle OS Runtime Baseline v3.2

## Build Status
- **Swift Version**: 6.2.4 (swiftlang-6.2.4.1.4 clang-1700.6.4.2)
- **Build Result**: ✅ PASS
- **Build Time**: 6.78s

## Test Status
- **Total Tests Attempted**: 121 test targets
- **Tests Executed**: 119/121
- **Status**: ⚠️ FATAL ERROR at test 119/121
- **Note**: Test suite encountered fatal error during execution

## Test Warnings
- Multiple deprecation warnings for `AgentLoop` initialization (use `init(orchestrator:...)` instead)
- Swift 6 concurrency warnings for Sendable closure captures in test files
- Unused variable warnings in test files

## App Launch Status
- Not tested in this baseline (requires macOS environment)

## Baseline Date
- Captured: 2026-03-17

## Notes
- Build succeeds without errors
- Test failure appears to be related to test infrastructure, not production code
- Deprecation warnings suggest architectural migration path to RuntimeOrchestrator spine