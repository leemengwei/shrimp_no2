# Part1 数据字典与采集口径（初版）

本字典基于官方公开API端点设计（仅公开数据）。

## 端点与字段（核心）

### 1) 用户持仓（当前）
- Endpoint: `GET https://data-api.polymarket.com/positions?user=<address>&limit=<n>&offset=<n>`
- 主要字段（示例）
  - `conditionId`：市场条件ID
  - `tokenId` / `outcome`：对应结果Token/方向
  - `size`：持仓数量
  - `avgCost`：平均成本
  - `value`：当前价值
  - `title` / `slug`（如有）

### 2) 用户持仓（已平仓）
- Endpoint: `GET https://data-api.polymarket.com/closed-positions?user=<address>&limit=<n>&offset=<n>`
- 主要字段（示例）
  - `conditionId`
  - `tokenId` / `outcome`
  - `size`
  - `avgCost`
  - `pnl` / `pnlPercent`（如有）
  - `resolvedAt` / `resolved`（如有）

### 3) 用户活动（事件流）
- Endpoint: `GET https://data-api.polymarket.com/activity?user=<address>&limit=<n>&offset=<n>`
- 主要字段（示例）
  - `type`：活动类型（交易、上架、结算等）
  - `timestamp`
  - `conditionId`
  - `side` / `price` / `size`

### 4) 用户交易（明细）
- Endpoint: `GET https://data-api.polymarket.com/trades?user=<address>&limit=<n>&offset=<n>`
- 主要字段（示例）
  - `conditionId`
  - `side` / `price` / `size`
  - `timestamp`
  - `market` / `title` / `slug`（如有）

### 5) 用户累计交易市场数
- Endpoint: `GET https://data-api.polymarket.com/traded?user=<address>`
- 返回：累计市场数等统计

### 6) 用户持仓总价值
- Endpoint: `GET https://data-api.polymarket.com/value?user=<address>`
- 返回：持仓总价值或相关统计

### 7) 市场信息（补充）
- Endpoint: `GET https://gamma-api.polymarket.com/markets?condition_ids=<id1>,<id2>`
- 主要字段（示例）
  - `conditionId` / `id`
  - `title` / `slug`
  - `liquidity` / `volume`
  - `endDate` / `resolutionDate`

## 数据落地
- 目录结构（支持后续 web 加载/筛选）：
  - `data/polymarket/<user>/user_bundle.json`（全集合）
  - `data/polymarket/<user>/<endpoint>.json`（分端点文件，便于按需加载）
  - `data/polymarket/<user>/manifest.json`（索引文件）
  - `data/polymarket/<user>/resume_state.json`（增量续跑时间戳）
- 分端点文件包含：
  - `positions`、`closed_positions`、`activity`、`trades`
  - `traded_markets`、`positions_value`
  - 可选 `markets`
