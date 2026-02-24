#!/bin/bash
# 钠API 配置工具 - Mac 一键启动

cd "$(dirname "$0")"

APP_NAME="NaAPICodex.app"
APP_PATH="./$APP_NAME"

# 如果同目录下没有 .app，尝试 ~/Downloads
if [ ! -d "$APP_PATH" ]; then
    APP_PATH="$HOME/Downloads/$APP_NAME"
fi

if [ ! -d "$APP_PATH" ]; then
    echo "未找到 $APP_NAME"
    echo "请将本脚本放在 $APP_NAME 同目录下，或确保 .app 在 ~/Downloads 中"
    read -p "按回车键退出..."
    exit 1
fi

echo "正在配置 macOS 环境..."

# 1. 移除 quarantine 隔离属性
echo "  → 移除 quarantine 隔离属性..."
xattr -dr com.apple.quarantine "$APP_PATH" 2>/dev/null
echo "隔离属性已移除"

# 2. 写入 Claude Code onboarding 跳过标记
CLAUDE_JSON="$HOME/.claude.json"
echo "  → 配置 Claude Code onboarding 跳过..."
if [ -f "$CLAUDE_JSON" ]; then
    # 文件已存在，检查是否已有 hasCompletedOnboarding
    if grep -q "hasCompletedOnboarding" "$CLAUDE_JSON"; then
        echo "Claude Code onboarding 已配置"
    else
        # 在最后一个 } 前插入字段（简单处理：用 python 操作 JSON）
        python3 -c "
import json, pathlib
p = pathlib.Path('$CLAUDE_JSON')
d = json.loads(p.read_text())
d['hasCompletedOnboarding'] = True
p.write_text(json.dumps(d, indent=2, ensure_ascii=False) + '\n')
" 2>/dev/null && echo "Claude Code onboarding 已配置" || echo "配置失败，可手动处理"
    fi
else
    echo '{"hasCompletedOnboarding": true}' > "$CLAUDE_JSON"
    echo "Claude Code onboarding 已配置"
fi

# 3. 启动应用
echo ""
echo "正在启动 $APP_NAME ..."
open "$APP_PATH"

echo "启动完成！本窗口可关闭。"
