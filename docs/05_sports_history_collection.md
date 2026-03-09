# 体育市场历史价格采集（最细公开粒度）

## 目标
- 覆盖所有 Polymarket 体育类市场。
- 拉取每个 outcome token 的历史价格序列。
- 按最细公开粒度采集（`fidelity=1`，通常为 1 分钟）。
- 同时保留原始响应（raw）与规范化点位（points），便于完全复现。

## 数据源
- 市场列表：`https://gamma-api.polymarket.com/markets`
- 价格历史：`https://clob.polymarket.com/prices-history`

## 脚本
- `src/collect_sports_history.py`

## 运行示例
```bash
python3 src/collect_sports_history.py \
  --output-dir data/polymarket/sports_history \
  --start-ts 1704067200 \
  --end-ts 1735689600 \
  --fidelity 1
```

## 输出结构
- `data/polymarket/sports_history/manifest.json`：全量索引
- `data/polymarket/sports_history/<market>/raw/<token>.jsonl`：原始响应分片
- `data/polymarket/sports_history/<market>/points/<token>.jsonl`：规范化点位

## 关键实现细节
- 通过多种市场状态组合抓取并按 `market_id` 去重，尽量避免漏市场。
- 体育识别不仅看 `sport`，也会匹配常见体育关键词（NFL/NBA/MLB/UFC 等）。
- 点位时间戳会自动归一化（秒/毫秒/微秒）并统计 `unique_points`。
- 请求按 `--chunk-days` 分块，降低单次响应过大或超时风险。

## 说明
- `fidelity=1` 依赖官方公开接口可用最细粒度；若官方未来开放更细粒度，可直接改参数。
