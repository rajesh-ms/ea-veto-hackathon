---
name: ea-copilot
description: Use when a personal Teams request asks Scout to schedule time with Exec A or Exec B through the local EA Copilot.
---

# EA Copilot Scheduling

Treat every meeting request as a recommendation workflow. The EA decides; Scout gathers delegated context and executes only an approved unsent draft.

## Workflow

1. Keep executive references as `Exec A` and `Exec B` in messages and summaries.
2. Call `ea_submit_request` with the Teams message ID, raw request, and explicit structured fields. Resolve aliases through the local tool; do not display mailbox identities.
3. Use Scout Work IQ read tools for free/busy, working hours, related mail, Teams context, prior meetings, and documents. Pass a bounded structured result to `ea_attach_snapshot`.
4. Call `ea_get_recommendation`. Present candidate slots, constraints, limitations, and preference versions to the EA.
5. Wait for an explicit EA `approve` or `edit` decision, then call `ea_record_decision` with the chosen option.
6. Call `ea_prepare_draft`. A successful result contains an approval-bound, one-time command.
7. Ask for action-time confirmation to create the real Microsoft 365 draft. Continue only after the human confirms in the current interaction.
8. Call `workiq_create_event` once using the command values. Set `subject` to `[DEMO] Executive scheduling prototype`, `draft` to the boolean `true`, and `attendees` to a one-item list containing the signed-in user.
9. Call `ea_complete_draft` with the command ID, transaction ID, Graph event ID, web link, and `draft: true`.
10. Report that the event is saved as an unsent draft for review in Outlook.

## Hard boundary

- Calendar reads may precede approval; calendar mutation begins only after the approval-bound command and action-time confirmation.
- The permitted Microsoft 365 mutation is `workiq_create_event` with `draft: true`. Do not call event update, delete, cancel, move, accept, decline, or send tools.
- If `draft: true` cannot be supplied or verified, stop before the Graph call.
- Graph-derived preferences remain evidence. Only an EA-approved profile version may influence ranking.
- Surface access denial as a limitation. Never substitute fixture data while claiming live results.
