import streamlit as st
import yfinance as yf
import feedparser
import requests
import time
from urllib.parse import quote
import google.generativeai as genai

# === 页面设置 ===
st.set_page_config(page_title="美股AI内参", page_icon="📈")
st.title("📈 华尔街宏观对冲雷达")
st.caption("Powered by Google Gemini 2.5 & Yahoo Finance")

# === 侧边栏：API Key 配置 ===
# 这样你就不用把 Key 写死在代码里，防止泄露
api_key = st.sidebar.text_input("输入 Google API Key", type="password")

# === 核心逻辑 ===
WATCHLIST = {
    "JPY=X": ["美元兑日元", "USD JPY exchange rate"], 
    "^N225": ["日经225", "Nikkei 225 market"],
    "^TNX":  ["10年期美债", "US 10 year treasury yield"], 
    "DX-Y.NYB": ["美元指数", "US Dollar index"],
    "GC=F":  ["黄金", "Gold price investing"], 
    "CL=F":  ["原油", "Crude oil price energy"], 
    "NVDA":  ["英伟达", "Nvidia stock news"],
    "AAPL":  ["苹果", "Apple Inc stock news"],
    "TSLA":  ["特斯拉", "Tesla stock news"],
    "MSFT":  ["微软", "Microsoft stock AI"],
    "TSM":   ["台积电", "TSMC stock news"],
}

SPECIAL_TOPICS = [
    "Bank of Japan Governor Ueda policy", 
    "US Federal Reserve Powell",           
    "Geopolitical tension Middle East Russia China", 
]

def get_news(query):
    encoded = quote(query)
    url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
    try:
        resp = requests.get(url, timeout=5)
        feed = feedparser.parse(resp.content)
        return [{"title": e.title, "link": e.link} for e in feed.entries[:2]]
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
    total_steps = len(WATCHLIST) + len(SPECIAL_TOPICS)
    current_step = 0

    # 1. 抓取资产数据
    for ticker, info in WATCHLIST.items():
        status_text.text(f"正在扫描: {info[0]}...")
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="2d")
            price = f"{hist['Close'].iloc[-1]:.2f}" if len(hist) > 0 else "N/A"
            
            news = get_news(info[1])
            market_data += f"\n【{info[0]}】 价格:{price}\n"
            for n in news:
                market_data += f"   - {n['title']}\n"
            
            # 在界面上展示实时数据卡片
            with st.expander(f"{info[0]} ({price})", expanded=False):
                for n in news:
                    st.write(f"- [{n['title']}]({n['link']})")

        except Exception as e:
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
        current_step += 1
        progress_bar.progress(current_step / total_steps)

    status_text.text("🤖 AI 正在撰写深度报告...")
    
    # 3. AI 分析
    prompt = f"""
    角色：全球宏观对冲基金策略师。
    任务：基于以下数据写一份【美股实战内参】。
    数据：{market_data}
    要求：全中文，去链接化，逻辑严密。
    板块：🇯🇵日本流动性 / 🌍地缘避险 / 🇺🇸宏观压力 / 👑科技七巨头 / 📝交易策略(含仓位建议)。
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