---
description: Brainstorm a feature idea with the Architect and turn it into draft issues
argument-hint: "<feature idea>"
---

Act as the **Architect**: if `.claude/agents/architect.md` exists, read it and follow it; otherwise follow the Architect role described in `CLAUDE.md`. Either way, read `CLAUDE.md`.

Feature idea: $ARGUMENTS

1. If no idea was given, ask me what I want to explore.
2. Explore the relevant code and `BLE_Protocol.md` first, so the discussion is grounded in what exists today. Call out hardware or protocol behaviour that is unknown instead of assuming it.
3. Brainstorm with me: clarify the goal, propose an approach with a recommendation, and point out trade-offs and risks. Keep it a conversation; ask before deciding for me.
4. When we agree, propose the ticket breakdown (an epic plus small issues per area, with investigation tickets first where something is unknown) and wait for my OK.
5. Then create the issues on `mmans/AquaBle` using the feature-draft sections, labelled `status:draft` plus `type:*` and `area:*`, with `Depends on #n` links. Give me the list of issue links.

Do not write or change any code.
