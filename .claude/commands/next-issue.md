---
description: Implement a ready GitHub issue with the Dev agent (ready → in-review, ending with a PR)
argument-hint: "[#<issue-number>]"
---

Act as the Dev agent in **implement mode**: read `.claude/agents/dev.md` and `CLAUDE.md`, then follow the implement-mode steps.

Issue: $ARGUMENTS

- If an issue number was given, implement that issue. It must be labelled `status:ready` (or `status:in-progress` with Reviewer feedback to address); otherwise stop and tell me.
- If no issue number was given, pick the next one yourself:
  1. Issues labelled `status:in-progress` with unaddressed Reviewer feedback come first.
  2. Otherwise, take the lowest-numbered `status:ready` issue whose `Depends on #n` issues are all closed.
  3. Tell me which issue you picked and why, then start.
- Always finish by opening the PR (`Closes #<n>`, following the PR template), linking it on the issue, and moving the issue to `status:in-review`. For Reviewer feedback, push to the existing PR's branch instead. Then stop; do not merge.
