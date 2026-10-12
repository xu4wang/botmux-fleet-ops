#!/bin/zsh
# Data MCP outbox 过期清理（方案 B：宿主负责，独立于业务查询触发）
#
# 为什么需要它：服务侧 DATA_MCP_EXPORT_FILE_TTL_SECONDS 只在「下次导出前」触发清理，
# 机器长时间不导出就永远不清；而沙盒业务 bot 对 outbox 能读不能删（rm → EPERM）。两头都清不掉。
#
# 用法:
#   data-mcp-outbox-cleanup.sh              # 真删
#   data-mcp-outbox-cleanup.sh --dry-run    # 只打印「会删什么」，不删（首次落地务必先跑这个）
# 环境变量:
#   DATA_MCP_OUTBOX          必填：Data MCP 导出文件的 outbox 目录
#   DATA_MCP_OUTBOX_TTL_MIN  过期阈值，分钟，默认 120（服务侧默认 3600 秒，留一倍余量）
set -euo pipefail
setopt null_glob

OUTBOX="${DATA_MCP_OUTBOX:?请设置 DATA_MCP_OUTBOX=<Data MCP 的 outbox 目录>}"
TTL_MIN=${DATA_MCP_OUTBOX_TTL_MIN:-120}
LOG="$HOME/.botmux/logs/data-mcp-outbox-cleanup.log"
DRY=0
[[ "${1:-}" == "--dry-run" ]] && DRY=1

[ -d "$OUTBOX" ] || exit 0
# 拒绝软链：避免 outbox 被换成指向别处的链接后误删他人数据
[ ! -L "$OUTBOX" ] || { echo "$(date '+%F %T') ABORT outbox 是软链" >> "$LOG"; exit 1; }

n=0
# 只碰第一层（-mindepth 1 -maxdepth 1），outbox 根目录本身永不参与
# -mmin +TTL = 修改时间早于 TTL ⇒ 只删「够老的」，新导出不会被提前清
while IFS= read -r p; do
  [ -L "$p" ] && continue
  if [ "$DRY" = 1 ]; then
    echo "WOULD-DELETE $p"
  else
    rm -rf -- "$p"
  fi
  n=$((n+1))
done < <(find "$OUTBOX" -mindepth 1 -maxdepth 1 -mmin +"$TTL_MIN" -print)

if [ "$DRY" = 1 ]; then
  echo "DRY-RUN: 共 $n 项会被删除（ttl_min=$TTL_MIN），未执行任何删除"
else
  echo "$(date '+%F %T') cleaned=$n ttl_min=$TTL_MIN" >> "$LOG"
fi
