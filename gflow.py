#!/usr/bin/env python3
"""A small, dependency-free terminal UI for everyday Git work."""

import curses
import shutil
import subprocess
import sys
from pathlib import Path


def git(root, *args, check=True, capture=True):
    command = ["git", "-C", str(root), *args]
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE if capture else None,
                            stderr=subprocess.PIPE if capture else None)
    if check and result.returncode:
        message = result.stderr.strip() if capture else "Git command failed"
        raise RuntimeError(message or "Git command failed")
    return result


def repository():
    result = subprocess.run(["git", "rev-parse", "--show-toplevel"], text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        raise RuntimeError("请先进入一个 Git 仓库。")
    return Path(result.stdout.strip()).resolve()


def select(title, entries, multiple=False, allow_empty=False):
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise RuntimeError("选择菜单需要交互式终端。")
    if not entries:
        return [] if multiple else None

    def ui(screen):
        curses.curs_set(0)
        screen.keypad(True)
        cursor = top = 0
        marked = set()
        while True:
            height, width = screen.getmaxyx()
            screen.erase()
            hint = "↑↓移动  空格勾选  Enter确定  q取消" if multiple else "↑↓移动  Enter选择  q取消"
            screen.addnstr(0, 0, title, max(0, width - 1), curses.A_BOLD)
            screen.addnstr(1, 0, hint, max(0, width - 1))
            visible = max(1, height - 3)
            if cursor < top:
                top = cursor
            if cursor >= top + visible:
                top = cursor - visible + 1
            for row, index in enumerate(range(top, min(len(entries), top + visible)), 2):
                prefix = ("[x] " if index in marked else "[ ] ") if multiple else "    "
                label = prefix + entries[index]
                screen.addnstr(row, 0, label, max(0, width - 1),
                               curses.A_REVERSE if index == cursor else 0)
            screen.refresh()
            key = screen.getch()
            if key in (curses.KEY_UP, ord('k')):
                cursor = max(0, cursor - 1)
            elif key in (curses.KEY_DOWN, ord('j')):
                cursor = min(len(entries) - 1, cursor + 1)
            elif key == ord(' ') and multiple:
                if cursor in marked:
                    marked.remove(cursor)
                else:
                    marked.add(cursor)
            elif key in (10, 13, curses.KEY_ENTER):
                if multiple:
                    if marked or allow_empty:
                        return [entries[i] for i in sorted(marked)]
                else:
                    return entries[cursor]
            elif key in (ord('q'), 27):
                return None

    return curses.wrapper(ui)


def choose_one(title, values):
    picked = select(title, [label for label, _ in values])
    return next((value for label, value in values if label == picked), None)


def yes_no(title, default=False):
    values = [("是", True), ("否", False)] if default else [("否", False), ("是", True)]
    return choose_one(title, values) is True


def status_entries(root):
    raw = subprocess.run(["git", "-C", str(root), "status", "--porcelain=v1", "-z",
                          "--untracked-files=all"], stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, check=True).stdout
    fields = raw.decode("utf-8", "surrogateescape").split("\0")
    result = []
    i = 0
    while i < len(fields) and fields[i]:
        field = fields[i]
        code, path = field[:2], field[3:]
        old_path = None
        i += 1
        if "R" in code or "C" in code:
            old_path = fields[i]
            i += 1
        result.append((code, path, old_path))
    return result


def normalize_paths(root, paths):
    root = root.resolve()
    normalized = []
    for raw in paths:
        path = Path(raw).resolve()
        try:
            normalized.append(str(path.relative_to(root)))
        except ValueError:
            raise RuntimeError(f"文件不在当前仓库内：{raw}")
    return normalized


def pager(output):
    if not output:
        print("（没有 diff）")
        return
    if sys.stdout.isatty() and shutil.which("less"):
        subprocess.run(["less", "-R"], input=output, text=True)
    else:
        print(output, end="" if output.endswith("\n") else "\n")


def status(root):
    print(git(root, "status", "-sb").stdout, end="")


def diff(root, paths):
    if not paths:
        entries = status_entries(root)
        if not entries:
            print("没有文件改动。")
            return
        choices = [(f"{code}  {path}", path) for code, path, _ in entries]
        path = choose_one("选择要对比的文件", choices)
        if path is None:
            return
        paths = [path]
    for path in paths:
        entry = next((item for item in status_entries(root) if item[1] == path), None)
        if entry and entry[0] == "??":
            output = git(root, "-c", "color.ui=always", "diff", "--no-index", "--",
                         "/dev/null", path, check=False).stdout
            pager(output)
            continue
        view = choose_one(f"{path}：选择对比内容", [("工作区改动", "work"),
                                             ("已暂存改动", "staged")])
        if view is None:
            return
        args = ["-c", "color.ui=always", "diff"]
        if view == "staged":
            args.append("--cached")
        args.extend(["--", path])
        pager(git(root, *args).stdout)


def commit(root, paths):
    entries = status_entries(root)
    staged = [item for item in entries if item[0][0] not in (" ", "?")]
    if staged:
        print("当前已经暂存的文件会包含在本次提交中：")
        for code, path, _ in staged:
            print(f"  {code}  {path}")
        if not yes_no("继续使用当前暂存内容？"):
            return
    if not paths:
        available = [item for item in entries if item[0][1] != " " or item[0] == "??"]
        labels = [f"{code}  {path}" for code, path, _ in available]
        picked = select("选择要加入本次提交的文件（可以多选）", labels,
                        multiple=True, allow_empty=bool(staged)) if labels else []
        if picked is None:
            return
        paths = [available[labels.index(label)][1] for label in picked]
    if paths:
        chosen = []
        for path in paths:
            matched = next((item for item in entries if item[1] == path), None)
            chosen.append(path)
            if matched and matched[2]:
                chosen.append(matched[2])
        git(root, "add", "-A", "--", *chosen)
    staged_stat = git(root, "diff", "--cached", "--stat").stdout
    if not staged_stat:
        print("没有可提交的暂存改动。")
        return
    print("\n即将提交：\n" + staged_stat)
    if yes_no("查看完整 diff？", default=True):
        pager(git(root, "-c", "color.ui=always", "diff", "--cached").stdout)
    if not yes_no("确认提交上面这些改动？"):
        print("已取消提交；新暂存的文件仍保持暂存。")
        return
    message = input("提交说明：").strip()
    if not message:
        print("提交说明为空，已取消；暂存内容仍保留。")
        return
    git(root, "commit", "-m", message, capture=False)
    if yes_no("现在推送当前分支？"):
        push(root)


def push(root):
    branch = git(root, "symbolic-ref", "--quiet", "--short", "HEAD", check=False)
    if branch.returncode:
        raise RuntimeError("当前处于 detached HEAD，请先切换到分支。")
    branch_name = branch.stdout.strip()
    upstream = git(root, "rev-parse", "--abbrev-ref", "--symbolic-full-name",
                   "@{upstream}", check=False)
    print(f"当前分支：{branch_name}")
    if upstream.returncode == 0:
        target = upstream.stdout.strip()
        print(f"推送目标：{target}")
        outgoing = git(root, "log", "--oneline", "@{upstream}..HEAD", check=False).stdout
        print("待推送提交：\n" + (outgoing or "（本地记录中没有新提交）"))
        if yes_no("确认执行 git push？"):
            git(root, "push", capture=False)
        return
    remotes = git(root, "remote").stdout.splitlines()
    if not remotes:
        raise RuntimeError("当前仓库没有配置远端。")
    remote = choose_one("首次推送：选择远端", [(name, name) for name in remotes])
    if remote is None:
        return
    print(f"将推送 {branch_name} 到 {remote}/{branch_name}，并设置上游分支。")
    if yes_no("确认推送？"):
        git(root, "push", "-u", remote, f"HEAD:refs/heads/{branch_name}", capture=False)


def log(root):
    output = git(root, "log", "-30", "--format=%h  %cs  %s", check=False).stdout
    lines = output.splitlines()
    if not lines:
        print("还没有提交记录。")
        return
    picked = select("选择一次提交查看详情（最近 30 次）", lines)
    if picked:
        commit_id = picked.split()[0]
        view = choose_one("选择查看内容", [("文件清单", "stat"), ("选择文件看 diff", "file"),
                                          ("完整 diff", "diff")])
        if view:
            if view == "file":
                files = git(root, "diff-tree", "--no-commit-id", "--name-only", "-r",
                            "--root", commit_id).stdout.splitlines()
                path = select("选择该提交中的文件", files)
                if path:
                    pager(git(root, "-c", "color.ui=always", "show", commit_id,
                              "--", path).stdout)
                return
            args = ["-c", "color.ui=always", "show"]
            if view == "stat":
                args.append("--stat")
            pager(git(root, *args, commit_id).stdout)


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help", "help"):
        print("用法：gflow [status|commit|push|diff|log] [文件路径...]\n"
              "直接运行 gflow 可用菜单选择；commit/diff 可接收拖入终端的文件路径。")
        return
    root = repository()
    command = sys.argv[1] if len(sys.argv) > 1 else choose_one(
        "选择 Git 操作", [("查看状态", "status"), ("选择文件并提交", "commit"),
                       ("推送当前分支", "push"), ("对比文件", "diff"),
                       ("查看提交历史", "log")])
    if command is None:
        return
    commands = {"status": status, "commit": commit, "push": push, "diff": diff, "log": log}
    if command not in commands:
        raise RuntimeError(f"未知操作：{command}。运行 gflow --help 查看用法。")
    paths = sys.argv[2:]
    if paths and command not in ("commit", "diff"):
        raise RuntimeError("只有 commit 和 diff 接收文件路径。")
    if command in ("commit", "diff"):
        commands[command](root, normalize_paths(root, paths))
    else:
        commands[command](root)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, KeyboardInterrupt) as error:
        if str(error):
            print(f"错误：{error}", file=sys.stderr)
        sys.exit(1)
