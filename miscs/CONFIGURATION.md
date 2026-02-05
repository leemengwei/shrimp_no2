# 配置和部署指南

## 开发环境配置

### 系统要求

- Python 3.7+
- Windows / macOS / Linux
- 现代浏览器 (Chrome, Firefox, Edge, Safari)
- 网络连接（访问 Polymarket API）

### 安装步骤

#### 1. 克隆或下载项目

```bash
# 或直接使用现有的 d:\polym 目录
cd d:\polym
```

#### 2. 创建虚拟环境（可选但推荐）

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

#### 3. 安装依赖

```bash
pip install -r requirements.txt
```

#### 4. 启动应用

```bash
python app.py
```

访问 `http://localhost:5000`

---

## 配置参数详解

### app.py 配置

#### 基本配置

```python
# Flask 应用启动配置
if __name__ == '__main__':
    app.run(
        debug=True,      # 开发模式（自动重载）
        port=5000,       # 监听端口
        host='127.0.0.1' # 监听地址
    )
```

#### API 配置

```python
# Polymarket API 基础 URL
GAMMA_API_BASE = "https://gamma-api.polymarket.com"
CLOB_API_BASE = "https://clob.polymarket.com"

# 获取事件数量
get_active_events(limit=10)  # 改为其他数字
```

#### 缓存配置

```python
# 缓存数据结构
cache = {
    'events': [],           # 事件列表
    'market_data': {},      # 市场数据
    'last_update': None,    # 最后更新时间
    'update_count': 0       # 更新次数
}
```

### index.html 配置

#### 刷新间隔

```javascript
// 自动刷新间隔（毫秒）
const REFRESH_INTERVAL = 10000;  // 10秒

// 修改为其他值：
// 5000  - 5秒
// 15000 - 15秒
// 30000 - 30秒
```

#### API 基础 URL

```javascript
// API 基础 URL（假设 Flask 在同一主机）
const API_BASE = '/api';

// 如果 Flask 在其他地址：
const API_BASE = 'http://localhost:5000/api';
```

---

## 性能优化

### 1. 减少 API 调用

```python
# app.py 中修改显示的市场数量
if len(markets_list) >= 3:  # 改为 3 而不是 5
    break
```

### 2. 增加刷新间隔

```javascript
// index.html 中
const REFRESH_INTERVAL = 30000;  // 30秒
```

### 3. 启用浏览器缓存

在 `app.py` 中添加：

```python
from flask import Flask
from datetime import timedelta

app = Flask(__name__)

@app.after_request
def add_cache_headers(response):
    response.cache_control.max_age = 300  # 5分钟缓存
    return response
```

### 4. 压缩响应

```bash
pip install flask-compress
```

在 `app.py` 中：

```python
from flask_compress import Compress
Compress(app)
```

---

## 生产环境部署

### 使用 Gunicorn（推荐）

#### 1. 安装 Gunicorn

```bash
pip install gunicorn
```

#### 2. 启动应用

```bash
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

参数说明：
- `-w 4` - 工作进程数
- `-b 0.0.0.0:8000` - 绑定地址和端口
- `app:app` - 应用模块和对象

### 使用 Nginx 反向代理

#### 1. 安装 Nginx

Windows: 从 [nginx.org](http://nginx.org) 下载

macOS: `brew install nginx`

Linux: `sudo apt install nginx`

#### 2. 配置 Nginx

编辑 `nginx.conf`：

```nginx
upstream flask_app {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name localhost;

    location / {
        proxy_pass http://flask_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

#### 3. 启动 Nginx

```bash
# Windows
nginx.exe

# macOS / Linux
sudo nginx
```

### 使用 Docker

#### 1. 创建 Dockerfile

```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV FLASK_APP=app.py
EXPOSE 5000

CMD ["gunicorn", "-b", "0.0.0.0:5000", "app:app"]
```

#### 2. 构建和运行

```bash
# 构建镜像
docker build -t polymarket-app .

# 运行容器
docker run -p 5000:5000 polymarket-app
```

### 使用 AWS/云平台

#### Heroku 部署

```bash
# 1. 安装 Heroku CLI
# 从 https://devcenter.heroku.com/articles/heroku-cli 下载

# 2. 登录
heroku login

# 3. 创建应用
heroku create your-app-name

# 4. 部署
git push heroku main

# 5. 查看日志
heroku logs --tail
```

#### AWS Elastic Beanstalk

```bash
# 1. 安装 EB CLI
pip install awsebcli

# 2. 初始化
eb init -p python-3.9 polymarket-app

# 3. 创建环境
eb create production

# 4. 部署
eb deploy
```

---

## 安全配置

### 1. 隐藏调试信息

在生产环境中关闭调试模式：

```python
# app.py
app.run(debug=False)  # 改为 False
```

### 2. 设置 SECRET_KEY

```python
import secrets

app.config['SECRET_KEY'] = secrets.token_hex(32)
```

### 3. 限制请求频率

```bash
pip install Flask-Limiter
```

```python
from flask_limiter import Limiter

limiter = Limiter(app, key_func=lambda: request.remote_addr)

@app.route('/api/markets')
@limiter.limit("30 per minute")
def api_markets():
    # ...
```

### 4. 启用 CORS

```bash
pip install flask-cors
```

```python
from flask_cors import CORS

CORS(app)
```

### 5. 添加 HTTPS

使用 Let's Encrypt 和 Certbot：

```bash
# 安装 Certbot
sudo apt install certbot

# 获取证书
sudo certbot certonly --standalone -d yourdomain.com

# 在 Nginx 配置中使用证书
ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
```

---

## 监控和日志

### 1. 配置日志

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
```

### 2. 性能监控

```bash
pip install flask-debugtoolbar
```

```python
from flask_debugtoolbar import DebugToolbarExtension

toolbar = DebugToolbarExtension(app)
app.config['DEBUG_TB_ENABLED'] = True
```

### 3. 错误追踪

集成 Sentry：

```bash
pip install sentry-sdk[flask]
```

```python
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration

sentry_sdk.init(
    dsn="your-sentry-dsn",
    integrations=[FlaskIntegration()]
)
```

---

## 故障排除

### 问题 1: 端口已被占用

```bash
# 查找占用端口的进程
netstat -ano | findstr :5000

# 杀死进程
taskkill /PID <PID> /F

# 或使用其他端口
python app.py --port 5001
```

### 问题 2: API 请求超时

在 `app.py` 中增加超时时间：

```python
response = requests.get(url, timeout=15)  # 改为 15 秒
```

### 问题 3: 内存占用过高

```python
# 定期清理缓存
from threading import Timer

def clear_cache():
    global cache
    cache['events'] = []
    cache['market_data'] = {}
    Timer(3600, clear_cache).start()  # 1小时清理一次

clear_cache()
```

### 问题 4: 数据库连接错误

如果添加了数据库，配置连接池：

```python
from sqlalchemy.pool import QueuePool

app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'poolclass': QueuePool,
    'pool_size': 10,
    'pool_recycle': 3600,
    'pool_pre_ping': True,
}
```

---

## 环境变量

创建 `.env` 文件：

```env
FLASK_ENV=development
FLASK_DEBUG=True
POLYMARKET_API_TIMEOUT=10
MARKET_LIMIT=5
REFRESH_INTERVAL=10000
```

在 `app.py` 中读取：

```python
import os
from dotenv import load_dotenv

load_dotenv()

TIMEOUT = int(os.getenv('POLYMARKET_API_TIMEOUT', 10))
MARKET_LIMIT = int(os.getenv('MARKET_LIMIT', 5))
```

---

## 备份和恢复

### 备份数据

```python
import json
from datetime import datetime

def backup_data():
    backup = {
        'timestamp': datetime.now().isoformat(),
        'markets': cache['market_data']
    }
    with open(f'backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json', 'w') as f:
        json.dump(backup, f)
```

### 定时备份

使用 cron (Linux) 或任务计划程序 (Windows)：

```bash
# Linux crontab
0 */6 * * * cd /path/to/app && python -c "from app import backup_data; backup_data()"
```

---

## 版本更新

### 更新依赖

```bash
pip install --upgrade -r requirements.txt
```

### 检查兼容性

```bash
pip check
```

### 冻结依赖版本

```bash
pip freeze > requirements.txt
```

---

**配置完成！祝您部署顺利！** 🚀
