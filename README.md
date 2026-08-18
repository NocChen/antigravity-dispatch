# agdispatch — a CLI for Google Antigravity's background coding agents

Dispatch, monitor and audit **Google Antigravity** AI coding agents from the
command line — or from **Claude Code**, as a skill.

Antigravity's Agent Manager ships an official-but-undocumented `agentapi` command
and a local RPC service. `agdispatch` wraps both into one tool: start agents, poll
them, read their transcripts, and optionally run them inside a coworking
convention that leaves a paper trail a human can actually read — then cross-check
what they claim against what they actually left on disk.

```bash
$ agdispatch dispatch --wait "Add retry-with-backoff to the fetch helper in src/api.ts"
```

No configuration, no API keys, no dependencies beyond Python 3. It talks to the
Antigravity you already have running and signed in.

**Contents** — [How it works](#how-it-works) · [Install](#install) ·
[Usage](#usage) · [The SubAgents convention](#the-subagents-convention) ·
[Reviewing what came back](#reviewing-what-came-back) · [Commands](#commands) ·
[Caveats](#caveats) · [FAQ](#faq)

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
exist, but the handoff doesn't. `STOPPED, not signed off` means the conversation
has gone idle while the log still claims work in progress: usually a mid-task
death, with half-finished edits still sitting in the tree.

---

## Reviewing what came back

The hard part of running background agents isn't starting them. It's working out
which parts of a confident report are true.

```bash
agdispatch audit                     # bookkeeping cross-check over every dispatched task
agdispatch audit --project my-app    # also scan that project's repo roots for stray files
```

`dispatch --task` records a small manifest in the task folder — conversation id,
model, timestamp, and a checksum of the brief. `audit` compares that against the
workspace as it stands now and reports what it can't reconcile:

| Finding | What it means |
|---|---|
| **Stopped without sign-off** | The conversation ended but `PROGRESS.md` never said delivered. Usually a mid-task death; the partial work is still on disk |
| **`HANDOFF.md` changed since dispatch** | An agent rewrote its own brief — typically replacing it with a completion report. Recover it from git |
| **No `done` line on the board** | The task ended without the entry the next person reads |
| **Untracked files at a repo root** | One-off patch scripts dropped where your tooling convention says they don't go |

Each of those checks exists because it silently went wrong in a real run.

**A clean audit means the paperwork is consistent — nothing more.** What it
can't check, you still have to:

- **Re-verify every reported defect before acting on it.** In one review, three of
  four reported "blockers" were wrong: two were assertions written against a
  guessed response shape, and the third was an endpoint correctly rejecting bad
  input. A false defect costs more than a missed one — read the route or the
  schema and confirm the expected behavior before scheduling a fix.
- **Check claimed coverage against delivered artifacts.** "Full sweep" next to
  three screenshots of two pages is not a full sweep.
- **Re-run your own test gates**, rather than trusting a report that says they passed.
- **Look for processes the agent left running.** A dev server outliving its agent
  collides with the next one — and against a single-writer database, that means
  two processes writing the same file.

The composed prompt pushes back on the same failures from the agent's side: the
brief is read-only, a failing assertion is a bug in your test until the contract
proves otherwise, coverage is reported as a fraction rather than an adjective,
and processes and scratch files get cleaned up before sign-off.

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
| `audit` | cross-check agent claims against the workspace and live status |
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

---

## FAQ

**Can I run Google Antigravity agents from the terminal?**
Yes — that's what this is. The Agent Manager hosts a local API; `agdispatch`
discovers it and drives it, so you can start and monitor agents without the GUI.

**Can I run several Antigravity agents in parallel?**
Yes. Give each one its own task folder and declare file ownership in each brief,
so two agents never write the same file. See
[the SubAgents convention](#the-subagents-convention).

**How do I use Antigravity from Claude Code?**
Copy `SKILL.md` and `agdispatch.py` into `~/.claude/skills/antigravity-dispatch/`.
Claude Code loads it as a skill and can dispatch, monitor and audit agents for you.

**How do I know whether an agent actually did the work?**
Read `PROGRESS.md` and the repository, not the transcript — transcripts overstate.
Run [`agdispatch audit`](#reviewing-what-came-back) for the bookkeeping check, then
re-verify any reported defect against the real contract before acting on it.

**Does it need an API key?**
No. It uses the Antigravity app you already have running and signed in. No keys,
no config files, no third-party dependencies — Python 3 standard library only.

**Does it work on Linux or Windows?**
Not yet. Endpoint discovery shells out to `ps` and `lsof`; the rest is portable.
Patches welcome.

## License

MIT
