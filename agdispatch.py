#!/usr/bin/env python3
"""
agdispatch — dispatch and manage Google Antigravity agents from the command line.

Talks to the local `language_server` process that backs the Antigravity Agent
Manager app. Dispatch goes through Antigravity's own `agentapi` command; status
and transcript reads use the same local RPC service the Agent Manager UI uses.

The Agent Manager app must be running — its RPC port and CSRF token are
allocated per launch and are discovered automatically.

Python 3 stdlib only. No configuration.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

SVC = "/exa.language_server_pb.LanguageServerService"
PROJECTS_DIR = Path.home() / ".gemini" / "config" / "projects"
CACHE = Path.home() / ".cache" / "agdispatch" / "endpoint.json"
BUSY = {"CASCADE_RUN_STATUS_RUNNING", "CASCADE_RUN_STATUS_BUSY",
        "CASCADE_RUN_STATUS_CANCELING"}
MODELS = ("flash_lite", "flash", "pro")

# A workspace may use the English or the Chinese file names; both are supported.
BOARD_NAMES = ("STATUS_BOARD.md", "状态看板.md")
GUIDE_NAMES = ("COLLABORATION.md", "并行协作指南.md")

# Strings that only survive in a HANDOFF.md nobody has filled in yet.
UNFILLED = ("# HANDOFF · <task name>", "<why this task exists", "<one sentence:",
            "# HANDOFF · <任务名>", "<为什么有这个任务", "<一句话说清做完之后")
EMPTY_PROGRESS = ("# PROGRESS · <task name>", "# PROGRESS · <任务名>")
DELIVERED = ("delivered", "已交付")


class AgError(Exception):
    pass


# ---------------------------------------------------------------- discovery

def _hub_process():
    """Return (pid, csrf_token, language_server_path) for the Agent Manager hub."""
    out = subprocess.run(["ps", "-axo", "pid=,command="],
                         capture_output=True, text=True).stdout
    for line in out.splitlines():
        line = line.strip()
        if "/language_server" not in line:
            continue
        if "--subclient_type hub" not in line:
            continue
        pid_s, _, cmd = line.partition(" ")
        parts = cmd.split()
        token = None
        for i, p in enumerate(parts):
            if p == "--csrf_token" and i + 1 < len(parts):
                token = parts[i + 1]
            elif p.startswith("--csrf_token="):
                token = p.split("=", 1)[1]
        if token:
            return int(pid_s), token, parts[0]
    raise AgError("The Antigravity Agent Manager is not running. Start it first.")


def _listen_ports(pid):
    out = subprocess.run(
        ["lsof", "-nP", "-iTCP", "-sTCP:LISTEN", "-a", "-p", str(pid)],
        capture_output=True, text=True).stdout
    ports = []
    for m in re.finditer(r":(\d+) \(LISTEN\)", out):
        p = int(m.group(1))
        if p not in ports:
            ports.append(p)
    return ports


def _probe(port, token):
    try:
        _rpc_raw(port, token, "GetAllCascadeTrajectories", {}, timeout=3)
        return True
    except Exception:
        return False


def endpoint():
    """Discover (port, token, ls_path), using a cached value when still valid."""
    pid, token, ls_path = _hub_process()
    try:
        c = json.loads(CACHE.read_text())
        if c.get("pid") == pid and c.get("token") == token and _probe(c["port"], token):
            return c["port"], token, ls_path
    except Exception:
        pass
    for port in _listen_ports(pid):
        if _probe(port, token):
            CACHE.parent.mkdir(parents=True, exist_ok=True)
            CACHE.write_text(json.dumps({"pid": pid, "port": port, "token": token}))
            return port, token, ls_path
    raise AgError("Found the Antigravity hub (pid %d) but no port answered the agent "
                  "RPC API. Try restarting the Agent Manager app." % pid)


# ---------------------------------------------------------------------- rpc

def _rpc_raw(port, token, method, body, timeout=30):
    req = urllib.request.Request(
        "http://127.0.0.1:%d%s/%s" % (port, SVC, method),
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json",
                 "x-codeium-csrf-token": token},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        try:
            detail = json.loads(detail).get("message", detail)
        except Exception:
            pass
        raise AgError("%s failed: %s" % (method, detail))


def rpc(method, body, timeout=30):
    port, token, _ = endpoint()
    return _rpc_raw(port, token, method, body, timeout)


# ----------------------------------------------------------------- projects

def load_projects():
    out = []
    if PROJECTS_DIR.is_dir():
        for f in sorted(PROJECTS_DIR.glob("*.json")):
            try:
                d = json.loads(f.read_text())
            except Exception:
                continue
            paths = []
            for r in d.get("projectResources", {}).get("resources", []):
                uri = (r.get("folderUri")
                       or (r.get("gitFolder") or {}).get("folderUri")
                       or (r.get("folder") or {}).get("folderUri") or "")
                if uri.startswith("file://"):
                    paths.append(urllib.request.url2pathname(uri[7:]))
            out.append({"id": d.get("id", f.stem),
                        "name": d.get("name", f.stem),
                        "paths": paths})
    out.append({"id": "outside-of-project", "name": "Outside of Project", "paths": []})
    return out


def _project_containing(path):
    """Innermost project whose workspace contains `path`, or None."""
    target = os.path.realpath(path)
    best = None
    for p in load_projects():
        for wp in p["paths"]:
            rp = os.path.realpath(wp)
            if target == rp or target.startswith(rp + os.sep):
                if best is None or len(rp) > best[1]:
                    best = (p, len(rp))
    return best[0] if best else None


def project_paths(pid):
    for p in load_projects():
        if p["id"] == pid:
            return p["paths"]
    return []


def resolve_project(spec):
    """Resolve a project id, name, or directory path to a project id."""
    projects = load_projects()
    if not spec or spec == "none":
        return "outside-of-project"
    if spec == "auto":
        p = _project_containing(os.getcwd())
        return p["id"] if p else "outside-of-project"
    for p in projects:
        if spec == p["id"]:
            return p["id"]
    for p in projects:
        if spec.lower() == p["name"].lower():
            return p["id"]
    if os.path.isdir(spec):
        p = _project_containing(spec)
        if p:
            return p["id"]
        raise AgError("No Antigravity project covers %s.\n"
                      "Open that folder once in Antigravity, or pass --project <name|id>."
                      % spec)
    raise AgError("Unknown project %r. Run `agdispatch projects` to list them." % spec)


# --------------------------------------------------------- SubAgents layout
#
#   SubAgents/
#   ├── README.md          working rules   — every agent reads this first
#   ├── COLLABORATION.md   parallel rules  — file ownership, contracts, board
#   ├── STATUS_BOARD.md    shared board    — append-only, all agents write it
#   ├── _TEMPLATE/         copy this to open a new task
#   └── <id-task-name>/
#       ├── HANDOFF.md     task brief  (the lead writes it, the agent reads it)
#       ├── PROGRESS.md    work log    (the agent writes it)
#       └── ...            that task's output

def _looks_like_subagents(p):
    return p.is_dir() and ((p / "README.md").exists() or (p / "_TEMPLATE").is_dir())


def find_subagents(spec=None):
    """Locate a SubAgents directory: explicit path, $AGD_SUBAGENTS, or near cwd.

    Walks up from cwd; at each ancestor looks for SubAgents/ directly and up to
    two levels below it, since note vaults commonly nest it.
    """
    if spec:
        p = Path(spec).expanduser()
        if _looks_like_subagents(p):
            return p.resolve()
        raise AgError("%s is not a SubAgents directory (no README.md or _TEMPLATE)." % p)
    if os.environ.get("AGD_SUBAGENTS"):
        p = Path(os.environ["AGD_SUBAGENTS"]).expanduser()
        if _looks_like_subagents(p):
            return p.resolve()

    home = Path.home().resolve()
    here = Path(os.getcwd()).resolve()
    for d in [here] + list(here.parents):
        if d.name == "SubAgents" and _looks_like_subagents(d):
            return d
        for pat in ("SubAgents", "*/SubAgents", "*/*/SubAgents"):
            try:
                hits = sorted(x for x in d.glob(pat) if _looks_like_subagents(x))
            except OSError:
                continue
            if hits:
                return hits[0].resolve()
        if d == home:
            break
    raise AgError("No SubAgents directory found.\n"
                  "Pass --subagents <path>, set AGD_SUBAGENTS, or run from inside the project.")


def pick(sa, names):
    """First of `names` that exists in the workspace, else the first as a default."""
    for n in names:
        if (sa / n).exists():
            return n
    return names[0]


def workspace_lang(sa):
    """'zh' if this workspace uses the Chinese convention files, else 'en'."""
    return "zh" if pick(sa, BOARD_NAMES) == "状态看板.md" else "en"


def task_code(task):
    """'W1-A-persistence' -> 'W1-A'  (the id used on the status board)."""
    m = re.match(r"^([A-Za-z]+\d*-[A-Za-z0-9]+)", task)
    return m.group(1) if m else task


def board_append(sa, code, event, note):
    """Append one line to the status board. Append only — never rewrite other lines."""
    board = sa / pick(sa, BOARD_NAMES)
    if not board.exists():
        board.write_text(
            "# Status board\n\n"
            "> **Every parallel agent writes to this one file. Append only — "
            "never edit someone else's line.**\n"
            "> Format: `YYYY-MM-DD HH:MM | id | event | note`\n\n---\n\n",
            encoding="utf-8")
    line = "%s | %s | %s | %s\n" % (time.strftime("%Y-%m-%d %H:%M"), code, event, note)
    with board.open("a", encoding="utf-8") as f:
        f.write(line)
    return line.strip()


def check_handoff(sa, task):
    """Refuse to dispatch against a task brief nobody filled in."""
    d = sa / task
    if not d.is_dir():
        raise AgError("Task directory not found: %s\nCreate it first:  agdispatch new-task %s"
                      % (d, task))
    h = d / "HANDOFF.md"
    if not h.exists():
        raise AgError("%s has no HANDOFF.md — copy _TEMPLATE or write one." % d)
    text = h.read_text(encoding="utf-8", errors="replace")
    if any(p in text for p in UNFILLED):
        raise AgError(
            "%s is still the unfilled template.\n"
            "Fill in background / goal / deliverables / file ownership / out-of-scope "
            "before dispatching — an agent sent against an empty task brief will "
            "invent its own scope." % h)
    return d


PROMPT_EN = """You are a subagent on this project, responsible for the task "{task}" (id {code}).

**Read these in order before you start. Do not skip any:**
1. `{readme}` — working rules (project background and hard constraints)
{guide}{n}. `{handoff}` — your task brief (background, goal, deliverables, file ownership, out of scope)

**You must maintain `{progress}`** (format: `{tpl}`):
one entry when you start, one for each deliverable unit you complete, and a handoff
note when you stop. The four blocks at the top are required:
Contracts I publish · What I depend on · Changes I need from others · Files I own.

**Append one line to `{board}`** at each of these moments (append only — never edit
someone else's line): start · contract published · contract CHANGED · blocked ·
unblocked · done.
Format: `YYYY-MM-DD HH:MM | {code} | event | note`

**Parallel-work discipline:**
- Only write the files HANDOFF.md declares as yours. Everything else is read-only.
  Need a change in someone else's file? Record it under "Changes I need from others" —
  do not edit it yourself.
- If others depend on you, publish your interface contract on day one, before the
  implementation is finished. If a published contract has to change, say so on the
  board as a CHANGED entry and name who is affected.
- When blocked, do the parts that do not depend on the answer. Write the question
  under "Open decisions" along with the default you are proceeding on. Do not stall.
- Do not infer from code alone: run pages in a browser and screenshot them, connect to
  the database and run the queries, paste the grep output.
- Report honestly. If it is not done, say it is not done. If a test failed, paste the output."""

PROMPT_ZH = """你是本项目的子代理，负责任务「{task}」（编号 {code}）。

**开工前按顺序读这几份，一份都不能跳：**
1. `{readme}` —— 通用工作准则（项目背景与硬性约束）
{guide}{n}. `{handoff}` —— 你的任务书（背景、目标、交付物、文件所有权、明确不做）

**工作期间你必须维护 `{progress}`**（格式见 `{tpl}`）：
开工记一条，每完成一个可交付单元记一条，收工必须留下交接说明。
顶部四块必须填：契约（供他人依赖）· 我依赖谁 · 需要他人改动 · 文件所有权。

**在这些时刻往 `{board}` 追加一行**（只追加，不修改别人的行）：
开工 · 契约发布 · ⚠️契约变更 · 被阻塞 · 解除阻塞 · 收工。
格式：`日期 时间 | {code} | 事件 | 说明`

**并行纪律：**
- 只写 HANDOFF.md 里声明归你的文件；别人的文件只读。要改别人的，写进「需要他人改动」，不要自己动手。
- 被依赖的话第一天就发布接口契约，不要等实现做完。契约发布后要改，必须在看板写一行 ⚠️契约变更。
- 被阻塞时先做不依赖这个答案的部分，把问题写进「待决策」并说明你按哪个默认往下做，不要停在那里等。
- 不许只凭代码推断：页面要真跑起来截图，数据库要真连上跑，外链合规要贴 grep 输出。
- 诚实报告。没做完就说没做完，测试没过就贴输出。"""

GUIDE_LINE = {"en": "2. `%s` — file ownership, interface contracts, status board rules\n",
              "zh": "2. `%s` —— 文件所有权、接口契约、状态看板规则\n"}
EXTRA_HDR = {"en": "\n\n**Extra instructions for this dispatch:**\n",
             "zh": "\n\n**本次派发的额外指示：**\n"}


def compose_prompt(sa, task, extra="", lang="auto"):
    """Build the dispatch prompt that puts the agent inside the SubAgents protocol."""
    if lang == "auto":
        lang = workspace_lang(sa)
    guide_name = pick(sa, GUIDE_NAMES)
    has_guide = (sa / guide_name).exists()
    body = (PROMPT_ZH if lang == "zh" else PROMPT_EN).format(
        task=task, code=task_code(task),
        readme=sa / "README.md",
        guide=(GUIDE_LINE[lang] % (sa / guide_name)) if has_guide else "",
        n=3 if has_guide else 2,
        handoff=sa / task / "HANDOFF.md",
        progress=sa / task / "PROGRESS.md",
        tpl=sa / "_TEMPLATE" / "PROGRESS.md",
        board=sa / pick(sa, BOARD_NAMES))
    return body + (EXTRA_HDR[lang] + extra if extra else "")


# ----------------------------------------------------------------- agentapi

def agentapi(args):
    port, token, ls_path = endpoint()
    shim = Path.home() / ".gemini" / "antigravity" / "bin" / "agentapi"
    cmd = [str(shim)] if shim.exists() else [ls_path, "agentapi"]
    env = dict(os.environ,
               ANTIGRAVITY_LS_ADDRESS="127.0.0.1:%d" % port,
               ANTIGRAVITY_CSRF_TOKEN=token)
    r = subprocess.run(cmd + args, capture_output=True, text=True, env=env)
    text = (r.stdout or r.stderr).strip()
    try:
        d = json.loads(text)
    except Exception:
        raise AgError("agentapi returned unparseable output:\n%s" % text)
    if d.get("error"):
        raise AgError(d["error"])
    return d.get("response", {})


# ------------------------------------------------------------------ helpers

def summaries():
    return rpc("GetAllCascadeTrajectories", {}).get("trajectorySummaries", {}) or {}


def status_of(cid):
    s = summaries().get(cid)
    if s is None:
        raise AgError("No such conversation: %s" % cid)
    return s


def transcript(cid):
    return rpc("ConvertTrajectoryToMarkdown", {"conversationId": cid}).get("markdown", "")


def wait_for(cid, timeout, quiet=False):
    """Block until the agent goes idle. Returns the final status string."""
    start = time.time()
    seen_busy = False
    grace = 8.0          # a just-dispatched agent can read idle before it spins up
    while True:
        st = status_of(cid).get("status", "")
        if st in BUSY:
            seen_busy = True
        elif seen_busy or (time.time() - start) > grace:
            return st
        if time.time() - start > timeout:
            raise AgError("Timed out after %ds waiting for %s (status %s). The agent is "
                          "still running; poll it with `agdispatch status %s`."
                          % (timeout, cid, st, cid))
        if not quiet:
            sys.stderr.write("\r  waiting… %ds" % int(time.time() - start))
            sys.stderr.flush()
        time.sleep(3)


# ----------------------------------------------------------------- commands

def cmd_doctor(a):
    port, token, ls_path = endpoint()
    print("Agent Manager  : running")
    print("RPC endpoint   : http://127.0.0.1:%d" % port)
    print("language_server: %s" % ls_path)
    print("projects       : %d" % len(load_projects()))
    print("conversations  : %d" % len(summaries()))
    print("\nOK — ready to dispatch.")


def cmd_projects(a):
    for p in load_projects():
        print("%-38s  %-28s  %s" % (p["id"], p["name"][:28],
                                    p["paths"][0] if p["paths"] else ""))


def cmd_workspace(a):
    sa = find_subagents(a.subagents)
    board, guide = pick(sa, BOARD_NAMES), pick(sa, GUIDE_NAMES)
    print("SubAgents    : %s" % sa)
    print("convention   : %s" % workspace_lang(sa))
    for label, name in (("README", "README.md"), ("collaboration", guide),
                        ("status board", board), ("_TEMPLATE", "_TEMPLATE")):
        print("%-13s: %s" % (label, "yes" if (sa / name).exists() else "MISSING"))
    print("\ntasks:")
    for d in sorted(p for p in sa.iterdir() if p.is_dir() and not p.name.startswith((".", "_"))):
        h, pr = d / "HANDOFF.md", d / "PROGRESS.md"
        if not h.exists():
            state = "no HANDOFF"
        elif any(x in h.read_text(encoding="utf-8", errors="replace") for x in UNFILLED):
            state = "HANDOFF unfilled"
        elif not pr.exists():
            state = "not started"
        else:
            txt = pr.read_text(encoding="utf-8", errors="replace")
            state = ("PROGRESS empty" if any(x in txt for x in EMPTY_PROGRESS)
                     else "delivered" if any(x in txt for x in DELIVERED)
                     else "in progress")
        print("  %-30s %-12s %s" % (d.name, task_code(d.name), state))


def cmd_new_task(a):
    sa = find_subagents(a.subagents)
    tpl = sa / "_TEMPLATE"
    if not tpl.is_dir():
        raise AgError("No _TEMPLATE in %s — nothing to copy from." % sa)
    dest = sa / a.task
    if dest.exists():
        raise AgError("%s already exists." % dest)
    subprocess.run(["cp", "-r", str(tpl), str(dest)], check=True)
    print("created %s" % dest)
    print("\nNext: fill in %s/HANDOFF.md — background, goal, deliverables table,\n"
          "      file-ownership declaration, constraints, out-of-scope, and open\n"
          "      decisions with a default for each. Then:\n"
          "      agdispatch dispatch --task %s" % (dest, a.task))


def cmd_board(a):
    print(board_append(find_subagents(a.subagents), a.code, a.event, a.note))


def cmd_dispatch(a):
    sa = None
    prompt = a.prompt
    if a.task:
        sa = find_subagents(a.subagents)
        check_handoff(sa, a.task)
        prompt = compose_prompt(sa, a.task, a.prompt or "", a.lang)
        if not a.title:
            a.title = a.task
        if a.project == "auto":
            a.project = str(sa)
    elif not prompt:
        raise AgError("Nothing to dispatch: give a prompt, or --task <id-task-name>.")

    pid = resolve_project(a.project)
    if a.dry_run:
        print("# project: %s   model: %s   title: %s\n" % (pid, a.model, a.title or "—"))
        print(prompt)
        return

    args = ["new-conversation", "--model=%s" % a.model]
    if a.title:
        args.append("--title=%s" % a.title)
    if a.profile:
        args.append("--profile=%s" % a.profile)
    args.append(prompt)

    env_backup = os.environ.get("ANTIGRAVITY_PROJECT_ID")
    os.environ["ANTIGRAVITY_PROJECT_ID"] = pid
    try:
        resp = agentapi(args)
    finally:
        if env_backup is None:
            os.environ.pop("ANTIGRAVITY_PROJECT_ID", None)
        else:
            os.environ["ANTIGRAVITY_PROJECT_ID"] = env_backup

    cid = resp.get("newConversation", {}).get("conversationId")
    if not cid:
        raise AgError("Dispatch returned no conversation id: %s" % resp)

    if sa is not None:
        # The dispatch itself is a board event — that line is how a human later
        # ties a conversation id back to a task folder.
        board_append(sa, a.by, "dispatched" if workspace_lang(sa) == "en" else "派发",
                     "%s (Antigravity %s, conversation %s)" % (a.task, a.model, cid))
        covered = [w for w in project_paths(pid)
                   if str(sa).startswith(os.path.realpath(w))]
        if not covered:
            print("warning: %s is not inside the '%s' workspace — the agent may not be\n"
                  "         able to read its HANDOFF.md or write PROGRESS.md. Use --project\n"
                  "         on a project that covers both the notes and the code.\n"
                  % (sa, pid), file=sys.stderr)

    if not a.wait:
        out = {"conversationId": cid, "projectId": pid,
               "model": a.model, "status": "dispatched"}
        if a.task:
            out["task"] = a.task
            out["progress"] = str(sa / a.task / "PROGRESS.md")
            out["board"] = str(sa / pick(sa, BOARD_NAMES))
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return
    st = wait_for(cid, a.timeout)
    sys.stderr.write("\r" + " " * 30 + "\r")
    print("# conversation: %s   (final status: %s)\n" % (cid, st))
    print(transcript(cid))


def cmd_send(a):
    agentapi(["send-message"] + (["--title=%s" % a.title] if a.title else [])
             + [a.conversation_id, a.message])
    if not a.wait:
        print(json.dumps({"conversationId": a.conversation_id,
                          "status": "message sent"}, indent=2))
        return
    st = wait_for(a.conversation_id, a.timeout)
    sys.stderr.write("\r" + " " * 30 + "\r")
    print("# conversation: %s   (final status: %s)\n" % (a.conversation_id, st))
    print(transcript(a.conversation_id))


def cmd_status(a):
    s = status_of(a.conversation_id)
    print(json.dumps({
        "conversationId": a.conversation_id,
        "title": s.get("annotations", {}).get("title") or s.get("summary"),
        "status": s.get("status"),
        "running": s.get("status") in BUSY,
        "stepCount": s.get("stepCount"),
        "lastModified": s.get("lastModifiedTime"),
        "projectId": s.get("trajectoryMetadata", {}).get("projectId"),
    }, indent=2, ensure_ascii=False))


def cmd_result(a):
    print(transcript(a.conversation_id))


def cmd_wait(a):
    st = wait_for(a.conversation_id, a.timeout)
    sys.stderr.write("\r" + " " * 30 + "\r")
    print(st)


def cmd_list(a):
    rows = []
    for cid, s in summaries().items():
        rows.append((s.get("lastModifiedTime", ""), cid, s.get("status", ""),
                     (s.get("annotations", {}).get("title") or s.get("summary") or "")[:52]))
    rows.sort(reverse=True)
    for t, cid, st, title in rows[:a.limit]:
        print("%-38s  %-12s  %-19s  %s"
              % (cid, st.replace("CASCADE_RUN_STATUS_", ""), t[:19], title))


def cmd_cancel(a):
    rpc("ForceStopCascadeTree", {"conversationId": a.conversation_id})
    print("cancel requested for %s" % a.conversation_id)


# -------------------------------------------------------------------- main

def main():
    p = argparse.ArgumentParser(prog="agdispatch", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("doctor", help="verify connectivity to the Agent Manager").set_defaults(fn=cmd_doctor)
    sub.add_parser("projects", help="list Antigravity projects").set_defaults(fn=cmd_projects)

    d = sub.add_parser("dispatch", help="start a new Antigravity agent")
    d.add_argument("prompt", nargs="?", default="",
                   help="the prompt; with --task this is appended as extra instructions")
    d.add_argument("--task", help="SubAgents task dir: wraps the dispatch in the "
                                  "HANDOFF / PROGRESS / status-board protocol")
    d.add_argument("--subagents", help="path to the SubAgents directory (default: auto-detect)")
    d.add_argument("--lang", default="auto", choices=("auto", "en", "zh"),
                   help="language of the composed protocol prompt")
    d.add_argument("--by", default="lead", help="who dispatched, for the board line")
    d.add_argument("--project", default="auto",
                   help="project id, name, or path; 'auto' (default) matches cwd, "
                        "'none' runs outside any project")
    d.add_argument("--model", default="flash", choices=MODELS)
    d.add_argument("--title")
    d.add_argument("--profile")
    d.add_argument("--wait", action="store_true", help="block until idle, then print the transcript")
    d.add_argument("--timeout", type=int, default=900)
    d.add_argument("--dry-run", action="store_true",
                   help="print the composed prompt and resolved project, dispatch nothing")
    d.set_defaults(fn=cmd_dispatch)

    ws = sub.add_parser("workspace", help="show the SubAgents layout and per-task state")
    ws.add_argument("--subagents")
    ws.set_defaults(fn=cmd_workspace)

    n = sub.add_parser("new-task", help="copy _TEMPLATE into a new task directory")
    n.add_argument("task", help="id-task-name, e.g. W2-A-search-ranking")
    n.add_argument("--subagents")
    n.set_defaults(fn=cmd_new_task)

    b = sub.add_parser("board", help="append one line to the status board")
    b.add_argument("code", help="task id, or your own name for coordination entries")
    b.add_argument("event", help="start / contract published / CHANGED / blocked / unblocked / done")
    b.add_argument("note")
    b.add_argument("--subagents")
    b.set_defaults(fn=cmd_board)

    s = sub.add_parser("send", help="send a follow-up message to a conversation")
    s.add_argument("conversation_id")
    s.add_argument("message")
    s.add_argument("--title")
    s.add_argument("--wait", action="store_true")
    s.add_argument("--timeout", type=int, default=900)
    s.set_defaults(fn=cmd_send)

    for name, fn, helptext in (("status", cmd_status, "show one conversation's status"),
                               ("result", cmd_result, "print a conversation transcript as markdown"),
                               ("cancel", cmd_cancel, "stop a running agent")):
        c = sub.add_parser(name, help=helptext)
        c.add_argument("conversation_id")
        c.set_defaults(fn=fn)

    w = sub.add_parser("wait", help="block until a conversation goes idle")
    w.add_argument("conversation_id")
    w.add_argument("--timeout", type=int, default=900)
    w.set_defaults(fn=cmd_wait)

    l = sub.add_parser("list", help="list recent conversations")
    l.add_argument("--limit", type=int, default=20)
    l.set_defaults(fn=cmd_list)

    a = p.parse_args()
    try:
        a.fn(a)
    except AgError as e:
        print("error: %s" % e, file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
