import streamlit as st
import yfinance as yf
import feedparser
import requests
import time
from urllib.parse import quote
import google.generativeai as genai

# === 页面设置 ===
st.set_page_config(page_title="美股全景AI雷达", page_icon="📡", layout="wide")
st.title("📡 美股全景AI雷达")
st.caption("Powered by Google Gemini 2.5 & Yahoo Finance | 全球宏观/科技/周期/避险")

# === 侧边栏：配置 ===
with st.sidebar:
    st.header("⚙️ 控制台")
    api_key = st.text_input("Google API Key", type="password", help="需要 Gemini API 权限")
    st.info("提示：由于监控标的增加到40+个，完整扫描可能需要 1-2 分钟，请耐心等待。")

# === 核心逻辑：资产分组清单 ===
WATCHLIST_GROUPS = {
    "🚀 市场总览": {
        "^GSPC":   ["标普500", "S&P 500 market analysis"],
        "^IXIC":   ["纳斯达克", "Nasdaq Composite analysis"],
        "^RUT":    ["罗素2000 (实体经济)", "Russell 2000 small cap stocks"],
        "^VIX":    ["VIX恐慌指数", "CBOE VIX volatility index"],
    },
    "👑 科技七巨头": {
        "NVDA":    ["英伟达", "Nvidia stock news"],
        "MSFT":    ["微软", "Microsoft stock AI"],
        "AAPL":    ["苹果", "Apple Inc stock news"],
        "GOOGL":   ["谷歌", "Alphabet Google stock"],
        "AMZN":    ["亚马逊", "Amazon stock news"],
        "META":    ["Meta", "Meta Platforms news"],
        "TSLA":    ["特斯拉", "Tesla stock news"],
    },
    "⚙️ 硬核半导体": {
        "TSM":     ["台积电", "TSMC stock news"],
        "ASML":    ["ASML", "ASML stock lithography"],
        "AVGO":    ["博通", "Broadcom stock news"],
        "AMD":     ["AMD", "AMD stock news"],
        "SMH":     ["半导体ETF", "VanEck Vectors Semiconductor ETF"],
    },
    "💰 宏观流动性": {
        "^TNX":    ["10年期美债", "US 10 year treasury yield"],
        "DX-Y.NYB": ["美元指数", "US Dollar index"],
        "JPY=X":   ["美元兑日元", "USD JPY exchange rate"],
        "TLT":     ["20年+美债", "iShares 20+ Year Treasury Bond ETF"],
    },
    "🚨 信用与避险": {
        "HYG":     ["高收益债(垃圾债)", "High Yield Corporate Bond ETF default risk"],
        "GLD":     ["黄金", "Gold price investing"],
        "BTC-USD": ["比特币", "Bitcoin crypto market sentiment"],
    },
    "🏭 周期与通胀": {
        "CL=F":    ["原油", "Crude oil price energy"],
        "XLE":     ["能源板块", "US Energy Sector ETF"],
        "XLF":     ["金融板块", "US Financials Sector ETF"],
        "CAT":     ["卡特彼勒", "Caterpillar stock economy"],
    },
    "🛡️ 防御板块": {
        "XLV":     ["医疗健康", "Health Care Sector ETF"],
        "XLP":     ["必需消费", "Consumer Staples Sector ETF"],
        "WMT":     ["沃尔玛", "Walmart stock consumer"],
    },
    "🇨🇳 中国与新兴": {
        "^HSI":    ["恒生指数", "Hang Seng Index Hong Kong"],
        "FXI":     ["中国大盘股", "China large cap ETF investing"],
        "KWEB":    ["中国互联网", "China internet ETF tech"],
    }
}

SPECIAL_TOPICS = [
    "US Federal Reserve Powell policy",           # 美联储
    "Bank of Japan Governor Ueda policy",         # 日本央行
    "Geopolitical tension Middle East Russia",    # 地缘政治
    "US China trade war tariffs",                 # 贸易战
    "US inflation CPI PCE data",                  # 通胀
    "US recession soft landing probability",      # 衰退预测
    "Artificial Intelligence AI market impact",   # AI 影响
    "trump",                                      # 特朗普

]

def get_news(query):
    encoded = quote(query)
    url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, timeout=6, headers=headers)
        feed = feedparser.parse(resp.content)
        return [{"title": e.title, "link": e.link} for e in feed.entries[:3]] # 限制每条3个新闻，避免过长
    except: return []

def run_analysis():
    if not api_key:
        st.error("❌ 请先在左侧输入 API Key")
        return

    genai.configure(api_key=api_key.strip(), transport='rest')
    model = genai.GenerativeModel('gemini-2.5-pro')
    
    # 界面初始化
    status_text = st.empty()
    progress_bar = st.progress(0)
    
    # 创建标签页
    tab_names = list(WATCHLIST_GROUPS.keys()) + ["🔍 宏观话题"]
    tabs = st.tabs(tab_names)
    
    market_data = ""
    all_news_titles = [] 
    
    # 计算总步数
    total_assets = sum(len(v) for v in WATCHLIST_GROUPS.values())
    total_topics = len(SPECIAL_TOPICS)
    total_steps = total_assets + total_topics
    current_step = 0

    # === 1. 分组抓取资产数据 ===
    # 遍历每一个分组（对应一个Tab）
    for i, (group_name, items) in enumerate(WATCHLIST_GROUPS.items()):
        with tabs[i]: # 切换到对应标签页显示
            cols = st.columns(2) # 每行显示两个卡片，更紧凑
            col_idx = 0
            
            market_data += f"\n=== 【{group_name}】板块数据 ===\n"
            
            for ticker, info in items.items():
                status_text.text(f"📡 正在扫描: {group_name} - {info[0]}...")
                
                try:
                    # 获取价格
                    stock = yf.Ticker(ticker)
                    time.sleep(0.1) # 防封控
                    hist = stock.history(period="2d")
                    
                    price_str = "N/A"
                    change_str = ""
                    if len(hist) > 0:
                        last_price = hist['Close'].iloc[-1]
                        price_str = f"{last_price:.2f}"
                        # 计算涨跌幅
                        if len(hist) > 1:
                            prev_price = hist['Close'].iloc[-2]
                            change = ((last_price - prev_price) / prev_price) * 100
                            emoji = "🔴" if change < 0 else "🟢"
                            change_str = f"({emoji} {change:+.2f}%)"

                    # 获取新闻
                    news = get_news(info[1])
                    
                    # 记录数据给 AI
                    market_data += f"[{info[0]}] 价格:{price_str} {change_str}\n"
                    for n in news:
                        market_data += f"   - News: {n['title']}\n"
                        all_news_titles.append(n['title'])
                    
                    # 界面展示 (使用 st.expander)
                    with cols[col_idx % 2].expander(f"{info[0]} {price_str} {change_str}", expanded=False):
                        for n in news:
                            st.write(f"- [{n['title']}]({n['link']})")
                    
                    col_idx += 1

                except Exception as e:
                    # st.warning(f"无法获取 {info[0]}: {e}")
                    pass
                
                current_step += 1
                progress_bar.progress(current_step / total_steps)

    # === 2. 抓取话题 ===
    with tabs[-1]: # 最后一个标签页
        status_text.text(f"📡 正在追踪宏观话题...")
        st.caption("基于 Google News 的实时话题追踪")
        
        market_data += f"\n=== 【宏观话题追踪】 ===\n"
        
        for topic in SPECIAL_TOPICS:
            news = get_news(topic)
            if news:
                market_data += f"Topic: {topic}\n"
                with st.expander(f"📌 {topic}", expanded=True):
                    for n in news:
                        st.write(f"- [{n['title']}]({n['link']})")
                        market_data += f"   - {n['title']}\n"
                        all_news_titles.append(n['title'])
            
            current_step += 1
            progress_bar.progress(current_step / total_steps)

    status_text.text("🤖 AI 正在基于全景数据撰写深度内参 (约需 10-20 秒)...")
    
    # === 3. AI 分析 ===
    unique_news_titles = "\n".join(list(set(all_news_titles)))
    
    prompt = f"""
    角色：华尔街顶级宏观对冲基金的首席策略师 (CIO)。
    任务：基于以下【全景市场数据】撰写一份《全球跨资产实战内参》。
    
    你需要综合分析：科技股动能、宏观流动性(美债/美元/日元)、信用风险(高收益债)、以及地缘与中国资产的影响。
    
    --- 📰 原始新闻池 (供概括) ---
    {unique_news_titles}
    
    --- 📊 全景市场数据 (含价格变动) ---
    {market_data}
    
    --- 写作要求 ---
    1. **结构化输出**：请严格按照下方目录结构输出。
    2. **去链接化**：不要包含任何 URL。
    3. **中文写作**：专业、犀利、简练。
    
    --- 报告目录结构 ---
    # 📰 本日焦点 (Market Focus)
    > (从新闻池中提炼5条最重要新闻，一句话概括，并在末尾标注其对市场是[利多]还是[利空])

    # 1. 🌡️ 市场温度计 (Market Breadth)
    > (分析标普vs罗素、恐慌指数VIX、以及比特币。判断当前是"全面牛市"、"只有科技股涨的虚假繁荣"还是"避险模式"？)

    # 2. 🇯🇵 宏观与流动性 (Liquidity Watch)
    > (重点分析美债收益率、日元汇率、美元指数。流动性是在收紧还是释放？)

    # 3. 🤖 科技与半导体 (Tech & AI)
    > (点评 NVDA/MSFT/TSM 等核心票走势。AI 泡沫不仅是信仰，还要看价格动能。)

    # 4. ⚠️ 风险雷达 (Risk Monitor)
    > (观察高收益债 HYG、黄金 GLD 和原油。是否有经济衰退或通胀反弹的迹象？)

    # 5. 📝 交易员策略 (Actionable Strategy)
    > (给出具体的操作建议：做多哪个板块？对冲什么风险？当前仓位建议是激进还是防御？)
    """
    
    try:
        response = model.generate_content(prompt)
        status_text.text("✅ 分析完成！")
        st.success("深度分析报告已生成")
        st.markdown("---")
        st.markdown(response.text)
    except Exception as e:
        st.error(f"AI 生成失败: {e}")

# === 启动按钮 ===
if st.button("🚀 启动全景雷达 (Full Scan)", type="primary"):
    run_analysis()