# 本地Web面板

## 说明
- 使用 Flask + 原生前端实现本地数据展示。
- 支持用户/端点切换、关键字搜索、时间戳筛选与分页。
- 数据来源固定：`data/polymarket/<user>/endpoints/*` 与 `manifest.json`。

## 启动命令
```bash
python web/app.py --data-dir data/polymarket --sports-dir data/polymarket/sports_history \
  --host 127.0.0.1 --port 8000
```

## 功能
- 用户切换
- 端点切换
- 搜索关键词（包含任意字段字符串）
- 时间戳范围过滤（Unix秒）
- 分页浏览

## 体育历史面板
- 访问 `/sports`
- 市场/Token 选择 + 时间范围过滤
- 价格点位表格 + 简单走势图
- 支持读取 `data/polymarket/sports_history`（由 `collect_sports_history.py` 生成）
