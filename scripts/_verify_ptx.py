import subprocess, os, sys, re
sys.stdout.reconfigure(encoding='utf-8')
CUOBJ = r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6\bin\cuobjdump.exe"
targets = [
    r"E:\AI\ninfer-rtx30-x64\ninfer-serve.exe",
    r"E:\AI\ninfer3090\ninfer-rtx3090-windows-x64-0.11.0-rtx3090\ninfer-serve.exe",
]
for t in targets:
    print("="*70)
    print(t, os.path.exists(t), f"{os.path.getsize(t)/1048576:.1f}MB" if os.path.exists(t) else "")
    for flag, label in [("-lelf","SASS/cubin(ELF)"), ("-lptx","PTX")]:
        try:
            r = subprocess.run([CUOBJ, flag, t], capture_output=True, text=True, timeout=300, errors="replace")
            lines = (r.stdout + r.stderr)
            archs = re.findall(r'\.(sm_\d+[a-z]?)\.', lines)
            from collections import Counter
            print(f"  -- {flag} rc={r.returncode} lines={len(lines.splitlines())} archs={Counter(archs)}")
            for ln in lines.splitlines()[:6]:
                print("     ", ln.strip()[:160])
        except Exception as e:
            print("  ERR", flag, e)
