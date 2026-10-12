#!/usr/bin/env python3
"""分享卡提交内容敏感串扫描器。
用法:  card-secret-scan.py <file>            # 扫单个文件
       cat text | card-secret-scan.py -      # 扫 stdin
输出:  JSON {verdict, findings:[{rule,severity,masked,line}]}
verdict: BLOCK(含密钥类,禁止上墙) / REVIEW(含个人信息或业务敏感,人工过目) / PASS
退出码: 2=BLOCK 1=REVIEW 0=PASS  (方便挂 Base 自动化)
"""
import sys,re,json,math,collections

def ent(s):
    if not s: return 0.0
    c=collections.Counter(s); n=len(s)
    return -sum(v/n*math.log2(v/n) for v in c.values())

def is_placeholder(s):
    """白名单：测试占位符 / 示例串，避免测试数据天天误报"""
    l=s.lower()
    if any(w in l for w in ("abcdef","example","placeholder","dummy","fake","xxxx","yyyy",
                            "1234567","your_","<your","changeme","redacted","foobar","test123")):
        return True
    body=re.sub(r'^[a-z]+[-_]','',l)            # 剥掉 glpat- / ghp_ 之类前缀
    if len(set(body))<=8: return True           # 字符多样性过低
    if len(body)>=16 and ent(body)<3.4: return True
    return False

def luhn(d):
    t=0
    for i,ch in enumerate(reversed(d)):
        v=int(ch)
        if i%2: v*=2; v-=9 if v>9 else 0
        t+=v
    return t%10==0

# (规则名, 正则, 严重度, 是否套占位符白名单)
RULES=[
 ("gitlab-pat",      r'glpat-[A-Za-z0-9_-]{20}',                        "BLOCK", True),
 ("github-pat",      r'gh[pousr]_[A-Za-z0-9]{36,}',                     "BLOCK", True),
 ("anthropic-key",   r'sk-ant-[A-Za-z0-9_-]{20,}',                      "BLOCK", True),
 ("openai-key",      r'sk-[A-Za-z0-9]{32,}',                            "BLOCK", True),
 ("aws-akid",        r'AKIA[0-9A-Z]{16}',                               "BLOCK", True),
 ("slack-token",     r'xox[bpasr]-[A-Za-z0-9-]{10,}',                   "BLOCK", True),
 ("feishu-appsecret",r'\b(?:cli_[a-z0-9]{16})\b',                       "REVIEW",False),
 ("jdbc-dsn",        r'jdbc:[a-z0-9]+://[^\s"\']+',                     "BLOCK", False),
 ("private-key",     r'-----BEGIN [A-Z ]*PRIVATE KEY-----',             "BLOCK", False),
 ("generic-passwd",  r'(?i)(?:password|passwd|pwd|secret|token)\s*[=:]\s*["\']?[^\s"\',;]{8,}', "REVIEW", True),
 ("merchant-no",     r'\bM00\d{5,7}\b',                                 "REVIEW",False),
 ("email",           r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b', "REVIEW",False),
 ("cn-mobile",       r'(?<!\d)1[3-9]\d{9}(?!\d)',                       "REVIEW",False),
 ("long-digits",     r'(?<!\d)\d{12,19}(?!\d)',                         "REVIEW",False),
]

def mask(s):
    if len(s)<=10: return s[:3]+"*"*max(0,len(s)-3)
    return s[:8]+"*"*6+s[-3:]

def scan(text):
    out=[]
    lines=text.split("\n")
    for name,pat,sev,wl in RULES:
        rx=re.compile(pat)
        for i,line in enumerate(lines,1):
            for m in rx.finditer(line):
                v=m.group(0)
                if wl and is_placeholder(v): continue
                if name=="long-digits":
                    d=v
                    sev2="REVIEW" if (13<=len(d)<=19 and luhn(d)) else "REVIEW"
                    name2="bank-card(Luhn通过)" if (13<=len(d)<=19 and luhn(d)) else name
                    out.append({"rule":name2,"severity":sev2,"masked":mask(v),"line":i})
                    continue
                out.append({"rule":name,"severity":sev,"masked":mask(v),"line":i})
    seen=set(); ded=[]
    for f in out:
        k=(f["rule"],f["masked"],f["line"])
        if k in seen: continue
        seen.add(k); ded.append(f)
    verdict="BLOCK" if any(f["severity"]=="BLOCK" for f in ded) else ("REVIEW" if ded else "PASS")
    return {"verdict":verdict,"count":len(ded),"findings":ded}

if __name__=="__main__":
    src=sys.argv[1] if len(sys.argv)>1 else "-"
    text=sys.stdin.read() if src=="-" else open(src,errors="replace").read()
    r=scan(text)
    print(json.dumps(r,ensure_ascii=False,indent=2))
    sys.exit({"BLOCK":2,"REVIEW":1,"PASS":0}[r["verdict"]])
