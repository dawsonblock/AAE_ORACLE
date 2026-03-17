from __future__ import annotations

import argparse
import json

from aae.integrations.deep_runtime import DeepIntegratedRuntime
from aae.integrations.models import IntegrationTaskRequest


def main() -> None:
    parser = argparse.ArgumentParser(description='Run the deeply integrated local AAE runtime')
    parser.add_argument('--task-id', default='deep-task-1')
    parser.add_argument('--objective', default='research and summarize the repository architecture')
    parser.add_argument('--user-message', default='Analyze the runtime and preserve the useful context.')
    parser.add_argument('--preferred-tool', default=None)
    args = parser.parse_args()

    runtime = DeepIntegratedRuntime()
    result = runtime.run(
        IntegrationTaskRequest(
            task_id=args.task_id,
            objective=args.objective,
            user_message=args.user_message,
            preferred_tool=args.preferred_tool,
        )
    )
    print(json.dumps(result.model_dump(), indent=2))


if __name__ == '__main__':
    main()
