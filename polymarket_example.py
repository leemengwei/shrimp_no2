"""
Polymarket API Python 样例
演示如何使用 Polymarket API 进行市场查询和价格获取
"""

import requests
import json
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime

# ============================================
# 数据类定义
# ============================================

@dataclass
class Event:
    """事件数据模型"""
    id: str
    slug: str
    title: str
    description: str
    startTime: str
    active: bool
    closed: bool

@dataclass
class Market:
    """市场数据模型"""
    id: str
    slug: str
    title: str
    outcomes: List[str]
    outcomePrices: List[str]
    clobTokenIds: List[str]
    volume: str
    liquidity: str

@dataclass
class PriceData:
    """价格数据模型"""
    price: str
    min_size: str
    max_size: str

# ============================================
# Polymarket API 客户端
# ============================================

class PolymartketAPI:
    """Polymarket API 客户端"""
    
    GAMMA_API_BASE = "https://gamma-api.polymarket.com"
    CLOB_API_BASE = "https://clob.polymarket.com"
    DATA_API_BASE = "https://data-api.polymarket.com"
    
    def __init__(self, timeout: int = 10):
        """初始化客户端"""
        self.session = requests.Session()
        self.timeout = timeout
    
    def _get(self, url: str, params: Optional[Dict] = None) -> Dict:
        """发起 GET 请求"""
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"❌ 请求失败: {e}")
            return {}
    
    def get_active_events(self, limit: int = 10) -> List[Dict]:
        """获取活跃事件列表"""
        url = f"{self.GAMMA_API_BASE}/events"
        params = {
            "active": "true",
            "closed": "false",
            "limit": limit
        }
        return self._get(url, params)
    
    def get_market_by_slug(self, slug: str) -> Optional[Dict]:
        """根据slug获取市场详情"""
        url = f"{self.GAMMA_API_BASE}/markets"
        params = {"slug": slug}
        markets = self._get(url, params)
        
        if markets:
            market = markets[0]
            # 解析可能是 JSON 字符串的字段
            import json as json_lib
            for field in ['outcomes', 'outcomePrices', 'clobTokenIds']:
                if field in market and isinstance(market[field], str):
                    try:
                        market[field] = json_lib.loads(market[field])
                    except:
                        pass
            return market
        return None
    
    def get_market_by_id(self, market_id: str) -> Optional[Dict]:
        """根据ID获取市场详情"""
        url = f"{self.GAMMA_API_BASE}/markets/{market_id}"
        return self._get(url)
    
    def get_price(self, token_id: str, side: str = "buy") -> Optional[Dict]:
        """获取实时价格"""
        url = f"{self.CLOB_API_BASE}/price"
        params = {
            "token_id": token_id,
            "side": side
        }
        return self._get(url, params)
    
    def get_orderbook(self, token_id: str) -> Dict:
        """获取订单簿"""
        url = f"{self.CLOB_API_BASE}/book"
        params = {"token_id": token_id}
        return self._get(url, params)
    
    def get_sports_leagues(self) -> Dict:
        """获取所有体育联赛"""
        url = f"{self.GAMMA_API_BASE}/sports"
        return self._get(url)
    
    def get_events_by_tag(self, tag_id: int, limit: int = 10) -> List[Dict]:
        """按标签获取事件"""
        url = f"{self.GAMMA_API_BASE}/events"
        params = {
            "tag_id": tag_id,
            "active": "true",
            "closed": "false",
            "limit": limit
        }
        return self._get(url, params)
    
    def get_all_tags(self, limit: int = 100) -> List[Dict]:
        """获取所有可用标签"""
        url = f"{self.GAMMA_API_BASE}/tags"
        params = {"limit": limit}
        return self._get(url, params)
    
    def get_user_positions(self, user_address: str) -> List[Dict]:
        """获取用户头寸"""
        url = f"{self.DATA_API_BASE}/user/{user_address}/positions"
        return self._get(url)
    
    def get_user_trades(self, user_address: str, limit: int = 100) -> List[Dict]:
        """获取用户交易历史"""
        url = f"{self.DATA_API_BASE}/user/{user_address}/trades"
        params = {"limit": limit}
        return self._get(url, params)


# ============================================
# 演示函数
# ============================================

def print_section(title: str):
    """打印分隔符"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def demonstrate_api():
    """演示 API 使用"""
    
    client = PolymartketAPI()
    
    print("\n🚀 Polymarket API Python 样例演示")
    
    # ======== 示例 1: 获取活跃事件 ========
    print_section("1️⃣ 获取活跃事件列表")
    events = client.get_active_events(limit=5)
    
    if events:
        print(f"\n找到 {len(events)} 个活跃事件:\n")
        for i, event in enumerate(events[:3], 1):
            start_date = event.get('startDate', '')
            if start_date:
                start_time = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                start_str = start_time.strftime('%Y-%m-%d %H:%M:%S')
            else:
                start_str = 'N/A'
            
            print(f"{i}. {event['title']}")
            print(f"   ID: {event['id']}")
            print(f"   开始时间: {start_str}")
            print(f"   描述: {event.get('description', 'N/A')[:50]}...")
            print()
        
        # ======== 示例 2: 获取市场详情 ========
        print_section("2️⃣ 获取特定市场详情")
        first_event = events[0]
        
        # 从事件的 markets 数组中获取市场，选择活跃的市场
        markets = first_event.get('markets', [])
        active_market = None
        for m in markets:
            if m.get('active') and not m.get('closed'):
                active_market = m
                break
        
        # 如果没有活跃市场，就用第一个
        if not active_market and markets:
            active_market = markets[0]
        
        if active_market:
            market = active_market
            
            # 解析可能是 JSON 字符串的字段
            for field in ['outcomes', 'outcomePrices', 'clobTokenIds']:
                if field in market and isinstance(market[field], str):
                    try:
                        market[field] = json.loads(market[field])
                    except:
                        pass
            
            print(f"\n市场标题: {market.get('question', 'N/A')}")
            outcomes = market.get('outcomes', [])
            prices = market.get('outcomePrices', [])
            if isinstance(outcomes, str):
                outcomes = json.loads(outcomes)
            if isinstance(prices, str):
                prices = json.loads(prices)
            
            print(f"预期结果: {' vs '.join(outcomes) if outcomes else 'N/A'}")
            print(f"当前价格: {' / '.join(prices) if prices else 'N/A'}")
            print(f"交易量: {market.get('volume', 'N/A')}")
            print(f"交易状态: {'活跃' if market.get('active') else '已关闭'}")
            
            # ======== 示例 3: 获取价格信息 ========
            # 解析 clobTokenIds（可能是 JSON 字符串）
            clob_token_ids = market.get('clobTokenIds', [])
            if isinstance(clob_token_ids, str):
                try:
                    clob_token_ids = json.loads(clob_token_ids)
                except:
                    clob_token_ids = []
            
            if clob_token_ids and market.get('active'):
                print_section("3️⃣ 获取实时价格")
                token_id = clob_token_ids[0]
                
                buy_price = client.get_price(token_id, 'buy')
                sell_price = client.get_price(token_id, 'sell')
                
                if buy_price and sell_price:
                    print(f"\nToken ID: {token_id}")
                    print(f"买入价: {buy_price.get('price', 'N/A')}")
                    print(f"卖出价: {sell_price.get('price', 'N/A')}")
                    print(f"最大交易量: {buy_price.get('max_size', 'N/A')}")
                    
                    # ======== 示例 4: 获取订单簿 ========
                    print_section("4️⃣ 获取订单簿")
                    orderbook = client.get_orderbook(token_id)
                    
                    if orderbook and 'bids' in orderbook:
                        print(f"\n最佳买单 (Bid):")
                        for i, bid in enumerate(orderbook['bids'][:3]):
                            print(f"  {i+1}. 价格: {bid['price']:>8} | 数量: {bid['size']:>12}")
                        
                        print(f"\n最佳卖单 (Ask):")
                        for i, ask in enumerate(orderbook['asks'][:3]):
                            print(f"  {i+1}. 价格: {ask['price']:>8} | 数量: {ask['size']:>12}")
                        
                        print(f"\n中间价格: {orderbook.get('mid', 'N/A')}")
                        print(f"价差: {orderbook.get('spread', 'N/A')}")
                else:
                    print_section("3️⃣ 获取实时价格")
                    print("\n⚠️  无法获取此市场的价格数据")
            else:
                if not clob_token_ids:
                    print_section("3️⃣ 获取实时价格")
                    print("\n⚠️  此市场没有有效的 Token ID")
                else:
                    print_section("3️⃣ 获取实时价格")
                    print("\n⚠️  此市场已关闭，无法获取实时价格")
    
    # ======== 示例 5: 体育赛事 ========
    print_section("5️⃣ 体育赛事联赛")
    sports = client.get_sports_leagues()
    
    if sports:
        print(f"\n获取体育联赛数据成功")
        # 体育赛事可能是列表或字典
        if isinstance(sports, list):
            print(f"找到 {len(sports)} 个体育赛事")
        elif isinstance(sports, dict):
            print(f"找到 {len(sports)} 个体育赛事")
        else:
            print(f"体育赛事数据: {str(sports)[:100]}")
    
    # ======== 示例 6: 按标签查询 ========
    print_section("6️⃣ 按标签查询事件 (政治)")
    political_events = client.get_events_by_tag(tag_id=2, limit=3)
    
    if political_events:
        print(f"\n找到 {len(political_events)} 个政治相关事件:\n")
        for i, event in enumerate(political_events, 1):
            print(f"{i}. {event['title']}")
    
    # ======== 示例 7: 获取所有标签 ========
    print_section("7️⃣ 可用标签列表")
    tags = client.get_all_tags(limit=20)
    
    if tags:
        print(f"\n标签列表 (前10个):\n")
        for tag in tags[:10]:
            print(f"  • {tag.get('label', 'N/A')} (ID: {tag.get('id')})")
    
    print_section("✅ 演示完成!")

# ============================================
# 实用工具函数
# ============================================

def find_market_by_keyword(keyword: str) -> Optional[Dict]:
    """根据关键词查找市场"""
    client = PolymartketAPI()
    events = client.get_active_events(limit=50)
    
    for event in events:
        if keyword.lower() in event['title'].lower():
            market = client.get_market_by_slug(event['slug'])
            if market:
                return market
    return None

def get_market_summary(slug: str) -> Optional[str]:
    """获取市场摘要"""
    client = PolymartketAPI()
    market = client.get_market_by_slug(slug)
    
    if not market:
        return None
    
    outcomes = market['outcomes']
    prices = market['outcomePrices']
    
    summary = f"""
    市场: {market['title']}
    预期: {' vs '.join(outcomes)}
    价格: {' vs '.join(prices)}
    ID: {market['id']}
    """
    return summary

if __name__ == "__main__":
    demonstrate_api()
    
    # 示例: 查找特定市场
    # market = find_market_by_keyword("Bitcoin")
    # if market:
    #     print(market)
