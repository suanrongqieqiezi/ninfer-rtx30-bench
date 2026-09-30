# 移植落点与坑清单（sm_86 / RTX 3060 实测记录）

> 场景：pkg1 极速档 PQ2 包，官方只编了 sm_89（40 系）与 sm_120（50 系），本机 RTX 3060 = **cc 8.6**，被架构门拒绝。
> 本页是**实际走过的路**，含命令与证据，可作下次移植的对照。

## 1. 取证原文

```
ninfer-serve.exe <model> --port 8099 --max-context 32768 --kv-cache 32768 --kv-dtype fp8
  -> ERROR startup failed | planning runtime | 1.05 ms
  -> FATAL server failed during startup | Qwen3.6 family runtime requires compute capability 12.0 or 8.9
```
五个启动件全部 `exit /b 5`（启动件自己带架构识别）。两份引擎：sm_89 那份 **PTX=0** ⇒ 无 JIT 回退。

## 2. 源码落点（本树实际四处）

| # | 文件 | 改动 |
|---|---|---|
| 1 | 顶层 `CMakeLists.txt` | 白名单 `^(120a\|120\|89)$` → 加入 `86` |
| 2 | 顶层 `CMakeLists.txt` | `NINFER_SM_COUNT` 档位分支加 `86 → 28`（3060 的 SM 数） |
| 3 | 顶层 `CMakeLists.txt` | 编译宏加 `NINFER_SM86=1` |
| 4 | `src/targets/qwen3_6/impl/runtime/layouts_impl.h` | `compute_capability() != 120 && != 89` 的架构门放行 `86` |

**CUDA 版本门**：代码实际要求 `>= 13.1`（文档写 `>=12.8`，**以代码为准**）。
**次要原因**：nvcc 12.8 会拒绝 VS 18 / MSVC 19.51（`unsupported Microsoft Visual Studio version`），
用 `-allow-unsupported-compiler` 绕过会撞到下一层 UCRT 头解析 ⇒ **直接旁装 CUDA 13.x 更省事**。

**本树已有 sm_86 分支**（`NINFER_SM86` 出现在 `w8_config.h`、`device.h`、多个 w8 GEMM 文件里），
只是 fork 打包时把它从白名单摘掉了 ⇒ 工作量比预期小。

## 3. FP8 墙（sm_86 无 FP8 张量核）

`-k 0`（遇错继续）构建枚举出**权威失败全集 = 6 个 TU**，全部 `ptxas fatal`：

```
ops/attn_input_proj/fp8/fp8_attn_input_a8.cu
ops/gdn_input_proj/fp8/fp8_gdn_input_a8.cu
ops/linear/fp8/fp8_a8.cu
ops/linear_add/fp8/fp8_linear_add_a8.cu
ops/linear_swiglu/fp8/fp8_linear_swiglu_a8.cu
ops/softmax_attention/dense/causal_cache/prompt_fp8.cu
```
报错原文：`Feature 'mma with FP8 floating point type' requires .target sm_89 or higher`

**解法（包内已有设计，照抄即可）**：
- `src/CMakeLists.txt` 里已有 sm_86 排除块（`HEADER_FILE_ONLY`）＋引用 `ops/fp8_a8_stubs.cpp`
- 写 `src/ops/fp8_a8_stubs.cpp`，为全部 16 个 FP8 入口提供"运行时明确报错"的实现
  （样板：`src/ops/nvfp4_w4a4_stubs.cpp`）
- 注意：**另 12 个 fp8 单元（decode / small_t / gemv）不含 FP8 mma，正常编译**，不要误排除

## 4. 工具链与沙箱坑

| 坑 | 症状 | 处置 |
|---|---|---|
| 沙箱拉黑 `reg.exe` | `vcvars64` 后 `WindowsSdkDir` 为空、`INCLUDE` 无 UCRT 路径 ⇒ `corecrt.h` 找不到 | 手动 `set INCLUDE=...;%SDKROOT%\Include\%SDKVER%\ucrt;...` 等 5 个路径 + `LIB` 2 个 |
| `.bat` 含非 ASCII | 命令被 cmd 按 ANSI 撕碎，报错莫名其妙 | **纯 ASCII + 无 BOM**，改动后用 `grep -P '[^\x00-\x7F]'` 自检 |
| 树根 `build_v1.0.8.bat` | 硬编码 VS 2022 路径，本机不存在 | 别用它，手写 configure |
| 并行度过高 | **内核 BugCheck 死机** | `-j 6`（见 SKILL.md 铁律 3） |
| 死机后文件系统暗伤 | 少量文件变成**全零**（尺寸正常、内容 `\0`） | 全盘扫全零文件；删掉整个依赖扫描层（`*.ddi`/`*.dd`/`*.modmap`）让 CMake 重新生成，**`.obj` 不必重编** |
| 链接期未解析符号 / "no work to do" | 改了 `.cuh` 但依赖扫描没跟上 | 跑包内 `tools\touch-dependents.ps1 -Header <改的.h> -Root <tree>\src` |

## 5. 运行库（自编件必撞）

`dumpbin -dependents ninfer-serve.exe` 暴露缺的两类：

1. **FFmpeg 7 个**：`avcodec-63` / `avdevice-63` / `avfilter-12` / `avformat-63` / `avutil-61` / `swresample-7` / `swscale-10`
   → 从原包 `engine\` 复制到 exe 同目录
2. **UCRT api-set**：本机 `C:\Windows\System32` 里 `api-ms-win-crt-*.dll` **数量为 0**（异常）
   → 从 `C:\Program Files (x86)\Windows Kits\10\Redist\10.0.26100.0\ucrt\DLLs\x64` 复制 46 个

**症状是"进程秒退 + 退出码 0xC0000135 + stderr 0 字节"** ⇒ 进程还没进 `main`。
判别要点：**"有输出"和"没输出"是两类故障**——stderr 全空就**先查 DLL**，别先怪驱动。

## 6. 构建结果

```
[398/398] Linking CXX executable apps\ninfer-perplexity.exe
[bld] ninja exit=0                      # 零 ptxas / CMake / LNK 错误
```
产物 `apps\`：`ninfer-serve.exe` 215 MB、`ninfer-perplexity.exe` 214 MB、`ninfer.exe` 214 MB。
启动：权重 6.70 GiB @ 4.5 GiB/s（1.4 s）；端到端就绪 **4.0 s**；`/v1/models` → **HTTP 200**。

## 7. A3 调度补丁（sched3-patch）

- **4 个文件整体替换**（不是打 diff）到 `src/ops/linear/ternary/`：
  `ternary_rowsplit_mma_small_t.cuh`、`ternary_rowsplit_gemm.cu`、
  `ternary_rowsplit_mma_wide_t.cuh`、`ternary_rowsplit_mma_s8.cuh`
- **替换前备份**；对比 sha 确认 4 个文件都与包内不同
- 开关 `NINFER_TERNARY_TOKEN_GRID`：`1`=开（默认）、`0`=对照臂；**capture 时读死 ⇒ 改值要重启进程**
- `NINFER_TERNARY_SMALL_T_ROWS` 的 `32` 档是**复现开关不是调优旋钮**（PQ2 编不出、PTQ1 算错）；`NINFER_TERNARY_KSPLIT`（A2）是**负收益**
- **本机收益 prefill +9.4%**（vs 40 系 80 SM 的 +30.8~31.1%）⇒ A3 买的是**并行度**，SM 越少余地越小
