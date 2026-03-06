# 注意这个项目需要代理
在nx家园设备跑时，nx上配置了clash服务，必须要开机启动 （目前是sudo nohup ./clash-linux-arm64-v1.18.0 -f ./config.yaml）
然后配置代理端口到对应位置， 如 AI 分析所说：

你这台机器能直接 curl www.google.com，原因已经查到了：

当前 shell 环境里设置了代理变量：
http_proxy=http://127.0.0.1:7890
https_proxy=http://127.0.0.1:7890

这些变量来源于你的 bash 配置文件：
~/.bashrc:122
~/.bashrc:123

本地 127.0.0.1:7890 确实有代理程序在监听，进程是 clash-linux-arm64-v1.18.0（2月20日启动的）。