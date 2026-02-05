import requests

import json
from datetime import datetime

user_id = '0xf0729143cbf9ade46743017ec4e1832a3564cee7'  # selector
user_id = '0x1ea6aab09d4b9b504fa24f961f0c6709efb72f5d'  # lmw

# 当前用户持仓情况
current_position_url = "https://data-api.polymarket.com/positions?sizeThreshold=1&limit=1000&sortBy=TOKENS&sortDirection=DESC&user=%s"%user_id
# 用户已结算持仓情况
closed_position_url = "https://data-api.polymarket.com/closed-positions?limit=1000&sortBy=REALIZEDPNL&sortDirection=DESC&user=%s"%user_id
# 获取用户交易记录  # NOTE： 必须takeronly给false，否则看不到挂单的
url = "https://data-api.polymarket.com/trades?limit=1000&user=%s&takerOnly=false"%user_id


def parse_closed_position_data(current_position_url):
    response = requests.get(current_position_url)
    json_data = response.json()
    print("="*60)
    print("Closed总体概览")
    print("="*60)
    parsed_data = []
    
    for item in json_data:
        parsed_item = {
            'proxyWallet': item.get('proxyWallet'),
            'asset': item.get('asset'),
            'conditionId': item.get('conditionId'),
            'avgPrice': item.get('avgPrice'),
            'totalBought': item.get('totalBought'),
            'realizedPnl': item.get('realizedPnl'),
            'curPrice': item.get('curPrice'),
            'title': item.get('title'),
            'slug': item.get('slug'),
            'icon': item.get('icon'),
            'eventSlug': item.get('eventSlug'),
            'outcome': item.get('outcome'),
            'outcomeIndex': item.get('outcomeIndex'),
            'oppositeOutcome': item.get('oppositeOutcome'),
            'oppositeAsset': item.get('oppositeAsset'),
            'endDate': item.get('endDate'),
            'timestamp': item.get('timestamp'),
        }
        
        # 转换时间戳为可读格式
        if parsed_item['timestamp']:
            parsed_item['timestamp_readable'] = datetime.fromtimestamp(parsed_item['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
        
        parsed_data.append(parsed_item)
    
    # 示例：打印所有标题
    print("所有市场标题:")
    print("-" * 50)
    for item in parsed_data:
        print(f"• {item['title']}")

    # 示例：计算总盈利
    print("\n盈利分析:")
    print("-" * 50)
    total_realized_pnl = sum(item['realizedPnl'] for item in parsed_data)

    print(f"已实现盈利: ${total_realized_pnl:,.2f} (%s)"%[item['realizedPnl'] for item in parsed_data])

    # # 示例：按盈利排序
    # print("\n按已实现盈利排序:")
    # print("-" * 50)
    # sorted_by_pnl = sorted(parsed_data, key=lambda x: x['realizedPnl'], reverse=True)
    # for item in sorted_by_pnl[:5]:  # 显示前5个
    #     print(f"{item['title']}: ${item['realizedPnl']:,.2f}")

    # 示例：按市场价格分类
    print("\n当前市场价格状态:")
    print("-" * 50)
    active_markets = [item for item in parsed_data if item['curPrice'] > 0 and item['curPrice'] != 1]

    print(f"至今还活跃市场: {len(active_markets)}个：%s"%[item['title'] for item in active_markets])


    # 示例：详细信息表格
    print("\n详细交易信息:")
    print("-" * 100)
    print(f"{'标题':<40} {'方向':<6} {'平均成本':<10} {'当前价':<10} {'数量':<12} {'已实现盈利':<12}")
    print("-" * 100)

    for item in parsed_data:
        title_short = item['title'][:38] + ".." if len(item['title']) > 40 else item['title']
        print(f"{title_short:<40} {item['outcome']:<6} {item['avgPrice']:<10.3f} "
            f"{item['curPrice']:<10.3f} {item['totalBought']:<12,.2f} ${item['realizedPnl']:<12,.2f}")

    # 保存解析后的数据到文件
    with open('parsed_data.json', 'w') as f:
        json.dump(parsed_data, f, indent=2, ensure_ascii=False)

    print("\n数据已保存到 parsed_data.json")
    return parsed_data


def parse_current_position_data(current_position_url):
    response = requests.get(current_position_url)
    data = response.json()
    
    print("="*60)
    print("Current持仓概览")
    print("="*60)

    # 1. 基本统计
    total_positions = len(data)
    total_initial = sum(item['initialValue'] for item in data)
    total_current = sum(item['currentValue'] for item in data)
    total_pnl = sum(item['cashPnl'] for item in data)

    print(f"持仓总数: {total_positions}")
    print(f"总投资额: ${total_initial:.2f}")
    print(f"当前价值: ${total_current:.2f}")
    print(f"总盈亏: ${total_pnl:.2f} ({(total_pnl/total_initial*100 if total_initial>0 else 0):.1f}%)")

    # 2. 按事件分组
    from collections import defaultdict
    events = defaultdict(list)
    for item in data:
        events[item['title']].append(item)

    print(f"\n涉及事件: {len(events)}个")

    # 3. 当前表现最佳/最差
    sorted_by_pnl = sorted(data, key=lambda x: x['percentPnl'])
    # print(f"\n表现最差: {sorted_by_pnl[0]['title'][:30]}... {sorted_by_pnl[0]['percentPnl']:.1f}%")
    # print(f"表现最佳: {sorted_by_pnl[-1]['title'][:30]}... {sorted_by_pnl[-1]['percentPnl']:.1f}%")

    # 4. 持仓详情表格
    print(f"\n持仓详情:")
    print("-"*80)
    print(f"{'市场':<40} {'方向':<6} {'成本价':<8} {'现价':<8} {'盈亏率':<10} {'已实现盈亏':<12}")
    print("-"*80)

    for item in data:
        title = item['title'][:38] + ".." if len(item['title']) > 40 else item['title']
        print(f"{title:<40} {item['outcome']:<6} {item['avgPrice']:<8.3f} "
            f"{item['curPrice']:<8.3f} {item['percentPnl']:<10.1f}% ${item['realizedPnl']:<12.2f}")

    # 5. 特殊情况检查
    print(f"\n特殊状态:")
    for item in data:
        if item.get('mergeable'):
            print(f"  {item['title'][:30]}... 可合并头寸")
        if item.get('curPrice') == 1:
            print(f"  {item['title'][:30]}... 已确定结果 (价格=1)")
        if item.get('curPrice') == 0:
            print(f"  {item['title'][:30]}... 已结算 (价格=0)")

    # 6. 风险分析
    negative_risk = [item for item in data if item.get('negativeRisk', False)]
    if negative_risk:
        print(f"\n注意: {len(negative_risk)}个头寸有负风险")
    


# 解析数据
parsed_data = parse_current_position_data(current_position_url)
parsed_data = parse_closed_position_data(closed_position_url)
