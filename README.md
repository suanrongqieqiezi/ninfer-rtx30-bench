# Ternary-Bonsai-2-27B × NInfer · RTX 30 系 Windows 构建（社区非官方重编译）

## 这是什么

NInfer 是一个 C++/CUDA 从零实现的推理引擎，为 Ternary-Bonsai-2-27B 设计，内置投机解码。官方代码把编译目标写死为 RTX 5090（sm_120a），构建脚本拒绝其他一切架构，且不发布任何预编译构建——官方文档原话："没有安装目标，没有打包发行版；从源码构建树里运行"，所有用户均需在 Linux 上自行编译。

本构建对源码做了两处改动，在 Windows 上重编译出 RTX 30 系（sm_86）版本：

1. 解锁架构限制，加入 RTX 30 系编译目标；
2. 修复一处 MSVC 编译器兼容性问题。

模型加载、量化内核、投机解码逻辑与官方代码一致，未做改动。

实测数据、复现脚本与踩坑记录：**https://github.com/suanrongqieqiezi/ninfer-rtx30-bench**

## 模型说明："三进制"的准确含义

Ternary-Bonsai-2-27B 是 PrismML 2026 年 9 月发布的 27B 模型，采用**三值权重量化（Ternary Weight Quantization）**：

- 所有线性层权重取值限定于 **{-1, 0, +1}** 三值（每个取值称为一个 trit）；
- 配 FP16 分组缩放系数，平均存储密度 **约 1.76 bit/参数**，三值权重本体约 **5.9GB**；
- 本构建使用的 `.ninfer` 单文件工件为 8.87GB，因为额外打包了 DFlash2 投机解码草稿模型、视觉模块等运行时组件；
- 推理时的激活值、KV 缓存仍为常规精度，"三值"仅指权重。

该技术路线源自微软研究院 BitNet b1.58 系列（论文 *The Era of 1-bit LLMs: All Large Language Models are in 1.58 Bits*, arXiv:2402.17764，log₂3 ≈ 1.58），因此社区也称"1.58-bit 模型"。模型名中的 "Ternary" 与本文所称"三进制"，均指文献中通行的"权重限定三值"用法，不是三进制记数系统。区别于训练后量化（PTQ）：三值约束在预训练阶段即生效。

官方指标：聚合基准 83.9 分，保留同规模全精度模型 **98.2%** 的能力；编码、工具调用、视觉三个分项保持稳定；支持 262K 上下文与图像输入。

## 显卡支持

| 显卡 | 建议 | 说明 |
|---|---|---|
| RTX 30 系（含全部笔记本型号） | 用本构建 | 3060 / 3060Ti / 3070 / 3070Ti / 3080 / 3080Ti / 3090。30 系现成 Windows 构建之一（社区另有 wei231 的 3080-20G 专版，HF 搜 ternary-bonsai-3080-sm86-ninfer） |
| RTX 40 / 50 系 | 可用本构建 | 本构建附带 compute_86 PTX（中间码），较新架构的显卡可由驱动即时编译（JIT）后运行；官方代码原生支持 5090 但无预编译发布，40 系同样需自行编译，不想编译可直接用本构建 |
| RTX 20 系 / GTX | 不可运行 | 本构建不含 Turing（sm_75）机器码与 PTX |

显存门槛（实测整套峰值约 8.6GB）：8GB 卡不建议尝试；10GB 可跑但余量小（约 1G，别同时开占显存的大程序）；12GB 舒适；16GB 及以上宽裕。

## 实测性能（RTX 3080 Laptop 16GB）

解码速度跟工况走，报数先说口径：

| 工况 | 解码速度 |
|---|---|
| 3.5K 长上下文 · DFlash2 投机解码 | **108.5 tok/s**（同轮预填 1520 tok/s，dense 解码 49.8 tok/s） |
| 256 token 短生成 · 普通问答 | 约 120 tok/s |
| 256 token 短生成 · 重复密集内容 · 加 `--lookup-ngram 8` | 135.7–164.5 tok/s（三次实测，波动大） |

对照基准：llama.cpp 官方 fork 跑同一权重（无损转存 Q8_0），同卡 35.7 tok/s。

后两档快，是因为投机解码的速度跟着草稿命中率走：内容越可预测（复读、模板文），命中越高。三档口径不同，别混着比。

## 运行前提

1. Windows 10/11 x64；NVIDIA 驱动 ≥ 570；无需安装 CUDA Toolkit；
2. 本构建约 1.5GB（发布时附 sha256）；
3. 模型：HuggingFace `WaveCut/Ternary-Bonsai-2-27B-NInfer-v3` 仓库中的 `Ternary-Bonsai-2-27B-ninfer-v3.ninfer` 单文件，9,520,051,456 字节，sha256 `cdc4810b0ff17c40d0f62cf214b6e0bcd08346e9eb05ca53371507037793c14a`；
4. 磁盘剩余约 12GB。

启动命令：

```
ninfer-serve.exe Ternary-Bonsai-2-27B-ninfer-v3.ninfer --host 127.0.0.1 --port 8905 --model-id bonsai-27b --max-context 8192 --kv-dtype rk8v4 --gdn-state-fp16 --spec dflash2 --draft-tokens 7
```

服务为 OpenAI 兼容 API，内置网页聊天界面。发布时附打包好的 `run.bat`，解压后双击启动。

## FAQ

**Q：官方为什么不支持 30 系？**
A：官方构建脚本把 CUDA 架构写死为 120a 并显式拒绝其他架构，且未发布预编译版。CUDA 机器码不能向下兼容，5090 编译产物在 30 系上无法运行。本构建加入 sm_86 目标重新编译。

**Q：相比 llama.cpp 的提升，是不是换了模型的缘故？**
A：同一模型同一权重。llama.cpp 不支持该三值格式，需用其官方 fork，同卡实测 35.7 tok/s；NInfer 开投机解码实测 108.5 tok/s。

**Q：平均 1.76 bit/参数，能力损失大吗？**
A：官方指标为聚合基准保留 98.2%（83.9 分），编码、工具调用、视觉等最难保留的分项稳定。这是训练时即施加三值约束的原生低比特模型，与对现成模型做训练后量化的损失机制不同。

## 协议与出处

- NInfer 采用 Apache 2.0 协议；本构建的两处改动已如上声明，编译方法可提供；
- `.ninfer` 模型工件来自 HuggingFace 社区仓库 WaveCut/Ternary-Bonsai-2-27B-NInfer-v3（Apache 2.0）；模型由 PrismML 训练发布；
- 移植思路参考 B 站 UP 主 shensanshu 的 RTX 4080 SUPER 视频，本构建面向 RTX 30 系重编译并实测；实测数据、复现脚本与踩坑记录：https://github.com/suanrongqieqiezi/ninfer-rtx30-bench
- 与 NInfer / PrismML 官方无关，引擎层问题请查阅官方仓库。
