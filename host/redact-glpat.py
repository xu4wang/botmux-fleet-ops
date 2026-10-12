#!/usr/bin/env python3
"""机队 GitLab PAT 脱敏器。默认 --dry-run 只报告不改文件。
token 由本机自行发现，不经参数传入，避免明文横穿网络/日志。
只清「日志/记账/transcript」类落点；专门存凭证的文件与 git 仓库内文件一律不动。"""
import os,re,sys,glob,math,hashlib,collections,shutil,time,json
H=os.path.expanduser("~")
DRY = "--apply" not in sys.argv
PURGE = "--purge-evidence" in sys.argv
EVID = os.path.join(H, "redact-evidence-" + time.strftime("%Y%m%d-%H%M%S"))
P=re.compile(rb'glpat-[A-Za-z0-9_-]{20}')
def ent(s):
    c=collections.Counter(s); n=len(s)
    return -sum(v/n*math.log2(v/n) for v in c.values())
def placeholder(t):
    b=t[6:].decode(); l=b.lower()
    return any(w in l for w in ("abcdef","example","xxxx","1234567","placeholder","dummy","fake")) or len(set(b))<=8 or ent(b)<3.4
# 清理目标：只有日志/记账/transcript 类
TARGETS=[]
for pat in [".botmux/usage/*.jsonl",".botmux/data/queues/*.jsonl",".botmux/data/sessions-*.json",
            ".botmux/data/turn-sends/*.jsonl",".botmux/logs/*.log",
            ".botmux/bots/*/claude/history.jsonl",".botmux/bots/*/claude/projects/*/*.jsonl",
            ".claude/history.jsonl",".claude/projects/*/*.jsonl",".claude-replay/autosave/*.json",
            ".zsh_history",".bash_history",".zsh_sessions/*.history"]:
    TARGETS+=glob.glob(os.path.join(H,pat))
# 明确豁免：专门存凭证的文件（该轮换+改权限，不是该改内容）
EXEMPT=re.compile(r'(token|credential|secret|\.gitlab)', re.I)
host=os.popen("scutil --get LocalHostName").read().strip()
changed=[]
tot_f=tot_l=0; toks=set()
rep=[]
for f in sorted(set(TARGETS)):
    if EXEMPT.search(os.path.basename(f)) and "history" not in f: continue
    try: data=open(f,"rb").read()
    except Exception: continue
    hits=[t for t in set(P.findall(data)) if not placeholder(t)]
    if not hits: continue
    nl=sum(1 for line in data.split(b"\n") if any(t in line for t in hits))
    toks.update(hits); tot_f+=1; tot_l+=nl
    rep.append((f.replace(H,"~"),len(hits),nl))
    if not DRY:
        # 备份进隔离目录(700)，不是原地留 .pre-redact —— 原地备份会让清理退化成改名
        b=os.path.join(EVID, os.path.relpath(f,H))
        os.makedirs(os.path.dirname(b),exist_ok=True); os.chmod(EVID,0o700)
        shutil.copy2(f,b); os.chmod(b,0o600)
        new=data
        for t in hits:
            tag=b"glpat-REDACTED-"+hashlib.sha256(t).hexdigest()[:8].encode()
            new=new.replace(t,tag)
        open(f,"wb").write(new)
        changed.append((f,b))
print(f"### {host}  [{'DRY-RUN 未改动' if DRY else 'APPLIED'}]  {tot_f} 文件 / {tot_l} 行 / {len(toks)} token")
for f,nt,nl in rep: print(f"    {nl:>4} 行  {nt} token  {f}")

if not DRY:
    # 1) 记账安全闸：usage-*.jsonl 被 baselineFromLedger() 当崩溃恢复的真相源重读，
    #    而它对 JSON.parse 失败的行是【静默跳过】—— 一行坏掉就会退回更旧的 baseline，
    #    导致下一次 reconcile 重复计费。所以改完必须逐行验 JSON，坏了立刻整体回滚。
    bad=[]
    for f,b in changed:
        if not f.endswith(".jsonl"): continue
        for i,line in enumerate(open(f,"rb").read().split(b"\n"),1):
            if not line.strip(): continue
            try: json.loads(line)
            except Exception: bad.append((f,i))
    if bad:
        print(f"\n!! JSON 校验失败 {len(bad)} 行，已从隔离备份整体回滚：")
        for f,b in changed: shutil.copy2(b,f)
        for f,i in bad[:10]: print(f"    {f.replace(H,'~')}:{i}")
        sys.exit(3)
    print(f"\n✅ 全部 {len([1 for f,_ in changed if f.endswith('.jsonl')])} 个 .jsonl 逐行 JSON 校验通过（记账不会因清理退回旧 baseline）")
    # 2) 明文证据的收尾必须在同一个脚本里做完，不能靠人记得
    if PURGE:
        shutil.rmtree(EVID, ignore_errors=True)
        print(f"✅ 隔离备份已删除：{EVID.replace(H,'~')}（回退依据用 --dry-run 报告）")
    else:
        n=sum(len(fs) for _,_,fs in os.walk(EVID))
        print(f"\n⚠️  仍有 {n} 个备份文件含明文 token，全部在 {EVID.replace(H,'~')}（700）")
        print("⚠️  清理尚未完成：这些备份和原文件同机、同用户可读，只是换了个路径。")
        print("⚠️  归档或删除后本次清理才算闭环 —— 重跑加 --purge-evidence 可让脚本自己删掉。")
