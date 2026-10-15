---
description: Refine a draft GitHub issue with the Dev agent (draft → ready)
argument-hint: "#<issue-number>"
---

Act as the Dev agent in **refine mode**: read `.claude/agents/dev.md` and `CLAUDE.md`, then follow the refine-mode steps for issue $ARGUMENTS on `mmans/AquaBle`.

- If no issue number was given, list the `status:draft` issues and ask which one to refine.
- If the issue is not labelled `status:draft`, say so and ask before continuing.
- Discuss open points with me before rewriting the issue, and only move it to `status:ready` after I agree.
- Do not write any code.
