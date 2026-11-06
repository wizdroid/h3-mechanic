"""Canonical rule registry and standardized violation schemas for H3 Prompt Studio (§1.5, §9.4)."""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Optional, Type
from app.validation.parser import ParsedPrompt

@dataclass
class Violation:
    rule_id: str
    section: str
    severity: str  # "error" | "warning"
    basis: str  # "structural" | "heuristic"
    message: str
    suggested_text: Optional[str] = None
    blocking: bool = True
    fixable: bool = False
    overridable: bool = False
    overridden: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass
class ValidationContext:
    clip: dict[str, Any]
    parsed_prompt: ParsedPrompt
    prompt: Optional[dict[str, Any]] = None
    lines: list[dict[str, Any]] = field(default_factory=list)
    speakers: list[dict[str, Any]] = field(default_factory=list)
    subjects: list[dict[str, Any]] = field(default_factory=list)
    subject_pictures: list[dict[str, Any]] = field(default_factory=list)
    references: list[dict[str, Any]] = field(default_factory=list)
    shots: list[dict[str, Any]] = field(default_factory=list)
    overrides: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

class BaseRule:
    rule_id: str = "PF-00"
    name: str = "Base Rule"
    default_severity: str = "error"  # "error" | "warning"
    basis: str = "structural"  # "structural" | "heuristic"
    fixable: bool = False
    overridable: bool = False

    def validate(self, ctx: ValidationContext) -> list[Violation]:
        raise NotImplementedError

    def make_violation(
        self,
        ctx: ValidationContext,
        section: str,
        message: str,
        severity: Optional[str] = None,
        suggested_text: Optional[str] = None,
        blocking: Optional[bool] = None,
        fixable: Optional[bool] = None,
    ) -> Violation:
        sev = severity or self.default_severity
        is_overridden = False
        if self.overridable and self.rule_id in ctx.overrides:
            is_overridden = True

        is_fixable = self.fixable if fixable is None else fixable
        is_blocking = (sev == "error" and not is_overridden) if blocking is None else blocking

        return Violation(
            rule_id=self.rule_id,
            section=section,
            severity=sev,
            basis=self.basis,
            message=message,
            suggested_text=suggested_text,
            blocking=is_blocking,
            fixable=is_fixable,
            overridable=self.overridable,
            overridden=is_overridden,
        )

class RuleRegistry:
    def __init__(self) -> None:
        self._rules: dict[str, BaseRule] = {}

    def register(self, rule_cls: Type[BaseRule]) -> None:
        rule_instance = rule_cls()
        self._rules[rule_instance.rule_id] = rule_instance

    def get_rule(self, rule_id: str) -> Optional[BaseRule]:
        return self._rules.get(rule_id)

    def list_rules(self) -> list[BaseRule]:
        return list(self._rules.values())

    def validate_all(self, ctx: ValidationContext) -> list[Violation]:
        violations: list[Violation] = []
        for rule in self._rules.values():
            try:
                res = rule.validate(ctx)
                if res:
                    violations.extend(res)
            except Exception as e:
                # Catch unexpected rule failure as blocking structural violation
                violations.append(
                    Violation(
                        rule_id=rule.rule_id,
                        section="preflight",
                        severity="error",
                        basis="structural",
                        message=f"Validator internal error in {rule.rule_id}: {str(e)}",
                        blocking=True,
                        fixable=False,
                        overridable=False,
                    )
                )
        return violations

# Global default registry
default_registry = RuleRegistry()
