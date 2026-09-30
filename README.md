# ninfer-rtx30-bench — RTX 30 系跑 NInfer + Ternary-Bonsai-2-27B 实测复现包

对 B 站视频「8G 显卡跑通 27B 三值量化模型」的复现与延伸作业。

视频作者在 NInfer 博主包 的《线上对照-50系与30系适配现状》里把 30 系（sm_86）路线标注为「真机性能未知 ❌」——他手上只有 40 系卡。本仓库补上这一格：**RTX 3080 Laptop 16GB** 与 **RTX 3060 12GB** 两台 30 系真机的完整读数、原始日志和测量脚本。

## 结论速览（RTX 3080 Laptop 16GB，sm_86 自编译引擎）

| 工况 | decode (t/s) | 备注 |
|---|---|---|
| 3.5K 长上下文 · DFlash2 K=7 | **108.5** | 同轮 prefill 1520 t/s，dense 对照 49.8 |
| 256 token 短生成 · 普通问答 | **~120** | 同一批实测 233 token 生成读数 117–119.5 |
| 短生成 · 重复密集内容 · `--lookup-ngram 8` | **135.7–164.5** | 三次实测波动大（135.7 / 156.4 / 164.5） |

⚠ **口径提醒**：三档测试条件不同，不要混着比。引用 108.5 必须带「3.5K 长上下文」限定；视频里说的 ~160 出自第三档（重复密集内容草稿命中率高），不代表普通问答速度。

RTX 3060 12GB（走 cc86 引擎 / DFlash2 路线）：decode **104–108.7 t/s**，详见 `docs/3060归档/`。

## 目录结构

```
docs/
  30系实测作业_sm86真机_填补博主留白.md   ← 主稿：从博主留白到真机读数
  NInfer自编译打通记录_20260927.md        ← sm_86 自编译全过程（含三个坑）
  NInfer隐藏开关实测报告_20260927.md      ← --lookup-ngram 等隐藏开关实测
  两条线对照_本机3080L_vs_3060归档.md     ← 两台 30 系卡的横向对照
  3060归档-00-索引.md                     ← 3060 侧阅读索引
  3060归档/报告/*.md                      ← 3060 适配/调优/死机诊断五篇
  3060归档/技能/                          ← ninfer-port-and-tune 技能文档
results/3080Laptop/
  variant_results.json                    ← 三档口径原始 JSON（本仓库核心证据）
  prefill_results.json                    ← prefill 专项
  f_*_serve.log / ab_*.log                ← 各变体服务端日志
bench/
  bench_variants.py                       ← 3080L 三档口径测量脚本
  bench_prefill_focus.py                  ← prefill 专项脚本
  ab_lookup.py / bench_draft_depth.py     ← lookup 深度扫描 / A/B
  3060-fixture/                           ← 3060 侧测量夹具（py+sh）
scripts/
  _count_ptx.py / _verify_ptx.py          ← 引擎 PTX/SASS 覆盖验证
  smoke_franken.py / ab_compare.py        ← 冒烟与对拍
```

## 复现要点

1. **引擎**：NInfer 官方预编译包不含 sm_86 SASS/PTX，30 系需自编译（PTX JIT 兜底也可跑，本机两种都验证过）。自编译细节见 `docs/NInfer自编译打通记录_20260927.md`。
2. **模型**：`Ternary-Bonsai-2-27B-ninfer-v3.ninfer`（27B 三值量化，8G 卡可跑）。
3. **脚本**：bench 脚本里的 `SERVE` / `MODEL` / `LOGD` 是本机绝对路径，运行前改成你的安装路径；脚本默认对 `http://127.0.0.1:8906` 起的 `ninfer-serve` 打点。
4. **测速口径**：decode 取 `completion_tokens / sec`；投机解码档接受率一并记录在 JSON 内。

## 已知坑（30 系专属）

- **C++20 静默降级**：nvcc 因宿主 cl.exe 太老把 `-std=c++20` 降级为 C++17，报错千奇百怪但不明说——先升 VS 到 ≥2019 16.11。
- **cublas 速度反常**：sm_86 上 `--cublas` 变体反而比默认慢，prefill 掉一半，别按 40 系经验开。
- **PTX JIT 首载慢**：官方 master 预编译版在 30 系靠 384 个 sm_86 PTX JIT 兜底（0 个 sm_89/sm_120 SASS），首次加载多等一两分钟属正常。

## 致谢与出处

- NInfer 引擎与 Ternary-Bonsai-2-27B 模型：见 NInfer 官方仓库与 Hugging Face 模型页（本仓库不含任何引擎二进制与模型权重）。
- 原始视频与博主发布包：B 站视频「8G 显卡跑通 27B」及其 GitHub 发布页。
- 本仓库只含：我们自己的实测数据、日志、脚本与文档。

## License

实测数据与文档：CC-BY-4.0；脚本：MIT。
