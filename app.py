import streamlit as st
import yfinance as yf
import feedparser
import requests
import time
from urllib.parse import quote
import google.generativeai as genai

# === 页面设置 ===
st.set_page_config(page_title="美股AI分析师", page_icon="📈")
st.title("📈 美股AI分析师")
st.caption("Powered by Google Gemini 2.5 & Yahoo Finance")

# === 侧边栏：API Key 配置 ===
# 这样你就不用把 Key 写死在代码里，防止泄露
api_key = st.sidebar.text_input("输入 Google API Key", type="password")

# === 核心逻辑 ===
WATCHLIST = {
    # --- 🇯🇵 日本与汇率 (流动性源头) ---
    "JPY=X": ["美元兑日元", "USD JPY exchange rate carry trade"], 
    "^N225": ["日经225", "Nikkei 225 stock market"],
    
    # --- 🇺🇸 宏观与避险 (地缘/通胀) ---
    "^TNX":  ["10年期美债", "US 10 year treasury yield"], 
    "DX-Y.NYB": ["美元指数", "US Dollar index"],
    "^VXN":  ["纳指恐慌指数", "Nasdaq Volatility Index"],
    "GC=F":  ["黄金 (地缘避险)", "Gold price investing"], 
    "CL=F":  ["原油 (通胀/中东)", "Crude oil price energy"], 

    # --- 🤖 科技七巨头 (Mag 7) ---
    "NVDA":  ["英伟达", "Nvidia stock news"],
    "AAPL":  ["苹果", "Apple Inc stock news"],
    "MSFT":  ["微软", "Microsoft stock AI"],
    "TSLA":  ["特斯拉", "Tesla stock news"],
    "AMZN":  ["亚马逊", "Amazon stock news"],
    "META":  ["Meta", "Meta Platforms news"],
    "GOOGL": ["谷歌", "Alphabet Google stock"],
    
    # --- ⚙️ 关键半导体 ---
    "TSM":   ["台积电", "TSMC stock news"],
}

SPECIAL_TOPICS = [
    "Bank of Japan Governor Ueda policy",  # 日本央行
    "US Federal Reserve Powell",           # 美联储
    "Geopolitical tension Middle East Russia China", # 地缘政治
    "US China trade war tariffs",          # 贸易战/关税
]

def get_news(query):
    encoded = quote(query)
    url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
    try:
        # 使用更合理的 User-Agent 避免某些网站的阻止
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, timeout=7, headers=headers)
        feed = feedparser.parse(resp.content)
        # 增加返回数量，以获得更全面的概括数据
        return [{"title": e.title, "link": e.link} for e in feed.entries[:5]]
    except: return []

def run_analysis():
    if not api_key:
        st.error("请先在左侧输入 API Key")
        return

    genai.configure(api_key=api_key.strip(), transport='rest')
    model = genai.GenerativeModel('gemini-2.5-pro')
    
    status_text = st.empty()
    progress_bar = st.progress(0)
    
    market_data = ""
    # 新增一个列表用于收集所有新闻，用于后续的概括
    all_news_titles = [] 
    
    total_steps = len(WATCHLIST) + len(SPECIAL_TOPICS)
    current_step = 0

    # 1. 抓取资产数据
    for ticker, info in WATCHLIST.items():
        status_text.text(f"正在扫描: {info[0]}...")
        try:
            stock = yf.Ticker(ticker)
            # 增加一些等待时间，防止 API 频率限制
            time.sleep(0.1) 
            hist = stock.history(period="2d")
            price = f"{hist['Close'].iloc[-1]:.2f}" if len(hist) > 0 else "N/A"
            
            news = get_news(info[1])
            market_data += f"\n【{info[0]}】 价格:{price}\n"
            for n in news:
                market_data += f"   - {n['title']}\n"
                # 收集新闻标题
                all_news_titles.append(n['title'])
            
            # 在界面上展示实时数据卡片
            with st.expander(f"{info[0]} ({price})", expanded=False):
                for n in news:
                    st.write(f"- [{n['title']}]({n['link']})")

        except Exception as e:
            # st.error(f"Error fetching data for {info[0]}: {e}") # Debugging
            pass
        
        current_step += 1
        progress_bar.progress(current_step / total_steps)

    # 2. 抓取话题
    for topic in SPECIAL_TOPICS:
        status_text.text(f"正在追踪: {topic}...")
        news = get_news(topic)
        if news:
            market_data += f"\n【话题: {topic}】\n"
            for n in news:
                market_data += f"   - {n['title']}\n"
                # 收集新闻标题
                all_news_titles.append(n['title'])

        current_step += 1
        progress_bar.progress(current_step / total_steps)

    status_text.text("🤖 AI 正在撰写深度报告...")
    
    # 3. AI 分析 - 重点修改 Prompt
    
    # 将收集到的所有新闻标题去重并整理成一个字符串，供模型概括使用
    unique_news_titles = "\n".join(list(set(all_news_titles)))
    
    prompt = f"""
    角色：全球宏观对冲基金策略师。
    任务：基于以下【市场数据】和【原始新闻标题】写一份【美股实战内参】。
    
    --- 原始新闻标题（需先概括为“本日焦点新闻速览”板块）---
    {unique_news_titles}
    
    --- 市场数据（用于后续分析）---
    {market_data}
    
    要求：
    1. **全中文**，逻辑严密，语气专业。
    2. **去链接化**。
    3. **必须先概括**所有【原始新闻标题】为一个单独的板块：**📰 本日焦点新闻速览**。这个板块应列出 5-8 条重要新闻，并对每条新闻进行**一句简要的中文概括**。
    
    最终板块结构：
    1. 📰 本日焦点新闻速览 (需对原始新闻标题进行概括，中文)
    2. 🇯🇵 日本流动性
    3. 🌍 地缘避险
    4. 🇺🇸 宏观压力
    5. 👑 科技七巨头
    6. 📝 交易策略(含仓位建议)
    """
    
    try:
        response = model.generate_content(prompt)
        st.success("分析完成！")
        st.markdown("---")
        st.markdown(response.text)
    except Exception as e:
        st.error(f"AI 生成失败: {e}")

# === 按钮 ===
if st.button("🚀 启动全景雷达", type="primary"):
    run_analysis()