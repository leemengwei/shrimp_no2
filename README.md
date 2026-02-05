# Polymarket API 示例和 Web 应用

基于 [Polymarket API 文档](https://docs.polymarket.com/quickstart/overview) 的 Python 示例和实时数据展示 Web 应用。

## 📦 项目结构

```
polymarket/
├── app.py                     # Flask Web 应用后端
├── polymarket_example.py      # Python API 调用示例
├── templates/
│   └── index.html            # Web 前端（实时仪表板）
└── README.md
```

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install flask requests
```

### 2. 运行 Web 应用

```bash
python app.py
```

然后在浏览器中访问：`http://localhost:5000`

### 3. 运行 Python 示例

如果只想使用 Python API 调用示例：

```bash
python polymarket_example.py
```

## 🌐 Web 应用功能

### 实时仪表板特性

✅ **实时市场数据展示**
- 显示最多5个活跃市场
- 实时价格更新（默认10秒刷新）
- 交易量和预期结果可视化

✅ **可视化界面**
- 响应式设计，支持移动端
- 美观的卡片式布局
- 动画过渡效果
- 深色渐变背景

✅ **自动刷新**
- 可启用/禁用自动刷新
- 可手动刷新数据
- 更新统计信息

✅ **订单簿查看**
- 点击市场查看详细订单簿
- 显示最佳买单/卖单
- 模态框展示

✅ **统计信息**
- 实时显示市场数量
- 数据更新次数计数
- 最后更新时间

## 📊 API 端点

### Flask 后端 API

```
GET /                          # 主页面
GET /api/markets              # 获取市场列表
GET /api/orderbook/<token_id> # 获取订单簿
GET /api/stats                # 获取统计信息
```

### Polymarket 官方 API

```
Gamma API      - https://gamma-api.polymarket.com
CLOB API       - https://clob.polymarket.com
Data API       - https://data-api.polymarket.com
```

## 💡 使用示例

### 启动 Web 应用

```bash
# 终端中运行
python app.py

# 浏览器访问
http://localhost:5000
```

### 页面交互

1. **刷新数据** - 立即获取最新的市场数据
2. **自动刷新** - 启用/禁用自动刷新（默认启用）
3. **查看订单簿** - 点击任意市场卡片的"查看订单簿"按钮

### Python 脚本使用

```python
from polymarket_example import PolymartketAPI

# 初始化客户端
api = PolymartketAPI()

# 获取活跃事件
events = api.get_active_events(limit=10)

# 获取市场详情
market = api.get_market_by_slug("some-market-slug")

# 获取价格
price = api.get_price("token_id_here", side="buy")

# 获取订单簿
orderbook = api.get_orderbook("token_id_here")
```

## 🎨 Web 页面功能详解

### 市场卡片

每个市场卡片显示：
- **市场标题** - 预测问题
- **预期结果** - Yes/No 的概率百分比
- **买卖价格** - 当前买入/卖出价
- **价差** - 买卖价差
- **交易量** - 可视化交易量条
- **订单簿按钮** - 查看深度数据

### 统计面板

显示：
- **市场数量** - 当前显示的活跃市场数
- **更新次数** - 总刷新次数
- **自动刷新状态** - 启用/禁用标识
- **最后更新时间** - 最近数据更新的时间戳

### 订单簿模态框

显示市场的：
- 前10个最佳买单（Price & Size）
- 前10个最佳卖单（Price & Size）

## 🔧 技术栈

- **后端**: Flask (Python)
- **前端**: HTML5 + CSS3 + Vanilla JavaScript
- **API**: Polymarket Gamma API & CLOB API
- **数据获取**: requests 库

## 📝 配置选项

在 `app.py` 中可以自定义：

```python
# 市场列表数量
limit: int = 10

# 自动刷新间隔
REFRESH_INTERVAL = 10000  # 毫秒
```

在 `index.html` 中可以自定义：

```javascript
const REFRESH_INTERVAL = 10000;  // 10秒
```

## 🐛 常见问题

### 1. 端口已被占用

修改 `app.py` 的最后一行：
```python
app.run(debug=True, port=5001)  # 改为其他端口
```

### 2. 无法获取某些市场的价格

可能原因：
- 市场已关闭
- Token ID 无效
- API 暂时无法访问

程序会自动处理这些情况并显示 N/A

### 3. 实时数据更新不及时

- 检查网络连接
- 增加刷新间隔（修改 `REFRESH_INTERVAL`）
- 手动点击"刷新数据"按钮

## 📚 API 文档

- [Polymarket 官方文档](https://docs.polymarket.com/)
- [Gamma API 文档](https://docs.polymarket.com/developers/gamma-markets-api/overview)
- [CLOB API 文档](https://docs.polymarket.com/developers/CLOB/introduction)

## 💬 数据模型

### 市场数据

```python
{
    'id': str,                    # 市场ID
    'question': str,              # 预测问题
    'slug': str,                  # URL slug
    'outcomes': List[str],        # 预期结果 ['Yes', 'No']
    'prices': List[str],          # 对应概率
    'volume': float,              # 交易量
    'active': bool,               # 是否活跃
    'closed': bool,               # 是否已关闭
    'buy_price': str,             # 当前买入价
    'sell_price': str,            # 当前卖出价
    'token_id': str               # CLOB Token ID
}
```

### 订单簿数据

```python
{
    'bids': [{'price': str, 'size': str}, ...],  # 买单列表
    'asks': [{'price': str, 'size': str}, ...],  # 卖单列表
    'mid': str,                                    # 中间价格
    'spread': str                                  # 价差
}
```

## ✨ 特色功能

🎯 **实时数据同步** - 数据自动刷新
📱 **响应式设计** - 完美适配各种设备
🎨 **现代UI** - 渐变背景 + 动画效果
⚡ **高效API** - 智能缓存 + 异步加载
🔔 **用户反馈** - 成功/错误消息提示
📊 **深度分析** - 查看订单簿深度数据

## 🚀 性能优化

- 缓存市场数据减少API调用
- 异步 JavaScript 加载不阻塞页面
- 响应式设计优化移动端体验
- CSS 动画使用 GPU 加速

## 📄 许可证

使用 Polymarket 官方 API，遵守其使用条款。

## 🙏 致谢

感谢 Polymarket 提供的开放 API 接口。


## 🔑 API 端点概览

### Gamma API（市场数据）
```
GET https://gamma-api.polymarket.com/events
GET https://gamma-api.polymarket.com/markets
GET https://gamma-api.polymarket.com/sports
GET https://gamma-api.polymarket.com/tags
```

### CLOB API（交易数据）
```
GET https://clob.polymarket.com/price
GET https://clob.polymarket.com/book
```

### Data API（用户数据）
```
GET https://data-api.polymarket.com/user/{address}/positions
GET https://data-api.polymarket.com/user/{address}/trades
```

## 📊 数据模型

### Event（事件）
```json
{
  "id": "string",
  "slug": "string",
  "title": "string",
  "description": "string",
  "startTime": "ISO 8601 date",
  "active": true,
  "closed": false,
  "tags": [{"id": 2, "label": "Politics"}]
}
```

### Market（市场）
```json
{
  "id": "string",
  "slug": "string",
  "title": "string",
  "outcomes": ["Yes", "No"],
  "outcomePrices": ["0.45", "0.55"],
  "clobTokenIds": ["string", "string"],
  "volume": "1234.56",
  "liquidity": "5000.00"
}
```

### Price（价格）
```json
{
  "price": "0.45",
  "min_size": "1",
  "max_size": "1000"
}
```

### OrderBook（订单簿）
```json
{
  "bids": [
    {"price": "0.44", "size": "100"},
    {"price": "0.43", "size": "200"}
  ],
  "asks": [
    {"price": "0.46", "size": "150"},
    {"price": "0.47", "size": "300"}
  ],
  "mid": "0.45",
  "spread": "0.02"
}
```

## 🎯 常见用途

### 1. 获取所有活跃市场
```python
api = PolymartketAPI()
events = api.get_active_events(limit=50)
```

### 2. 查找特定市场
```python
market = api.get_market_by_slug("will-bitcoin-reach-100k-by-2025")
```

### 3. 监控实时价格
```python
price = api.get_price("token_id_here", side="buy")
print(f"当前买入价: {price.price}")
```

### 4. 分析订单簿
```python
orderbook = api.get_orderbook("token_id_here")
best_bid = orderbook['bids'][0]
best_ask = orderbook['asks'][0]
```

### 5. 查看体育赛事
```python
sports = api.get_sports_leagues()
# 按联赛ID查询特定赛事
```

### 6. 按类别浏览
```python
# tag_id 参考:
# 2 - Politics（政治）
# 其他标签通过 get_all_tags() 获取

political_events = api.get_events_by_tag(tag_id=2, limit=10)
```

## 🔗 相关文档

- [Polymarket 官方文档](https://docs.polymarket.com/)
- [Gamma API 文档](https://docs.polymarket.com/developers/gamma-markets-api/overview)
- [CLOB API 文档](https://docs.polymarket.com/developers/CLOB/introduction)
- [Data API 文档](https://docs.polymarket.com/developers/misc-endpoints/data-api-get-positions)
- [SDK 和库](https://docs.polymarket.com/quickstart/overview#sdks--libraries)

## 📦 官方 SDK

### TypeScript
```bash
npm install @polymarket/clob-client
```

### Python
```bash
pip install py-clob-client
```

## 💡 提示

- ✅ 无需身份验证即可查询市场数据
- ✅ 所有价格都表示为 0-1 之间的小数（隐含概率）
- ✅ `outcomePrices` 的索引与 `outcomes` 一一对应
- ✅ 要进行交易操作，需要钱包和身份验证
- ✅ 实时价格通过 CLOB API 获取，市场数据通过 Gamma API 获取

## 🚀 快速开始

1. **选择你喜欢的语言** - JavaScript/TypeScript 或 Python
2. **复制相应的文件**到你的项目
3. **安装依赖**（如果需要）
4. **运行示例**查看输出
5. **修改代码**以满足你的需求

## 📝 注意事项

- API 调用没有速率限制，但建议避免过度请求
- 价格数据可能有轻微延迟
- 某些端点可能需要特定的用户代理
- WebSocket 连接可用于实时更新

## 🤝 贡献

欢迎改进这些示例！
