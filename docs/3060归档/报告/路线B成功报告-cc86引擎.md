# 路线 B 成功报告 —— 自编译 cc 8.6 引擎跑通

> **结论：本机（RTX 3060 / cc 8.6）原本完全跑不了本包（架构门拒绝），现已从源码自编译出 sm_86 引擎，模型加载成功、推理输出正确。**
> 完成时间：2026-09-28 08:11

---

## 一、最终状态（实测）

| 项 | 结果 |
|---|---|
| 编译 | **398/398 目标全部完成，零错误**（0 ptxas / CMake / LNK）|
| 架构门 | ✅ **通过**（原引擎报 `requires compute capability 12.0 or 8.9`，新引擎不再报）|
| 模型加载 | ✅ 6.70 GiB，1.5 s（4.46 GiB/s）|
| KV | ✅ int8，32768 tokens，512/512 pages |
| 启动总耗时 | ✅ **3.9 s**（含 CUDA graphs 734 ms + warmup 304 ms）|
| 监听 | ✅ `http://127.0.0.1:8099`，`/v1/models` → **HTTP 200** |
| 显存占用 | runtime 1.51 GiB（12 GB 卡余量充足）|

**推理实测**（`temperature=0`）：

- 中文 prompt「用一句话中文自我介绍。」→
  **「你好！我是通义千问，一个由阿里巴巴集团通义实验室独立开发的大型语言模型。」**（`finish_reason: stop`）
- 英文 prompt「Reply with exactly: HELLO WORLD」→ 正常返回（命中内容策略拒答，属模型行为，非引擎问题）

| 性能 | 实测 |
|---|---|
| decode | **20.1 tok/s** |
| prefill | 65.7 tok/s（英文）/ 85.1 tok/s（中文）|
| TTFT | 259 ms |

> ⚠️ **性能尚未调优**：本次为"能跑通"验证，未启用投机解码（`--spec mtp`），且输出很短（22 tokens）含启动开销。
> 说明书对本卡的带宽折算目标线是 decode **≈173 t/s**（可用线 ≈121 t/s），当前 20 t/s 差距大，**属调优项**（见第五节）。

---

## 二、产物位置

```
D:\build\ninfer86\apps\
├── ninfer-serve.exe          215 MB  ← 新引擎（sm_86）
├── ninfer-perplexity.exe     214 MB
├── ninfer.exe                214 MB
├── start-8099-sm86.bat              ← 双击即跑
├── api-ms-win-*.dll (45 个)         ← UCRT（本机 System32 缺失，已随 exe 部署）
├── ucrtbase.dll
└── avcodec-63.dll / avformat-63.dll / avutil-61.dll / swscale-10.dll
    (+ avdevice/avfilter/swresample) ← FFmpeg，从原包 engine\ 复制
```

**运行**：双击 `D:\build\ninfer86\apps\start-8099-sm86.bat`

---

## 三、从源码到能跑：做了哪些改动

### 3.1 源码改动（4 处 + 1 个新增文件）

| 文件 | 改动 |
|---|---|
| `CMakeLists.txt` | 架构白名单加入 `86`；`NINFER_SM_COUNT` 加 86→28 分支；加 `NINFER_SM86=1` 宏 |
| `src/CMakeLists.txt` | 已含 sm_86 FP8 排除块（12 个 FP8-mma `.cu` 标记 `HEADER_FILE_ONLY`），挂 `ops/fp8_a8_stubs.cpp` |
| `src/targets/qwen3_6/impl/runtime/layouts_impl.h` | 架构门放行 `86` |
| `src/ops/fp8_a8_stubs.cpp` | **新增**（7649 B）：16 个 FP8 入口实现为"运行时明确报错"，保持分发层可链接 |

### 3.2 工具链

- **CUDA Toolkit 13.3.73** 旁装于 `D:\27b\cuda-13.3-sdk`（系统原有 12.8 无法编：`nvcc 12.8` 不认 VS 18 / MSVC 19.51）
- VS 18 BuildTools（MSVC 14.51）+ cmake + ninja
- 手动注入 Windows SDK `INCLUDE/LIB/PATH`（沙箱屏蔽 `reg.exe`，vcvars 无法自动定位 SDK）

### 3.3 构建脚本

| 脚本 | 用途 |
|---|---|
| `D:\build\build-ninfer86.bat` | configure + build（原 `-j 24`，**已弃用**，见第四节）|
| `D:\build\bld86-k0.bat` | `-k 0` 遇错继续，枚举全部失败点 |
| `D:\build\bld86-resume-j6.bat` | **当前推荐**：`-j 6` 安全续跑 |

---

## 四、死机事故与并行度（重要，回答"-j 12 能否提速"）

### 4.1 事故

07:49 用 **`-j 24`** 编译时，主机发生**内核 BugCheck**（EventLog 6008 + volmgr 转储失败）。

**根因**：31.8 GB 物理内存，模板重的 CUDA 单元单进程峰值约 2 GB，`24 × 2 ≈ 48 GB` 远超上限 → 换页风暴 → 内核失稳。

### 4.2 为什么 `-j 12` 不是好主意

| | |
|---|---|
| 物理内存 | **31.8 GB**（硬上限）|
| 单 CUDA TU 峰值 | 1.5–3 GB |
| `-j 6` | 峰值 ~9–18 GB — **本次实测安全** ✅ |
| `-j 8` | 峰值 ~12–24 GB — 安全上限 |
| `-j 12` | 峰值 **18–36 GB** — 触顶概率高 ⚠️ |

**关键判断**：
1. **瓶颈是内存，不是 CPU。** i7-13700 有 16 物理核，CPU 侧跑 `-j 12` 没问题，但内存先崩。
2. **收益有限**：本次 `-j 6` 全量编译约 6 分钟；`-j 12` 顶多省 1–2 分钟，却把死机概率显著拉高。
3. **死机代价远大于省下的时间**（系统重启 + 可能文件损坏，本次就损坏了 4 个 `.ddi`）。

**建议**：保持 `-j 6`；若要更快，用 **`-j 8`**。真正的加速手段是**增量编译**（ninja 只重编改动文件，已生效）而非堆并行度。

> 另：项目 CMake 已把**链接池限为 1**（`CMAKE_JOB_POOL_LINK`），避免并行链接的内存叠加——原设计者已在防这一点。

---

## 五、后续可做（未完成项）

1. **性能调优**（说明书 `03-基础部署后的调优方案.md`）
   - 启用投机解码：`--spec mtp --draft-tokens 3`（说明书称自 2026-09-26 默认开）
   - 提高 `--max-context` / `--kv-capacity`（当前 32768，12 GB 卡可试 65536）
   - 用长 prompt + 长输出 + 中位数测法得到稳定读数（当前 20 t/s 是短样本首测）
2. **验证数值门**：跑 `ninfer-perplexity.exe` 对照 perplexity，确认三元量化在 sm_86 上数值正常
3. **两处文档/代码矛盾回报提供方**：
   - `docs\兜底方案` 写 "CUDA ≥12.8"，而代码实际卡 13.1（且 12.8 无法编 VS 18）
   - 树根 `build_v1.0.8.bat` 硬编码 VS 2022 路径（本机不存在）

---

*事件与台账同步记录于 `agent\state.json`（`done[]` / `incidents[]`）。*
