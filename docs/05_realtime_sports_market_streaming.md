# 体育市场高实时价格流采集（批量）

新增脚本：`src/stream_sports_prices.py`

## 设计目标
- 批量订阅大量体育市场资产（asset id）价格事件。
- 使用 WebSocket 流式接收，尽量降低延迟。
- 实时落盘 Tick 原始数据（JSONL），并周期性维护最新快照（JSON）。
- 自动断线重连，支持吞吐率监控。
- 当 `--max-connections` 小于理论分片数时，程序会自动合并批次，确保不丢失任何 asset id。

## 数据来源
- 市场发现：`https://gamma-api.polymarket.com/markets`（过滤 active + sports tag）。
- 实时流：`wss://ws-subscriptions-clob.polymarket.com/ws/market`。

## 运行命令
```bash
python3 src/stream_sports_prices.py \
  --output data/realtime/sports_ticks.jsonl \
  --snapshot-output data/realtime/sports_latest_snapshot.json \
  --batch-size 350 \
  --max-connections 10
```

## 关键参数
- `--batch-size`：每个 WebSocket 连接订阅的 asset id 数量。
- `--max-connections`：最大并发连接数（用于横向扩展吞吐）。
- `--flush-interval` / `--flush-lines`：控制落盘频率。
- `--snapshot-interval`：最新价格快照刷新间隔。
- `--limit-markets`：压测前可先小规模验证。

## 依赖
```bash
python3 -m pip install websockets
```

## 注意事项
- 若网络环境需要代理，请先配置好代理变量再运行。
- 输出文件可能增长很快，建议定期按时间切分文件。
- 初始市场列表是启动时抓取；若需动态增量市场发现，可在后续迭代中加入定时刷新与重平衡。
