#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
target_dir="$HOME/.local/bin"
target="$target_dir/gflow"
mkdir -p "$target_dir"
ln -sfn "$script_dir/gflow.py" "$target"
chmod +x "$script_dir/gflow.py"

line='export PATH="$HOME/.local/bin:$PATH"'
if ! grep -Fqx "$line" "$HOME/.zshrc" 2>/dev/null; then
    printf '\n%s\n' "$line" >> "$HOME/.zshrc"
fi

printf '已安装：%s\n' "$target"
printf '运行 source ~/.zshrc 后，即可在任意 Git 仓库使用 gflow。\n'
