# AI Council

## Operating Model

Codex is the primary orchestrator, product owner, and technical lead.

Claude can act as a developer provider when available. Roles are not providers:

- Developer can be Claude, Codex, or a future provider.
- Reviewer can be Codex, Claude, or a future provider.
- Researcher is a role, not synonymous with Claude.

## Provider Status

Current validated state:

- Codex agents: available for orchestration/review.
- Claude Code: installed, authenticated, and usable when executed with adequate
  permissions outside the restricted sandbox.
- Sherpa: not installed; evaluate before adopting.

## Default Workflow

```text
request
-> discovery
-> spec
-> architecture
-> implementation plan
-> implementation
-> review
-> tests
-> evaluation
-> documentation
```

Large features should not be implemented directly from a prompt without a spec.

## Safety Rule

No agent may enable real trading without:

- accepted spec
- passing tests
- broker/local reconciliation
- explicit user approval
- explicit runtime gates

Unavailable providers must be reported as unavailable. The Council must not
fabricate a Claude or Codex verdict.
