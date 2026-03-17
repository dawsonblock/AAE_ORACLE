import os

with open("Sources/OracleOS/Runtime/OracleRuntime.swift", "r") as f:
    orig = f.read()

# 1. Extract `executeCodeIntent`
# Find `    public func executeCodeIntent(_ intent: ActionIntent) -> ToolResult {`
start_idx = orig.find('    public func executeCodeIntent(_ intent: ActionIntent) -> ToolResult {')
# Find `public func makeExecutionDriver(`
end_idx = orig.find('    public func makeExecutionDriver(', start_idx)

code_intent_func = orig[start_idx:end_idx]

# Create CodeActionGateway
gateway = f"""import Foundation

@MainActor
public struct CodeActionGateway {{
    public let context: RuntimeContext
    
    public init(context: RuntimeContext) {{
        self.context = context
    }}
    
{code_intent_func.replace("    public func executeCodeIntent", "    public func execute")}
}}
"""

with open("Sources/OracleOS/Runtime/CodeActionGateway.swift", "w") as f:
    f.write(gateway)

# 2. Add CodeActionGateway to RuntimeContext?
# Actually no, we can just instantiate it locally or let RuntimeOrchestrator do `CodeActionGateway(context: self.context).execute(intent)`
# Wait, let's look at `performAction`. `executeCodeIntent` is not called in `OracleRuntime.performAction`. 
# Where is `executeCodeIntent` called? In the skills! e.g., Code skills call it passing the runtime context, or it's called by `agent.execute(...)`

# Remove `executeCodeIntent` from OracleRuntime.swift
new_runtime = orig[:start_idx] + orig[end_idx:]

# Rename OracleRuntime to RuntimeOrchestrator
new_runtime = new_runtime.replace("public final class OracleRuntime {", "public final class RuntimeOrchestrator {")
new_runtime = new_runtime.replace("OracleRuntime", "RuntimeOrchestrator")

# Let's save `RuntimeOrchestrator.swift` and delete `OracleRuntime.swift`
with open("Sources/OracleOS/Runtime/RuntimeOrchestrator.swift", "w") as f:
    f.write(new_runtime)

if os.path.exists("Sources/OracleOS/Runtime/OracleRuntime.swift"):
    os.remove("Sources/OracleOS/Runtime/OracleRuntime.swift")

# 3. Replace usage of OracleRuntime globally
for root, dirs, files in os.walk("Sources"):
    for file in files:
        if file.endswith(".swift"):
            filepath = os.path.join(root, file)
            with open(filepath, "r") as f:
                content = f.read()
            
            # If the file is RuntimeOrchestrator.swift, we don't need to replace, we already did
            if filepath == "Sources/OracleOS/Runtime/RuntimeOrchestrator.swift":
                continue

            new_content = content.replace("OracleRuntime", "RuntimeOrchestrator")
            new_content = new_content.replace("executeCodeIntent", "executeCodeIntent") # not changing the method name yet as I will update callers to use CodeActionGateway
            
            if new_content != content:
                with open(filepath, "w") as f:
                    f.write(new_content)
