# results/3080Laptop — 实测数据索引（RTX 3080 Laptop 16GB）

| 文件 | 内容 |
|---|---|
| `variant_results.json` | 三档口径主数据：3.5K 长上下文·DFlash2（108.5 tok/s）、256 短生成·普通问答（约 120）、256 短生成·重复密集·`--lookup-ngram 8`（135.7–164.5） |
| `prefill_results.json` | 预填 1520 tok/s、dense 解码 49.8 tok/s |
| `ab_franken_serve.log` / `ab_official_serve.log` | 与 llama.cpp fork 的 A/B 对照服务端日志（同权重，35.7 tok/s） |
| `f_base_serve.log` / `f_cublas_serve.log` | 引擎特性开关对照实验日志 |

失败实验的日志（未跑通的组合）已清理；结论以两个 JSON 为准，口径详见仓库主页 README。
