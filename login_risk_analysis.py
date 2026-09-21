import os,re,shutil,subprocess
from pathlib import Path
from download_bins import download_apkeditor
from xhs_build_ci import BINS_DIR,OUTPUT_DIR,download_apk,ensure_dirs,run,sha256

URL="https://dl.coolapk.com/down?pn=com.xingin.xhs&id=15276&v=MTUyNzY&type=apk&from=market-v13&vc=9334801&nd=0&h=3c30e27f"
PATS=re.compile(r"(安全|风险|异常|验证|登录|账号|手机号|手机号码|security|risk|abnormal|verify|challenge|login|signin|sms|captcha|country.?code|area.?code|\+86|mainland|oversea|device.?id|fingerprint|attest|integrity|root|magisk|xposed|tamper|one.?click|onekey|carrier|com/unicom/online/account|com/mobile/auth)",re.I)
FIRST=re.compile(r"(login|account|auth|security|risk|passport)",re.I)
NATIVE=re.compile(r"(login|account|phone|mobile|risk|security|verify|captcha|token|device|fingerprint|sign|cert|root|xposed|magisk|hook|tamper)",re.I)

def ctx(lines,i,r=6):
    return "\n".join(f"{n+1:6d}: {lines[n]}" for n in range(max(0,i-r),min(len(lines),i+r+1)))

def main():
    ensure_dirs(); base=download_apk(URL)
    jar=os.path.join(BINS_DIR,"apkeditor.jar")
    if not os.path.exists(jar): download_apkeditor()
    dec="xhs_login_risk_analysis"
    if os.path.exists(dec): shutil.rmtree(dec)
    run("java","-Xmx8g","-jar",jar,"d","-f","-i",base,"-o",dec)
    out=["XHS login/risk static analysis","==============================",f"base_sha256={sha256(base)}",""]
    hits=[]
    for p in Path(dec,"smali").rglob("*.smali"):
        try: text=p.read_text(encoding="utf-8")
        except: continue
        rel=str(p).replace("\\","/"); lines=text.splitlines()
        for i,line in enumerate(lines):
            if PATS.search(line) and "dalvik/annotation/Signature" not in line:
                score=(5 if "/com/xingin/" in rel or "/com/xingyin/" in rel else 0)+(4 if FIRST.search(rel) else 0)+(3 if "const-string" in line else 0)
                hits.append((score,rel,i,ctx(lines,i)))
    hits.sort(key=lambda x:(-x[0],x[1],x[2]))
    for n,(s,rel,i,c) in enumerate(hits[:700],1):
        out += [f"[{n}] score={s} {rel}:{i+1}",c,""]
    out += ["","## first-party callers into carrier SDKs",""]
    n=0
    for p in Path(dec,"smali").rglob("*.smali"):
        rel=str(p).replace("\\","/")
        if "/com/xingin/" not in rel and "/com/xingyin/" not in rel: continue
        try: lines=p.read_text(encoding="utf-8").splitlines()
        except: continue
        for i,line in enumerate(lines):
            low=line.lower()
            if any(k in low for k in ("com/unicom/online/account","com/mobile/auth","onekey","oneclick","carrier")):
                n+=1; out += [f"[{n}] {rel}:{i+1}",ctx(lines,i,10),""]
                if n>=200: break
        if n>=200: break
    out += ["","## native security/login strings",""]
    names=("libsecurebase.so","libdexvmp.so","libentryexpro.so","libxEF4.so","libcapahook.so","libapkpatch.so")
    by={p.name:p for p in Path(dec).rglob("*.so")}
    for name in names:
        p=by.get(name)
        if not p: continue
        out += [f"### {name}"]
        r=subprocess.run(["strings","-a","-n","5",str(p)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,errors="replace")
        vals=[x for x in r.stdout.splitlines() if NATIVE.search(x)]
        out += vals[:200] or ["(none)"]
    path=Path(OUTPUT_DIR,"login-risk-analysis.txt")
    path.write_text("\n".join(out),encoding="utf-8")
    print(path.read_text(encoding="utf-8")[:120000])

if __name__=="__main__": main()
