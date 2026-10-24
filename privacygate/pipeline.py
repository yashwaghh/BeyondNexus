"""Rule-first PII guardrail; intentionally returns no 'guaranteed safe' verdict."""
from __future__ import annotations

from dataclasses import dataclass, asdict
import re

from .detectors import Finding, detect_rules, merge_nonoverlapping
from .model import GemmaLocalClient, LocalModelError

# Context hints are heuristics, not a comprehensive name/address detector.
_CONTEXT_HINTS = re.compile(
    r'\b(?:my name is|i live at|residing at|home address|shipping address|'
    r'full name|father.?s name|mother.?s name|account holder|'
    r'address|नाम|पता|पत्ता|नाव)\b', re.I
)
HIGH_THRESHOLD = 0.90


@dataclass
class Result:
    sanitized_text: str
    findings: list[dict]
    status: str
    requires_human_review: bool
    llm_attempted: bool
    llm_succeeded: bool
    warnings: list[str]
    # No source text or original matched values in finding metadata.

    def to_dict(self) -> dict:
        return asdict(self)


def sanitize(text: str, findings: list[Finding]) -> str:
    chunks: list[str] = []
    cursor = 0
    counters: dict[str, int] = {}
    for finding in findings:
        chunks.append(text[cursor:finding.start])
        counters[finding.entity] = counters.get(finding.entity, 0) + 1
        chunks.append(f'[{finding.entity}_{counters[finding.entity]}]')
        cursor = finding.end
    chunks.append(text[cursor:])
    return ''.join(chunks)


def review_text(text: str, mode: str = 'on-uncertain', model: GemmaLocalClient | None = None,
                max_model_chars: int = 1200) -> Result:
    if mode not in {'off', 'on-uncertain', 'always'}:
        raise ValueError('mode must be off, on-uncertain, or always')
    if not text or not text.strip():
        raise ValueError('Provide nonempty text')
    if len(text) > 50000:
        raise ValueError('Input too large for iteration 1 (50,000 character cap)')
    rule_findings = detect_rules(text)
    uncertain_rules = any(f.confidence < HIGH_THRESHOLD for f in rule_findings)
    has_hints = bool(_CONTEXT_HINTS.search(text))
    llm_needed = mode == 'always' or (mode == 'on-uncertain' and (uncertain_rules or has_hints))
    warnings: list[str] = []
    model_findings: list[Finding] = []
    llm_succeeded = False
    if llm_needed:
        if model is None:
            warnings.append('Local model unavailable: contextual detection incomplete. Do not share without review.')
        elif len(text) > max_model_chars:
            warnings.append('Text exceeds per-call model budget: model skipped; manual review required.')
        else:
            try:
                model_findings = model.detect(text)
                llm_succeeded = True
            except LocalModelError:
                warnings.append('Local model failed or returned invalid output; manual review required.')

    findings = merge_nonoverlapping(rule_findings + model_findings)
    masked_text = sanitize(text, findings)
    needs_review = any(f.confidence < HIGH_THRESHOLD for f in findings)
    if llm_needed and not llm_succeeded:
        status = 'BLOCKED_UNVERIFIED'
    elif needs_review:
        status = 'REVIEW_REQUIRED'
    else:
        status = 'READY_FOR_MANUAL_APPROVAL'

    # With mode off, unknown contextual fields can remain. Never claim privacy safety.
    if mode == 'off' and has_hints:
        status = 'BLOCKED_UNVERIFIED'
        warnings.append('Possible contextual personal information not analyzed by a model.')
    if mode == 'on-uncertain' and not llm_needed:
        warnings.append('No semantic scan was performed: undetected contextual PII may remain.')
    warnings.append('No automated detector guarantees complete removal of personal information.')
    metadata = [
        {'start': f.start, 'end': f.end, 'entity': f.entity, 'score_heuristic': f.confidence,
         'source': f.source, 'rationale': f.rationale,
         'decision': 'mask_and_review' if f.confidence < HIGH_THRESHOLD else 'mask'}
        for f in findings
    ]
    return Result(masked_text, metadata, status, status != 'READY_FOR_MANUAL_APPROVAL',
                  llm_needed, llm_succeeded, warnings)
