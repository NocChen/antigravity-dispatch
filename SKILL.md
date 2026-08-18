---
name: antigravity-dispatch
description: Dispatch background coding agents to Google Antigravity and read their results, optionally following the SubAgents coworking convention (HANDOFF.md task briefs, PROGRESS.md work logs, an append-only status board). Use when the user wants to hand work to Antigravity, open or dispatch a subagent task, run something in Antigravity, check the status board or a task's progress, or follow up with / cancel an Antigravity conversation.
---

# Dispatching Antigravity agents

Antigravity's Agent Manager exposes a local RPC API and an official `agentapi`
command. `agdispatch.py` (in this skill's directory) wraps both, and can wrap
them in a coworking convention so a dispatched agent lands inside a structure a
human can read, rather than an opaque chat.

```bash
AGD="python3 ~/.claude/skills/antigravity-dispatch/agdispatch.py"
```

## Prerequisite

The **Antigravity Agent Manager app must be running** — it hosts the API. Its
port and CSRF token are regenerated per launch and discovered automatically.

```bash
python3 ~/.claude/skills/antigravity-dispatch/agdispatch.py doctor
```

If it reports the app is not running, start it. Don't try to launch the bare
`language_server` binary.

## Plain dispatch

```bash
$AGD dispatch "Add retry-with-backoff to the fetch helper in src/api.ts"
$AGD dispatch --wait --model=pro "Refactor the auth middleware"
```

| Option | Meaning |
|---|---|
| `--project` | `auto` (default) picks the project containing cwd; also accepts an id, a name, or a path; `none` = no workspace |
| `--model` | `flash_lite`, `flash` (default), `pro` |
| `--wait` | block until idle, then print the transcript |
| `--timeout` | seconds before `--wait` gives up (default 900); the agent keeps running |
| `--dry-run` | print the composed prompt and resolved project, dispatch nothing |

**Project selection decides what the agent can see and edit.** `auto` only
matches when cwd is inside a folder Antigravity already knows about; otherwise it
silently falls back to `outside-of-project`, where there's no repo. When the task
is about a specific codebase, check `$AGD projects` and pass `--project`
explicitly rather than trusting `auto`.

## The SubAgents convention

If the project keeps a `SubAgents/` directory, use it — it's the coworking
surface a human reads to know what every agent is doing.

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

The directory is auto-detected from cwd (including one or two levels of nesting,
for note vaults); override with `--subagents` or `$AGD_SUBAGENTS`. Chinese file
names (`并行协作指南.md`, `状态看板.md`) are recognized too, and the composed prompt
follows whichever language the workspace uses unless you pass `--lang`.

```bash
$AGD workspace                              # layout + per-task state
$AGD new-task W2-A-search-ranking           # cp -r _TEMPLATE
# → now fill in HANDOFF.md
$AGD dispatch --task W2-A-search-ranking --dry-run    # review the prompt first
$AGD dispatch --task W2-A-search-ranking --model=pro
```

`--task` does four things a bare prompt doesn't:

1. **Refuses to dispatch against an unfilled `HANDOFF.md`.** An agent sent
   against an empty brief invents its own scope.
2. **Composes the protocol prompt**: read `README.md` → `COLLABORATION.md` → its
   own `HANDOFF.md`; maintain `PROGRESS.md` with the four required top blocks
   (contracts I publish / what I depend on / changes I need from others / files I
   own); append to the status board at start · contract published · contract
   changed · blocked · unblocked · done; write only files it owns; don't stall
   when blocked.
3. **Logs a dispatch line to the status board** carrying the conversation id —
   how a human later ties a conversation back to a task folder.
4. **Titles the conversation** with the task name, so the Agent Manager list
   matches the folder names.

A positional prompt passed alongside `--task` is appended as extra instructions
for that dispatch — it does not replace the brief.

### Writing the HANDOFF.md

This decides whether the dispatch is worth anything. Fill in every section:
background (don't assume context), goal (one sentence), a deliverables table
(deliverable / location / acceptance criteria), **the file-ownership declaration**
(what this agent may write — everything else read-only), constraints, out of
scope, and open decisions each with a stated default so the agent never stalls.

File ownership prevents the expensive failure: two agents writing the same file.
The route table, dependency manifest, schema file and any `.env` are never
co-written.

### Logging to the board yourself

```bash
$AGD board lead "dispatched wave 2" "W2-A and W2-B out in parallel"
$AGD board lead decision "open decision #3 settled: option B"
```

Append only — never rewrite someone else's line.

## Following up and reading results

```bash
$AGD list                       # recent conversations: id, status, time, title
$AGD status <conversation_id>   # JSON, includes a "running" boolean
$AGD result <conversation_id>   # transcript as markdown
$AGD wait   <conversation_id>
$AGD send   <conversation_id> "Also add tests for the retry path" [--wait]
$AGD cancel <conversation_id>
```

Status is `CASCADE_RUN_STATUS_IDLE` when done, `..._RUNNING` / `..._BUSY` while
working.

**For "did it actually work?", read `PROGRESS.md` and the repository — not the
transcript.** Transcripts overstate. Agents cite test scripts that were never
written to disk, and screenshots that came out byte-identical because nothing
rendered. `$AGD workspace` flags tasks whose `PROGRESS.md` is still an empty
template, and marks a task `STOPPED, not signed off` when its conversation has
gone idle while the log still reads in-progress.

## Reviewing what came back

```bash
$AGD audit                      # bookkeeping cross-check over every dispatched task
$AGD audit --project MedTour    # also scan that project's repo roots for stray files
```

`audit` compares the manifest written at dispatch against the workspace now, and
reports what it cannot reconcile:

- **Stopped without sign-off** — the conversation ended but `PROGRESS.md` never
  said delivered. Usually a mid-task death, and the half-finished edits are still
  on disk.
- **`HANDOFF.md` changed since dispatch** — an agent rewrote its own brief,
  typically replacing it with a completion report. Recover it from git.
- **No `done` line on the board**, or a `PROGRESS.md` still on the template.
- **Untracked files at a repo root** — one-off patch scripts dropped where the
  project's tooling convention says they don't belong.

A clean audit means the paperwork is consistent, nothing more. These four checks
exist because each one silently went wrong. What audit cannot check, you have to:

- **Re-verify every reported defect before acting on it.** In one review, three of
  four reported "blockers" were wrong: two were assertions written against a
  guessed response shape, and the third was an endpoint correctly rejecting bad
  input. Read the route or schema and confirm the expected behavior before you
  schedule a fix — a false defect costs more than a missed one.
- **Check claimed coverage against delivered artifacts.** "Full sweep" alongside
  three screenshots of two pages is not a full sweep.
- **Re-run the project's own gates yourself**, rather than trusting a report that
  says they passed.
- **Check for processes the agent left running** — a dev server outliving its
  agent will collide with the next one, and on a single-writer database that means
  two processes writing the same file.

## Things to get right

- **The agent acts autonomously** in the target repository — it edits files and
  runs commands. Confirm before dispatching work that modifies a codebase the
  user hasn't pointed you at.
- **Dispatches consume quota**, and long parallel runs can hit session limits
  mid-task. One dispatch per real task; prefer fire-and-forget over `--wait` for
  long work.
- **Prompts must be self-contained.** The Antigravity agent cannot see this
  conversation. With `--task`, the `HANDOFF.md` carries the context — which is
  exactly why it must be filled in before dispatch.
- **Don't write another agent's files** on the user's behalf either. If a task's
  `PROGRESS.md` needs correcting, note it on the board rather than editing it —
  record your own conclusions in a review note you own, and say which of the
  agent's claims it supersedes.
- **Believe the disk over the report.** Every check in `audit` exists because a
  confident write-up did not match what was actually there.
