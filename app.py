import streamlit as st
import yfinance as yf
import feedparser
import requests
import time
from urllib.parse import quote
import google.generativeai as genai
from datetime import datetime, timedelta
import matplotlib.pyplot as plt # <--- 新增绘图库
import pandas as pd
from fredapi import Fred

# === 新增模块：全景红绿灯系统 (Market Radar System) ===
class MarketRadarSystem:
    def __init__(self):
        self.sectors = {
            'XLK': '科技', 'XLI': '工业', 'XLB': '材料', 'XLE': '能源',
            'XLF': '金融', 'XLV': '医疗', 'XLY': '可选', 'XLP': '必选',
            'XLC': '通信', 'XLRE': '地产', 'XLU': '公用'
        }
        self.tickers = ['SPY', 'RSP', '^VIX'] + list(self.sectors.keys())
        
    def get_data(self):
        """批量获取过去 1 年的数据"""
        # 批量下载以提高速度
        data = yf.download(self.tickers, period="1y", auto_adjust=True)['Close']
        return data

    def analyze_traffic_light(self, data):
        """
        核心算法：计算红绿灯状态
        逻辑：
        1. 趋势分 (40%): SPY 与 RSP 是否都在 20日/50日均线之上？
        2. 结构分 (30%): 广度 (RSP/SPY) 是否在上升？
        3. 攻击分 (30%): 进攻型板块 (XLK/XLI) 是否跑赢 防御型板块 (XLU/XLP)？
        """
        score = 0
        reasons = []
        
        # --- 1. 趋势判定 (Trend) ---
        spy = data['SPY']
        spy_ma50 = spy.rolling(50).mean().iloc[-1]
        spy_curr = spy.iloc[-1]
        
        if spy_curr > spy_ma50:
            score += 20
            reasons.append("✅ 大盘(SPY) 位于 50日生命线上方")
        else:
            reasons.append("⚠️ 大盘(SPY) 跌破 50日生命线")

        # --- 2. 广度判定 (Structure) ---
        rsp = data['RSP']
        breadth_ratio = rsp / spy
        breadth_ma20 = breadth_ratio.rolling(20).mean().iloc[-1]
        breadth_curr = breadth_ratio.iloc[-1]
        
        if breadth_curr > breadth_ma20:
            score += 30
            reasons.append("✅ 市场广度 (RSP/SPY) 正在走强 (中小票复苏)")
        else:
            reasons.append("⚠️ 市场广度走弱 (巨头吸血/背离)")

        # --- 3. 行业攻击性判定 (Rotation) ---
        # 进攻组: XLK(科技) + XLI(工业)
        # 防御组: XLU(公用) + XLP(必选)
        offense = (data['XLK'] + data['XLI']) / 2
        defense = (data['XLU'] + data['XLP']) / 2
        
        ratio_od = offense / defense
        ratio_od_ma20 = ratio_od.rolling(20).mean().iloc[-1]
        
        if ratio_od.iloc[-1] > ratio_od_ma20:
            score += 30
            reasons.append("✅ 资金正在流向进攻板块 (科技/工业)")
        else:
            reasons.append("🛡️ 资金流向防御板块 (避险模式)")

        # --- 4. 恐慌指数修正 (Sentiment) ---
        vix = data['^VIX'].iloc[-1]
        if vix < 15:
            score += 10
            reasons.append("✅ VIX 低位 (情绪稳定)")
        elif vix > 25:
            score -= 20 # 极度恐慌扣分
            reasons.append("🛑 VIX 飙升 (恐慌模式)")
            
        # --- 判定红绿灯 ---
        if score >= 70:
            status = "🟢 绿灯 (积极进攻)"
            color_code = "green"
        elif score >= 40:
            status = "🟡 黄灯 (震荡/观察)"
            color_code = "orange"
        else:
            status = "🔴 红灯 (防守/空仓)"
            color_code = "red"
            
        return {
            "status": status,
            "color": color_code,
            "score": score,
            "reasons": reasons,
            "vix": vix,
            "sector_data": data # 返回原始数据用于绘图
        }

    def plot_sector_heatmap(self, data):
        """绘制行业强弱横向柱状图 (修复中文乱码，使用英文标签)"""
        
        # 定义中英文映射 (仅用于图表显示)
        sector_map_en = {
            '科技': 'Technology (XLK)', 
            '工业': 'Industrial (XLI)', 
            '材料': 'Materials (XLB)', 
            '能源': 'Energy (XLE)',
            '金融': 'Financials (XLF)', 
            '医疗': 'Healthcare (XLV)', 
            '可选': 'Cons. Disc (XLY)', 
            '必选': 'Cons. Staples (XLP)',
            '通信': 'Comm. Svcs (XLC)', 
            '地产': 'Real Estate (XLRE)', 
            '公用': 'Utilities (XLU)'
        }

        # 计算过去 20 天的涨幅
        sector_perf = {}
        for ticker, cn_name in self.sectors.items():
            try:
                hist = data[ticker]
                # 计算涨幅
                pct_change = (hist.iloc[-1] - hist.iloc[-20]) / hist.iloc[-20] * 100
                
                # 将中文名转换为英文名用于绘图
                en_name = sector_map_en.get(cn_name, ticker)
                sector_perf[en_name] = pct_change
            except:
                continue
        
        # 转为 DataFrame 并排序
        df_perf = pd.DataFrame(list(sector_perf.items()), columns=['Sector', 'Change'])
        df_perf = df_perf.sort_values('Change', ascending=True)
        
        # 绘图
        fig, ax = plt.subplots(figsize=(8, 5))
        
        # 设定颜色：涨(绿) 跌(红) -> 注意：美股习惯是 绿涨红跌，或者 绿跌红涨(国内)，这里用国际通用的 绿涨红跌
        colors = ['#d32f2f' if x < 0 else '#388e3c' for x in df_perf['Change']]
        
        bars = ax.barh(df_perf['Sector'], df_perf['Change'], color=colors)
        
        # 样式美化
        ax.set_title("Sector Rotation (20-Day Performance)", fontsize=12, fontweight='bold')
        ax.set_xlabel("% Change", fontsize=10)
        ax.grid(axis='x', linestyle='--', alpha=0.3)
        
        # 在柱子旁标注具体数值
        for bar in bars:
            width = bar.get_width()
            label_x_pos = width if width > 0 else width - 0.5 # 调整标签位置
            ax.text(label_x_pos, bar.get_y() + bar.get_height()/2, f'{width:.1f}%', 
                    va='center', fontsize=9, color='black')

        plt.tight_layout()
        return fig

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

    st.info("提示：AI模型变更为Gemini3.0 Pro，请使用自有API key。")

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
    "Federal Reserve balance sheet QE QT expansion contraction", 
    "Fed reverse repo facility RRP liquidity",          
    "US Federal Reserve interest rate decision",        
    "Fed Chair speech testimony",         
    "Bank of Japan Governor Ueda monetary policy",      

    # --- 📊 关键经济指引 (新增 PMI) ---
    "US GDP growth rate",                        
    "US ISM Manufacturing PMI report",                  
    "US ISM Services PMI report economy",               
    "US inflation CPI PCE data report",                 
    "US Core PCE Price Index inflation report",         
    "US Non-farm payrolls unemployment rate",           
    "US ADP National Employment Report private payrolls", 
    "US unemployment rate jobless claims data",         
    "US Initial and Continuing Jobless Claims report", 
    
    # --- 🏛️ 政治与大选 (新增川普/新政) ---
    "Donald Trump economic policy tariffs trade",       
    "US government debt ceiling budget deficit",        

    # --- ⚔️ 地缘与新政 (突发风险) ---
    "Geopolitical tension Middle East Israel Iran",     
    "Russia Ukraine war latest news",                   
    "US China trade war tariffs restrictions",          

    # --- 📉 经济前景 ---
    "US economic recession soft landing probability",   # 衰退vs软着陆
    "Global supply chain disruption shipping",          # 供应链/红海危机
    "US commercial real estate crisis office",          # 商业地产危机
    "US economic recession soft landing probability",   # 衰退概率        
    
    # --- 🤖 产业变革 ---
    "Artificial Intelligence regulation safety",        
    "Global energy transition electric vehicles demand" 
]

# 初始化 FRED
try:
    fred_key = st.secrets["general"]["FRED_API_KEY"]
    fred = Fred(api_key=fred_key)
    HAS_FRED = True
except:
    HAS_FRED = False

# === 新增功能：市场广度与背离分析 ===
def analyze_market_breadth():
    """
    计算并绘制 RSP (等权) vs SPY (市值加权) 的背离情况
    返回: figure对象, 信号文本
    """
    tickers = ['RSP', 'SPY']
    try:
        # 获取过去1年的数据
        data = yf.download(tickers, period="1y", auto_adjust=True)['Close']
        
        # 简单清洗，防止 MultiIndex 问题
        if isinstance(data.columns, pd.MultiIndex):
             # 如果是多层索引，尝试扁平化或直接提取
             pass # yfinance最近版本下载多个ticker时通常返回 (Date, Ticker) 结构

        df = pd.DataFrame()
        df['RSP'] = data['RSP']
        df['SPY'] = data['SPY']
        
        # 1. 计算 RSP/SPY 比率 (Breadth Ratio)
        df['Breadth_Ratio'] = df['RSP'] / df['SPY']
        
        # 2. 归一化 (以第一天为 1.0)
        df['Normalized_Ratio'] = df['Breadth_Ratio'] / df['Breadth_Ratio'].iloc[0]
        df['SPY_Normalized'] = df['SPY'] / df['SPY'].iloc[0]
        df['Ratio_MA20'] = df['Normalized_Ratio'].rolling(window=20).mean() # 20日均线趋势

        # 3. 绘图 (双轴)
        fig, ax1 = plt.subplots(figsize=(10, 4))
        
        # 左轴：SPY
        color = 'tab:red'
        ax1.set_xlabel('Date')
        ax1.set_ylabel('S&P 500 (SPY)', color=color, fontweight='bold')
        ax1.plot(df.index, df['SPY_Normalized'], color=color, label='SPY Price', linewidth=1.5)
        ax1.tick_params(axis='y', labelcolor=color)
        ax1.grid(False)

        # 右轴：Breadth Ratio
        ax2 = ax1.twinx()  
        color = 'tab:blue'
        ax2.set_ylabel('Market Breadth (RSP/SPY)', color=color, fontweight='bold')
        ax2.plot(df.index, df['Normalized_Ratio'], color=color, label='Breadth Ratio', linewidth=1.5)
        ax2.plot(df.index, df['Ratio_MA20'], color=color, linestyle='--', alpha=0.3, linewidth=1)
        ax2.tick_params(axis='y', labelcolor=color)

        plt.title('Market Breadth Divergence (Red=Index, Blue=Breadth)', fontsize=10)
        plt.tight_layout()

        # 4. 生成信号逻辑
        latest = df.iloc[-1]
        prev_week = df.iloc[-5] # 一周前
        
        spy_trend = "UP" if latest['SPY_Normalized'] > prev_week['SPY_Normalized'] else "DOWN"
        breadth_trend = "UP" if latest['Normalized_Ratio'] > prev_week['Normalized_Ratio'] else "DOWN"
        
        signal_text = f"Current Status: SPY Trend is {spy_trend}, Breadth(Equal Weight) Trend is {breadth_trend}."
        
        if spy_trend == "UP" and breadth_trend == "DOWN":
            signal_text += " [⚠️ WARNING: DIVERGENCE DETECTED (Price High, Breadth Low)]"
        elif spy_trend == "UP" and breadth_trend == "UP":
            signal_text += " [✅ HEALTHY: Broad Participation]"
            
        return fig, signal_text

    except Exception as e:
        return None, f"Data Error: {str(e)}"

def get_macro_hard_data():
    """
    从 FRED 获取精准的宏观经济硬数据
    """
    if not HAS_FRED:
        return "⚠️ 未配置 FRED API Key，无法获取精准宏观数据。请继续依赖新闻。"

    data_summary = ""
    
    indicators = {
        "Real GDP Growth (实际GDP年化季率)": "A191RL1Q225SBEA", 
        "CPI (消费者物价指数)": "CPIAUCSL",
        "PCE (名义PCE物价指数)": "PCEPI",          
        "Core PCE (核心PCE - 联储锚点)": "PCEPILFE", 
        "Unemployment Rate (失业率)": "UNRATE",
        "Non-Farm Payrolls (非农就业)": "PAYEMS",
        "10Y Treasury Yield (10年美债)": "DGS10",
        "Initial Jobless Claims (初请失业金)": "ICSA", 
        "Continuing Claims (续请失业金)": "CCSA"     
    }

    data_summary += "--- 🔢 官方宏观硬数据 (FRED Verified) ---\n"
    start_date = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%d')

    try:
        for name, series_id in indicators.items():
            series = fred.get_series(series_id, observation_start=start_date).dropna()
            if series.empty: continue

            latest_date = series.index[-1].strftime('%Y-%m-%d')
            latest_val = series.iloc[-1]
            prev_val = series.iloc[-2]

            if "GDP" in name:
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

            elif "Claims" in name:
                val_k = latest_val / 1000
                change_k = (latest_val - prev_val) / 1000
                display_val = f"{val_k:.0f}k | WoW: {change_k:+.0f}k"
            else:
                display_val = f"{latest_val:.2f}"

            data_summary += f"* **{name}**: {display_val} [Date: {latest_date}]\n"
            
    except Exception as e:
        return f"⚠️ FRED 数据获取部分失败: {str(e)}"

    return data_summary

def get_news(query):
    time_window = "when:3d"
    q_upper = query.upper()
    macro_keywords = ["CPI", "PCE", "CORE PCE", "INFLATION", "PAYROLL", "NON-FARM", "JOBS", "HIRES", "UNEMPLOYMENT", "CLAIMS", "JOBLESS", "PMI", "ISM", "INTEREST RATE", "FED DECISION", "GDP", "ECONOMIC GROWTH", "RECESSION"]
    policy_keywords = ["BALANCE SHEET", "QE", "QT", "REVERSE REPO", "RRP", "POWELL", "FED CHAIR", "SPEECH", "TESTIMONY", "YELLEN", "POLICY", "TRUMP", "BIDEN", "CONGRESS", "DEBT", "DEFICIT", "BUDGET", "TARIFFS", "TRADE WAR", "REGULATION", "ANTITRUST"]

    if any(k in q_upper for k in macro_keywords):
        if "CLAIMS" in q_upper or "JOBLESS" in q_upper: time_window = "when:7d"
        elif "PCE" in q_upper or "CPI" in q_upper or "GDP" in q_upper: time_window = "when:14d"
        else: time_window = "when:14d"
    elif any(k in q_upper for k in policy_keywords):
        time_window = "when:7d"
    else:
        time_window = "when:3d"

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
    url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Referer": "https://www.cnn.com/"
    }
    try:
        r = requests.get(url, headers=headers, timeout=5)
        r.raise_for_status()
        data = r.json()
        score = data['fear_and_greed']['score']
        rating = data['fear_and_greed']['rating']
        return f"{score:.0f} ({rating})"
    except Exception as e:
        return f"N/A (获取失败: {str(e)})"

def run_analysis():
    if 'final_api_key' not in globals() or not final_api_key:
        st.error("❌ 请先在左侧配置 API Key")
        return

    genai.configure(api_key=final_api_key.strip(), transport='rest')
    model = genai.GenerativeModel('gemini-3-pro-preview')
    
    status_text = st.empty()
    progress_bar = st.progress(0)
    
# ==========================================
    # 🚦 新增：启动全景红绿灯系统 (Traffic Light)
    # ==========================================
    status_text.text("🚥 正在启动全景红绿灯系统 (下载 VIX, 行业, 广度数据)...")
    
    # 1. 实例化雷达并计算
    radar = MarketRadarSystem()
    raw_data = radar.get_data()
    radar_result = radar.analyze_traffic_light(raw_data)
    
    # 2. 获取恐慌指数 (CNN)
    fng_score = get_cnn_fear_and_greed()
    
    # 3. 获取市场广度 (RSP vs SPY) - 复用之前的函数用于画图
    breadth_fig, breadth_signal = analyze_market_breadth()

    # === 界面展示：红绿灯仪表盘 ===
    st.markdown("### 🚦 市场全景红绿灯 (Market Traffic Light)")
    
    # 使用 3 列布局
    col_traffic, col_details, col_chart = st.columns([1, 1.5, 2])
    
    with col_traffic:
        # 显示巨大的红绿灯状态
        st.markdown(f"<h1 style='text-align: center; color: {radar_result['color']}'>{radar_result['status']}</h1>", unsafe_allow_html=True)
        st.metric("综合得分 (0-100)", f"{radar_result['score']} 分")
        st.metric("VIX 恐慌指数", f"{radar_result['vix']:.2f}")
        st.metric("CNN 贪婪指数", fng_score)

    with col_details:
        st.markdown("**📊 决策依据:**")
        for reason in radar_result['reasons']:
            st.write(reason)
            
    with col_chart:
        # 绘制行业强弱图
        fig_sector = radar.plot_sector_heatmap(raw_data)
        st.pyplot(fig_sector)

    # 广度背离图折叠区
    if breadth_fig:
        with st.expander("📉 查看市场广度与背离图 (鳄鱼嘴监测)", expanded=False):
            st.pyplot(breadth_fig)
            st.info(breadth_signal)
            
    st.divider()
    # ==========================================
    # 🚦 红绿灯系统结束，下面接回原来的逻辑
    # ==========================================

    # === 1. 获取 FRED 硬数据 ===
    if HAS_FRED:
        status_text.text("🔢 正在连接美联储数据库 (FRED) 获取精准读数...")
        macro_hard_data = get_macro_hard_data()
    else:
        macro_hard_data = "⚠️ 未配置 FRED API Key，无法获取精准宏观数据。"

    # === 创建标签页 ===
    tab_names = list(WATCHLIST_GROUPS.keys()) + ["🔍 宏观话题", "🔢 宏观数据 (FRED)"]
    tabs = st.tabs(tab_names)
    
    market_data = ""
    all_news_titles = [] 
    
    # 计算总步数
    total_assets = sum(len(v) for v in WATCHLIST_GROUPS.values())
    total_topics = len(SPECIAL_TOPICS)
    total_steps = total_assets + total_topics
    current_step = 0

    # === 2. 分组抓取资产数据 (原来的 Watchlist 代码) ===
    for i, (group_name, items) in enumerate(WATCHLIST_GROUPS.items()):
        with tabs[i]: 
            cols = st.columns(2)
            col_idx = 0
            market_data += f"\n=== 【{group_name}】板块数据 ===\n"
            
            for ticker, info in items.items():
                status_text.text(f"📡 正在扫描: {group_name} - {info[0]}...")
                try:
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

    # === 3. 抓取话题 ===
    with tabs[-2]: 
        status_text.text(f"📡 正在追踪宏观话题...")
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

    # === 4. 展示 FRED 硬数据 ===
    with tabs[-1]:
        st.header("🔢 官方宏观经济硬数据")
        st.info("💡 这些是未经调整的官方原始数值，AI 将结合这些数据与市场新闻进行交叉验证。")
        if HAS_FRED:
            st.markdown(macro_hard_data)
        else:
            st.warning("⚠️ 检测到未配置 FRED API Key。")

    status_text.text("🤖 AI 正在基于全景数据撰写深度内参 (约需 10-20 秒)...")
    
    # === AI 分析 (Prompt 已更新以包含红绿灯数据) ===
    unique_news_titles = "\n".join(list(set(all_news_titles)))
    today_date = datetime.now().strftime('%Y-%m-%d')

    prompt = f"""
    ### 角色设定
    你是一家顶级华尔街宏观对冲基金的首席投资官（CIO）。你的风格是**Bridgewater（桥水）的极度求真**与**Soros（索罗斯）的反身性视角**的结合。你不对市场进行流水账式的报道，而是寻找**市场定价偏差**、**流动性拐点**和**不对称交易机会**。

    ### 关键背景信息
    * **当前日期**: {today_date}
    * **时效性红线**: 任何发布时间超过 30 天的数据（GDP除外），只能作为【背景趋势】，严禁作为【最新事件】。

    ### 输入数据

    --- 🚦 市场红绿灯系统 (Traffic Light System) ---
    状态: {radar_result['status']}
    得分: {radar_result['score']}
    VIX: {radar_result['vix']}
    决策理由: {'; '.join(radar_result['reasons'])}
    (CIO注意：这是你的核心仪表盘，如果状态是红灯或黄灯，请在报告开头直接发出警告。)

    --- 🔢 权威宏观数据 (FRED) ---
    {macro_hard_data}
    
    --- 🌡️ 市场情绪与结构 (Sentiment & Breadth) ---
    CNN Fear & Greed Index: {fng_score}
    **Market Breadth Analysis**: {breadth_signal}
    (注意：如果 Breadth Signal 显示 Warning，必须在报告中强调市场正在出现背离，大盘上涨不可持续。)

    --- 📰 市场叙事 ---
    {unique_news_titles}
    
    --- 📊 资产价格 ---
    {market_data}
    
    ### 核心思维框架 (Chain of Thought)
    在写作前，请在后台进行如下逻辑推演：
    1. **红绿灯定调**：首先看 Traffic Light System 的状态。如果是“红灯”，直接定调为防御/避险；如果是“绿灯”，定调为进攻。
    2. **交叉验证**：新闻说"利好"，但股价跌了？这说明市场已经Price-in（计价完毕）还是由流动性主导？
    3. **相关性检查**：美债收益率(^TNX)与科技股(QQQ/NVDA)的相关性是正还是负？这决定了当前是"杀估值"还是"业绩牛"。
    4. **风险传导**：高收益债(HYG)是否出现裂痕？这是判断"衰退交易"的金标准。
    5. **经济权重修正**：**切记美国是服务业导向经济(>80%)**。如果新闻显示"制造业PMI"疲软但"服务业PMI"强劲，这是**软着陆**特征，而非衰退。**严禁**仅因制造业数据差就过度渲染衰退恐慌，除非服务业PMI也跌破荣枯线。
    6. **流动性真伪验证 (BTC vs Yields)**：检查比特币(BTC-USD)与10年期美债(^TNX)的关系。如果美债收益率飙升（通常利空风险资产），但BTC依然坚挺甚至创新高，说明市场正在交易"法币贬值"或"财政赤字失控"逻辑，这对硬资产（包括科技巨头）是深层支撑。
    7. **川普交易修正**：如果新闻提及关税，检查美元(DXY)是否走强？这对新兴市场(EEM/FXI)是直接打击。
    8. **硬数据 vs 软数据**：对比情绪指标(PMI)与实锤数据(失业金/非农/ADP)。如果PMI差但就业强，定义为"软着陆"而非衰退。
    9. **情绪反指验证**：如果 CNN 恐慌贪婪指数显示“极度贪婪({fng_score})”且 VIX 处于低位，警惕市场是否过于自满(Complacency)，此时利好消息可能不再推动上涨。
    10. **时效性清洗 (Time Decay Check)**：
       - 首先检查每条新闻或数据的日期。
       - 例子：如果今天是 12月，看到“9月非农数据(Sept NFP)”，直接忽略或仅视为长期背景，**绝对不要**写在“核心叙事”里说“美国就业刚刚降温”。
       - **只关注最近 2 周内发生的边际变化**。
    11. **通胀粘性拆解 (PCE vs Core PCE)**：
       - 检查 **PCE (名义)** 与 **Core PCE (核心)** 的差值。
       - 如果名义PCE下降（因油价跌），但 Core PCE 依然顽固（YoY > 2.8%），判定为“通胀粘性高”，这将迫使美联储维持高利率（Higher for Longer）。
       - 如果两者双双回落，判定为“通胀退潮”，利好降息交易。
    12. **后视镜 vs 挡风玻璃 (GDP vs PMI)**：
       - **GDP是后视镜**：如果 FRED 里的 Real GDP 强劲 (>2.5%) 但新闻里的 ISM PMI 跌破 48，**必须警告**经济正在快速失速，市场会交易"衰退"，不要被旧的GDP数据误导。
       - **软着陆确认**：如果 GDP 保持在 1.5%-2.5% 且 Core PCE 缓慢下行，这是完美的"金发姑娘(Goldilocks)"环境，利好风险资产。
    
    ### 写作约束
    1. **语气**：冷峻、客观、数据驱动。拒绝模棱两可的废话（如"市场可能涨也可能跌"）。
    2. **格式**：严格遵守Markdown目录结构。
    3. **去链接化**：严禁包含任何URL。
    4. **时效性适应**：基于数据中的价格涨跌幅和新闻时间，自动判断分析的时间跨度（是日内波动还是周度趋势）。

    ### 报告正文结构
    >输出date(格式：YYYY-MM-DD)和subject(一句话总结行情)

    # 🚦 市场全景红绿灯 (Traffic Light Verdict)
    > (基于红绿灯系统的得分和理由，给出最直接的操作定调。解释为什么是绿/黄/红灯。)
    
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
    > (重点分析：根据输入的 Market Breadth Signal，当前是“健康的普涨”还是“虚假的指数繁荣”？结合 CNN 恐慌指数判断拥挤度。)

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

    # 3. 🤖 科技股动能解构
    > (不要只看涨跌。分析 NVDA/MSFT/TSM 的价格动能。当前是"基本面驱动"的上涨，还是"逼空式"的情绪宣泄？关注半导体板块(SMH)是否出现顶部背离。)

    # 4. ⚠️ 尾部风险监测
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