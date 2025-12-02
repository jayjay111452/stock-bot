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
    
    # 1. 获取用户输入的 Key
    user_api_key = st.text_input("Google API Key", type="password", help="即刻申请: https://aistudio.google.com/")
    
    # 2. 尝试从 Secrets 获取公共演示 Key
    # 注意：这里的名字 GEMINI_DEMO_KEY 必须和你 Streamlit 后台 Secrets 里设置的一模一样
    system_api_key = st.secrets.get("GEMINI_DEMO_KEY", None)
    
    # 3. 决定最终使用的 Key
    if user_api_key:
        final_api_key = user_api_key
        key_type = "user"
    elif system_api_key:
        final_api_key = system_api_key
        key_type = "system"
    else:
        final_api_key = None
        key_type = "none"

    # 4. 显示当前状态
    if key_type == "user":
        st.success("✅ 使用您的个人 Key (速度快/隐私)")
    elif key_type == "system":
        st.warning("⚠️ 试用模式：使用公共 Key (可能会限流)")
    else:
        st.error("❌ 未检测到 Key，请先配置")

    st.info("提示：由于监控标的增加到40+个，完整扫描可能需要 1-2 分钟，请耐心等待。")

# === 核心逻辑：资产分组清单 ===
WATCHLIST_GROUPS = {
    "🚀 市场总览": {
        "^GSPC":   ["标普500 (美股基准)", "S&P 500 market analysis"],
        "^IXIC":   ["纳斯达克 (科技风向)", "Nasdaq Composite analysis"],
        "^DJI":    ["道琼斯 (传统蓝筹)", "Dow Jones Industrial Average news"],
        "^RUT":    ["罗素2000 (美国实体经济)", "Russell 2000 small cap stocks"],
        "^VIX":    ["VIX 恐慌指数", "CBOE VIX volatility index market fear"],
        "^VXN":    ["纳指恐慌指数", "Nasdaq Volatility Index"],
    },
    "👑 科技七巨头": {
        "NVDA":    ["英伟达 (AI算力)", "Nvidia stock news"],
        "MSFT":    ["微软 (AI应用)", "Microsoft stock AI news"],
        "AAPL":    ["苹果 (消费电子)", "Apple Inc stock news"],
        "GOOGL":   ["谷歌 (搜索/AI)", "Alphabet Google stock news"],
        "AMZN":    ["亚马逊 (云/电商)", "Amazon stock news"],
        "META":    ["Meta (社交/广告)", "Meta Platforms stock news"],
        "TSLA":    ["特斯拉 (电车/机器人)", "Tesla stock news"],
    },
    "⚙️ 硬核半导体": {
        "TSM":     ["台积电 (代工霸主)", "TSMC stock news"],
        "ASML":    ["ASML (光刻机)", "ASML stock lithography"],
        "AVGO":    ["博通 (网络芯片)", "Broadcom stock news"],
        "AMD":     ["AMD (算力老二)", "AMD stock news"],
        "MU":      ["美光 (存储芯片)", "Micron Technology stock news"],
        "SMH":     ["半导体ETF", "VanEck Vectors Semiconductor ETF"],
    },
    "💰 宏观流动性": {
        "^TNX":    ["10年期美债", "US 10 year treasury yield"],
        "DX-Y.NYB": ["美元指数", "US Dollar index"],
        "JPY=X":   ["美元兑日元", "USD JPY exchange rate"],
        "TLT":     ["20年+美债", "iShares 20+ Year Treasury Bond ETF"],
        "BTC-USD": ["比特币", "Bitcoin crypto market sentiment"],
    },
    "🚨 信用与避险": {
        "HYG":     ["高收益债ETF (垃圾债)", "High Yield Corporate Bond ETF default risk"], # 关键：跌则衰退风险增
        "LQD":     ["投资级债ETF", "Investment Grade Corporate Bond ETF"],
        "GLD":     ["黄金ETF (终极避险)", "Gold price investing safe haven"],
        "SLV":     ["白银ETF", "Silver price investing"],
    },
    "🏭 周期与通胀": {
        "CL=F":    ["原油期货 (通胀源头)", "Crude oil price energy news"],
        "XLE":     ["能源板块ETF", "US Energy Sector ETF"],
        "XLF":     ["金融板块 (银行)", "US Financials Sector ETF bank earnings"],
        "XLI":     ["工业板块", "US Industrials Sector ETF economy"],
        "CAT":     ["卡特彼勒 (工业风向)", "Caterpillar stock economy"],
        "JETS":    ["航空ETF (地缘/消费)", "U.S. Global Jets ETF travel demand"],
    },
    "🛡️ 防御板块": {
        "XLV":     ["医疗健康ETF", "Health Care Sector ETF"],
        "XLP":     ["必需消费ETF", "Consumer Staples Sector ETF"],
        "WMT":     ["沃尔玛 (零售巨头)", "Walmart stock consumer spending"],
        "KO":      ["可口可乐", "Coca-Cola stock defensive"],
        "UNH":     ["联合健康", "UnitedHealth Group stock"],
    },
    "🇨🇳 中国与新兴": {
        "^HSI":    ["恒生指数", "Hang Seng Index Hong Kong"],
        "FXI":     ["中国大盘股ETF", "China large cap ETF investing"],
        "KWEB":    ["中国互联网ETF", "China internet ETF tech regulation"],
        "EEM":     ["新兴市场ETF", "Emerging Markets ETF growth"],
    }
}

SPECIAL_TOPICS = [
    # --- 🏦 央行与政策 (市场最关注) ---
    "US Federal Reserve Powell interest rate decision", # 美联储/鲍威尔
    "Bank of Japan Governor Ueda monetary policy",      # 日本央行/植田和男
    "US inflation CPI PCE data report",                 # 通胀数据
    "US Non-farm payrolls unemployment rate",           # 就业/非农

    # --- 📊 关键经济指引 (新增 PMI) ---
    "US ISM Manufacturing PMI report",                  # 制造业 PMI (关注是否萎缩)
    "US ISM Services PMI report economy",               # 服务业 PMI (美国经济的核心支柱)
    
    # --- ⚔️ 地缘与新政 (突发风险) ---
    "Geopolitical tension Middle East Israel Iran",     # 中东局势
    "Russia Ukraine war latest news",                   # 俄乌局势
    "US China trade war tariffs restrictions",          # 中美贸易/关税

    # --- 📉 经济前景 ---
    "US economic recession soft landing probability",   # 衰退vs软着陆
    "Global supply chain disruption shipping",          # 供应链/红海危机
    "US commercial real estate crisis office",          # 商业地产危机
    
    # --- 🤖 产业变革 ---
    "Artificial Intelligence regulation safety",        # AI 监管
    "Global energy transition electric vehicles demand" # 能源转型/电车需求
]

def get_news(query):
    # 默认针对普通新闻：只看最近 3 天，确保"本日焦点"是新鲜热辣的
    time_window = "when:3d"
    
    # 针对 PMI 数据：因为是月度数据，必须放宽到 30 天，否则容易抓空
    if "PMI" in query.upper():
        time_window = "when:30d"
    
    # 针对大选或长期政策：可以适当放宽到 7 天 (可选)
    elif "POLICY" in query.upper() or "TRUMP" in query.upper():
        time_window = "when:7d"

    search_query = f"{query} {time_window}"
    encoded = quote(search_query)
    
    url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, timeout=6, headers=headers)
        feed = feedparser.parse(resp.content)
        return [{"title": e.title, "link": e.link} for e in feed.entries[:3]]
    except: return []

def run_analysis():
    # 检查全局变量 final_api_key 是否存在且有效
    if 'final_api_key' not in globals() or not final_api_key:
        st.error("❌ 请先在左侧配置 API Key")
        return

    # 使用选定的 Key 进行配置
    genai.configure(api_key=final_api_key.strip(), transport='rest')
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
    
    你需要综合分析：科技股动能、宏观流动性(美债/美元/日元/比特币)、信用风险(高收益债)、地缘与中国资产以及宏观话题（央行政策、地缘政治与大选、经济前景、产业变革等）的影响。
    
    --- 📰 原始新闻池 (供概括) ---
    {unique_news_titles}
    
    --- 📊 全景市场数据 (含价格变动) ---
    {market_data}
    
    --- 写作要求 ---
    1. **结构化输出**：请严格按照下方目录结构输出。
    2. **去链接化**：不要包含任何 URL。
    3. **中文写作**：逻辑严密、语气专业。
    
    --- 报告目录结构 ---
    # 📰 本日焦点 (Market Focus)
    > (从新闻池中提炼5条最重要新闻，简要概括，并在末尾标注其对市场是[利多]还是[利空])

    # 1. 🌡️ 市场温度计 (Market Breadth)
    > (分析标普vs罗素、道琼斯指数、恐慌指数VIX、以及比特币。判断当前是"全面牛市"、"只有科技股涨的虚假繁荣"还是"避险模式"？)

    # 2. 🇯🇵 宏观与流动性 (Liquidity Watch)
    > (重点分析美债收益率、日元汇率、美元指数、比特币。流动性是在收紧还是释放？)

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