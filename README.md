# agdispatch

Dispatch background coding agents to **Google Antigravity** from the command line —
or from Claude Code, as a skill.

Antigravity's Agent Manager ships an official-but-undocumented `agentapi` command
and a local RPC service. `agdispatch` wraps both into one tool: start agents, poll
them, read their transcripts, and optionally run them inside a coworking
convention that leaves a paper trail a human can actually read.

```bash
$ agdispatch dispatch --wait "Add retry-with-backoff to the fetch helper in src/api.ts"
```

No configuration, no API keys, no dependencies beyond Python 3. It talks to the
Antigravity you already have running and signed in.

---

## How it works

The Agent Manager runs a `language_server` process that hosts everything:

- A **Connect-RPC service** on `127.0.0.1`, authenticated with an
  `x-codeium-csrf-token` header. This is the same API the Agent Manager UI uses —
  `GetAllCascadeTrajectories` for status, `ConvertTrajectoryToMarkdown` for
  transcripts, `ForceStopCascadeTree` to cancel.
- An **`agentapi` subcommand** built into the same binary, exposed as
  `~/.gemini/antigravity/bin/agentapi`, with `new-conversation`, `send-message`
  and `get-conversation-metadata`. It reads `ANTIGRAVITY_LS_ADDRESS`,
  `ANTIGRAVITY_CSRF_TOKEN` and `ANTIGRAVITY_PROJECT_ID` from the environment.

The port and CSRF token are regenerated on every launch, so `agdispatch`
discovers them each run: it finds the hub process, reads the token from its
command line, and probes its listening ports for the one that answers the agent
API. The result is cached and re-validated, so discovery costs nothing on repeat
calls.

Projects come from `~/.gemini/config/projects/*.json`. The project you dispatch
into determines the workspace the agent can read and edit.

> Verified against Antigravity 2.7.1 on macOS. It leans on internal details —
> a future release may move them.

---

## Install

```bash
git clone https://github.com/NocChen/antigravity-dispatch.git
cd antigravity-dispatch
chmod +x agdispatch.py
```

Use it directly (`python3 agdispatch.py …`), or put it on your `PATH`:

```bash
ln -s "$PWD/agdispatch.py" /usr/local/bin/agdispatch
```

### As a Claude Code skill

```bash
mkdir -p ~/.claude/skills/antigravity-dispatch
cp SKILL.md agdispatch.py ~/.claude/skills/antigravity-dispatch/
```

Claude Code picks it up on the next session. Ask it to "dispatch this to
Antigravity" and it will.

### Check the connection

```bash
$ agdispatch doctor
Agent Manager  : running
RPC endpoint   : http://127.0.0.1:65234
language_server: /Applications/Antigravity.app/Contents/Resources/bin/language_server
projects       : 16
conversations  : 13

OK — ready to dispatch.
```

The Agent Manager app must be running and signed in.

---

## Usage

### Dispatch

```bash
agdispatch dispatch "Summarize what changed in db/companies.js this week"
agdispatch dispatch --wait --model=pro "Refactor the auth middleware"
agdispatch dispatch --project my-app --dry-run "..."
```

| Option | Meaning |
|---|---|
| `--project` | project id, name, or path. `auto` (default) matches cwd; `none` = no workspace |
| `--model` | `flash_lite`, `flash` (default), `pro` |
| `--wait` | block until the agent goes idle, then print the transcript |
| `--timeout` | seconds before `--wait` gives up (default 900). The agent keeps running |
| `--dry-run` | print the composed prompt and resolved project, dispatch nothing |

Without `--wait` you get a conversation id back immediately:

```json
{
  "conversationId": "aa89aac2-1b14-474b-b83f-7c660d2d2a84",
  "projectId": "4a5c086d-2cbb-45e9-844e-dd28a9a91097",
  "model": "flash",
  "status": "dispatched"
}
```

### Follow up

```bash
agdispatch list                       # recent conversations: id, status, time, title
agdispatch status <conversation_id>   # JSON, includes a "running" boolean
agdispatch result <conversation_id>   # transcript as markdown
agdispatch wait   <conversation_id>
agdispatch send   <conversation_id> "Also add tests for the retry path" --wait
agdispatch cancel <conversation_id>
```

---

## The SubAgents convention

A dispatched agent that leaves nothing behind but a chat log is hard to
coordinate and impossible to audit. `agdispatch` supports a lightweight file
convention that fixes that — and the tool enforces the parts that are easy to
skip.

```
SubAgents/
├── README.md            working rules   — project background + hard constraints
├── COLLABORATION.md     parallel rules  — file ownership, contracts, board rules
├── STATUS_BOARD.md      shared board    — append-only, every agent writes to it
├── _TEMPLATE/           copy this to open a new task
└── <id-task-name>/
    ├── HANDOFF.md       the brief — the human writes it, the agent reads it
    ├── PROGRESS.md      the work log — the agent writes it
    └── ...              that task's output
```

Copy [`subagents-template/`](subagents-template/) into your project as
`SubAgents/` and fill in the placeholders. Then:

```bash
agdispatch workspace                            # layout + per-task state
agdispatch new-task W2-A-search-ranking         # cp -r _TEMPLATE
# → fill in HANDOFF.md: background, goal, deliverables, FILE OWNERSHIP, out of scope
agdispatch dispatch --task W2-A-search-ranking --dry-run
agdispatch dispatch --task W2-A-search-ranking --model=pro
```

`--task` adds four things:

1. **It refuses to dispatch against an unfilled `HANDOFF.md`.** An agent sent
   against an empty brief invents its own scope — this is the single highest-value
   guard in the tool.
2. **It composes the protocol prompt**: read the working rules → the
   collaboration guide → your own brief; maintain `PROGRESS.md` with the four
   required top blocks; write to the status board at the six moments that matter;
   only write files you own; when blocked, proceed on a stated default rather
   than stalling.
3. **It logs the dispatch to the status board** with the conversation id, so a
   conversation can always be traced back to a task folder.
4. **It titles the conversation** after the task, so the Agent Manager list
   matches your folder names.

`agdispatch workspace` gives you the state of every task at a glance:

```
SubAgents    : /path/to/project/SubAgents
convention   : en
README       : yes
collaboration: yes
status board : yes
_TEMPLATE    : yes

tasks:
  W1-A-persistence               W1-A         delivered
  W1-B-directory-prototype       W1-B         delivered
  W1-C-design-system             W1-C         PROGRESS empty
  W1-D-auth-and-rate-limit       W1-D         in progress
```

`PROGRESS empty` means an agent finished without writing its log — the work may
exist, but the handoff doesn't.

### Why the convention is shaped this way

Running several agents in parallel fails for four reasons, and none of them is
that the model can't write code:

| Failure | What the convention does |
|---|---|
| Two agents edit the same file; the later write silently wins | Every file has exactly one declared owner. Not yours → read-only, request the change instead |
| B waits for A to finish, so parallel becomes serial | Whoever others depend on publishes an interface contract on day one; dependants start against stubs |
| Everyone's piece is correct, nothing fits together | A contract change requires a board entry naming who is affected. Silent contract drift is the most expensive mistake available |
| Nobody knows where things stand | `PROGRESS.md` per task, one shared append-only board, mandatory entries at six moments |

And one that isn't about parallelism at all: **transcripts overstate.** Agents
report test suites that were never written to disk, and screenshots that are
byte-identical because nothing rendered. The convention answers that by asking
for evidence — command output, a real screenshot, a real query — and by making
the work log, not the chat, the thing you read.

### Language

Chinese file names (`并行协作指南.md`, `状态看板.md`) are recognized alongside the
English ones, and the composed prompt follows whichever the workspace uses. Force
it with `--lang en|zh`.

---

## Commands

| Command | Purpose |
|---|---|
| `doctor` | verify connectivity to the Agent Manager |
| `projects` | list Antigravity projects and their workspace paths |
| `dispatch` | start a new agent |
| `workspace` | show the SubAgents layout and per-task state |
| `new-task` | copy `_TEMPLATE` into a new task directory |
| `board` | append one line to the status board |
| `send` | send a follow-up message to a conversation |
| `status` / `result` / `wait` / `cancel` / `list` | manage running and finished agents |

---

## Caveats

- **macOS.** Discovery uses `ps` and `lsof`. The rest is portable; patches welcome.
- **Dispatched agents act autonomously** in the target repository — they edit
  files and run commands. Treat a dispatch into a real project as a change to
  that repository.
- **Dispatches consume your Antigravity quota**, and long parallel runs can hit
  session limits mid-task.
- **Undocumented surface.** `agentapi` and the RPC service are internal to
  Antigravity. This works today; a future release may change it.

## License

MIT
