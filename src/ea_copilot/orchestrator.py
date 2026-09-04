"""Request pipeline boundary for FR-101..FR-107, FR-201..FR-205, and INV-1."""

from __future__ import annotations

import json
from datetime import datetime

from ea_copilot.agents.a01_intake import IntakeAgent
from ea_copilot.agents.a02_context import ContextAgent
from ea_copilot.agents.a03_priority import PriorityAgent
from ea_copilot.agents.a04_scheduling import SchedulingAgent
from ea_copilot.agents.a05_ranking import RankingAgent
from ea_copilot.agents.a06_explanation import ExplanationAgent
from ea_copilot.agents.a07_workbench import WorkbenchAgent
from ea_copilot.agents.a08_draft_action import DraftActionAgent
from ea_copilot.agents.a09_feedback import FeedbackAgent
from ea_copilot.agents.a10_pattern import PatternAgent
from ea_copilot.agents.a11_preference_review import PreferenceReviewAgent
from ea_copilot.agents.a12_evaluation import EvaluationAgent
from ea_copilot.domain.enums import EADecision, ReasonCode, RequestStatus
from ea_copilot.domain.live_models import DraftCommand, DraftCompletion, DraftSubmission
from ea_copilot.domain.models import (
    ApprovalEvent,
    ApprovedPreference,
    CandidateRule,
    ContextPackage,
    DraftEvent,
    EvaluationSummary,
    ExecutiveProfile,
    FeasibleSet,
    FeedbackEvent,
    MeetingRequest,
    QualificationResult,
    RecommendationPacket,
    Requester,
)
from ea_copilot.domain.state_machine import transition
from ea_copilot.ports.clock import ClockPort
from ea_copilot.services.audit import AuditStore
from ea_copilot.services.ids import stable_id
from ea_copilot.services.profile import ProfileStore
from ea_copilot.services.requests import RequestStore


class RequestOrchestrator:
    def __init__(
        self,
        *,
        intake: IntakeAgent,
        context: ContextAgent,
        priority: PriorityAgent,
        scheduling: SchedulingAgent,
        ranking: RankingAgent,
        explanation: ExplanationAgent,
        workbench: WorkbenchAgent,
        draft_action: DraftActionAgent,
        feedback: FeedbackAgent,
        pattern: PatternAgent,
        preference_review: PreferenceReviewAgent,
        evaluation: EvaluationAgent,
        profile_store: ProfileStore,
        requests: RequestStore,
        audit: AuditStore,
        clock: ClockPort,
    ) -> None:
        self._intake = intake
        self._context = context
        self._priority = priority
        self._scheduling = scheduling
        self._ranking = ranking
        self._explanation = explanation
        self._workbench = workbench
        self._draft_action = draft_action
        self._feedback = feedback
        self._pattern = pattern
        self._preference_review = preference_review
        self._evaluation = evaluation
        self._profiles = profile_store
        self._requests = requests
        self.audit = audit
        self._clock = clock
        self._qualifications: dict[str, QualificationResult] = {}
        self._contexts: dict[str, ContextPackage] = {}
        self._feasible_sets: dict[str, FeasibleSet] = {}
        self._recommendations: dict[str, RecommendationPacket] = {}
        self._feedback_by_recommendation: dict[str, FeedbackEvent] = {}
        self._request_recommendations: dict[str, list[str]] = {}
        self._status_history: dict[str, list[RequestStatus]] = {}
        self.structured_logs: list[str] = []

    def _log(self, agent: str, request_id: str, outcome: str) -> None:
        self.structured_logs.append(
            json.dumps(
                {"agent": agent, "outcome": outcome, "request_id": request_id},
                separators=(",", ":"),
                sort_keys=True,
            )
        )

    def submit(
        self,
        raw_text: str,
        requester: Requester,
        *,
        structured_fields: dict[str, object] | None = None,
    ) -> MeetingRequest:
        sequence = self._requests.count() + 1
        request = MeetingRequest(
            request_id=stable_id("MR", sequence, requester.entra_object_id, raw_text),
            created_at=self._clock.now(),
            requester=requester,
            raw_text=raw_text,
        )
        request = self._intake.extract(request, structured_fields)
        self._requests.save(request)
        self._status_history[request.request_id] = [RequestStatus.DRAFT]
        self._intake.audit_transition(request, "request_submitted", RequestStatus.DRAFT.value)
        return self._apply_qualification(request)

    def _apply_qualification(self, request: MeetingRequest) -> MeetingRequest:
        result = self._intake.qualify(request)
        if result.rejection_reason:
            target = RequestStatus.REJECTED
        elif result.is_qualified:
            target = RequestStatus.QUALIFIED
        else:
            target = RequestStatus.NEEDS_INFO
        request = request.model_copy(update={"status": transition(request.status, target)})
        self._requests.save(request)
        self._qualifications[request.request_id] = result
        self._status_history[request.request_id].append(target)
        self._intake.audit_transition(request, "request_qualified", target.value)
        self._log("a01_intake", request.request_id, target.value)
        return request

    def answer(self, request_id: str, answers: dict[str, str]) -> MeetingRequest:
        request = self._requests.get(request_id)
        draft = request.model_copy(
            update={"status": transition(request.status, RequestStatus.DRAFT)}
        )
        self._status_history[request_id].append(RequestStatus.DRAFT)
        merged = self._intake.merge_answers(draft, answers)
        self._requests.save(merged)
        self._intake.audit_transition(merged, "request_answers_merged", RequestStatus.DRAFT.value)
        return self._apply_qualification(merged)

    def qualification_for(self, request_id: str) -> QualificationResult:
        return self._qualifications[request_id]

    def build_context(self, request_id: str) -> ContextPackage:
        request = self._requests.get(request_id)
        if request.status is not RequestStatus.QUALIFIED:
            raise ValueError("Context can be built only for a qualified request")
        context = self._context.build(request)
        self._contexts[request_id] = context
        self._log("a02_context", request_id, f"{len(context.items)} items")
        return context

    def request(self, request_id: str) -> MeetingRequest:
        return self._requests.get(request_id)

    def status_history(self, request_id: str) -> list[RequestStatus]:
        return list(self._status_history[request_id])

    def build_recommendation(self, request_id: str) -> RecommendationPacket:
        request = self._requests.get(request_id)
        if request.status not in {RequestStatus.QUALIFIED, RequestStatus.AWAITING_EA_REVIEW}:
            raise ValueError("A recommendation requires a qualified request")
        context = self._contexts.get(request_id) or self.build_context(request_id)
        priority = self._priority.recommend(request, context)
        self._log("a03_priority", request_id, priority.tier.value)
        feasible = self._scheduling.solve(request)
        self._log("a04_scheduling", request_id, f"{len(feasible.feasible)} feasible")
        options = self._ranking.rank(feasible, request, priority, context)
        self._log("a05_ranking", request_id, f"{len(options)} options")
        executive = request.requested_executives[0]
        profile_version = self._profiles.current(executive).profile_version
        generation = len(self._request_recommendations.get(request_id, [])) + 1
        packet = self._explanation.compose(
            request=request,
            options=options,
            feasible=feasible,
            priority=priority,
            context=context,
            profile_version=profile_version,
            generation=generation,
        )
        self._log("a06_explanation", request_id, packet.recommendation_id)
        target = RequestStatus.AWAITING_EA_REVIEW
        request = request.model_copy(update={"status": transition(request.status, target)})
        self._requests.save(request)
        self._status_history[request_id].append(target)
        self._feasible_sets[request_id] = feasible
        self._recommendations[packet.recommendation_id] = packet
        self._request_recommendations.setdefault(request_id, []).append(packet.recommendation_id)
        self._workbench.register(packet)
        self._draft_action.register(packet, request)
        return packet

    def feasible_for(self, request_id: str) -> FeasibleSet:
        return self._feasible_sets[request_id]

    def context_for(self, request_id: str) -> ContextPackage:
        return self._contexts[request_id]

    def recommendation(self, recommendation_id: str) -> RecommendationPacket:
        return self._recommendations[recommendation_id]

    def latest_recommendation(self, request_id: str) -> RecommendationPacket:
        recommendation_id = self._request_recommendations[request_id][-1]
        return self._recommendations[recommendation_id]

    def solve_request(self, request_id: str) -> FeasibleSet:
        return self._scheduling.solve(self._requests.get(request_id))

    def decide(
        self,
        recommendation_id: str,
        actor: str,
        decision: EADecision,
        *,
        chosen_option_id: str | None = None,
        edits: dict[str, object] | None = None,
        comment: str | None = None,
        reason_code: ReasonCode | None = None,
        free_text: str | None = None,
    ) -> ApprovalEvent:
        approval = self._workbench.decide(
            recommendation_id,
            actor,
            decision,
            chosen_option_id,
            edits,
            comment,
        )
        request = self._requests.get(approval.request_id)
        packet = self._recommendations[recommendation_id]
        self._log("a07_workbench", request.request_id, decision.value)
        feedback = self._feedback.capture(
            approval,
            packet,
            request,
            reason_code,
            free_text,
        )
        self._feedback_by_recommendation[recommendation_id] = feedback
        self._log("a09_feedback", request.request_id, "captured")
        target = {
            EADecision.APPROVE: RequestStatus.APPROVED,
            EADecision.EDIT: RequestStatus.APPROVED,
            EADecision.REJECT: RequestStatus.REJECTED,
            EADecision.RETURN_FOR_INFO: RequestStatus.NEEDS_INFO,
            EADecision.REGENERATE: RequestStatus.AWAITING_EA_REVIEW,
        }[decision]
        updates: dict[str, object] = {"status": transition(request.status, target)}
        if decision is EADecision.REGENERATE:
            earliest = (edits or {}).get("earliest")
            if isinstance(earliest, str):
                updates["earliest"] = datetime.fromisoformat(earliest.replace("Z", "+00:00"))
        request = request.model_copy(update=updates)
        self._requests.save(request)
        self._status_history[request.request_id].append(target)
        if decision is EADecision.REGENERATE:
            self.build_recommendation(request.request_id)
        return approval

    def create_draft(self, recommendation_id: str, actor: str) -> DraftSubmission:
        draft = self._draft_action.create_draft(recommendation_id, actor)
        request = self._requests.get(draft.request_id)
        if isinstance(draft, DraftCommand):
            if request.status is RequestStatus.APPROVED:
                request = request.model_copy(
                    update={"status": transition(request.status, RequestStatus.DRAFT_PENDING)}
                )
                self._requests.save(request)
                self._status_history[request.request_id].append(RequestStatus.DRAFT_PENDING)
            self._log("a08_draft_action", request.request_id, "pending_execution")
            return draft
        request = request.model_copy(
            update={"status": transition(request.status, RequestStatus.DRAFT_CREATED)}
        )
        self._requests.save(request)
        self._status_history[request.request_id].append(RequestStatus.DRAFT_CREATED)
        self._log("a08_draft_action", request.request_id, "unsent")
        return draft

    def complete_draft(self, completion: DraftCompletion) -> DraftEvent:
        draft = self._draft_action.complete_draft(completion)
        request = self._requests.get(draft.request_id)
        if request.status is RequestStatus.DRAFT_CREATED:
            return draft
        request = request.model_copy(
            update={"status": transition(request.status, RequestStatus.DRAFT_CREATED)}
        )
        self._requests.save(request)
        self._status_history[request.request_id].append(RequestStatus.DRAFT_CREATED)
        self._log("a08_draft_action", request.request_id, "unsent")
        return draft

    def feedback_for(self, recommendation_id: str) -> FeedbackEvent:
        return self._feedback_by_recommendation[recommendation_id]

    def detect_patterns(self, executive_upn: str) -> list[CandidateRule]:
        candidates = self._pattern.detect(executive_upn)
        self._log(
            "a10_pattern",
            stable_id("PROFILE", executive_upn),
            f"{len(candidates)} candidates",
        )
        return candidates

    def list_candidates(self, executive_upn: str | None = None) -> list[CandidateRule]:
        return self._preference_review.list_candidates(executive_upn)

    def decide_candidate(
        self,
        candidate_id: str,
        actor: str,
        decision: str,
        *,
        edits: dict[str, object] | None = None,
    ) -> ApprovedPreference | None:
        preference = self._preference_review.decide(candidate_id, actor, decision, edits)
        self._log("a11_preference_review", candidate_id, decision)
        return preference

    def rollback_profile(
        self,
        executive_upn: str,
        to_version: str,
        actor: str,
    ) -> ExecutiveProfile:
        return self._preference_review.rollback(executive_upn, to_version, actor)

    def metrics_summary(self) -> EvaluationSummary:
        return self._evaluation.summary()
