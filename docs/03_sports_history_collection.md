# 收集历史体育数据（Sports Historical Data）

## 1. 当前功能覆盖

对应脚本：`src/collect_sports_history.py`

已覆盖流程：
- 从 `GET https://gamma-api.polymarket.com/sports` 获取体育标签信息
- 基于 `tag_id + active/closed/archived` 分模式扫描 `GET /markets`
- 提取每个市场的 token(asset) id
- 对每个 token 按时间分块调用 `GET https://clob.polymarket.com/prices-history`
- 同时保存：
  - 原始响应（`raw/*.jsonl`）
  - 规范点位（`points/*.jsonl`，含 ts/price）
  - 全局 `manifest.json` 汇总

支持能力：
- 支持 `--start-ts/--end-ts` 时间边界
- 支持 `--fidelity` 与 `--chunk-days` 精度和分块
- 支持 `--only-active`、`--market-limit` 调试与范围控制
- 详细日志输出（含 `--log-file`）

## 2. 与官方信息对照

官方文档中：
- `Gamma API` 负责 markets/sports 元信息发现
- `CLOB API /prices-history` 提供 token 历史价格数据（支持 `market/startTs/endTs/fidelity`）

脚本采用的“Gamma 发现市场 + CLOB 拉历史价格”架构与官方能力划分一致。

## 3. 设计合理性评估

结论：设计合理，且偏稳健。

优点：
- 数据链路清晰：市场发现和价格采样职责分离。
- 分块查询避免超大响应，降低超时风险。
- 同时保留 raw 与 normalized 数据，利于审计与重放。
- 覆盖 active/closed/archived，有助于完整回测样本。

主要风险：
- 历史全量抓取耗时与请求量大，需长期运行监控。
- 若官方字段改名（如 token id 字段），当前 fallback 逻辑需及时更新。
- 当前测试覆盖不足，尚未覆盖该脚本核心逻辑。

## 4. 建议与后续

建议优先级：
1. 增加断点续跑（按 market/token 级 checkpoint）。
2. 增加失败 token 重试清单（单独补抓）。
3. 增加输出压缩与分区（按日期/运动类型）以降低存储成本。

## 5. 运行示例

```bash
python3 src/collect_sports_history.py \
  --output-dir data/polymarket/sports_history \
  --start-ts 2024-01-01T00:00:00Z \
  --end-ts 2025-01-01T00:00:00Z \
  --fidelity 1 \
  --chunk-days 7
```
