---
description: Implement a ready GitHub issue with the Dev agent (ready → in-review)
argument-hint: "[#<issue-number>]"
---

Act as the Dev agent in **implement mode**: read `.claude/agents/dev.md` and `CLAUDE.md`, then follow the implement-mode steps.

Issue: $ARGUMENTS

- If an issue number was given, implement that issue. It must be labelled `status:ready` (or `status:in-progress` with Reviewer feedback to address); otherwise stop and tell me.
- If no issue number was given, pick the next one yourself:
  1. Issues labelled `status:in-progress` with unaddressed Reviewer feedback come first.
  2. Otherwise, take the lowest-numbered `status:ready` issue whose `Depends on #n` issues are all closed.
  3. Tell me which issue you picked and why, then start.
- Stop after pushing the branch and moving the issue to `status:in-review`. Do not open a PR.
