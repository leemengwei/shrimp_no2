# 🚀 30秒快速启动指南

## 最快的启动方式

### Windows Cmd
```bash
cd d:\polym
run.bat
```

### Windows PowerShell
```powershell
cd d:\polym
powershell -ExecutionPolicy Bypass -File run.ps1
```

### 手动启动
```bash
cd d:\polym
python app.py
```

## 然后访问

打开浏览器访问：**http://localhost:5000**

---

## 停止应用

按 **Ctrl + C** 停止 Flask 服务器

---

## 主要功能一览

✅ **实时市场数据** - 显示最新的预测市场
✅ **自动刷新** - 每10秒更新一次（可配置）  
✅ **订单簿** - 查看买卖单深度
✅ **美观UI** - 现代化设计和动画效果
✅ **响应式** - 支持手机/平板访问

---

## 文件说明

| 文件 | 用途 |
|------|------|
| app.py | Flask 后端（提供 API） |
| polymarket_example.py | Python API 示例 |
| templates/index.html | Web 前端（仪表板） |
| requirements.txt | Python 依赖 |
| run.bat / run.ps1 | 快速启动脚本 |

---

## 常见问题

**Q: 显示无法连接？**  
A: 确保 Flask 应用正在运行，检查端口 5000 是否被占用

**Q: 显示 "N/A" 怎么办？**  
A: 某些市场没有可用的 Token ID，等待数据更新

**Q: 如何修改刷新间隔？**  
A: 编辑 `templates/index.html`，找到 `REFRESH_INTERVAL = 10000` 改成其他值

---

更多信息查看：
- **QUICKSTART.md** - 详细快速开始指南
- **README.md** - 完整项目文档
- **CONFIGURATION.md** - 配置和部署指南

---

🎉 现在就启动应用吧！
