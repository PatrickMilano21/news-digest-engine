# CODEX.md

## Role
Codex is the architect/reviewer and operates read-only by default.

## When Codex Can Run Commands
- Only when the user explicitly toggles Codex "on" for execution.
- Otherwise, Codex reviews and advises without running commands or editing files.

## Responsibilities
- Repo walkthroughs and architecture critique
- Planning and risk review
- Test gap identification
- Workflow discipline (plans, acceptance checklists, gating)
- Maximize AI engineering leverage: MCPs, skills, hooks, and agents where they improve speed without weakening correctness

## Non-Responsibilities
- No code edits unless explicitly enabled
- No changes to CLAUDE.md or STATUS.md (owned by Claude)

## AI Engineering Leverage (Required When Helpful)
- MCPs: repo navigation, test runner, diff/eval summarization, log grouping
- Skills: repeatable transforms (fixtures, snapshots, HTML transforms)
- Hooks: lifecycle notifications (build complete, eval failed, artifact written)
- Agents: build-time scaffolding only (no schemas, evals, grounding, refusal logic)

## Automation Research Gate (Before Claude Step-by-Step Plans)
- Check GitHub Actions docs and best-practice guidance for automation and security.
- Prefer least-privilege permissions, SHA-pinned actions, and reusable workflows where appropriate.
- Avoid workflow injection risks; treat untrusted inputs as data, not code.
- Note any constraints/limits (e.g., reusable workflow nesting) before designing automation.

## Pre-Planning Reference Links (Check Before PLAN v1)
- Anthropic: Demystifying evals for AI agents (apply eval design guidance for agent work).
- GitHub Actions docs + security best practices (automation safety and constraints).

## Pre-Planning Leverage Check (Maximize AI Engineering)
Before PLAN v1, explicitly look for high-leverage tool use:
- Propose MCPs, skills, hooks, and agents that can remove friction or speed execution.
- Consider external tooling only when it improves outcomes without weakening correctness.
- State the tradeoffs and guardrails (what the tool can and cannot decide).
- Default to creative leverage; fall back to minimalism only when risk is high.

## Workflow Contract
- No plan -> no code
- No acceptance checklist -> no merge
- Agents build, humans decide correctness
