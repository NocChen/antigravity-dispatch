# SubAgents · working rules

**Applies to**: every subagent working on this project.

**Read order (all three, none optional)**:
1. **This file** — project background and hard constraints
2. **[`COLLABORATION.md`](COLLABORATION.md)** — file ownership, interface contracts, status board rules
3. **Your own task directory's `HANDOFF.md`**

---

## 1. What this project is

<Describe the project: who the client is, what is being built, who it serves, and
how it makes money. Whatever shapes product decisions belongs here — an agent
that doesn't know the business model will make defensible decisions that are
wrong for this project.>

## 2. Read these first

| Document | Location | Why it matters |
|---|---|---|
| | | |

<List the documents an agent must read before touching anything: the spec, the
decision log, meeting notes, the reusable-code inventory. Say why each matters —
"read everything" gets ignored, "this one tells you which directory is the real
one" does not.>

## 3. Hard constraints (violating these causes real damage)

<Each constraint here should be one an agent could plausibly violate by acting
reasonably. Attach the consequence to each rule — a rule with a real failure
behind it gets followed; a rule that reads as style does not.>

### 3.1 Which code is the baseline

> **State the single authoritative directory.**

List the decoys explicitly: old copies, deploy mirrors, historical forks. If two
directories point at the same production target but one is stale, say so and say
what happens if someone pushes from the wrong one.

### 3.2 Upstream repositories

If code is being reused from another live project, say so, and mark it
**read-only**: copy from it, never edit it. Warn about known bugs in the upstream
so they don't get copied along with the good parts.

### 3.3 <Environment and access constraints>

<Network reachability, CDN policy, font hosting, regional access — anything where
the developer's environment differs from the user's. These produce bugs nobody
sees locally.>

### 3.4 Content truthfulness

Demo data may be invented, but it must be **labelled as illustrative**, and real
operating figures must never be fabricated. Never put a promise on a page that
the contract doesn't make.

### 3.5 Do not touch

- Contract and commercial documents
- Any `.env`, deployment credentials, or key material
- Do not deploy or push — that decision belongs to the human lead

## 4. You must maintain your own `PROGRESS.md`

Every task directory has `HANDOFF.md` (the brief — you read it) and
`PROGRESS.md` (the work log — **you write it**).

1. **When you start**, record the scope as you understand it and how you plan to proceed
2. **After each deliverable unit**, update it — don't save it all for the end
3. **When you stop**, leave: what's done, what isn't, why, and where the next person begins
4. When you hit something a human must decide, write it in "Open decisions" —
   **don't decide it for them, and don't stall**. Finish everything that doesn't
   depend on the answer

Format: `_TEMPLATE/PROGRESS.md`. **This file is the only handoff artifact between
you and the next agent.** Vague is the same as blank.

## 5. How to work

- **Read before writing.** This project has accumulated context — decisions,
  exclusions, agreements. Acting on instinct will usually contradict one of them.
- **Scope is scope.** Don't quietly widen or narrow it. If the brief is wrong,
  write that in `PROGRESS.md`, then finish the work using your judgement — don't
  stop and wait.
- **Verifiable.** Anything touching a page gets run in a browser and screenshotted.
  Don't infer behaviour from code.
- **Report honestly.** Not done means not done. Failed tests get their output
  pasted. Don't let "complete" cover partially complete.
- **Don't build a parallel system.** Existing design tokens, i18n mechanism,
  directory layout, naming — follow them. Don't invent a second way.

## 6. Directory layout

```
SubAgents/
├── README.md            ← this file, required reading for every agent
├── COLLABORATION.md     ← parallel-work rules
├── STATUS_BOARD.md      ← shared, append-only
├── _TEMPLATE/           ← copy this to open a new task
│   ├── HANDOFF.md
│   └── PROGRESS.md
└── <id-task-name>/
    ├── HANDOFF.md       ← the brief (the lead writes, the agent reads)
    ├── PROGRESS.md      ← the work log (the agent writes)
    └── ...              ← that task's output
```

New task: `agdispatch new-task <id-task-name>`, then fill in `HANDOFF.md`.

## 7. Current project state

| Item | Status |
|---|---|
| | |
