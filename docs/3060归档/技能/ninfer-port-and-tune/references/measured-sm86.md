# sm_86 / RTX 3060 12G 实测参照值

> 用途：下次在同卡（或邻近卡）上跑完部署后，用这些数判断读数是否正常。
> **跨卡不可比**；同卡同参数才可比。
> **v2（2026-09-28 晚）**：新增 **DFlash2 路线**一节 —— 它把 decode 从 64.0 拉到 **104~109 t/s**（复测中位 108.7），
> 并纠正了 v1 里"已达带宽水位、无法再快"的结论。

## 机器档案

| 项 | 值 |
|---|---|
| GPU | NVIDIA GeForce RTX 3060 |
| 算力 | **8.6**（sm_86，非 8.9/12.0） |
| SM 数 | **28** |
| 显存 | 12,287 MiB |
| 带宽（理论） | ~360 GB/s |
| 驱动 | 596.36（驱动侧 CUDA 运行时 13.2） |
| Toolkit | 12.8（系统）+ **13.3.73**（旁装，编译用） |
| CPU / 内存 | i7-13700（16 核 24 线程）/ 31.8 GB |

## 官方预期（包内 `复现手册-附录A`）

| 指标 | 3060 12G 预期 | 置信度 |
|---|---|---|
| decode | **~110~130 t/s** | 🟡 外推/第三方 |
| prefill | **~500~700 t/s** | 🟡 外推/第三方 |

> ★ **v1 的参照系错误已纠正**：附录A 的 226 / 104.9 都是 **MTP** 口径，**拿来当 decode 目标会得出"64 已达标"的错误结论**。
> 真正的 4080 峰值写在 `start-8085-dflash2.bat` 注释里：**DFlash2 K=7 → 354 t/s（高度可预测内容）/ 194（HTML·代码）**。
> **用错参照系 = 用错路线。** 见 SKILL.md 铁律 8。

## 本机实测 · 两条投机路线对照（唯一有意义的对照）

口径：长提示 3,755–4,074 token（带 nonce 冷缓存）｜输出 **700 token**｜贪心｜`--no-thinking`｜单路｜3 轮取中位。

| 配置 | 每轮耗时 | tok/轮 | **decode** | 接受率 |
|---|---:|---:|---:|---:|
| 无投机 | 57 ms | 1.00 | 17.5 | — |
| MTP d2 | 66 ms | 2.99 | 45.0 | 99.6% |
| MTP d3 | 72 ms | 3.97 | 55.2 | 99.1% |
| MTP d4 | 77 ms | 4.92 | 63.8 | 98.1% |
| MTP d5（**MTP 上限**） | 83 ms | 5.92 | 71.2 | 98.5% |
| DFlash2 K=5 | 72 ms | 5.78 | 80.5 | 96.0% |
| **DFlash2 K=7（最终）** | **74 ms** | **7.77** | **104.6** | **97.4%** |

**服务端（HTTP）三轮回合复核**：`103.4 / 104.0 / 104.3` ⇒ **中位 104.0 t/s**，接受率 **96.2%（608/632）**，prefill 643.3 t/s。

**复测（同日 30 分钟后，进程常驻）**：`103.5 / 110.1 / 108.7` ⇒ **中位 108.7 t/s**，接受率仍 **96.2%（608/632）**，prefill 640.2 t/s。
**⇒ 稳态 ~105 t/s（±5%），无漂移。** 若以后测出显著低于 100，先怀疑**短输出污染**（见下文"测量陷阱"），而不是配置回退。

> ⚠️ **接受率逐轮完全相同（608/632）不是缓存命中** —— 服务端 `cache 0 (0.0%)`。固定输入（3806 提示 / 700 输出）
> 下接受统计本就是确定性的。别把它误判成 KV 复用。

> **要点**：MTP 每加一个草稿 token 约 **+5 ms/轮**（草稿头串行）；DFlash2 的每轮耗时**对 K 不敏感**（K=5→7 只 +2 ms）。
> 这是 DFlash2 快 47% 的全部机理。**MTP 传 `--draft-tokens 6` 直接 usage 报错；DFlash2 的硬上界是 K=7。**

## DFlash2 在 12 GB 卡上：内存墙与上下文

dflash2 制品权重 **9.10 GiB**（基座 6.70 GiB）。`--kv-capacity auto` 会强制多留 **1.0 GiB sizing headroom** ⇒ **拒启**：

```
error: minimum Engine runtime reservation requires 1,414,716,672 bytes in addition to
       1,073,741,824 bytes of automatic headroom, but only 2,028,002,816 bytes are available after weights
```

**处方：把 `--kv-capacity` 写成显式值**（去掉那 1 GiB）。且 **上下文几乎不影响速度**：

| 配置 | decode | 启动后余量 |
|---|---:|---:|
| ctx 32768 + `auto` | ❌ 拒启 | — |
| **ctx 24576 + 显式（选定）** | **105.1** | 426 MiB |
| ctx 16384 + 显式 | 104.6 | 740 MiB |
| ctx 32768 + 显式 + `--wddm-evictable-budget` | 104.6 | 163 MiB |

⇒ **选上下文只看内存余量，不必为速度牺牲窗口。** 计划设备总量 10.7 GiB / 12 GiB。
⚠️ 显式 `--kv-capacity` **只在显存紧的卡上是对的**；16 GB+ 保留 `auto`。
⚠️ **`--lm-head-draft` 是 dflash2 的强制项**，不加启动即崩：`linear_topk: unsupported head profile`。

## 正确性（DFlash2 路线）

| 判据 | 结果 |
|---|---|
| 输出一致性 | dflash2 K=7 输出与**基座无投机输出逐字节相同**（700 token，`cmp` 通过）⇒ 投机不改数值 |
| 金标准 | Paris ✅ ｜ 北京 ✅ ｜ 391 ✅ **3/3** |

## 参数扫描（本机）

| 参数 | 结果 | 选定 |
|---|---|---|
| **投机后端** | **DFlash2 K=7 = 104.6** vs MTP d5 = 71.2（+47%） | **dflash2 K=7** |
| KV dtype | bf16 38.3 vs **int8 37.3**（差 2.7%，噪声内，MTP 口径） | **int8**（省一半 KV 显存） |
| 上下文 | 12 GB 上到 24576（显式）/ 32768（+wddm）；65536 不可行 | **24576** |
| 激活 int8 档 | 开 prefill 637 / 关 **331**（腰斩） | **保持默认开** |
| A3 补丁 | prefill 588.5 → **644.0**（+9.4%；80 SM 卡上是 +31%） | **开启** |

## 数值门（corpus，21,599 token）

| 臂 | PPL |
|---|---|
| int8 KV / ctx512-256（基准） | **2.453026** |
| bf16 KV / ctx512-256 | 2.453280（+0.010%） |
| 激活 int8 档关闭 | 2.454070（**+0.042%**，落在手册预测的 +0.0015%~+0.05% 内） |
| ctx32-16 | 25.769239（短窗口，正常偏高） |
| **A3 开 vs 关（两独立进程）** | **都 0.897322 / 2.453026 ⇒ 逐位相同** |

## ★ 测量陷阱：短输出会伪造"低接受率"

服务端同一批请求：

```
req#7  output 268 | decode  46.8 | dflash2 accepted 191/532 (35.9%)   <- stop token，收尾句
req#8  output 700 | decode 103.4 | dflash2 accepted 608/632 (96.2%)   <- output limit，长输出
```

**收尾句不可预测 ⇒ 投机必然低效。** v1 报的"接受率 44~50%"就是被这类请求污染的。
**判据：输出 ≥400 token 且以 output-limit 收尾。**

## 机器侧核查（排除"坏环境的慢"）

满载采样：PCIe **Gen4 x16**（空闲显示 Gen1 只是省电，**不是故障**）｜SM 1,927–1,950 MHz｜
功耗 148–169 W（上限 170 W）｜GPU 利用率 **99–100%**（未静默回退 CPU）。
⚠️ Windows 上 `utilization.gpu` 只是"有 kernel 在执行的时间占比"，**不是算力饱和度**；
要判带宽是否打满，用 `权重字节 ÷ 每轮耗时` 反算（本机 DFlash2：9.10 GiB ÷ ~72 ms ≈ 137 GB/s，是 360 的 38%）。

## ★ 本机踩过的环境坑（与模型无关）

**系统设了 `http_proxy=http://127.0.0.1:49919`** ⇒ 对 `127.0.0.1` 的请求也被送进代理，
报 **502 Bad Gateway** / **`upstream connect failed` (os error 10061)**，**看起来像服务端崩了，其实服务端好好的**。
处方：基准命令前 `export NO_PROXY=127.0.0.1,localhost`（curl 加 `--noproxy '*'`）。

**用 `nohup … &` 起的服务端会在命令结束时被回收**（进程消失、端口 TIME_WAIT、日志停在 `listening`）。
处方：用受管的**后台任务**启动，别用 `nohup &`。

## 最终启动配置（两条，按需选）

**8099 · 最快档（DFlash2 K=7，日常用这个）**
```bat
ninfer-serve.exe "D:\27b\pkg1-fast-pq2\model\bonsai2_27b_ternary_v2-dflash2.ninfer" ^
  --host 127.0.0.1 --port 8099 --model-id qwen3.8-27b ^
  --max-context 24576 --kv-capacity 24576 --kv-dtype int8 ^
  --max-concurrency 1 --no-thinking --greedy ^
  --log-stats-interval-ms 5000 --spec dflash2 --draft-tokens 7 --lm-head-draft
```
**8098 · 回退档（MTP d5，要 32K 上下文或 dflash2 制品缺失时）**
```bat
ninfer-serve.exe "D:\27b\pkg1-fast-pq2\model\bonsai2_27b_ternary_v2.ninfer" ^
  --host 127.0.0.1 --port 8098 --model-id qwen3.8-27b ^
  --max-context 32768 --kv-capacity auto --kv-dtype int8 ^
  --max-concurrency 1 --no-thinking --greedy ^
  --log-stats-interval-ms 5000 --spec mtp --draft-tokens 5
```
两份都已落盘：`D:\build\ninfer86\apps\start-8099-sm86.bat` / `start-8098-sm86-mtp.bat`。
