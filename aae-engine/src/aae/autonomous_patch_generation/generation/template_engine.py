"""autonomous_patch_generation/generation/template_engine — patch templates."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class PatchTemplate:
    """A named patch template with variable placeholders."""

    name: str
    description: str
    template: str           # ``{variable}`` placeholders
    variables: List[str] = field(default_factory=list)
    language: str = "python"

    def render(self, values: Dict[str, str]) -> str:
        """Substitute *values* into the template."""
        result = self.template
        for key, val in values.items():
            result = result.replace(f"{{{key}}}", val)
        return result

    def missing(self, values: Dict[str, str]) -> List[str]:
        """Return variable names not present in *values*."""
        return [v for v in self.variables if v not in values]


_BUILTIN_TEMPLATES: List[PatchTemplate] = [
    PatchTemplate(
        name="add_type_hint",
        description="Add a type hint to a function parameter",
        template=(
            "def {func_name}({param}: {type_hint}) -> {return_type}:\n"
            "    {body}"
        ),
        variables=["func_name", "param", "type_hint", "return_type", "body"],
    ),
    PatchTemplate(
        name="wrap_try_except",
        description="Wrap a block in try/except",
        template=(
            "try:\n"
            "    {body}\n"
            "except {exception} as exc:\n"
            "    {handler}"
        ),
        variables=["body", "exception", "handler"],
    ),
    PatchTemplate(
        name="add_docstring",
        description="Add a docstring to a function",
        template=(
            'def {func_name}({params}):\n'
            '    """{docstring}"""\n'
            '    {body}'
        ),
        variables=["func_name", "params", "docstring", "body"],
    ),
    PatchTemplate(
        name="replace_hardcoded_secret",
        description="Replace a hardcoded secret with env var lookup",
        template=(
            "import os\n"
            "{var_name} = os.environ.get({env_key!r}, {default!r})"
        ),
        variables=["var_name", "env_key", "default"],
    ),
]


class TemplateEngine:
    """Manage and render :class:`PatchTemplate` objects."""

    def __init__(self) -> None:
        self._templates: Dict[str, PatchTemplate] = {
            t.name: t for t in _BUILTIN_TEMPLATES
        }

    def register(self, template: PatchTemplate) -> None:
        self._templates[template.name] = template

    def get(self, name: str) -> Optional[PatchTemplate]:
        return self._templates.get(name)

    def render(self, name: str, values: Dict[str, str]) -> Optional[str]:
        tpl = self.get(name)
        if not tpl:
            return None
        missing = tpl.missing(values)
        if missing:
            return None
        return tpl.render(values)

    def list_templates(self) -> List[str]:
        return list(self._templates.keys())

    def suggest(self, goal: str) -> List[PatchTemplate]:
        """Suggest templates that may match *goal* via keyword search."""
        goal_lower = goal.lower()
        return [
            t
            for t in self._templates.values()
            if any(kw in goal_lower for kw in t.name.replace("_", " ").split())
        ]
