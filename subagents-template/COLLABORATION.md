# Parallel collaboration guide · one agent per subtask

**Applies to**: every agent working in parallel on this project.
**Read order**: [`README.md`](README.md) (working rules) → this file → your own
task directory's `HANDOFF.md`.

---

## 1. The bottleneck in parallel work is conflict, not compute

When several agents work at once, the failure is almost never that one of them
couldn't write the code. It's:

1. **Two agents edit the same file** → the later write silently destroys the earlier one, and nobody notices
2. **B can't start until A is finished** → parallelism degrades to serial, plus coordination overhead
3. **Each has a different understanding of the same thing** → every piece is correct, nothing fits together
4. **Nobody recorded what they did** → next morning, no one knows where things stand

The four sections below address those four failures in order. **These rules take
precedence over writing elegant code.**

---

## 2. File ownership: every file has exactly one owner

### 2.1 The hard rule

> **Every agent declares the files/directories it owns in its `HANDOFF.md`.
> Only the owner may write them.**
> **Not yours? Read-only. Need it changed? See §2.3.**

### 2.2 Ownership table

Maintain a table here mapping each agent to what it may write, and what is
read-only for it. Fill it in before dispatching the first agent of a wave.

| Agent | Writable | Read-only |
|---|---|---|
| | | everything else |

Where two agents meet at a boundary, name the boundary explicitly and say which
side owns the mechanism and which side supplies the content. Do not let both
sides build their own version of the same thing.

### 2.3 When you need someone else's file changed

**Do not just edit it.** Pick one of three:

1. **Can you solve it inside your own files?** → do that (preferred)
2. **Small change** → record it under "Changes I need from others" in your
   `PROGRESS.md`, and leave a line on the status board
3. **Interface change** → follow the contract process in §3

### 2.4 Files that are never co-written

The route table, the dependency manifest, the schema file, and any `.env`.

> **What about routes?** Each agent writes its own routes in a separate module
> that exports a registration function. One integration pass mounts them all at
> the end. **Do not add your line to the shared route file yourself.**

---

## 3. Contracts first: don't wait for the implementation

### 3.1 The rule

> **An agent others depend on publishes its interface contract on day one, not
> when the implementation is done.**
> **Dependants start as soon as they have the contract, coding against it with
> stub data.**

### 3.2 Changing a published contract

Once published, any change **must** get a `CHANGED` line on the status board
saying what changed and who is affected. Dependants only find out if you write
it down. **Silently changing a contract is the most expensive mistake available.**

---

## 4. Shared understanding: things nobody gets to improvise

List here the decisions that are already settled — deployment shape, dependency
policy, i18n mechanism, upstream repositories and their read-only status. Every
agent follows them as written; nobody re-litigates them mid-task.

| Item | Decision | Source |
|---|---|---|
| | | |

Also keep an explicit **out of scope** list. Work delivered against something on
that list is work thrown away.

---

## 5. Recording progress: two files

### 5.1 Your own `PROGRESS.md` (one per agent)

One entry when you start, one per deliverable unit, a handoff note when you stop.

In parallel work these four blocks are required at the top:

```markdown
## Contracts I publish
<the interface others may depend on. "none" if nothing does>

## What I depend on
<whose contract, and whether you're on the real implementation or a stub>

## Changes I need from others
<what must change in someone else's files>

## Files I own
<what you actually wrote. If it exceeds HANDOFF.md, say why>
```

### 5.2 The shared status board (everyone writes the same file)

**Append only. Never edit someone else's line.** One line per event:

```
2026-01-05 14:30 | W1-A | contract published | db/companies.js — see my PROGRESS
2026-01-05 16:10 | W1-B | start              | coding against W1-A's contract, stub data for now
2026-01-05 18:40 | W1-A | CHANGED            | searchCompanies now returns facets — affects W1-B
```

**When a board entry is mandatory**: start · contract published · contract
changed · blocked · unblocked · done. Everything else is optional.

---

## 6. When you're blocked

> **Do the parts that don't depend on the answer. Do not stop and wait.**

1. Put a "blocked + why" line on the status board
2. In your `PROGRESS.md` "Open decisions" table, write the question, the options,
   **your recommendation**, and **which default you are proceeding on**
3. **Keep working on something else**

---

## 7. Verification: inferring from code is not allowed

- Touches a page → actually run it in a browser, screenshot as evidence
- Touches a database → actually connect and run the queries, paste the output
- Touches dependency/network policy → paste the grep output

**Watch for false success.** A command that exits 0 is not proof. If three
screenshots come out byte-identical, nothing rendered — the tooling succeeded and
the work didn't. "Looks fine" is not "verified".

---

## 8. Standard procedure for dispatching a new agent

1. `cp -r _TEMPLATE <id-task-name>`
2. Fill in `HANDOFF.md`: background, goal, deliverables table, **file-ownership
   declaration**, constraints, out of scope, open decisions with defaults
3. Dispatch with a prompt that tells the agent to read, in order:
   `README.md` → `COLLABORATION.md` → its own `HANDOFF.md`
4. Dispatch critical-path agents **first**; wait for their published contract
   before dispatching their dependants
5. Agents with no dependency between them go out at the same time

`agdispatch dispatch --task <id-task-name>` performs steps 3 and 5 for you and
refuses to dispatch against an unfilled `HANDOFF.md`.
