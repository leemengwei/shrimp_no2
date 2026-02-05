# 🚀 Polymarket 实时市场数据展示系统

## 项目已完成！

您现在拥有一个完整的 **Polymarket 市场数据展示 Web 应用**。

### ✅ 已完成的操作

1. ✓ 删除了 JavaScript 和 TypeScript 示例文件
2. ✓ 保留了功能完整的 Python API 示例 (`polymarket_example.py`)
3. ✓ 创建了 Flask Web 应用后端 (`app.py`)
4. ✓ 创建了现代化的前端仪表板 (`templates/index.html`)
5. ✓ 支持实时数据刷新和可视化展示

---

## 📂 项目结构

```
d:\polym\
├── app.py                    # Flask 后端服务器
├── polymarket_example.py     # Python API 示例脚本
├── templates/
│   └── index.html           # Web 前端（完整仪表板）
├── requirements.txt          # Python 依赖
├── run.bat                  # Windows 启动脚本
├── run.ps1                  # PowerShell 启动脚本
└── README.md                # 详细文档
```

---

## 🎯 快速开始

### 方式 1: 运行 Web 应用（推荐）

**Windows Cmd:**
```bash
cd d:\polym
run.bat
```

**PowerShell:**
```powershell
cd d:\polym
powershell -ExecutionPolicy Bypass -File run.ps1
```

**或直接运行：**
```bash
cd d:\polym
pip install -r requirements.txt
python app.py
```

然后在浏览器访问：**http://localhost:5000**

### 方式 2: 运行 Python 脚本

```bash
cd d:\polym
python polymarket_example.py
```

---

## 🌐 Web 应用界面

### 主页面功能

📊 **实时市场看板**
- 显示最多 5 个活跃市场
- 实时显示买入/卖出价格
- 交易量可视化条形图
- 预期结果概率展示

🔄 **自动刷新**
- 默认 10 秒自动刷新一次
- 可启用/禁用自动刷新
- 手动刷新按钮

📈 **订单簿深度**
- 点击市场卡片查看订单簿
- 显示最佳 10 个买单/卖单
- 实时价格和数量信息

📊 **统计面板**
- 实时市场数量
- 总刷新次数计数
- 最后更新时间戳

### 界面特点

✨ 现代化渐变设计
🎨 动画过渡效果
📱 响应式布局（支持移动端）
⚡ 快速加载和实时更新

---

## 🔧 使用指南

### Web 应用控制

| 功能 | 说明 |
|-----|------|
| 🔄 刷新数据 | 立即更新市场数据 |
| ⏸ 自动刷新 | 启用/禁用自动更新 |
| 🔁 重新加载 | 刷新整个页面 |
| 📊 查看订单簿 | 查看市场深度数据 |

### 市场卡片信息

- **市场标题** - 预测问题
- **预期结果** - Yes/No 的概率百分比
- **买入/卖出价** - 当前市场价格
- **价差** - 买卖价差
- **交易量** - 可视化历史交易量

---

## 📡 API 端点

### Flask 后端 API

```
GET  /                      # 主页面
GET  /api/markets          # 获取市场列表
GET  /api/orderbook/<id>   # 获取订单簿
GET  /api/stats            # 获取统计信息
```

### Polymarket 官方 API

```
https://gamma-api.polymarket.com     # 市场数据
https://clob.polymarket.com          # 交易数据
https://data-api.polymarket.com      # 用户数据
```

---

## 💻 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Flask (Python) |
| 前端 | HTML5 + CSS3 + JavaScript |
| API | Requests (Python) |
| 数据源 | Polymarket 官方 API |

---

## 🐍 Python API 使用示例

### 基本使用

```python
from polymarket_example import PolymartketAPI

# 初始化 API 客户端
api = PolymartketAPI()

# 获取活跃事件
events = api.get_active_events(limit=10)

# 获取市场详情
market = api.get_market_by_slug("bitcoin-price-by-2025")

# 获取实时价格
price = api.get_price("token_id_xxx", side="buy")

# 获取订单簿
orderbook = api.get_orderbook("token_id_xxx")

# 按标签查询（政治市场 tag_id=2）
political_events = api.get_events_by_tag(tag_id=2, limit=10)
```

### 获取所有标签

```python
tags = api.get_all_tags(limit=100)
for tag in tags:
    print(f"{tag['label']} (ID: {tag['id']})")
```

---

## ⚙️ 配置选项

### Flask 应用配置

编辑 `app.py`：

```python
# 修改监听端口
app.run(debug=True, port=5001)  # 改为 5001

# 修改事件数量
get_active_events(limit=20)  # 改为 20 个
```

### 前端配置

编辑 `templates/index.html`：

```javascript
// 修改自动刷新间隔（毫秒）
const REFRESH_INTERVAL = 5000;  // 改为 5 秒
```

---

## 🐛 常见问题

### Q1: 无法访问 http://localhost:5000

**解决方案：**
- 确保 Flask 应用正在运行
- 检查防火墙设置
- 尝试使用 `http://127.0.0.1:5000`

### Q2: 某些市场显示 "N/A" 价格

**原因：**
- 市场已关闭
- 尚无有效的 Token ID
- API 暂时无法访问

**解决方案：** 等待数据更新或手动刷新

### Q3: 页面加载缓慢

**原因：** 网络延迟或 API 响应慢

**解决方案：**
- 增加刷新间隔
- 检查网络连接
- 减少显示的市场数量

### Q4: 自动刷新不工作

**解决方案：**
- 检查浏览器控制台是否有错误
- 按 F12 打开开发者工具
- 手动点击"刷新数据"按钮

### Q5: ModuleNotFoundError: No module named 'flask'

**解决方案：**
```bash
pip install -r requirements.txt
```

---

## 📊 数据说明

### 市场数据结构

```python
{
    'id': '市场ID',
    'question': '预测问题',
    'outcomes': ['Yes', 'No'],
    'prices': ['0.45', '0.55'],  # 概率值
    'volume': 1234567.89,        # 交易量
    'buy_price': '0.45',         # 当前买入价
    'sell_price': '0.46',        # 当前卖出价
    'active': True,              # 是否活跃
    'token_id': 'XXXXX'          # CLOB Token ID
}
```

### 订单簿数据结构

```python
{
    'bids': [                    # 买单
        {'price': '0.44', 'size': '100'},
        {'price': '0.43', 'size': '200'}
    ],
    'asks': [                    # 卖单
        {'price': '0.47', 'size': '150'},
        {'price': '0.48', 'size': '300'}
    ]
}
```

---

## 🎨 界面预览

**主仪表板：**
- 紫色渐变背景
- 市场卡片网格布局
- 实时更新指示器
- 统计信息面板

**订单簿弹窗：**
- 买单表格（价格 × 数量）
- 卖单表格（价格 × 数量）
- 响应式设计
- 流畅动画

---

## 🚀 性能优化建议

1. **减少刷新频率** - 改为 30 秒刷新一次
2. **限制市场数量** - 改为显示 3 个市场
3. **启用缓存** - 减少不必要的 API 调用
4. **异步加载** - 提高页面响应速度

---

## 📚 参考文档

- [Polymarket 官方文档](https://docs.polymarket.com/)
- [Gamma API 文档](https://docs.polymarket.com/developers/gamma-markets-api/overview)
- [CLOB API 文档](https://docs.polymarket.com/developers/CLOB/introduction)
- [Flask 文档](https://flask.palletsprojects.com/)

---

## 💡 进阶功能建议

### 可以添加的功能

1. 📈 历史价格图表
2. 🔔 价格变动提醒
3. 💾 数据导出 (CSV/JSON)
4. 🔐 用户认证和钱包连接
5. 📱 移动端应用
6. 🎯 自定义市场过滤
7. 💬 社区评论
8. 🏆 排行榜

---

## ✨ 项目特点

✅ **零配置** - 开箱即用
✅ **实时更新** - 自动刷新数据
✅ **美观界面** - 现代化 UI 设计
✅ **响应式** - 支持各种设备
✅ **轻量级** - 依赖少，启动快
✅ **易扩展** - 代码结构清晰

---

## 📝 下一步

1. **访问应用** → http://localhost:5000
2. **查看市场** → 实时显示的活跃预测市场
3. **查询订单簿** → 点击市场卡片了解深度
4. **修改配置** → 根据需求调整参数
5. **部署上线** → 使用生产服务器

---

## 🆘 获取帮助

如遇问题：
1. 检查 `requirements.txt` 中的依赖是否安装
2. 查看 Flask 输出的错误信息
3. 检查浏览器控制台 (F12)
4. 确保网络连接正常

---

**项目已准备就绪！🎉**

祝您使用愉快！如有任何问题，欢迎查阅文档或调整配置。
