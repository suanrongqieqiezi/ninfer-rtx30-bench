import os, sys, re
sys.stdout.reconfigure(encoding='utf-8')
p = r"E:\AI\ninfer-rtx30-x64\ninfer-serve.exe"
print("size", os.path.getsize(p))
data = open(p,'rb').read()
print("raw '.target sm_86' occurrences:", data.count(b".target sm_86"))
for arch in [b".target sm_89", b".target sm_120a", b".target sm_120", b".target sm_80"]:
    print(" ", arch.decode(), data.count(arch))
print("version strings:")
for m in set(re.findall(rb"\.version \d+\.\d+", data)):
    print("   ", m.decode())
print("ptx .address_size occurrences:", data.count(b".address_size"))
