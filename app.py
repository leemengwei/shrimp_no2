"""
Polymarket 市场实时数据展示 Web 应用
Flask 后端 - 提供 API 接口
"""

from flask import Flask, jsonify, render_template
import requests
import json
from typing import Dict, List, Optional
import threading
from datetime import datetime

app = Flask(__name__)

# ============================================
# Polymarket API 配置
# ============================================

GAMMA_API_BASE = "https://gamma-api.polymarket.com"
CLOB_API_BASE = "https://clob.polymarket.com"

# 缓存数据
cache = {
    'events': [],
    'market_data': {},
    'last_update': None,
    'update_count': 0
}

# ============================================
# API 数据获取函数
# ============================================

def get_active_events(limit: int = 10) -> List[Dict]:
    """获取活跃事件列表"""
    try:
        url = f"{GAMMA_API_BASE}/events"
        params = {
            "active": "true",
            "closed": "false",
            "limit": limit
        }
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ 获取事件失败: {e}")
        return []

def get_market_details(market: Dict) -> Dict:
    def parse_market_data(market: Dict) -> Dict:
        """解析市场数据中的 JSON 字符串字段"""
        for field in ['outcomes', 'outcomePrices', 'clobTokenIds']:
            if field in market and isinstance(market[field], str):
                try:
                    market[field] = json.loads(market[field])
                except:
                    pass
        return market
    """提取市场关键信息"""
    parsed = parse_market_data(market)
    
    outcomes = parsed.get('outcomes', [])
    prices = parsed.get('outcomePrices', [])
    
    if isinstance(outcomes, str):
        outcomes = json.loads(outcomes)
    if isinstance(prices, str):
        prices = json.loads(prices)
    
    return {
        'id': parsed.get('id'),
        'question': parsed.get('question', 'N/A'),
        'slug': parsed.get('slug'),
        'outcomes': outcomes,
        'prices': prices,
        'volume': float(parsed.get('volume', 0)),
        'active': parsed.get('active', False),
        'closed': parsed.get('closed', False),
        'clobTokenIds': parsed.get('clobTokenIds', []),
        'endDate': parsed.get('endDate'),
        'lastTradePrice': parsed.get('lastTradePrice'),
        'bestBid': parsed.get('bestBid'),
        'bestAsk': parsed.get('bestAsk')
    }

def get_price(token_id: str, side: str = "buy") -> Optional[str]:
    """获取实时价格"""
    try:
        url = f"{CLOB_API_BASE}/price"
        params = {
            "token_id": token_id,
            "side": side
        }
        response = requests.get(url, params=params, timeout=5)
        data = response.json()
        return data.get('price')
    except Exception as e:
        return None

def get_orderbook(token_id: str) -> Optional[Dict]:
    """获取订单簿"""
    try:
        url = f"{CLOB_API_BASE}/book"
        params = {"token_id": token_id}
        response = requests.get(url, params=params, timeout=5)
        return response.json()
    except Exception as e:
        return None

# ============================================
# Flask 路由
# ============================================

@app.route('/')
def index():
    """主页"""
    return render_template('index.html')

@app.route('/api/markets')
def api_markets():
    """获取市场列表 API"""
    try:
        events = get_active_events(limit=10)
        markets_list = []
        
        for event in events:
            event_markets = event.get('markets', [])
            
            # 获取活跃市场
            for market in event_markets:
                if market.get('active') and not market.get('closed'):
                    market_info = get_market_details(market)
                    
                    # 获取价格数据
                    clob_token_ids = market_info.get('clobTokenIds', [])
                    if clob_token_ids:
                        token_id = clob_token_ids[0]
                        buy_price = get_price(token_id, 'buy')
                        sell_price = get_price(token_id, 'sell')
                        
                        market_info['buy_price'] = buy_price
                        market_info['sell_price'] = sell_price
                        market_info['token_id'] = token_id
                    
                    markets_list.append(market_info)
                    
                    if len(markets_list) >= 5:
                        break
            
            if len(markets_list) >= 5:
                break
        
        # 更新缓存
        cache['events'] = events
        cache['market_data'] = markets_list
        cache['last_update'] = datetime.now().isoformat()
        cache['update_count'] += 1
        
        return jsonify({
            'success': True,
            'data': markets_list,
            'timestamp': cache['last_update'],
            'update_count': cache['update_count']
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/orderbook/<token_id>')
def api_orderbook(token_id):
    """获取订单簿 API"""
    try:
        orderbook = get_orderbook(token_id)
        if not orderbook:
            return jsonify({'success': False, 'error': 'Order book not found'}), 404
        
        return jsonify({
            'success': True,
            'data': orderbook,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/stats')
def api_stats():
    """获取统计信息"""
    return jsonify({
        'last_update': cache['last_update'],
        'update_count': cache['update_count'],
        'markets_count': len(cache['market_data'])
    })

# ============================================
# 错误处理
# ============================================

@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(e):
    return jsonify({'error': 'Internal server error'}), 500

# ============================================
# 启动应用
# ============================================

if __name__ == '__main__':
    print("🚀 启动 Polymarket 市场数据展示应用...")
    print("📊 访问: http://localhost:5000")
    app.run(debug=True, port=5000)
