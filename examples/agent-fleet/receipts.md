> **How this was tested.** On 2026-10-27, Claude Code installed and ran Orca 1.4.242, OpenRig 0.7.4, Herdr 0.9.5 on the author's Apple silicon Mac. Every terminal line quoted here comes from that session. The evidence is 17 excerpts from the agent session transcript and 2 tool outputs reformatted by the test script. Local paths are shown as ~/ry-ops. Where something is marked documented, it comes from the project's own docs and was not tested. Not tested: anything across two machines; Codex or Pi agents; Orca's orchestration commands and automations; OpenRig's watchdog and host pairing.

| Capability | Orca | OpenRig | Herdr |
|---|---|---|---|
| Agents keep running when you disconnect | Documented, not tested | Tested | Documented, not tested |
| Working, blocked and idle detection | Documented, not tested | Tested | Tested |
| Each task in its own git worktree | Tested | Not found | Documented, not tested |
| Roles, owned work queue, handoffs | Documented, not tested | Tested | Not found |
| Bring a stopped team back where it left off | Documented, not tested | Tested | Documented, not tested |
| More than one machine | Documented, not tested | Documented, not tested | Documented, not tested |
| Search what agents did before | Documented, not tested | Tested | Not found |
| Scheduled jobs | Documented, not tested | Documented, not tested | Not found |
| **Memory shared across tools and machines** | Not found | Not found | Not found |
| **A warning before parallel agents collide** | Not found | Not found | Not found |
| **Placing work by machine capacity or model limits** | Not found | Not found | Not found |
| **One permission and audit policy for all three** | Not found | Not found | Not found |

Rows in bold are gaps: not found for any of them.

<details><summary>Quotes checked against their sources</summary>

- “The agent development environment”: [https://onorca.dev/](https://onorca.dev/), checked 2026-10-28
- “Herdr is where your coding agents live”: [https://herdr.dev/](https://herdr.dev/), checked 2026-10-28
- “Herdr doesn't wrap them or replace them”: [https://herdr.dev/](https://herdr.dev/), checked 2026-10-28
- “Herdr isn't an app you keep open”: [https://herdr.dev/](https://herdr.dev/), checked 2026-10-28
- “OpenRig is the Terraform for Coding Agents”: [https://openrig.dev/blog](https://openrig.dev/blog), checked 2026-10-28
- “A harness wraps a model. A rig wraps your harnesses.”: [https://raw.githubusercontent.com/mvschwarz/openrig/main/README.md](https://raw.githubusercontent.com/mvschwarz/openrig/main/README.md), checked 2026-10-28
- “OpenRig doesn't guarantee it can preserve or roll back these files, so back them up first”: [https://raw.githubusercontent.com/mvschwarz/openrig/main/README.md](https://raw.githubusercontent.com/mvschwarz/openrig/main/README.md), checked 2026-10-28
- “ships with broad access”: [https://raw.githubusercontent.com/mvschwarz/openrig/main/README.md](https://raw.githubusercontent.com/mvschwarz/openrig/main/README.md), checked 2026-10-28

</details>

*Versions tested: Orca 1.4.242, OpenRig 0.7.4, Herdr 0.9.5, on 2026-10-27. These projects change fast, so check their release notes before relying on any limitation described here.*
