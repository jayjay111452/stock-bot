import streamlit as st
import yfinance as yf
import feedparser
import requests
import time
from urllib.parse import quote
import google.generativeai as genai
from datetime import datetime, timedelta

# === 页面设置 ===
st.set_page_config(page_title="美股全景AI雷达", page_icon="📡", layout="wide")
st.title("📡 美股全景AI雷达")
st.caption("Powered by Google Gemini 3.0 Pro & Yahoo Finance | 全球宏观/科技/周期/避险")

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

    st.info("提示：AI模型变更为Gemini3.0 Pro，请使用自由API key。")

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
    # --- 🏦 央行与流动性 (已优化：双向追踪 QE 和 QT) ---
    "Federal Reserve balance sheet QE QT expansion contraction", # 美联储资产负债表 (扩表/缩表)
    "Fed reverse repo facility RRP liquidity",          # 逆回购 (流动性蓄水池)
    "US Federal Reserve interest rate decision",        # 美联储利率决议 (通用版)
    "Fed Chair speech testimony",         # 【新增】美联储主席讲话/听证会 (这是市场波动之源)
    "Bank of Japan Governor Ueda monetary policy",      # 日本央行 (全球流动性源头)

    # --- 📊 关键经济指引 (新增 PMI) ---
    "US GDP growth rate",                        # 美国GDP增长率 (核心经济指标)
    "US ISM Manufacturing PMI report",                  # 制造业 PMI (关注是否萎缩)
    "US ISM Services PMI report economy",               # 服务业 PMI (美国经济的核心支柱)
    "US inflation CPI PCE data report",                 # 一般通胀
    "US Core PCE Price Index inflation report",         # 【新增】核心PCE (剔除能源食品)
    "US Non-farm payrolls unemployment rate",           # 就业/非农
    "US ADP National Employment Report private payrolls", # 【新增】ADP 小非农 (非农前瞻)
    "US unemployment rate jobless claims data",         # 【新增】失业率 + 初请失业金 (高频与低频结合)
    "US Initial and Continuing Jobless Claims report", # 强制覆盖：初请(裁员力度) + 续请(再就业难度)
    
    # --- 🏛️ 政治与大选 (新增川普/新政) ---
    "Donald Trump economic policy tariffs trade",       # 【新增】川普经济学 (关税/贸易/制造业)
    "US government debt ceiling budget deficit",        # 美国债务/赤字 (长期隐患)

    # --- ⚔️ 地缘与新政 (突发风险) ---
    "Geopolitical tension Middle East Israel Iran",     # 中东局势
    "Russia Ukraine war latest news",                   # 俄乌局势
    "US China trade war tariffs restrictions",          # 中美贸易/关税

    # --- 📉 经济前景 ---
    "US economic recession soft landing probability",   # 衰退vs软着陆
    "Global supply chain disruption shipping",          # 供应链/红海危机
    "US commercial real estate crisis office",          # 商业地产危机
    "US economic recession soft landing probability",   # 衰退概率
    
    # --- 🤖 产业变革 ---
    "Artificial Intelligence regulation safety",        # AI 监管
    "Global energy transition electric vehicles demand" # 能源转型/电车需求
]

from fredapi import Fred
import pandas as pd

# 初始化 FRED (尝试从 secrets 获取 key)
# 如果用户没有配置 FRED Key，这个功能会静默失败，不影响主程序
try:
    fred_key = st.secrets["general"]["FRED_API_KEY"]
    fred = Fred(api_key=fred_key)
    HAS_FRED = True
except:
    HAS_FRED = False

from datetime import datetime, timedelta # <--- 必须导入这个库

def get_macro_hard_data():
    """
    从 FRED 获取精准的宏观经济硬数据 (CPI, PCE, 失业率, 非农, 失业金)
    """
    if not HAS_FRED:
        return "⚠️ 未配置 FRED API Key，无法获取精准宏观数据。请继续依赖新闻。"

    data_summary = ""
    
    # === 1. 定义数据 ID (新增 Initial & Continued Claims) ===
    indicators = {
        "Real GDP Growth (实际GDP年化季率)": "A191RL1Q225SBEA", # 【新增】关注 QoQ Annualized
        "CPI (消费者物价指数)": "CPIAUCSL",
        "PCE (名义PCE物价指数)": "PCEPI",          # Headline PCE
        "Core PCE (核心PCE - 联储锚点)": "PCEPILFE", # 【新增】Core PCE (Ex Food & Energy)
        "Unemployment Rate (失业率)": "UNRATE",
        "Non-Farm Payrolls (非农就业)": "PAYEMS",
        "10Y Treasury Yield (10年美债)": "DGS10",
        # --- 新增高频就业数据 ---
        "Initial Jobless Claims (初请失业金)": "ICSA", # 周度，季节性调整
        "Continuing Claims (续请失业金)": "CCSA"     # 周度，季节性调整
    }

    data_summary += "--- 🔢 官方宏观硬数据 (FRED Verified) ---\n"
    
    # 计算2年前日期，确保只抓取最近数据
    start_date = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%d')

    try:
        for name, series_id in indicators.items():
            # 获取数据
            series = fred.get_series(series_id, observation_start=start_date).dropna()
            
            if series.empty:
                continue

            latest_date = series.index[-1].strftime('%Y-%m-%d')
            latest_val = series.iloc[-1]
            prev_val = series.iloc[-2]

            # === 2. 针对不同数据做格式化处理 ===
            if "GDP" in name:
                # 【新增】GDP 已经是百分比变化形式，直接显示
                # 逻辑：如果 GDP > 3% 为强劲，< 1% 为疲软
                change = latest_val - prev_val
                emoji = "🔥" if latest_val >= 3.0 else ("❄️" if latest_val < 1.0 else "⚖️")
                display_val = f"{latest_val:.2f}% {emoji} | Prev: {prev_val:.2f}%"

            elif "CPI" in name or "PCE" in name:
                if len(series) >= 13:
                    year_ago_val = series.iloc[-13]
                    yoy = ((latest_val - year_ago_val) / year_ago_val) * 100
                    display_val = f"{yoy:.2f}% (YoY) | Index: {latest_val:.2f}"
                else:
                    display_val = f"Index {latest_val:.1f}"
            
            elif "Non-Farm" in name:
                change = (latest_val - prev_val)
                display_val = f"Total {latest_val:,.0f}k | Change: {change:+,.0f}k"
            
            elif "Rate" in name or "Yield" in name:
                display_val = f"{latest_val:.2f}%"

            # --- 新增：失业金数据格式化 (显示为 k) ---
            elif "Claims" in name:
                # FRED 数据单位通常是“人”，除以1000转换为 k
                val_k = latest_val / 1000
                change_k = (latest_val - prev_val) / 1000
                # 格式：220k | Change: -2k (周环比)
                display_val = f"{val_k:.0f}k | WoW: {change_k:+.0f}k"

            else:
                display_val = f"{latest_val:.2f}"

            data_summary += f"* **{name}**: {display_val} [Date: {latest_date}]\n"
            
    except Exception as e:
        return f"⚠️ FRED 数据获取部分失败: {str(e)}"

    return data_summary

def get_news(query):
    # === 默认设置 ===
    # 针对个股 (NVDA, AAPL) 或 突发地缘新闻 (War, Crisis)，3天足够
    time_window = "when:3d"
    
    q_upper = query.upper()

    # === 1. 宏观硬数据关键词 ===
    macro_keywords = [
        "CPI", "PCE", "CORE PCE", "INFLATION", # 【更新】增加 CORE PCE
        "PAYROLL", "NON-FARM", "JOBS", "HIRES",
        "UNEMPLOYMENT", "CLAIMS", "JOBLESS",  # <--- 新增 CLAIMS, JOBLESS
        "PMI", "ISM",
        "INTEREST RATE", "FED DECISION",
        "GDP", "ECONOMIC GROWTH", "RECESSION" # 【新增】涵盖 GDP 和 增长/衰退 关键词
    ]

    # === 2. 政策/官员讲话/财政/贸易 (Policy & Narrative) -> 7天 ===
    # 逻辑：鲍威尔讲话、财政部发债、贸易战、监管，通常发酵周期为一周。
    policy_keywords = [
        # 央行工具与流动性
        "BALANCE SHEET", "QE", "QT", "REVERSE REPO", "RRP",
        # 核心人物与讲话 (新增 POWELL, CHAIR, SPEECH)
        "POWELL", "FED CHAIR", "SPEECH", "TESTIMONY", "YELLEN",
        # 财政与贸易 (新增 DEBT, DEFICIT, TARIFFS)
        "POLICY", "TRUMP", "BIDEN", "CONGRESS",
        "DEBT", "DEFICIT", "BUDGET",      # 债务/赤字
        "TARIFFS", "TRADE WAR",           # 贸易/关税
        "REGULATION", "ANTITRUST"         # 监管
    ]

# === 逻辑判断 (优化时间窗口) ===
    if any(k in q_upper for k in macro_keywords):
        # 1. 周度数据 (Claims): 7天
        if "CLAIMS" in q_upper or "JOBLESS" in q_upper:
             time_window = "when:7d"
        # 2. 月度重磅通胀数据 (CPI/PCE): 14天
        # PCE 数据发布后通常会有一周的深度发酵期，14天能确保覆盖“预测-发布-解读”全过程
        elif "PCE" in q_upper or "CPI" in q_upper or "GDP" in q_upper:
             time_window = "when:14d"
        # 3. 其他月度数据
        else:
             time_window = "when:14d"
             
    elif any(k in q_upper for k in policy_keywords):
        time_window = "when:7d"
    else:
        time_window = "when:3d"

    # 生成搜索链接
    search_query = f"{query} {time_window}"
    encoded = quote(search_query)
    
    url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, timeout=6, headers=headers)
        feed = feedparser.parse(resp.content)
        return [{"title": e.title, "link": e.link} for e in feed.entries[:3]]
    except: 
        return []

def get_cnn_fear_and_greed():
    """
    抓取 CNN Fear & Greed Index (恐慌贪婪指数)
    由于 CNN 没有官方公开 API，这里使用其图表数据端点。
    """
    url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
    # 必须伪装 User-Agent，否则会被拦截
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Referer": "https://www.cnn.com/"
    }
    
    try:
        r = requests.get(url, headers=headers, timeout=5)
        r.raise_for_status()
        data = r.json()
        
        # 解析数据
        score = data['fear_and_greed']['score']
        rating = data['fear_and_greed']['rating'] # 如 "Extreme Greed"
        
        # 格式化输出
        return f"{score:.0f} ({rating})"
    except Exception as e:
        return f"N/A (获取失败: {str(e)})"

def run_analysis():
    # 检查全局变量 final_api_key 是否存在且有效
    if 'final_api_key' not in globals() or not final_api_key:
        st.error("❌ 请先在左侧配置 API Key")
        return

    # 使用选定的 Key 进行配置
    genai.configure(api_key=final_api_key.strip(), transport='rest')
    model = genai.GenerativeModel('gemini-3-pro-preview')
    
    # 界面初始化
    status_text = st.empty()
    progress_bar = st.progress(0)
    
    # === 1. 获取 FRED 硬数据 ===
    # 注意：我们把这一步提前，确保数据在渲染标签页之前就已经准备好
    if HAS_FRED:
        status_text.text("🔢 正在连接美联储数据库 (FRED) 获取精准读数...")
        macro_hard_data = get_macro_hard_data()
    else:
        macro_hard_data = "⚠️ 未配置 FRED API Key，无法获取精准宏观数据。请在 secrets.toml 中配置。"

    # === 创建标签页 (新增：FRED 数据页) ===
    # 这里的顺序决定了界面上 Tab 的排列顺序
    tab_names = list(WATCHLIST_GROUPS.keys()) + ["🔍 宏观话题", "🔢 宏观数据 (FRED)"]
    tabs = st.tabs(tab_names)
    
    market_data = ""
    all_news_titles = [] 
    
# === 新增：获取恐慌指数 ===
    status_text.text("😨 正在探测市场情绪 (CNN Fear & Greed)...")
    fng_score = get_cnn_fear_and_greed()
    
    # 在第一个 Tab (市场总览) 顶部直接展示
    with tabs[0]:
        st.markdown(f"### 🌡️ 市场情绪仪表盘")
        st.metric("CNN 恐慌贪婪指数", fng_score, help="0=极度恐慌, 100=极度贪婪")
        st.divider()

    # 计算总步数
    total_assets = sum(len(v) for v in WATCHLIST_GROUPS.values())
    total_topics = len(SPECIAL_TOPICS)
    total_steps = total_assets + total_topics
    current_step = 0

    # === 2. 分组抓取资产数据 ===
    # 遍历每一个分组（对应前面的 Tab）
    for i, (group_name, items) in enumerate(WATCHLIST_GROUPS.items()):
        with tabs[i]: # 切换到对应标签页显示
            cols = st.columns(2)
            col_idx = 0
            
            market_data += f"\n=== 【{group_name}】板块数据 ===\n"
            
            for ticker, info in items.items():
                status_text.text(f"📡 正在扫描: {group_name} - {info[0]}...")
                
                try:
                    # 获取价格
                    stock = yf.Ticker(ticker)
                    time.sleep(0.1) 
                    hist = stock.history(period="2d")
                    
                    price_str = "N/A"
                    change_str = ""
                    if len(hist) > 0:
                        last_price = hist['Close'].iloc[-1]
                        price_str = f"{last_price:.2f}"
                        if len(hist) > 1:
                            prev_price = hist['Close'].iloc[-2]
                            change = ((last_price - prev_price) / prev_price) * 100
                            emoji = "🔴" if change < 0 else "🟢"
                            change_str = f"({emoji} {change:+.2f}%)"

                    # 获取新闻
                    news = get_news(info[1])
                    
                    market_data += f"[{info[0]}] 价格:{price_str} {change_str}\n"
                    for n in news:
                        market_data += f"   - News: {n['title']}\n"
                        all_news_titles.append(n['title'])
                    
                    with cols[col_idx % 2].expander(f"{info[0]} {price_str} {change_str}", expanded=False):
                        for n in news:
                            st.write(f"- [{n['title']}]({n['link']})")
                    
                    col_idx += 1

                except Exception as e:
                    pass
                
                current_step += 1
                progress_bar.progress(current_step / total_steps)

    # === 3. 抓取话题 (使用倒数第二个 Tab) ===
    # 因为我们最后追加了 FRED Tab，所以话题 Tab 变成了 tabs[-2]
    with tabs[-2]: 
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
            else:
                with st.expander(f"⚪ {topic} (暂无突发)", expanded=False):
                    st.caption("🔍 过去 3-30 天内未检索到核心报道，或搜索源暂时无响应。")
            
            current_step += 1
            progress_bar.progress(current_step / total_steps)

    # === 4. 展示 FRED 硬数据 (新增：使用最后一个 Tab) ===
    with tabs[-1]:
        st.header("🔢 官方宏观经济硬数据")
        st.caption("数据来源: Federal Reserve Economic Data (FRED) | St. Louis Fed")
        st.info("💡 这些是未经调整的官方原始数值，AI 将结合这些数据与市场新闻进行交叉验证。")
        
        # 直接渲染 markdown 格式的数据
        if HAS_FRED:
            st.markdown(macro_hard_data)
        else:
            st.warning("⚠️ 检测到未配置 FRED API Key。请在 `.streamlit/secrets.toml` 中配置 `FRED_API_KEY` 以获取精准数据。")
            st.code("""
[general]
FRED_API_KEY = "你的_API_KEY"
            """, language="toml")

    status_text.text("🤖 AI 正在基于全景数据撰写深度内参 (约需 10-20 秒)...")
    
# === 3. AI 分析与策略生成 ===
    
    # 3.1 数据清洗
    # 将抓取到的所有新闻标题去重，整合成一个字符串
    unique_news_titles = "\n".join(list(set(all_news_titles)))
    
    # 3.2 准备宏观硬数据 (FRED)
    # 如果配置了 FRED API，这里会获取精准数值；否则提示使用新闻推测
    if 'HAS_FRED' in globals() and HAS_FRED:
        macro_hard_data = get_macro_hard_data()
    else:
        macro_hard_data = "（未配置 FRED API，仅依赖新闻模糊推测数据）"

    # 1. 获取当前日期 (用于告诉 AI 今天是哪一天)
    today_date = datetime.now().strftime('%Y-%m-%d')

    # 3.3 构建核心 Prompt (最终优化版)
    prompt = f"""
    ### 角色设定
    你是一家顶级华尔街宏观对冲基金（Global Macro Hedge Fund）的首席投资官（CIO）。你的风格是**Bridgewater（桥水）的极度求真**与**Soros（索罗斯）的反身性视角**的结合。你不对市场进行流水账式的报道，而是寻找**市场定价偏差**、**流动性拐点**和**不对称交易机会**。同时你**基于当下最新信息**进行定价。你极度厌恶陈旧信息，认为“交易过期的新闻就是给市场送钱”。

    ### 关键背景信息
    * **当前日期 (Today)**: {today_date}  <--- 注入当前日期
    * **时效性红线**: 任何发布时间超过 30 天的数据（GDP除外），只能作为【背景趋势】，**严禁**作为【最新事件】列出。

    ### 任务目标
    基于提供的【原始新闻池】和【全景市场数据】，撰写一份《全球跨资产实战内参》。
    
    ### 输入数据
    --- 🔢 权威宏观数据 (FRED) ---
    {macro_hard_data}
    (注意：请检查上述数据的 [Date] 字段。如果日期距离 {today_date} 超过 45 天，说明最新数据尚未公布，请明确指出“数据滞后”，不要强行解读为最新利好/利空。)
    
    --- 🌡️ 市场情绪 (Sentiment) ---    <--- 新增这一段
    CNN Fear & Greed Index: {fng_score}

    --- 📰 市场叙事 ---
    {unique_news_titles}
    
    --- 📊 资产价格 ---
    {market_data}
    
    ### 核心思维框架 (Chain of Thought)
    在写作前，请在后台进行如下逻辑推演（无需输出推演过程，直接输出结果）：
    1. **交叉验证**：新闻说"利好"，但股价跌了？这说明市场已经Price-in（计价完毕）还是由流动性主导？
    2. **相关性检查**：美债收益率(^TNX)与科技股(QQQ/NVDA)的相关性是正还是负？这决定了当前是"杀估值"还是"业绩牛"。
    3. **风险传导**：高收益债(HYG)是否出现裂痕？这是判断"衰退交易"的金标准。
    4. **经济权重修正**：**切记美国是服务业导向经济(>80%)**。如果新闻显示"制造业PMI"疲软但"服务业PMI"强劲，这是**软着陆**特征，而非衰退。**严禁**仅因制造业数据差就过度渲染衰退恐慌，除非服务业PMI也跌破荣枯线。
    5. **流动性真伪验证 (BTC vs Yields)**：检查比特币(BTC-USD)与10年期美债(^TNX)的关系。如果美债收益率飙升（通常利空风险资产），但BTC依然坚挺甚至创新高，说明市场正在交易"法币贬值"或"财政赤字失控"逻辑，这对硬资产（包括科技巨头）是深层支撑。
    6. **川普交易修正**：如果新闻提及关税，检查美元(DXY)是否走强？这对新兴市场(EEM/FXI)是直接打击。
    7. **硬数据 vs 软数据**：对比情绪指标(PMI)与实锤数据(失业金/非农/ADP)。如果PMI差但就业强，定义为"软着陆"而非衰退。
    8. **情绪反指验证**：如果 CNN 恐慌贪婪指数显示“极度贪婪({fng_score})”且 VIX 处于低位，警惕市场是否过于自满(Complacency)，此时利好消息可能不再推动上涨。
    9. **时效性清洗 (Time Decay Check)**：
       - 首先检查每条新闻或数据的日期。
       - 例子：如果今天是 12月，看到“9月非农数据(Sept NFP)”，直接忽略或仅视为长期背景，**绝对不要**写在“核心叙事”里说“美国就业刚刚降温”。
       - **只关注最近 2 周内发生的边际变化**。
    10. **通胀粘性拆解 (PCE vs Core PCE)**：
       - 检查 **PCE (名义)** 与 **Core PCE (核心)** 的差值。
       - 如果名义PCE下降（因油价跌），但 Core PCE 依然顽固（YoY > 2.8%），判定为“通胀粘性高”，这将迫使美联储维持高利率（Higher for Longer）。
       - 如果两者双双回落，判定为“通胀退潮”，利好降息交易。
    11. **后视镜 vs 挡风玻璃 (GDP vs PMI)**：
       - **GDP是后视镜**：如果 FRED 里的 Real GDP 强劲 (>2.5%) 但新闻里的 ISM PMI 跌破 48，**必须警告**经济正在快速失速，市场会交易"衰退"，不要被旧的GDP数据误导。
       - **软着陆确认**：如果 GDP 保持在 1.5%-2.5% 且 Core PCE 缓慢下行，这是完美的"金发姑娘(Goldilocks)"环境，利好风险资产。
    
    ### 写作约束
    1. **语气**：冷峻、客观、数据驱动。拒绝模棱两可的废话（如"市场可能涨也可能跌"）。
    2. **格式**：严格遵守Markdown目录结构。
    3. **去链接化**：严禁包含任何URL。
    4. **时效性适应**：基于数据中的价格涨跌幅和新闻时间，自动判断分析的时间跨度（是日内波动还是周度趋势）。

    ### 报告正文结构
    >输出date(格式：YYYY-MM-DD)和subject(一句话总结行情)

    # 📰 核心叙事与噪音过滤 (Narrative & Signal)
    > **CIO 警告**：仅筛选 **最近 2 周内** 真正改变预期的事件。如果近期无大事，直接写“当前处于数据真空期，市场由情绪/资金流主导”。
    > (**关键指令**：请开启“降噪模式”，从新闻池中仅筛选 3-5 条真正驱动资产定价的关键事件，忽略无关痛痒的噪音。每条新闻请严格按照以下格式输出：
    > * **核心事件**：用一句话精练概括新闻事实。
    > * **逻辑传导**：深度分析该事件如何改变市场预期（如：降息预期落空 -> 杀估值 / 避险情绪升温 -> 资金流向美债）。
    > * **定价影响**：[利多/利空: 具体的资产代码])
    >
    > --- (此处插入分割线) ---
    >
    > * **核心事件**：(下一条新闻...)

    > --- (此处插入分割线) ---
    > 
    > ...

    # 1. 🌡️ 市场广度与背离 (Market Breadth & Divergence)
    > (对比标普500(^GSPC)与罗素2000(^RUT)的表现，判断资金是在抱团巨头还是从广泛复苏？结合恐慌指数(^VIX)判断当前市场的情绪拥挤度。)

    # 2. 🦅 宏观流动性阀门 (Liquidity & Rates)
    > (这是分析的基石。结合10年期美债(^TNX)、美元指数(DX-Y)和日元(JPY=X)的走势。
    > (结合 **就业/通胀** 与 **比特币/美债** 进行定性。)
    > **核心关注**：
    > * **增长象限判定**：结合最新的 **Real GDP** (基准) 与 **PMI/就业** (边际变化) 进行定位。当前是 [复苏 / 过热 / 滞胀 / 衰退恐慌]？
    >   - *如果 GDP 强且通胀高 -> 过热 (No Cut)*
    >   - *如果 GDP 稳且通胀降 -> 软着陆 (Bullish)*
    > * **通胀性质判定**：基于最新的 **Core PCE** 数据，当前的通胀是供给侧（油价）扰动，还是需求侧（服务业）顽疾？这决定了降息路径的快慢。
    > * **QT/QE 信号**：从新闻中判断美联储当前的缩表(QT)节奏是加速还是放缓？逆回购(RRP)资金释放是否对冲了缩表影响？
    > * **经济周期定位**：当前处于 [复苏 / 过热 / 滞胀 / 衰退恐慌] 的哪个阶段？(依据：PMI vs 失业率)
    > * **流动性温度计**：
        * **传统端**：10年期美债(^TNX)是否突破关键位(如4.5%)从而压制估值？
        * **加密端**：比特币(BTC)作为"全球流动性敏感度最高的资产"，当前是随纳指回调(风险偏好退潮)，还是独立走强(对冲法币/赤字交易)？

    # 3. 🤖 科技股动能解构 (Tech Momentum)
    > (不要只看涨跌。分析 NVDA/MSFT/TSM 的价格动能。当前是"基本面驱动"的上涨，还是"逼空式"的情绪宣泄？关注半导体板块(SMH)是否出现顶部背离。)

    # 4. ⚠️ 尾部风险监测 (Tail Risk Monitor)
    > (紧盯信用利差——即高收益债(HYG)的表现。如果股市涨但HYG跌，这是危险的背离。结合原油(CL=F)和黄金(GLD)判断是否有"滞胀"或"地缘冲突"的隐形定价。)

    5. 🎯 首席策略建议 (The CIO Verdict)
    > (**结论性板块**。基于上述分析，给出明确的战术建议：
    > * **当前宏观象限**：(例如：类金发姑娘 / 滞胀 / 衰退恐慌 / 再通胀)
    > * **纳指100决策**：(专门针对 QQQ/NDX 的操作指引：当前估值是"透支"还是"合理"？是该"逢低买入"、"高位减仓"还是"趋势持有"？)
    > * **仓位建议**：(激进进攻 / 防御 / 现金为王)
    > * **首选做多**：(具体板块或资产)
    > * **核心对冲**：(需要对冲什么风险))
    > * **关键监控点**：(例如：BTC是否跌破xx，或美债是否突破xx)
    
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