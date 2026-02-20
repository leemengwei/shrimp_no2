#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import os
import sys
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timedelta

# 将项目 src 添加到 sys.path，方便导入本地模块
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from common.http_client import request_json

# Data / Gamma API 地址
DATA_API = "https://data-api.polymarket.com"
GAMMA_API = "https://gamma-api.polymarket.com"

# 报告输出路径（Markdown）
REPORT_PATH = os.path.join(os.path.dirname(__file__), "report.md")

# 日志文件路径模式
LOG_PATTERN = os.path.join(os.path.dirname(__file__), "user_activity.log.{}.jsonl")


def to_float(value):
    """将可能为 None 或空字符串的值安全地转换为浮点数，失败时返回 0.0"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def fetch_api_data(user_id):
    """从 API 获取用户相关数据"""
    profile = request_json("GET", GAMMA_API, "/public-profile", params={"address": user_id})
    activity = request_json(
        "GET",
        DATA_API,
        "/activity",
        params={"user": user_id, "limit": 500, "offset": 0},
    )
    trades = request_json(
        "GET",
        DATA_API,
        "/trades",
        params={"user": user_id, "limit": 500, "offset": 0, "takerOnly": True},
    )
    positions = request_json(
        "GET",
        DATA_API,
        "/positions",
        params={"user": user_id, "limit": 500, "offset": 0},
    )
    closed_positions = []
    offset = 0
    limit = 50  # API 最大 limit 是 50
    while True:
        batch = request_json(
            "GET",
            DATA_API,
            "/closed-positions",
            params={"user": user_id, "limit": limit, "offset": offset},
        )
        if not batch:
            break
        closed_positions.extend(batch)
        if len(batch) < limit:
            break
        offset += limit
    value = request_json("GET", DATA_API, "/value", params={"user": user_id})
    traded = request_json("GET", DATA_API, "/traded", params={"user": user_id})
    leaderboard = request_json("GET", DATA_API, "/v1/leaderboard", params={"user": user_id, "timePeriod": "ALL", "orderBy": "VOL"})
    comments = request_json(
        "GET",
        GAMMA_API,
        f"/comments/user_address/{user_id}",
        params={"limit": 200000, "offset": 0, "order": "createdAt", "ascending": False},
    )
    return {
        "profile": profile,
        "activity": activity,
        "trades": trades,
        "positions": positions,
        "closed_positions": closed_positions,
        "value": value,
        "traded": traded,
        "leaderboard": leaderboard,
        "comments": comments,
    }


def load_activity_logs(user_id):
    """从日志文件加载用户活动数据"""
    logs = []
    # 尝试不同的日志文件，如 user_activity.log.RN1.jsonl 等
    for suffix in ["", ".RN1", ".The-Selector"]:  # 根据工作区中的文件
        log_path = LOG_PATTERN.format(suffix.strip("."))
        if os.path.exists(log_path):
            try:
                with open(log_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            entry = json.loads(line.strip())
                            logs.append(entry)
            except Exception as e:
                print(f"Warning: Failed to load {log_path}: {e}")
    return logs


def build_user_profile(user_id, api_data, logs):
    """构建用户画像"""
    profile = api_data["profile"] or {}
    positions = api_data["positions"] or []
    closed_positions = api_data["closed_positions"] or []
    trades = api_data["trades"] or []
    activity = api_data["activity"] or []
    comments = api_data["comments"] or []

    # 基本统计
    current_value = to_float(api_data["value"][0]["value"]) if api_data.get("value") else 0
    total_positions = len(positions)
    total_closed = len(closed_positions)
    total_trades = len(trades)
    total_comments = len(comments)

    # 活动和交易分布
    activity_types = Counter(item.get("type") for item in activity if item.get("type"))
    trade_sides = Counter(item.get("side") for item in trades if item.get("side"))

    # 市场偏好
    market_counter = Counter()
    for item in positions + closed_positions + trades:
        market = item.get("market") or item.get("title")
        if market:
            market_counter[market] += 1

    # 从日志中补充交易数据
    log_trades = [entry for entry in logs if entry.get("type") == "trade"]
    for entry in log_trades:
        market = entry.get("market")
        if market:
            market_counter[market] += 1

    # Leaderboard pnl
    leaderboard_data = api_data.get("leaderboard", [])
    leaderboard_pnl = 0
    if leaderboard_data:
        leaderboard_pnl = to_float(leaderboard_data[0].get("pnl", 0)) if leaderboard_data else 0

    # 胜率计算（基于 closed_positions 的 pnl）
    def get_pnl(pos):
        # 优先使用 realizedPnl（根据 API 文档）
        pnl = to_float(pos.get("realizedPnl")) or to_float(pos.get("pnl")) or to_float(pos.get("profit")) or to_float(pos.get("pnlAmount"))
        if pnl != 0:
            return pnl
        # 如果没有，直接字段，尝试计算
        exit_price = to_float(pos.get("exitPrice"))
        entry_price = to_float(pos.get("avgEntryPrice")) or to_float(pos.get("avgPrice")) or to_float(pos.get("entryPrice"))
        size = to_float(pos.get("size")) or to_float(pos.get("totalBought"))
        if exit_price and entry_price and size:
            # 假设 BUY 是 long，SELL 是 short，但对于 closed，可能需要检查 side
            side = pos.get("side", "BUY")
            pnl = (exit_price - entry_price) * size
            if side == "SELL":
                pnl = -pnl  # SELL 是 short
            return pnl
        return 0

    winning_trades = sum(1 for pos in closed_positions if get_pnl(pos) > 0)
    total_closed_value = sum(get_pnl(pos) for pos in closed_positions)
    win_rate = winning_trades / len(closed_positions) if closed_positions else 0

    # 交易频率（假设从最早活动到最新）
    timestamps = []
    for item in activity + trades + log_trades:
        ts = item.get("timestamp") or item.get("createdAt") or item.get("eventTimeLocal")
        if ts:
            try:
                if isinstance(ts, str):
                    # 尝试解析不同格式
                    if "T" in ts:
                        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                        # 如果有 tzinfo，转换为 UTC 然后移除
                        if dt.tzinfo is not None:
                            dt = dt - dt.utcoffset()  # 转换为 naive UTC
                    else:
                        dt = datetime.fromtimestamp(float(ts))
                else:
                    dt = datetime.fromtimestamp(ts)
                # 确保所有 datetime 都是 naive
                dt = dt.replace(tzinfo=None)
                # 转换为 timestamp 以便比较
                timestamps.append(dt.timestamp())
            except Exception as e:
                # 跳过无法解析的时间戳
                pass
    if timestamps:
        min_ts = min(timestamps)
        max_ts = max(timestamps)
        days_active = max((max_ts - min_ts) / 86400, 1)  # 86400 seconds in a day
        trade_frequency = total_trades / days_active if total_trades > 0 else 0
    else:
        trade_frequency = 0

    # 持仓集中度（前三大持仓的价值占比）
    pos_values = sorted([to_float(pos.get("currentValue")) for pos in positions], reverse=True)
    top3_value = sum(pos_values[:3]) if len(pos_values) >= 3 else sum(pos_values)
    concentration = top3_value / current_value if current_value > 0 else 0

    # 评论活跃度
    recent_comment = comments[0].get("createdAt") if comments else None

    return {
        "profile": profile,
        "current_value": current_value,
        "total_positions": total_positions,
        "total_closed": total_closed,
        "total_trades": total_trades,
        "total_comments": total_comments,
        "activity_types": dict(activity_types),
        "trade_sides": dict(trade_sides),
        "market_preferences": dict(market_counter.most_common(10)),
        "win_rate": win_rate,
        "total_pnl": total_closed_value,
        "leaderboard_pnl": leaderboard_pnl,
        "trade_frequency": trade_frequency,
        "concentration": concentration,
        "recent_comment": recent_comment,
        "top_positions": sorted(positions, key=lambda x: to_float(x.get("currentValue")), reverse=True)[:5],
        "traded_markets": api_data.get("traded", {}).get("traded", 0),
        "value_data": api_data.get("value"),
    }


def analyze_behavior(profile):
    """分析用户行为模式和诊断交易表现"""
    analysis = {}

    # 胜率分析
    win_rate = profile["win_rate"]
    if win_rate > 0.6:
        analysis["win_rate_assessment"] = "优秀胜率，交易策略有效"
    elif win_rate > 0.5:
        analysis["win_rate_assessment"] = "中等胜率，需要改进"
    else:
        analysis["win_rate_assessment"] = "胜率较低，建议调整策略"

    # 交易频率分析
    freq = profile["trade_frequency"]
    if freq > 10:
        analysis["frequency_assessment"] = "高频交易，风险较高"
    elif freq > 1:
        analysis["frequency_assessment"] = "中等频率，较为活跃"
    else:
        analysis["frequency_assessment"] = "低频交易，较为保守"

    # 持仓集中度分析
    conc = profile["concentration"]
    if conc > 0.8:
        analysis["concentration_assessment"] = "高度集中，风险极高"
    elif conc > 0.5:
        analysis["concentration_assessment"] = "中等集中，需要分散"
    else:
        analysis["concentration_assessment"] = "良好分散，风险可控"

    # 市场偏好分析
    markets = profile["market_preferences"]
    top_market = max(markets, key=markets.get) if markets else "无"
    analysis["market_preference"] = f"主要关注市场：{top_market}"

    # 总体诊断
    pnl = profile["total_pnl"]
    if pnl > 0:
        analysis["overall_diagnosis"] = "盈利用户，策略可行"
    elif pnl > -1000:  # 假设单位
        analysis["overall_diagnosis"] = "轻微亏损，可调整"
    else:
        analysis["overall_diagnosis"] = "重大亏损，需重新评估"

    # 行为模式总结
    sides = profile["trade_sides"]
    buy_ratio = sides.get("BUY", 0) / sum(sides.values()) if sides else 0
    if buy_ratio > 0.8:
        analysis["behavior_pattern"] = "主要做多，乐观策略"
    elif buy_ratio < 0.2:
        analysis["behavior_pattern"] = "主要做空，谨慎策略"
    else:
        analysis["behavior_pattern"] = "平衡买卖，中性策略"

    return analysis


def generate_report(user_id, profile, analysis):
    """生成 Markdown 报告"""
    lines = []
    lines.append("# 用户交易行为分析报告")
    lines.append("")
    lines.append(f"生成时间: {datetime.utcnow().isoformat()}Z")
    lines.append(f"用户 ID: {user_id}")
    lines.append("")

    # 用户基本信息
    prof = profile["profile"] or {}
    lines.append("## 用户基本信息")
    lines.append("")
    lines.append(f"- 姓名: {prof.get('name', '未知')}")
    lines.append(f"- 昵称: {prof.get('pseudonym', '未知')}")
    lines.append(f"- 代理钱包: {prof.get('proxyWallet', '未知')}")
    lines.append(f"- 创建时间: {prof.get('createdAt', '未知')}")
    lines.append("")

    # 持仓概况
    lines.append("## 持仓概况")
    lines.append("")
    lines.append(f"- 当前持仓价值: {profile['current_value']:.6f}")
    lines.append(f"- 持仓数量: {profile['total_positions']}")
    lines.append(f"- 已平仓数量: {profile['total_closed']}")
    lines.append(f"- 持仓集中度: {profile['concentration']:.2%}")
    lines.append("")

    # 交易统计
    lines.append("## 交易统计")
    lines.append("")
    lines.append(f"- 总交易次数: {profile['total_trades']}")
    lines.append(f"- 已交易市场数: {profile['traded_markets']}")
    lines.append(f"- 胜率: {profile['win_rate']:.2%}")
    lines.append(f"- 总盈亏: {profile['total_pnl']:.6f}")
    lines.append(f"- Leaderboard 盈亏: {profile['leaderboard_pnl']:.6f}")
    lines.append(f"- 交易频率 (次/天): {profile['trade_frequency']:.2f}")
    lines.append(f"- 活动类型分布: {profile['activity_types']}")
    lines.append(f"- 交易方向分布: {profile['trade_sides']}")
    lines.append("")

    # 市场偏好
    lines.append("## 市场偏好 (前10)")
    lines.append("")
    for market, count in profile["market_preferences"].items():
        lines.append(f"- {market}: {count} 次")
    lines.append("")

    # 评论活跃度
    lines.append("## 评论活跃度")
    lines.append("")
    lines.append(f"- 评论总数: {profile['total_comments']}")
    lines.append(f"- 最新评论时间: {profile['recent_comment'] or '无'}")
    lines.append("")

    # 行为分析
    lines.append("## 行为模式分析")
    lines.append("")
    for key, value in analysis.items():
        lines.append(f"- {key.replace('_', ' ').title()}: {value}")
    lines.append("")

    # 顶部持仓
    lines.append("## 顶部持仓 (按当前价值)")
    lines.append("")
    for pos in profile["top_positions"]:
        title = pos.get("title", "未知")
        outcome = pos.get("outcome", "未知")
        value = to_float(pos.get("currentValue"))
        lines.append(f"- {title} | {outcome} | {value:.6f}")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="生成用户交易行为分析报告")
    parser.add_argument("user_id", help="用户 ID (地址)")
    args = parser.parse_args()

    user_id = args.user_id

    # 获取数据
    api_data = fetch_api_data(user_id)
    logs = load_activity_logs(user_id)

    # 构建画像
    profile = build_user_profile(user_id, api_data, logs)

    # 分析行为
    analysis = analyze_behavior(profile)

    # 生成报告
    report = generate_report(user_id, profile, analysis)

    # 保存报告
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"报告已保存到 {REPORT_PATH}")


if __name__ == "__main__":
    main()
