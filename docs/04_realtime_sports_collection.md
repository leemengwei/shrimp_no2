# 收集实时体育数据（Real-time Sports Data）

## 1. 当前功能覆盖

对应脚本：`src/collect_stream_sports_prices.py`

已覆盖流程：
- 先用 `GET https://gamma-api.polymarket.com/sports` + `GET /markets` 筛选活跃体育市场
- 提取所有 asset/token id
- 按 batch 建立多路 WebSocket 订阅：
  - `wss://ws-subscriptions-clob.polymarket.com/ws/market`
- 实时接收并归一化事件（含 `price_change` 展开）
- 输出两类文件：
  - tick 级流式明细：`sports_ticks.jsonl`
  - 最新快照：`sports_latest_snapshot.json`

支持能力：
- 批次大小、连接数可调（`--batch-size` / `--max-connections`）
- 周期 flush + fsync，降低异常中断丢数据
- 自动重连与吞吐指标日志
- 信号退出时排空队列（尽量优雅停机）

## 2. 与官方信息对照

官方文档中 WebSocket Market Channel 支持公共实时市场更新；
`Gamma API` 负责市场发现，`CLOB WSS` 负责实时价量/盘口事件。

脚本采用“REST发现资产 + WSS订阅更新”的组合，符合官方推荐的数据路径。

## 3. 设计合理性评估

结论：总体合理，工程上可用。

优点：
- 对高频场景做了分连接并发和批处理。
- 事件归一化后输出结构统一，便于后续回放/特征工程。
- 有 backoff 重连、指标日志、落盘缓冲策略，实战友好。

主要风险：
- 订阅字段使用 `assets_ids`；若官方协议字段变更，需要同步验证。
- 缺少端到端回放测试（当前以函数级单元测试为主）。

## 4. 建议与后续

建议优先级：
1. 统一命名（脚本、测试、AGENTS 命令）以避免运行错误。
2. 增加协议兼容层（订阅字段可配置）。
3. 增加采集健康指标输出（延迟、队列积压、每资产更新频率）。

## 5. 运行示例

```bash
python3 src/collect_stream_sports_prices.py \
  --output data/realtime/sports_ticks.jsonl \
  --snapshot-output data/realtime/sports_latest_snapshot.json \
  --batch-size 350 \
  --max-connections 10
```
