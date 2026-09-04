"""Candidate-rule proposal and policy validation for FR-703, FR-704, FR-711, FR-905."""

from __future__ import annotations

from datetime import timedelta

from ea_copilot.config import Settings
from ea_copilot.domain.enums import CandidateStatus
from ea_copilot.domain.live_models import GraphPreferenceEvidence
from ea_copilot.domain.models import AuditRecord, CandidateRule, PatternEvidence
from ea_copilot.ports.clock import ClockPort
from ea_copilot.services.audit import AuditStore
from ea_copilot.services.candidates import CandidateStore
from ea_copilot.services.evidence import EvidenceStore
from ea_copilot.services.ids import stable_id
from ea_copilot.services.live_evidence import LiveEvidenceStore
from ea_copilot.services.patterns import detect_candidates
from ea_copilot.services.policy import PolicyService


class PatternAgent:
    def __init__(
        self,
        evidence: EvidenceStore,
        candidates: CandidateStore,
        policy: PolicyService,
        clock: ClockPort,
        settings: Settings,
        audit: AuditStore,
        live_evidence: LiveEvidenceStore | None = None,
    ) -> None:
        self._evidence = evidence
        self._candidates = candidates
        self._policy = policy
        self._clock = clock
        self._settings = settings
        self._audit = audit
        self._live_evidence = live_evidence

    def validate(self, candidate: CandidateRule) -> CandidateRule:
        conflict = self._policy.conflicting_rule(candidate)
        validated = candidate.model_copy(
            update={
                "status": CandidateStatus.BLOCKED if conflict else CandidateStatus.PROPOSED,
                "blocked_by_policy_rule": conflict,
            }
        )
        self._candidates.save(validated)
        return validated

    def detect(self, executive_upn: str) -> list[CandidateRule]:
        now = self._clock.now()
        evidence = self._evidence.in_window(
            executive_upn,
            now - timedelta(days=self._settings.pattern_window_days),
            now,
        )
        proposed = detect_candidates(
            evidence,
            executive_upn=executive_upn,
            threshold=self._settings.pattern_threshold,
            window_days=self._settings.pattern_window_days,
            created_at=now,
        )
        result = [self.validate(candidate) for candidate in proposed]
        for candidate in result:
            self._audit.append(
                AuditRecord(
                    audit_id=stable_id("AUD", candidate.candidate_id, "candidate"),
                    request_id=candidate.evidence.feedback_ids[0],
                    actor="agent:a10_pattern",
                    action="candidate_rule_proposed",
                    occurred_at=now,
                    outcome=candidate.status.value,
                    payload={"candidate": candidate.model_dump(mode="json")},
                )
            )
        return result

    def detect_graph(self, executive_upn: str) -> list[CandidateRule]:
        if self._live_evidence is None:
            return []
        now = self._clock.now()
        evidence = self._live_evidence.in_window(
            executive_upn,
            now - timedelta(days=self._settings.pattern_window_days),
            now,
        )
        groups: dict[tuple[str, str], list[GraphPreferenceEvidence]] = {}
        for item in evidence:
            groups.setdefault((item.dimension, item.value), []).append(item)
        result: list[CandidateRule] = []
        for (dimension, value), raw_items in sorted(groups.items()):
            items = sorted(raw_items, key=lambda item: item.evidence_id)
            if len(items) < self._settings.pattern_threshold:
                continue
            graph_ids = [item.evidence_id for item in items]
            if dimension == "time_of_day" and value == "tuesday_after_12":
                description = "Prefer Tuesday meetings at or after 12:00."
                expression: dict[str, object] = {
                    "kind": "avoid_before",
                    "day": "tuesday",
                    "hour": 12,
                }
            else:
                description = f"Prefer Graph pattern {dimension}: {value}."
                expression = {"kind": dimension, "value": value}
            candidate = CandidateRule(
                candidate_id=stable_id("CAND", "graph", executive_upn, dimension, value),
                executive_upn=executive_upn,
                proposed_rule=description,
                rule_expression=expression,
                evidence=PatternEvidence(
                    feedback_ids=[],
                    graph_evidence_ids=graph_ids,
                    observation=(
                        f"{len(items)} consistent Graph observations within "
                        f"{self._settings.pattern_window_days} days."
                    ),
                    occurrences=len(items),
                    window_days=self._settings.pattern_window_days,
                ),
                confidence=round(len(items) / max(1, len(evidence)), 3),
                projected_impact="Future matching options would rank after the preferred window.",
                exceptions=["Enterprise policy and hard constraints always take precedence."],
                created_at=now,
            )
            validated = self.validate(candidate)
            result.append(validated)
            self._audit.append(
                AuditRecord(
                    audit_id=stable_id("AUD", validated.candidate_id, "graph_candidate"),
                    request_id=graph_ids[0],
                    actor="agent:a10_pattern",
                    action="candidate_rule_proposed",
                    occurred_at=now,
                    outcome=validated.status.value,
                    evidence_refs=graph_ids,
                    payload={"candidate": validated.model_dump(mode="json")},
                )
            )
        return result
