# 用户行为收集（User Activity Collection）

## 1. 当前功能覆盖

对应脚本：`src/collect_user_activity.py`

已覆盖的用户行为/画像数据：
- 用户当前持仓：`GET https://data-api.polymarket.com/positions`
- 用户历史平仓：`GET https://data-api.polymarket.com/closed-positions`
- 用户行为流水：`GET https://data-api.polymarket.com/activity`
- 用户交易流水（由 activity 过滤 `type=TRADE`）：`GET https://data-api.polymarket.com/activity?type=TRADE`
- 用户参与市场数：`GET https://data-api.polymarket.com/traded`
- 用户持仓总价值：`GET https://data-api.polymarket.com/value`

支持能力：
- 多用户批量抓取（`--users`）
- 全量 + 增量续跑（基于 `resume_state.json`）
- 最近窗口抓取（`--recent HOURS`）
- 分页落盘与清单输出（`manifest.json`、`user_bundle.json`）

## 2. 与官方信息对照

官方 API 介绍明确将用户画像与行为放在 `Data API`，且为公开读取接口（无需鉴权）。

本脚本使用的 `positions / activity / value / traded` 与官方文档中 Profile/Core 分组一致，方向正确。

## 3. 设计合理性评估

结论：整体设计合理，适合研究型数据采集。

优点：
- 采集口径完整：仓位、交易行为、账户价值都覆盖到了。
- 续跑机制实用：`activity_last_ts` / `trade_last_ts` 可减少重复抓取。
- 数据可追溯：按 endpoint 分页原始落盘，便于后续复算和纠错。
- 对时间戳格式有兼容处理（秒/毫秒/微秒/ISO），鲁棒性较好。

主要风险：
- `activity` 与 `trades(activity type=TRADE)` 存在一定重复语义，后续建模要去重。
- 未显式限流策略（仅 sleep/backoff），高并发时可能受平台节流影响。
- 各 endpoint 返回字段可能演进，当前 schema 校验较弱。

## 4. 建议与后续

建议优先级：
1. 增加统一 schema 快照（字段字典 + 版本时间）。
2. 增加 `--retries` 参数暴露（目前部分请求 retries 为 None）。
3. 产出一层规范化表（如 `user_activity_flat.parquet`），减少下游重复清洗。

## 5. 运行示例

```bash
python3 src/collect_user_activity.py \
  --users 0x2005d16a84ceefa912d4e380cd32e7ff827875ea \
  --recent 48 \
  --out-dir data/polymarket/user_activities
```
