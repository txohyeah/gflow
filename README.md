# gflow

一个适用于多个 Git 仓库的轻量终端菜单。只依赖 Python 3 和 Git；在任意仓库目录运行同一个命令。

## 安装（macOS / zsh）

```sh
./install.sh
source ~/.zshrc
```

安装脚本会把 `gflow` 链接到 `~/.local/bin/gflow`，并在需要时把该目录加入 `~/.zshrc` 的 `PATH`。代码更新后无需重新安装。运行 `gflow --help` 检查是否可用。

## 日常使用

进入任意 Git 仓库后运行 `gflow`，用上下箭头选择操作并按 Enter；多选文件时用空格勾选、Enter 确定，`q` 退出。

也可以直接运行：

```sh
gflow status  # 当前状态
gflow commit  # 选择文件、查看暂存 diff、输入说明、提交；随后可选择推送
gflow push    # 推送当前分支
gflow diff    # 选择文件，对比工作区或暂存内容
gflow log     # 选择提交，查看文件清单或 diff
```

在终端输入 `gflow diff ` 或 `gflow commit ` 后，可以从 Finder 拖入文件，让终端填入路径，再按 Enter。文件必须位于当前仓库中。

提交时，已暂存的内容会先显示并要求确认；新选择的文件会加入暂存区。提交前会列出最终暂存内容，并可查看完整 diff。取消提交不会撤销已经执行的暂存操作。推送不会强制覆盖远端。

## 开发

直接运行 `python3 gflow.py --help`。代码使用 Python 标准库，适配 macOS 系统自带的 Python 3。
