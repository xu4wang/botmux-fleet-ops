#!/bin/zsh
# ~/amber 单写入者锁：同一时间只允许一个会话改这个仓库（2026-10-08 定）。
# 用法：amber-writer-lock.sh acquire [说明] | release | status | check
# 锁文件放在 .git 里，不进版本库。超过 4 小时没刷新视为过期，可以被接管。
set -u
REPO=${AMBER_REPO:-$HOME/amber}
LOCK=$REPO/.git/amber-writer.lock
TTL=$((4*3600))
SID=${BOTMUX_SESSION_ID:-}
now=$(date +%s)
read_lock(){ [ -f $LOCK ] && { owner=$(sed -n 1p $LOCK); since=$(sed -n 2p $LOCK); note=$(sed -n 3p $LOCK); } || owner=""; }
read_lock
stale(){ [ -n "$owner" ] && [ $((now - since)) -gt $TTL ]; }
describe(){ echo "占用者: ${owner}  起始: $(date -r ${since} '+%m-%d %H:%M')  说明: ${note:-无}"; }
case ${1:-status} in
  acquire)
    [ -n "$SID" ] || { echo "没有 BOTMUX_SESSION_ID，不能加锁（人在终端里改不需要锁）"; exit 2; }
    if [ -n "$owner" ] && [ "$owner" != "$SID" ] && ! stale; then echo "❌ 仓库正被别的会话写入"; describe; exit 1; fi
    [ -n "$owner" ] && [ "$owner" != "$SID" ] && echo "接管过期锁：$(describe)"
    printf '%s\n%s\n%s\n' "$SID" "$now" "${2:-}" > $LOCK; echo "✅ 已加锁（本会话 $SID）";;
  release)
    if [ "$owner" = "$SID" ]; then rm -f $LOCK; echo "✅ 已释放"; elif [ -z "$owner" ]; then echo "本来就没有锁"; else echo "❌ 锁不是本会话的，不能释放"; describe; exit 1; fi;;
  check)  # 给 git 钩子用：会话里提交/推送前必须持有锁；人在终端里（没有会话 id）放行
    [ -z "$SID" ] && exit 0
    [ "$owner" = "$SID" ] && { printf '%s\n%s\n%s\n' "$SID" "$now" "$note" > $LOCK; exit 0; }   # 顺便刷新时间
    echo "❌ ~/amber 同一时间只允许一个会话写入。" >&2
    if [ -n "$owner" ] && ! stale; then echo "   $(describe)" >&2; else echo "   当前没有会话持锁，先执行：~/.botmux/ops-scripts/amber-writer-lock.sh acquire \"<改什么>\"" >&2; fi
    exit 1;;
  status|*) if [ -z "$owner" ]; then echo "空闲"; elif stale; then echo "已过期：$(describe)"; else describe; fi;;
esac
