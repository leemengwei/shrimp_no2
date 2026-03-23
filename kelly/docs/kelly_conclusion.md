# Kelly 仓位结论与代数推广

## 1. 具体问题结论
问题：每轮下注同一固定仓位 `f`（占当前资金比例），赢了下注部分翻倍，输了下注部分减半，且胜率 `p=0.5`，可无限重复。

- 参数对应：`p=0.5, r=1, l=0.5`
- 单轮财富因子：
  - 赢：`1 + f*r = 1 + f`
  - 输：`1 - f*l = 1 - 0.5f`
- 目标（长期几何增长率）：
  `g(f)=p*ln(1+fr)+(1-p)*ln(1-fl)`

最优 Kelly 仓位：
`f* = (p*r-(1-p)*l)/(r*l) = 0.5`

即：**每轮下注当前资金的 50%**。

对应最优对数增长：
`g(f*) = 0.0588915...`，每轮几何增长因子 `exp(g)=1.06066...`。

## 2. 代数推广（可复用函数）
一般化参数：
- `p`：胜率，`0<=p<=1`
- `r`：赢时下注部分净收益倍数（>0）
- `l`：输时下注部分亏损比例（>0）

封闭解：
`f* = (p*r-(1-p)*l)/(r*l) = p/l-(1-p)/r`

实现函数见：
- [kelly_core.py](/home/feifeichouchou/shrimp_no2/kelly/src/kelly_core.py)

核心接口：
- `kelly_fraction(p, r, l, long_only=True, max_fraction=None)`
- `expected_log_growth(f, p, r, l)`
- `solve_kelly(p, r, l)`

## 3. 实验脚本
- 单场景理论+仿真验证：
  `python3 src/kelly_bet_sizing_experiment.py`
- 多参数共调用（回报/亏损/胜率代数输入）：
  `python3 src/kelly_param_sweep.py --p-list 0.45,0.5,0.55 --r-list 0.8,1.0,1.2 --l-list 0.4,0.5`

补充：保守实践通常使用 fractional Kelly（如 0.5 Kelly）：
`f_used = c * f*`, `c in (0,1]`。
