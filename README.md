# d1_flow_filter_failureprove

**日线突破 + 订单流过滤** 的失败档案，属于 [量化失败合集 quant-failure-archive](https://github.com/runningshark/quant-failure-archive)。

这一条不是"亏钱"的失败，而是**"指标无效"**：加上订单流过滤后，策略并没有变好，反而略差。

- 结论和全部数字：[FAILURE_REPORT.md](FAILURE_REPORT.md)
- 复现：`python verify.py`（只需要 Python 3，不用装库），结果写到 `results/output.txt`
- 代码：`strategies/`（策略原文件和它依赖的基础突破策略，未改动）、`core/engine.py`（原项目回测引擎，未改动）
- 数据：`data/`，币安现货日线快照（含主动买入量），截至 2026-11-23

不构成任何投资建议。
