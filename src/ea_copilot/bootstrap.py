"""Offline composition root for NFR-01, NFR-02, and M0-M8."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from ea_copilot.adapters.clock_fixed import FixedClock
from ea_copilot.adapters.clock_system import SystemClock
from ea_copilot.adapters.llm_fake import FakeLlmAdapter
from ea_copilot.adapters.m365_fake import FakeM365Adapter
from ea_copilot.adapters.scout_m365 import ScoutM365Adapter
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
from ea_copilot.config import Settings, load_settings
from ea_copilot.orchestrator import RequestOrchestrator
from ea_copilot.ports.clock import ClockPort
from ea_copilot.ports.llm import LlmPort
from ea_copilot.ports.m365 import M365Port
from ea_copilot.services.aliases import AliasDirectory
from ea_copilot.services.audit import AuditStore
from ea_copilot.services.candidates import CandidateStore
from ea_copilot.services.database import Database
from ea_copilot.services.evidence import EvidenceStore
from ea_copilot.services.live_evidence import LiveEvidenceStore
from ea_copilot.services.policy import PolicyService
from ea_copilot.services.profile import ProfileStore
from ea_copilot.services.requests import RequestStore
from ea_copilot.services.scoring import ScoringService
from ea_copilot.services.solver import ConstraintSolver


@dataclass(frozen=True)
class ApplicationRuntime:
    orchestrator: RequestOrchestrator
    database: Database
    m365: M365Port
    llm: LlmPort
    clock: ClockPort
    profiles: ProfileStore
    evidence: EvidenceStore
    candidates: CandidateStore
    pattern: PatternAgent
    preference_review: PreferenceReviewAgent
    evaluation: EvaluationAgent
    live_evidence: LiveEvidenceStore
    live_mode: bool = False
    aliases: AliasDirectory | None = None
    self_identifier: str | None = None


def build_runtime(
    root: Path,
    *,
    settings: Settings | None = None,
    database: Database | None = None,
    clock: ClockPort | None = None,
    m365: M365Port | None = None,
    llm: LlmPort | None = None,
) -> ApplicationRuntime:
    selected = settings or load_settings(root)
    selected_database = database or Database.memory()
    selected_clock = clock or FixedClock(selected.fixed_clock_instant)
    fixtures = root / "tests" / "fixtures"
    selected_m365 = m365 or FakeM365Adapter(
        fixtures / "calendars" / "week_2026_09_14",
        selected_clock,
    )
    selected_llm = llm or FakeLlmAdapter(fixtures / "llm" / "responses.json")
    audit = AuditStore(selected_database)
    requests = RequestStore(selected_database)
    profiles = ProfileStore(
        selected_database,
        fixture_dir=fixtures / "profiles",
        clock=selected_clock,
    )
    evidence = EvidenceStore(selected_database)
    live_evidence = LiveEvidenceStore(selected_database)
    candidates = CandidateStore(selected_database)
    policy_service = PolicyService(root / "config" / "policy.yaml")
    scoring = ScoringService(root / "config" / "weights.yaml", clock=selected_clock)
    intake = IntakeAgent(selected_llm, selected_clock, audit, selected)
    context = ContextAgent(selected_m365, selected_llm, selected_clock, audit)
    priority = PriorityAgent(policy_service, audit, selected_clock)
    scheduling = SchedulingAgent(
        selected_m365,
        ConstraintSolver(settings=selected),
        selected_clock,
        audit,
        selected,
    )
    ranking = RankingAgent(scoring, profiles, selected_m365, audit, selected_clock)
    explanation = ExplanationAgent(selected_llm, selected_clock, audit, scoring)
    workbench = WorkbenchAgent(audit, selected_clock)
    draft_action = DraftActionAgent(selected_m365, audit, selected_clock, selected)
    feedback = FeedbackAgent(evidence, selected_llm, selected_clock, audit)
    pattern = PatternAgent(
        evidence,
        candidates,
        policy_service,
        selected_clock,
        selected,
        audit,
        live_evidence,
    )
    preference_review = PreferenceReviewAgent(candidates, profiles, audit, selected_clock)
    evaluation = EvaluationAgent(audit, evidence, selected_clock)
    orchestrator = RequestOrchestrator(
        intake=intake,
        context=context,
        priority=priority,
        scheduling=scheduling,
        ranking=ranking,
        explanation=explanation,
        workbench=workbench,
        draft_action=draft_action,
        feedback=feedback,
        pattern=pattern,
        preference_review=preference_review,
        evaluation=evaluation,
        profile_store=profiles,
        requests=requests,
        audit=audit,
        clock=selected_clock,
    )
    return ApplicationRuntime(
        orchestrator=orchestrator,
        database=selected_database,
        m365=selected_m365,
        llm=selected_llm,
        clock=selected_clock,
        profiles=profiles,
        evidence=evidence,
        candidates=candidates,
        pattern=pattern,
        preference_review=preference_review,
        evaluation=evaluation,
        live_evidence=live_evidence,
    )


def build_live_runtime(
    root: Path,
    *,
    aliases: AliasDirectory,
    self_identifier: str,
    settings: Settings | None = None,
    database: Database | None = None,
    clock: ClockPort | None = None,
    llm: LlmPort | None = None,
) -> ApplicationRuntime:
    """Build a Scout-backed runtime without copying Scout authentication state."""

    selected_clock = clock or SystemClock()
    adapter = ScoutM365Adapter(selected_clock)
    runtime = build_runtime(
        root,
        settings=settings,
        database=database,
        clock=selected_clock,
        m365=adapter,
        llm=llm,
    )
    return replace(
        runtime,
        live_mode=True,
        aliases=aliases,
        self_identifier=self_identifier,
    )
