"""Authorized candidate review, profile versioning, and rollback for FR-705..FR-709, INV-3."""

from __future__ import annotations

from ea_copilot.domain.enums import CandidateStatus
from ea_copilot.domain.errors import DecisionValidationError
from ea_copilot.domain.models import (
    ApprovedPreference,
    AuditRecord,
    CandidateRule,
    ExecutiveProfile,
)
from ea_copilot.ports.clock import ClockPort
from ea_copilot.services.audit import AuditStore
from ea_copilot.services.candidates import CandidateStore
from ea_copilot.services.ids import stable_id
from ea_copilot.services.profile import ProfileStore


class PreferenceReviewAgent:
    def __init__(
        self,
        candidates: CandidateStore,
        profile_store: ProfileStore,
        audit: AuditStore,
        clock: ClockPort,
    ) -> None:
        self._candidates = candidates
        self._profiles = profile_store
        self._audit = audit
        self._clock = clock

    def list_candidates(self, executive_upn: str | None = None) -> list[CandidateRule]:
        return self._candidates.list(executive_upn)

    def decide(
        self,
        candidate_id: str,
        actor: str,
        decision: str,
        edits: dict[str, object] | None = None,
    ) -> ApprovedPreference | None:
        candidate = self._candidates.get(candidate_id)
        normalized = decision.lower()
        if normalized == "approve":
            if candidate.status is CandidateStatus.BLOCKED:
                raise DecisionValidationError(
                    f"Candidate conflicts with {candidate.blocked_by_policy_rule}"
                )
            expression = dict(candidate.rule_expression)
            expression.update(edits or {})
            current = self._profiles.current(candidate.executive_upn)
            next_version = f"v{int(current.profile_version.removeprefix('v')) + 1}"
            preference = ApprovedPreference(
                preference_id=stable_id("PREF", candidate.candidate_id),
                executive_upn=candidate.executive_upn,
                profile_version=next_version,
                rule_expression=expression,
                description=candidate.proposed_rule,
                effective_from=self._clock.now(),
                approved_by=actor,
                source_candidate_id=candidate.candidate_id,
            )
            profile = self._profiles.add_preference(preference)
            stored = next(
                item
                for item in profile.preferences
                if item.source_candidate_id == candidate.candidate_id
            )
            candidate = candidate.model_copy(update={"status": CandidateStatus.APPROVED})
            self._candidates.save(candidate)
            outcome = CandidateStatus.APPROVED.value
        else:
            status_by_decision = {
                "edit": CandidateStatus.PROPOSED,
                "reject": CandidateStatus.REJECTED,
                "pause": CandidateStatus.PAUSED,
                "defer": CandidateStatus.DEFERRED,
            }
            if normalized not in status_by_decision:
                raise DecisionValidationError(f"Unsupported candidate decision: {decision}")
            update_values: dict[str, object] = {"status": status_by_decision[normalized]}
            if normalized == "edit" and edits:
                expression = dict(candidate.rule_expression)
                expression.update(edits)
                update_values["rule_expression"] = expression
            candidate = candidate.model_copy(update=update_values)
            self._candidates.save(candidate)
            stored = None
            outcome = candidate.status.value
        evidence_request_id = (
            candidate.evidence.feedback_ids[0]
            if candidate.evidence.feedback_ids
            else candidate.evidence.graph_evidence_ids[0]
        )
        self._audit.append(
            AuditRecord(
                audit_id=stable_id("AUD", candidate_id, "candidate_decision", actor, decision),
                request_id=evidence_request_id,
                actor=actor,
                action="candidate_decided",
                occurred_at=self._clock.now(),
                profile_version=(stored.profile_version if stored else None),
                outcome=outcome,
                payload={
                    "candidate": candidate.model_dump(mode="json"),
                    "approved_preference": stored.model_dump(mode="json") if stored else None,
                },
            )
        )
        return stored

    def rollback(self, executive_upn: str, to_version: str, actor: str) -> ExecutiveProfile:
        profile = self._profiles.rollback(executive_upn, to_version)
        self._audit.append(
            AuditRecord(
                audit_id=stable_id("AUD", executive_upn, "rollback", profile.profile_version),
                request_id=stable_id("PROFILE", executive_upn),
                actor=actor,
                action="profile_rolled_back",
                occurred_at=self._clock.now(),
                profile_version=profile.profile_version,
                outcome=f"restored {to_version}",
                payload={"profile": profile.model_dump(mode="json"), "source_version": to_version},
            )
        )
        return profile
