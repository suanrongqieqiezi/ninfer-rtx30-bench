---
name: ninfer-port-and-tune
description: 在不被官方引擎支持的 GPU 架构（如 sm_86 / RTX 30 系）上，从源码移植、编译、补齐运行库并调优 ninfer 离线推理包（Bonsai-2-27B 三元量化）的完整流程。触发词：ninfer、极速档/均衡档/省显档、架构门、requires compute capability、引擎启动即退出、0xC0000135、自编译引擎、A3 调度补丁、sched3-patch、投机解码调优、数值门 PPL、gpu-probe。Use when porting ninfer (or a similar CUDA inference pack) to an unsupported compute capability, or when tuning ninfer throughput and running its numerical gates.
agent_created: true
---

# ninfer 移植与调优

为**官方引擎不支持的 GPU 架构**从源码编一支 ninfer 引擎，然后按包内手册做性能调优。

## 何时用

- 引擎/启动件报 `requires compute capability 12.0 or 8.9` 之类的**架构门**，本机算力不在白名单里
- 自编引擎**秒退、退出码 `0xC0000135`、stderr 全空**
- 需要对 ninfer 做性能调优（投机解码 / KV 档 / 上下文 / A3 补丁）
- 需要跑数值门（PPL）与逐位判据

## 铁律（先读，能省掉几小时返工）

1. **先取证，再下结论**。跑 `gpu-probe.exe --json` 建档；**直接运行引擎本体**拿它的拒绝原文（绕开所有启动件）。不要凭型号表推断。
2. **"跑不了" ≠ "方案坏了"**，通常是"包内没为你的算力编引擎"。源码树若在包内，就走自编译。
3. **构建并行度按内存算，不按 CPU 核数算**。CUDA 模板密集单元单进程峰值 1.5–3 GB。
   `-j 24` 在 32 GB 机器上会打爆内存 → 换页风暴 → **内核 BugCheck 死机**（佐证：转储创建失败 + EventLog 6008 意外关机）。
   **用 `-j 6`，上限 `-j 8`。** 若 `-j 6` 仍崩，才怀疑硬件。
4. **`.bat` 必须纯 ASCII 无 BOM**。cmd 会把含非 ASCII 的 .bat 当 ANSI 解析，把命令本身撕碎。
5. **测量口径决定结论**。两个最常踩的坑（都会让读数低 1.5–3.7×）：
   - **前缀复用**：请求不带随机 nonce ⇒ `prompt_n` 塌成个位数，**prefill 根本没发生**
   - **输出太短**：<400 token 的输出测的是冷启动毛刺
6. **改完 `.cuh` 头要当心 MSVC 依赖扫描**：本树扫描是坏的，可能"no work to do"然后链接期报未解析符号。
7. **"改了参数但计数器一模一样" ⇒ 先怀疑开关没生效**，不是"这个参数不重要"。env 常在 CUDA graph capture 时读死 ⇒ **改 env 必须重启进程**。
8. ★ **调不动时先换"路线"，别在参数里刨。** ninfer 有**两条互斥的投机路线**，每轮成本结构完全不同：
   - `--spec mtp --draft-tokens 1..5` —— 草稿头**逐 token 串行**，**每个草稿 token 约 +5 ms 每轮成本**；
     **`--draft-tokens 6` 直接 usage 报错，5 是硬上限** ⇒ MTP 的天花板很低（sm_86 上实测 71 t/s）。
   - `--spec dflash2 --draft-tokens 1..7 --lm-head-draft` —— K 个草稿**一趟并行出**（K=5 与 K=7 每轮耗时几乎相同），
     **必须配 `-dflash2` 制品**；**K≤7 是硬上界**（K=8 起单轮成本跳 3 倍）。
   ⇒ **在 MTP 上扫 2/3/4/5 扫到死也追不上 DFlash2。** 本机实测：MTP d5 = 71.2，DFlash2 K=7 = **104.6 t/s（+47%）**。
   **先问"这条路线是不是我要的那条"，再问"参数调没调对"。** 官方 README/启动件注释里的"预期读数"往往写明了它用的是哪条路线。
9. ★ **接受率是"内容类型 × 输出长度"的属性，不是卡的属性 —— 别用短输出测它。**
   同一批请求里，长输出（700 tok，output-limit）实测接受率 **96.2%**，而同参数下的短输出收尾请求（268 tok，stop token）只有 **35.9%**。
   原因：模型在写收尾句时不可预测，投机必然低效。**用短输出测接受率会伪造出"这张卡投机不行"的假结论。**
   判据：**输出必须 ≥400 token 且以 output-limit 收尾**；同时报"接受率"和"t/s"，缺一不可。

## 六步主流程

### 1. 探针建档
```
gpu-probe.exe --json        # 算力 / SM 数 / 显存 / 带宽 / shared 预算
nvidia-smi --query-gpu=name,compute_cap,driver_version,memory.total --format=csv
```
把结果写进 `agent/state.json`（该文件就是设计来被写入的台账）。

### 2. 取证（不可跳过）
直接跑引擎本体拿失败原文；逐个跑启动件记录退出码。
**确认两份引擎的 cubin/PTX 组合**（PTX=0 意味着没有任何 JIT 回退）。

### 3. 定位源码落点
在源码树里定位**架构门**与**架构白名单**。典型四处：

| # | 位置 | 改什么 |
|---|---|---|
| 1 | 顶层 `CMakeLists.txt` | 架构白名单正则加上你的算力（如 `86`） |
| 2 | 顶层 `CMakeLists.txt` | `NINFER_SM_COUNT` 的档位分支加你的 SM 数 |
| 3 | 顶层 `CMakeLists.txt` | 编译宏 `NINFER_SM<XX>=1` |
| 4 | runtime 里的 `compute_capability()` 判定 | 放行你的算力 |

同时**查 CUDA 版本门**（常比文档写的更严）与**你算力上不存在的指令**（见第 4 步）。

### 4. 工具链对齐 + 编译
- CUDA 版本门**以代码为准**（文档常与代码矛盾，以代码为准）。
- **老 nvcc 会拒绝新 VS**（`unsupported Microsoft Visual Studio version`）⇒ 旁装新版 Toolkit 到独立目录，回退=删目录。
- 沙箱常拉黑 `reg.exe` ⇒ `vcvars64` 定位不到 Windows SDK ⇒ **手动注入 `INCLUDE/LIB/PATH` 的 SDK 路径**（症状：`corecrt.h` 找不到）。
- **算力缺失的指令要走"排除 + stub"**：例如 sm_86 没有 FP8 张量核，FP8-mma 单元会 `ptxas fatal`
  ⇒ 把这些 TU 从构建剔除（`HEADER_FILE_ONLY`）、另写 stub 文件提供同名入口（运行时明确报错）。
  **照抄包内已有的 stub 文件模式**，别自己发明。

### 5. 补齐运行库（自编件必撞）
自编 exe 旁边没有那 7 个 FFmpeg DLL（`avcodec-*` / `avdevice-*` / `avfilter-*` / `avformat-*` /
`avutil-*` / `swresample-*` / `swscale-*`），且本机 `System32` 可能**一个 `api-ms-win-crt-*.dll` 都没有**
⇒ 进程在 `main` 之前就死，**stderr 0 字节**。

诊断顺序：**先数 exe 旁边有没有这些 DLL**，再查驱动。用法：`dumpbin -dependents <exe>` 看真实依赖表。
来源：FFmpeg 从原包 `engine\` 复制；UCRT 从 `Windows Kits\10\Redist\<ver>\ucrt\DLLs\x64` 复制。
**别用 Git Bash 的 `timeout` 包裹 Windows exe**（会报 MSYS 风格 dll 错，误导排查方向）。

### 6. 调优 + 数值门
按 `03-基础部署后的调优方案.md` 的**三档线**判定，重点：

- ★ **投机解码是最大杠杆**（本机 5.95×）。**先选路线**（见铁律 8）：`mtp`(K≤5) 还是 `dflash2`(K≤7，需配套制品 + 强制 `--lm-head-draft`)。
  **选对了再看接受率 × 每轮 token 的乘积**。**每轮耗时也要单独记** —— DFlash2 的价值就在于它的每轮耗时对 K 不敏感。
- ★ **投机制品的权重更大，12 GB 卡上 `--kv-capacity auto` 会拒启**：dflash2 权重 9.10 GiB（基座 6.70 GiB），
  报 `minimum Engine runtime reservation requires 1.32 GiB in addition to 1.0 GiB of automatic headroom`。
  **那 1.0 GiB 就是 `auto` 的 sizing headroom** ⇒ 换**显式** `--kv-capacity <N>` 即去掉它。
  ⚠️ 这条**只对显存紧的卡成立**；16 GB+ 应保留 `auto`。且 **上下文几乎不影响 decode 速度**（16K/24K/32K 实测 104.6/105.1/104.6），
  ⇒ 选上下文只看**内存余量**，别为速度牺牲窗口。
- **KV 档要看架构可用性**（老卡常只有 `bf16`/`int8`）。同算力下 dtype 对速度几乎无影响，**选省显存的**。
- **上下文按 `free ≥1.5 GiB` 判据逐档加**，别照抄大卡口径。
- **数值门**：`ninfer-perplexity.exe <model> --text <corpus> --context 512 --stride 256 --kv-dtype <d>`
  ＋短口径 `--context 32 --stride 16`（覆盖短 T 段），配金标准问答。
- **逐位判据**：A3/A1 这类"只改调度"的补丁，必须让开/关两臂的 **PPL 逐位相等**
  （两个独立进程跑，比 sha 更可靠）。**服务端 sha 对比要保证两臂请求历史对称**，否则差异来自缓存状态而非补丁。

## 判据来源（包内真值）

真值分散，别只读根目录那几篇薄索引页：
`docs\`（手册）｜`agent\must-do.json`（机读必做项 + `order_tiers` 排序）｜
`agent\governance.json`（能否跳、给多久）｜`判据.txt`。

## 资源

- `references/arch-port-checklist.md` —— 移植落点、坑清单、本机实测的完整命令与证据
- `references/measured-sm86.md` —— sm_86 / RTX 3060 12G 上的实测参照值（判断读数是否正常）
- `scripts/bench.py` —— 遵守测量口径的基准夹具（nonce 冷缓存 + 长提示 + 长输出 + 丢首轮 + 3 轮中位 + 引擎自报读数）
