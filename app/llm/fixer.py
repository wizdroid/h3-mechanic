"""Preflight Fixer Loop and Integrity Guard (§5.5, §8.0, §9.3).

Executes:
1. Deterministic autofix (Pass 1-5)
2. Checks for unfixable blocking violations (aborts LLM call if present)
3. Integrity Guard: rejects any fixer output that drops, alters, or adds {{Lk}} or {{Tm}} placeholders
4. At most max_retries (default 2)
"""

from __future__ import annotations
import logging
from typing import Any, Optional
import re

from app.validation.autofix import run_deterministic_autofix
from app.validation.registry import default_registry, ValidationContext, Violation
from app.validation.parser import parse_prompt
from app.engine.placeholders import PLACEHOLDER_LK_RE, PLACEHOLDER_TM_RE
from app.llm.client import OllamaClient
from app.llm.prompt_bank import PREFLIGHT_FIXER_PROMPT, calculate_num_predict

logger = logging.getLogger("h3studio.fixer")

def check_placeholder_multiset_equality(orig_text: str, fixed_text: str) -> bool:
    """
    Integrity Guard (§5.5, §8.0):
    Fixer output must contain exactly the same multiset of {{Lk}} and {{Tm}} placeholders.
    """
    orig_lk = sorted(PLACEHOLDER_LK_RE.findall(orig_text))
    fixed_lk = sorted(PLACEHOLDER_LK_RE.findall(fixed_text))
    if orig_lk != fixed_lk:
        return False

    orig_tm = sorted(PLACEHOLDER_TM_RE.findall(orig_text))
    fixed_tm = sorted(PLACEHOLDER_TM_RE.findall(fixed_text))
    if orig_tm != fixed_tm:
        return False

    return True

async def run_fixer_loop(
    ctx: ValidationContext,
    client: OllamaClient,
    model: str,
    max_retries: int = 2,
    temperature: float = 0.2,
    seed: int = 42,
    num_ctx: int = 8192,
) -> tuple[str, list[Violation], int]:
    """
    Run the preflight repair loop per §5.5 and §9.3.
    Returns (final_template_or_body, remaining_violations, retries_used).
    """
    current_body = ctx.parsed_prompt.raw_body
    audio_policy = ctx.clip.get("audio_policy", "dialogue_only")
    mode = ctx.clip.get("mode", "T2VA")

    # Step 1: Deterministic autofix first
    current_body = run_deterministic_autofix(current_body, audio_policy=audio_policy, mode=mode)
    ctx.parsed_prompt = parse_prompt(current_body)
    violations = default_registry.validate_all(ctx)

    blocking = [v for v in violations if v.blocking]
    if not blocking:
        return current_body, violations, 0

    # Step 2: If any blocking violation is unfixable, stop and do NOT call LLM
    unfixable = [v for v in blocking if not v.fixable]
    if unfixable:
        logger.info("Unfixable blocking violations present; skipping LLM fixer (%s)", [u.rule_id for u in unfixable])
        return current_body, violations, 0

    # Step 3: LLM fixer loop
    retries_used = 0
    curr_temp = temperature
    curr_seed = seed

    while retries_used < max_retries:
        blocking = [v for v in violations if v.blocking]
        if not blocking:
            break

        retries_used += 1
        violations_summary = "; ".join(
            f"{v.rule_id} ({v.section}): {v.message}" + (f" (Suggest: '{v.suggested_text}')" if v.suggested_text else "")
            for v in blocking
        )

        prompt_str = PREFLIGHT_FIXER_PROMPT.format(
            mode=mode,
            violations=violations_summary,
        )

        num_predict = calculate_num_predict("preflight_fixer", {"template_text": current_body})
        opts = {
            "temperature": curr_temp,
            "seed": curr_seed,
            "num_ctx": num_ctx,
            "num_predict": num_predict,
        }

        try:
            resp = await client.generate(
                model=model,
                prompt=f"{prompt_str}\n\nTemplate to fix:\n{current_body}",
                options=opts,
            )
            candidate_text = resp.response_text.strip()

            # Step 4: Integrity Guard check
            if not check_placeholder_multiset_equality(current_body, candidate_text):
                logger.warning(
                    "Integrity guard failed: fixer output tampered with placeholders. Discarding attempt %d.",
                    retries_used,
                )
                curr_temp += 0.1
                curr_seed = (curr_seed + 1) % 4294967296
                continue

            # Candidate passed integrity guard: update body and re-validate
            current_body = candidate_text
            ctx.parsed_prompt = parse_prompt(current_body)
            violations = default_registry.validate_all(ctx)

        except Exception as e:
            logger.warning("Fixer attempt %d failed with error: %s", retries_used, str(e))
            curr_temp += 0.1
            curr_seed = (curr_seed + 1) % 4294967296

    return current_body, violations, retries_used
