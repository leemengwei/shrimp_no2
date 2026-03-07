# 基于 CLOB 的实时市场发现与价格查询

> 说明：本设计以 Polymarket 官方文档体系为准（CLOB API、Gamma API、SDK），
> 实现上提供 **SDK 模式** 和 **直接接口模式** 两套路径。

## 1. 目标

实现两个核心能力：

1. **实时市场发现**：持续发现当前活跃市场，并筛选关注关键词。
2. **实时价格查询**：针对市场 outcome token 持续查询中间价（midpoint）并计算变化量。

## 2. 实现文件

- `src/realtime_clob_market_monitor.py`

该脚本支持：

- `--mode sdk`：优先使用 `py-clob-client`。
- `--mode http`：直接调用公开接口（`gamma-api` + `clob`）。

## 3. 运行示例（可直接复制）

### 3.1 SDK 模式（推荐）

```bash
python3 src/realtime_clob_market_monitor.py \
  --mode sdk --query election --limit 5 --interval 3 --watch-seconds 30
```

若未安装 SDK：

```bash
pip install py-clob-client
```

### 3.2 直接接口模式（零 SDK 依赖）

```bash
python3 src/realtime_clob_market_monitor.py \
  --mode http --query bitcoin --limit 5 --interval 3 --watch-seconds 30
```

## 4. 数据流与实时性说明

1. 通过市场发现接口获取活跃市场（问题、slug、outcome token id）。
2. 对每个 token id 周期性读取 CLOB midpoint。
3. 维护上一次 price，输出 `delta` 来描述实时波动。

当前脚本使用“短周期轮询”实现近实时。后续可扩展为 WebSocket 订阅模式以进一步降低延迟。

## 5. CLOB SDK vs 直接 CLOB 接口对比

| 维度 | CLOB SDK (`py-clob-client`) | 直接接口（HTTP） |
|---|---|---|
| 上手速度 | 快，封装签名/请求细节 | 中，需要自己维护请求与解析 |
| 依赖管理 | 需要安装 SDK，版本兼容需关注 | 依赖少（标准库即可） |
| 功能覆盖 | 对常见交易/查询能力友好 | 任何开放接口都可直接调用 |
| 可控性 | 中，受 SDK 抽象影响 | 高，请求参数与容错完全可控 |
| 调试透明度 | 中，需看 SDK 内部实现 | 高，看到原始请求与响应 |
| 长期维护 | SDK 升级可能带来 API 变更 | 接口变更时可快速定向修复 |
| 推荐场景 | 交易执行、签名、账户相关流程 | 数据采集、研究、轻量监控 |

### 结论建议

- **生产交易链路**：优先 SDK（降低签名和协议细节错误）。
- **研究/监控链路**：可先直接接口，快速迭代；稳定后再抽象统一网关。
- **本仓库当前实现**：同一脚本内支持两模式，便于 A/B 评估。

## 6. 风险与边界

- 接口可能限流，建议增加重试和指数退避。
- 市场字段可能不稳定（如 outcomes 字段格式变化），已在脚本中兼容 JSON 字符串/数组两种形态。
- 仅做市场发现与价格查询，不包含自动下单逻辑。
