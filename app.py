import streamlit as st
import yfinance as yf
import feedparser
import requests
import time
from urllib.parse import quote
import google.generativeai as genai
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import pandas as pd
from fredapi import Fred

# === 页面配置 (必须在第一行) ===
st.set_page_config(page_title="Global Market AI Radar", page_icon="📡", layout="wide")

# === 语言设置与翻译字典 ===
# 在侧边栏最上方添加语言选择
lang_option = st.sidebar.selectbox(
    "Language / 语言",
    ["中文", "English"],
    index=0
)
LANG = "CN" if lang_option == "中文" else "EN"

# UI 文本字典
TRANS = {
    "CN": {
        "title": "📡 美股全景AI雷达",
        "caption": "Powered by Google Gemini 3.0 Pro & Yahoo Finance | 宏观·广度·情绪·轮动",
        "sidebar_header": "⚙️ 控制台",
        "api_input": "Google API Key",
        "api_help": "即刻申请: https://aistudio.google.com/",
        "key_user": "✅ 使用您的个人 Key (速度快/隐私)",
        "key_system": "⚠️ 取消试用模式，请使用自有API key",
        "key_none": "❌ 未检测到 Key，请先配置",
        "key_info": "提示：AI模型变更为Gemini3.0 Pro，请使用自有API key。",
        "start_btn": "🚀 启动全景雷达 (Full Scan)",
        "traffic_light_title": "🚦 市场全景红绿灯 (Market Traffic Light)",
        "score": "综合得分 (0-100)",
        "decision_basis": "📊 决策依据:",
        "breadth_chart": "📉 查看市场广度与背离图 (鳄鱼嘴监测)",
        "fred_title": "🔢 官方宏观经济硬数据",
        "fred_info": "💡 这些是未经调整的官方原始数值，AI 将结合这些数据与市场新闻进行交叉验证。",
        "ai_processing": "🤖 AI 正在基于全景数据撰写深度内参 (约需 10-20 秒)...",
        "analysis_done": "✅ 分析完成！",
        "success_msg": "深度分析报告已生成",
        "error_gen": "AI 生成失败: ",
        "tab_macro_topics": "🔍 宏观话题",
        "tab_macro_data": "🔢 宏观数据 (FRED)"
    },
    "EN": {
        "title": "📡 US Market AI Radar",
        "caption": "Powered by Google Gemini 3.0 Pro & Yahoo Finance | Macro·Breadth·Sentiment·Rotation",
        "sidebar_header": "⚙️ Control Panel",
        "api_input": "Google API Key",
        "api_help": "Get one here: https://aistudio.google.com/",
        "key_user": "✅ Using your personal Key (Fast/Private)",
        "key_system": "⚠️ Demo mode disabled, please use own API key",
        "key_none": "❌ No Key detected, please configure",
        "key_info": "Note: Model updated to Gemini 3.0 Pro. Please use your own API Key.",
        "start_btn": "🚀 Start Full Scan",
        "traffic_light_title": "🚦 Market Traffic Light System",
        "score": "Composite Score (0-100)",
        "decision_basis": "📊 Decision Basis:",
        "breadth_chart": "📉 View Market Breadth & Divergence Chart",
        "fred_title": "🔢 Official Macro Hard Data",
        "fred_info": "💡 These are raw official figures. AI will cross-validate them with market news.",
        "ai_processing": "🤖 AI is generating the Deep Dive Report (approx 10-20s)...",
        "analysis_done": "✅ Analysis Complete!",
        "success_msg": "Deep Dive Report Generated",
        "error_gen": "AI Generation Failed: ",
        "tab_macro_topics": "🔍 Macro Topics",
        "tab_macro_data": "🔢 Macro Data (FRED)"
    }
}
T = TRANS[LANG]

# === 资产清单配置 (根据语言返回不同名称) ===
def get_watchlist_groups(lang):
    if lang == "CN":
        return {
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
                "HYG":     ["高收益债ETF (垃圾债)", "High Yield Corporate Bond ETF default risk"],
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
    else:
        # 英文版配置
        return {
            "🚀 Market Overview": {
                "^GSPC":   ["S&P 500", "S&P 500 market analysis"],
                "^IXIC":   ["Nasdaq Composite", "Nasdaq Composite analysis"],
                "^DJI":    ["Dow Jones", "Dow Jones Industrial Average news"],
                "^RUT":    ["Russell 2000", "Russell 2000 small cap stocks"],
                "^VIX":    ["VIX Index", "CBOE VIX volatility index market fear"],
                "^VXN":    ["Nasdaq VIX", "Nasdaq Volatility Index"],
            },
            "👑 Mag 7 Tech": {
                "NVDA":    ["Nvidia", "Nvidia stock news"],
                "MSFT":    ["Microsoft", "Microsoft stock AI news"],
                "AAPL":    ["Apple", "Apple Inc stock news"],
                "GOOGL":   ["Google", "Alphabet Google stock news"],
                "AMZN":    ["Amazon", "Amazon stock news"],
                "META":    ["Meta", "Meta Platforms stock news"],
                "TSLA":    ["Tesla", "Tesla stock news"],
            },
            "⚙️ Semiconductors": {
                "TSM":     ["TSMC", "TSMC stock news"],
                "ASML":    ["ASML", "ASML stock lithography"],
                "AVGO":    ["Broadcom", "Broadcom stock news"],
                "AMD":     ["AMD", "AMD stock news"],
                "MU":      ["Micron", "Micron Technology stock news"],
                "SMH":     ["Semi ETF (SMH)", "VanEck Vectors Semiconductor ETF"],
            },
            "💰 Macro Liquidity": {
                "^TNX":    ["10Y Treasury", "US 10 year treasury yield"],
                "DX-Y.NYB": ["DXY Index", "US Dollar index"],
                "JPY=X":   ["USD/JPY", "USD JPY exchange rate"],
                "TLT":     ["20Y+ Treasury ETF", "iShares 20+ Year Treasury Bond ETF"],
                "BTC-USD": ["Bitcoin", "Bitcoin crypto market sentiment"],
            },
            "🚨 Credit & Safety": {
                "HYG":     ["High Yield Bond", "High Yield Corporate Bond ETF default risk"],
                "LQD":     ["Inv Grade Bond", "Investment Grade Corporate Bond ETF"],
                "GLD":     ["Gold ETF", "Gold price investing safe haven"],
                "SLV":     ["Silver ETF", "Silver price investing"],
            },
            "🏭 Cyclical/Inflation": {
                "CL=F":    ["Crude Oil", "Crude oil price energy news"],
                "XLE":     ["Energy ETF", "US Energy Sector ETF"],
                "XLF":     ["Financials ETF", "US Financials Sector ETF bank earnings"],
                "XLI":     ["Industrials ETF", "US Industrials Sector ETF economy"],
                "CAT":     ["Caterpillar", "Caterpillar stock economy"],
                "JETS":    ["Jets ETF", "U.S. Global Jets ETF travel demand"],
            },
            "🛡️ Defensive": {
                "XLV":     ["Healthcare ETF", "Health Care Sector ETF"],
                "XLP":     ["Staples ETF", "Consumer Staples Sector ETF"],
                "WMT":     ["Walmart", "Walmart stock consumer spending"],
                "KO":      ["Coca-Cola", "Coca-Cola stock defensive"],
                "UNH":     ["UnitedHealth", "UnitedHealth Group stock"],
            },
            "🇨🇳 China/Emerging": {
                "^HSI":    ["Hang Seng", "Hang Seng Index Hong Kong"],
                "FXI":     ["China Large Cap", "China large cap ETF investing"],
                "KWEB":    ["China Internet", "China internet ETF tech regulation"],
                "EEM":     ["Emerging Markets", "Emerging Markets ETF growth"],
            }
        }

SPECIAL_TOPICS = [
    "Federal Reserve balance sheet QE QT expansion contraction", 
    "Fed reverse repo facility RRP liquidity",          
    "US Federal Reserve interest rate decision",        
    "Fed Chair speech testimony",         
    "Bank of Japan Governor Ueda monetary policy",      
    "US GDP growth rate",                        
    "US ISM Manufacturing PMI report",                  
    "US ISM Services PMI report economy",               
    "US inflation CPI PCE data report",                 
    "US Core PCE Price Index inflation report",         
    "US Non-farm payrolls unemployment rate",           
    "US ADP National Employment Report private payrolls", 
    "US unemployment rate jobless claims data",         
    "US Initial and Continuing Jobless Claims report", 
    "Donald Trump economic policy tariffs trade",       
    "US government debt ceiling budget deficit",        
    "Geopolitical tension Middle East Israel Iran",     
    "Russia Ukraine war latest news",                   
    "US China trade war tariffs restrictions",          
    "US economic recession soft landing probability",   
    "Global supply chain disruption shipping",          
    "US commercial real estate crisis office",                  
    "Artificial Intelligence regulation safety",        
    "Global energy transition electric vehicles demand" 
]

# === 新增模块：全景红绿灯系统 (Market Radar System) ===
class MarketRadarSystem:
    def __init__(self, lang="CN"):
        self.lang = lang
        self.sectors = {
            'XLK': '科技' if lang=='CN' else 'Tech', 
            'XLI': '工业' if lang=='CN' else 'Industrials', 
            'XLB': '材料' if lang=='CN' else 'Materials', 
            'XLE': '能源' if lang=='CN' else 'Energy',
            'XLF': '金融' if lang=='CN' else 'Financials', 
            'XLV': '医疗' if lang=='CN' else 'Healthcare', 
            'XLY': '可选' if lang=='CN' else 'Cons. Disc', 
            'XLP': '必选' if lang=='CN' else 'Cons. Staples',
            'XLC': '通信' if lang=='CN' else 'Comm. Svcs', 
            'XLRE': '地产' if lang=='CN' else 'Real Estate', 
            'XLU': '公用' if lang=='CN' else 'Utilities'
        }
        self.tickers = ['SPY', 'RSP', '^VIX'] + list(self.sectors.keys())
        
    def get_data(self):
        raw_data = yf.download(self.tickers, period="1y", interval="1d", auto_adjust=True, threads=True)
        try:
            if isinstance(raw_data.columns, pd.MultiIndex):
                data = raw_data['Close']
            else:
                data = raw_data
        except Exception as e:
            st.error(f"Data struct error: {e}")
            return pd.DataFrame()

        data = data.ffill().dropna()
        return data

    def analyze_traffic_light(self, data):
        score = 0
        reasons = []
        is_cn = (self.lang == "CN")
        
        if data.empty or 'SPY' not in data.columns:
            return {
                "status": "⚪ 数据获取失败" if is_cn else "⚪ Data Error", 
                "color": "gray", "score": 0,
                "reasons": ["无法连接 Yahoo Finance" if is_cn else "Cannot connect to Yahoo Finance"], 
                "vix": 0, "sector_data": data
            }

        # --- 1. 趋势判定 (Trend) ---
        spy = data['SPY']
        spy_ma50 = spy.rolling(50).mean().iloc[-1]
        spy_curr = spy.iloc[-1]
        
        if pd.isna(spy_curr) or pd.isna(spy_ma50):
            reasons.append("⚠️ 数据不足，无法计算均线" if is_cn else "⚠️ Insufficient data for MA calc")
        elif spy_curr > spy_ma50:
            score += 20
            diff = (spy_curr - spy_ma50) / spy_ma50 * 100
            reasons.append(f"✅ 大盘(SPY) 站上 50日线 (+{diff:.1f}%)" if is_cn else f"✅ SPY above 50MA (+{diff:.1f}%)")
        else:
            diff = (spy_ma50 - spy_curr) / spy_ma50 * 100
            reasons.append(f"⚠️ 大盘(SPY) 跌破 50日线 (-{diff:.1f}%)" if is_cn else f"⚠️ SPY below 50MA (-{diff:.1f}%)")

        # --- 2. 广度判定 (Structure) ---
        if 'RSP' in data.columns:
            rsp = data['RSP']
            breadth_ratio = rsp / spy
            breadth_ma20 = breadth_ratio.rolling(20).mean().iloc[-1]
            breadth_curr = breadth_ratio.iloc[-1]
            
            if breadth_curr > breadth_ma20:
                score += 30
                reasons.append("✅ 市场广度 (RSP/SPY) 走强 (中小票复苏)" if is_cn else "✅ Market Breadth (RSP/SPY) Strengthening")
            else:
                reasons.append("⚠️ 市场广度走弱 (巨头吸血/背离)" if is_cn else "⚠️ Market Breadth Weakening (Megacap divergence)")

        # --- 3. 行业攻击性判定 (Rotation) ---
        cols = ['XLK', 'XLI', 'XLU', 'XLP']
        if all(c in data.columns for c in cols):
            offense = (data['XLK'] + data['XLI']) / 2
            defense = (data['XLU'] + data['XLP']) / 2
            
            ratio_od = offense / defense
            ratio_od_ma20 = ratio_od.rolling(20).mean().iloc[-1]
            
            if ratio_od.iloc[-1] > ratio_od_ma20:
                score += 30
                reasons.append("✅ 资金流向进攻板块 (科技/工业)" if is_cn else "✅ Capital Flow to Cyclicals (Tech/Ind)")
            else:
                reasons.append("🛡️ 资金流向防御板块 (避险模式)" if is_cn else "🛡️ Capital Flow to Defensives (Risk Off)")
        else:
            reasons.append("⚪ 板块数据缺失，跳过结构分析" if is_cn else "⚪ Missing sector data, skipping structure analysis")

        # --- 4. 恐慌指数修正 (Sentiment) ---
        if '^VIX' in data.columns:
            vix = data['^VIX'].iloc[-1]
            if vix < 15:
                score += 10
                reasons.append(f"✅ VIX 低位 ({vix:.2f})" if is_cn else f"✅ VIX Low ({vix:.2f})")
            elif vix > 25:
                score -= 20 
                reasons.append(f"🛑 VIX 飙升 ({vix:.2f})" if is_cn else f"🛑 VIX Spiking ({vix:.2f})")
        else:
            vix = 0
            
        # --- 判定红绿灯 ---
        if score >= 70:
            status = "🟢 绿灯 (积极进攻)" if is_cn else "🟢 GREEN LIGHT (Risk On)"
            color_code = "green"
        elif score >= 40:
            status = "🟡 黄灯 (震荡/观察)" if is_cn else "🟡 YELLOW LIGHT (Caution)"
            color_code = "orange"
        else:
            status = "🔴 红灯 (防守/空仓)" if is_cn else "🔴 RED LIGHT (Defensive)"
            color_code = "red"
            
        return {
            "status": status,
            "color": color_code,
            "score": score,
            "reasons": reasons,
            "vix": vix,
            "sector_data": data 
        }

    def plot_sector_heatmap(self, data):
        """绘制行业强弱横向柱状图"""
        if data.empty:
            return plt.figure()

        # 映射英文 Key 到显示名称
        sector_map_display = {
            'Technology (XLK)': 'Tech (XLK)', 'Industrial (XLI)': 'Ind (XLI)', 
            'Materials (XLB)': 'Mat (XLB)', 'Energy (XLE)': 'Energy (XLE)',
            'Financials (XLF)': 'Fin (XLF)', 'Healthcare (XLV)': 'Health (XLV)', 
            'Cons. Disc (XLY)': 'Disc (XLY)', 'Cons. Staples (XLP)': 'Staples (XLP)',
            'Comm. Svcs (XLC)': 'Comm (XLC)', 'Real Estate (XLRE)': 'RE (XLRE)', 
            'Utilities (XLU)': 'Util (XLU)'
        }
        
        # 基础英文名称映射，用于图表统一
        base_map = {
             'XLK': 'Technology (XLK)', 'XLI': 'Industrial (XLI)', 'XLB': 'Materials (XLB)', 
             'XLE': 'Energy (XLE)', 'XLF': 'Financials (XLF)', 'XLV': 'Healthcare (XLV)', 
             'XLY': 'Cons. Disc (XLY)', 'XLP': 'Cons. Staples (XLP)', 'XLC': 'Comm. Svcs (XLC)', 
             'XLRE': 'Real Estate (XLRE)', 'XLU': 'Utilities (XLU)'
        }

        sector_perf = {}
        
        # 使用 ticker 直接遍历
        for ticker in self.sectors.keys():
            if ticker in data.columns:
                hist = data[ticker]
                if len(hist) >= 20:
                    pct_change = (hist.iloc[-1] - hist.iloc[-20]) / hist.iloc[-20] * 100
                    en_name = base_map.get(ticker, ticker)
                    sector_perf[en_name] = pct_change
        
        if not sector_perf:
            return plt.figure()

        df_perf = pd.DataFrame(list(sector_perf.items()), columns=['Sector', 'Change'])
        df_perf = df_perf.sort_values('Change', ascending=True)
        
        fig, ax = plt.subplots(figsize=(8, 5))
        colors = ['#d32f2f' if x < 0 else '#388e3c' for x in df_perf['Change']]
        bars = ax.barh(df_perf['Sector'], df_perf['Change'], color=colors)
        
        ax.set_title("Sector Rotation (20-Day Performance)", fontsize=12, fontweight='bold')
        ax.set_xlabel("% Change", fontsize=10)
        ax.grid(axis='x', linestyle='--', alpha=0.3)
        
        for bar in bars:
            width = bar.get_width()
            label_x_pos = width if width > 0 else width - 0.5 
            ax.text(label_x_pos, bar.get_y() + bar.get_height()/2, f'{width:.1f}%', 
                    va='center', fontsize=9, color='black')

        plt.tight_layout()
        return fig

# 初始化 FRED
try:
    fred_key = st.secrets["general"]["FRED_API_KEY"]
    fred = Fred(api_key=fred_key)
    HAS_FRED = True
except:
    HAS_FRED = False

def analyze_market_breadth(lang="CN"):
    tickers = ['RSP', 'SPY']
    try:
        data = yf.download(tickers, period="1y", auto_adjust=True)['Close']
        df = pd.DataFrame()
        df['RSP'] = data['RSP']
        df['SPY'] = data['SPY']
        
        df['Breadth_Ratio'] = df['RSP'] / df['SPY']
        df['Normalized_Ratio'] = df['Breadth_Ratio'] / df['Breadth_Ratio'].iloc[0]
        df['SPY_Normalized'] = df['SPY'] / df['SPY'].iloc[0]
        df['Ratio_MA20'] = df['Normalized_Ratio'].rolling(window=20).mean()

        fig, ax1 = plt.subplots(figsize=(10, 4))
        color = 'tab:red'
        ax1.set_xlabel('Date')
        ax1.set_ylabel('S&P 500 (SPY)', color=color, fontweight='bold')
        ax1.plot(df.index, df['SPY_Normalized'], color=color, label='SPY Price', linewidth=1.5)
        ax1.tick_params(axis='y', labelcolor=color)
        ax1.grid(False)

        ax2 = ax1.twinx()  
        color = 'tab:blue'
        ax2.set_ylabel('Market Breadth (RSP/SPY)', color=color, fontweight='bold')
        ax2.plot(df.index, df['Normalized_Ratio'], color=color, label='Breadth Ratio', linewidth=1.5)
        ax2.plot(df.index, df['Ratio_MA20'], color=color, linestyle='--', alpha=0.3, linewidth=1)
        ax2.tick_params(axis='y', labelcolor=color)

        plt.title('Market Breadth Divergence (Red=Index, Blue=Breadth)', fontsize=10)
        plt.tight_layout()

        latest = df.iloc[-1]
        prev_week = df.iloc[-5]
        
        spy_trend = "UP" if latest['SPY_Normalized'] > prev_week['SPY_Normalized'] else "DOWN"
        breadth_trend = "UP" if latest['Normalized_Ratio'] > prev_week['Normalized_Ratio'] else "DOWN"
        
        signal_text = f"Current Status: SPY Trend is {spy_trend}, Breadth(Equal Weight) Trend is {breadth_trend}."
        
        if spy_trend == "UP" and breadth_trend == "DOWN":
            signal_text += " [⚠️ WARNING: DIVERGENCE DETECTED]"
        elif spy_trend == "UP" and breadth_trend == "UP":
            signal_text += " [✅ HEALTHY: Broad Participation]"
            
        return fig, signal_text
    except Exception as e:
        return None, f"Data Error: {str(e)}"

def get_macro_hard_data(lang="CN"):
    """从 FRED 获取数据，根据语言调整输出 (带日期版)"""
    if not HAS_FRED:
        return "⚠️ FRED Key Missing." if lang=="EN" else "⚠️ 未配置 FRED API Key。"

    data_summary = ""
    # 根据语言选择标签
    if lang == "CN":
        indicators = {
            "Real GDP Growth (实际GDP)": "A191RL1Q225SBEA", 
            "CPI (消费者物价)": "CPIAUCSL",
            "PCE (名义PCE)": "PCEPI",          
            "Core PCE (核心PCE)": "PCEPILFE", 
            "Unemployment Rate (失业率)": "UNRATE",
            "Non-Farm Payrolls (非农就业)": "PAYEMS",
            "10Y Treasury Yield (10年美债)": "DGS10",
            "Initial Jobless Claims (初请失业金)": "ICSA",
            "Continuing Claims (续请失业金)": "CCSA" 
        }
        header = "--- 🔢 官方宏观硬数据 (FRED Verified) ---\n"
    else:
        indicators = {
            "Real GDP Growth": "A191RL1Q225SBEA", 
            "CPI (Consumer Price Index)": "CPIAUCSL",
            "PCE (PCE Price Index)": "PCEPI",          
            "Core PCE (Fed's Favorite)": "PCEPILFE", 
            "Unemployment Rate": "UNRATE",
            "Non-Farm Payrolls": "PAYEMS",
            "10Y Treasury Yield": "DGS10",
            "Initial Jobless Claims": "ICSA",
            "Continuing Claims": "CCSA" 
        }
        header = "--- 🔢 Official Macro Hard Data (FRED Verified) ---\n"

    data_summary += header
    start_date = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%d')

    try:
        for name, series_id in indicators.items():
            series = fred.get_series(series_id, observation_start=start_date).dropna()
            if series.empty: continue

            # === 新增：获取数据日期 ===
            latest_date = series.index[-1].strftime('%Y-%m-%d')
            
            latest_val = series.iloc[-1]
            prev_val = series.iloc[-2]

            if "GDP" in name:
                emoji = "🔥" if latest_val >= 3.0 else ("❄️" if latest_val < 1.0 else "⚖️")
                display_val = f"{latest_val:.2f}% {emoji}"
            elif "CPI" in name or "PCE" in name:
                if len(series) >= 13:
                    year_ago_val = series.iloc[-13]
                    yoy = ((latest_val - year_ago_val) / year_ago_val) * 100
                    display_val = f"{yoy:.2f}% (YoY)"
                else:
                    display_val = f"{latest_val:.1f}"
            elif "Non-Farm" in name:
                change = (latest_val - prev_val)
                display_val = f"Total {latest_val:,.0f}k | Change: {change:+,.0f}k"
            elif "Claims" in name:
                val_k = latest_val / 1000
                display_val = f"{val_k:.0f}k"
            else:
                display_val = f"{latest_val:.2f}"

            # === 修改：输出时加上日期 ===
            data_summary += f"* **{name}**: {display_val} [🗓️ {latest_date}]\n"
            
    except Exception as e:
        return f"FRED Error: {str(e)}"

    return data_summary

def get_news(query):
    # 新闻抓取逻辑通用，无需翻译查询词（因为查询词本身多为英文或通用金融术语）
    time_window = "when:3d"
    q_upper = query.upper()
    macro_keywords = ["CPI", "PCE", "INFLATION", "PAYROLL", "JOBS", "PMI", "FED", "GDP", "RECESSION"]
    
    if any(k in q_upper for k in macro_keywords):
        time_window = "when:14d"
    
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

# === 渲染 UI ===
st.title(T['title'])
st.caption(T['caption'])

with st.sidebar:
    st.header(T['sidebar_header'])
    user_api_key = st.text_input(T['api_input'], type="password", help=T['api_help'])
    system_api_key = st.secrets.get("GEMINI_DEMO_KEY", None)
    
    if user_api_key:
        final_api_key = user_api_key
        key_type = "user"
    elif system_api_key:
        final_api_key = system_api_key
        key_type = "system"
    else:
        final_api_key = None
        key_type = "none"

    if key_type == "user":
        st.success(T['key_user'])
    elif key_type == "system":
        st.warning(T['key_system'])
    else:
        st.error(T['key_none'])

    st.info(T['key_info'])

def run_analysis():
    if 'final_api_key' not in globals() or not final_api_key:
        st.error(T['key_none'])
        return

    genai.configure(api_key=final_api_key.strip(), transport='rest')
    model = genai.GenerativeModel('gemini-3-pro-preview') 
    
    status_text = st.empty()
    progress_bar = st.progress(0)
    
    status_text.text(f"🚥 {T['traffic_light_title']}...")
    
    # 1. 雷达计算
    radar = MarketRadarSystem(lang=LANG)
    raw_data = radar.get_data()
    radar_result = radar.analyze_traffic_light(raw_data)
    fng_score = get_cnn_fear_and_greed()
    breadth_fig, breadth_signal = analyze_market_breadth(lang=LANG)

    # UI: 红绿灯
    st.markdown(f"### {T['traffic_light_title']}")
    col_traffic, col_details, col_chart = st.columns([1, 1.5, 2])
    
    with col_traffic:
        st.markdown(f"<h3 style='text-align: center; color: {radar_result['color']}'>{radar_result['status']}</h3>", unsafe_allow_html=True)
        st.metric(T['score'], f"{radar_result['score']}")
        st.metric("VIX", f"{radar_result['vix']:.2f}")
        st.metric("CNN Fear/Greed", fng_score)

    with col_details:
        st.markdown(f"**{T['decision_basis']}**")
        for reason in radar_result['reasons']:
            st.write(reason)
            
    with col_chart:
        fig_sector = radar.plot_sector_heatmap(raw_data)
        st.pyplot(fig_sector)

    if breadth_fig:
        with st.expander(T['breadth_chart'], expanded=False):
            st.pyplot(breadth_fig)
            st.info(breadth_signal)
            
    st.divider()

    # 2. 宏观硬数据
    if HAS_FRED:
        status_text.text("🔢 Connecting to FRED...")
        macro_hard_data = get_macro_hard_data(lang=LANG)
    else:
        macro_hard_data = T['fred_info']

    # 3. Watchlist 数据抓取
    current_watchlist = get_watchlist_groups(LANG)
    tab_names = list(current_watchlist.keys()) + [T['tab_macro_topics'], T['tab_macro_data']]
    tabs = st.tabs(tab_names)
    
    market_data = ""
    all_news_titles = [] 
    
    total_assets = sum(len(v) for v in current_watchlist.values())
    total_topics = len(SPECIAL_TOPICS)
    total_steps = total_assets + total_topics
    current_step = 0

    # 遍历资产
    for i, (group_name, items) in enumerate(current_watchlist.items()):
        with tabs[i]: 
            cols = st.columns(2)
            col_idx = 0
            market_data += f"\n=== [{group_name}] ===\n"
            
            for ticker, info in items.items():
                status_text.text(f"📡 Scanning: {info[0]}...")
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
                    market_data += f"[{info[0]}] Price:{price_str} {change_str}\n"
                    for n in news:
                        market_data += f"   - News: {n['title']}\n"
                        all_news_titles.append(n['title'])
                    
                    with cols[col_idx % 2].expander(f"{info[0]} {price_str} {change_str}", expanded=False):
                        for n in news:
                            st.write(f"- [{n['title']}]({n['link']})")
                    col_idx += 1
                except:
                    pass
                current_step += 1
                progress_bar.progress(current_step / total_steps)

    # 遍历话题
    with tabs[-2]: 
        status_text.text(f"📡 Tracking Macro Topics...")
        market_data += f"\n=== [Macro Topics] ===\n"
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

    with tabs[-1]:
        st.header(T['fred_title'])
        st.info(T['fred_info'])
        if HAS_FRED:
            st.markdown(macro_hard_data)

    status_text.text(T['ai_processing'])
    
    unique_news_titles = "\n".join(list(set(all_news_titles)))
    today_date = datetime.now().strftime('%Y-%m-%d')

    # === 构建 Prompt (区分中英文) ===
    if LANG == "CN":
        # 中文 Prompt (保持原有逻辑)
        prompt = f"""
        ### 角色设定
        你是一家顶级华尔街宏观对冲基金的首席投资官（CIO）。你的风格是**Bridgewater（桥水）的极度求真**与**Soros（索罗斯）的反身性视角**的结合。

        ### 关键背景信息
        * **当前日期**: {today_date}
        * **时效性红线**: 任何发布时间超过 30 天的数据（GDP除外），只能作为【背景趋势】，严禁作为【最新事件】。

        ### 输入数据
        * **Traffic Light**: {radar_result['status']} (Reason: {'; '.join(radar_result['reasons'])})
        * **VIX**: {radar_result['vix']} | CNN Fear/Greed: {fng_score}
        * **Market Breadth**: {breadth_signal}
        * **Macro Data**: {macro_hard_data}
        * **News & Prices**: {market_data}
        * **Current Date**: {today_date}

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
    else:
        # 英文 Prompt
        prompt = f"""
        ### Role Definition
        You are the Chief Investment Officer (CIO) of a top-tier Wall Street macro hedge fund. Your style combines **Bridgewater's "Radical Truth"** with **Soros's "Reflexivity"**. You do not provide generic market summaries; you hunt for **pricing errors**, **liquidity turning points**, and **asymmetric trading opportunities**.

        ### Key Context
        * **Current Date**: {today_date}
        * **Time Sensitivity Red Line**: Any data released more than 30 days ago (except GDP) must be treated solely as [Background Trend] and strictly forbidden from being cited as [Latest Events].

        ### Input Data
        * **Traffic Light System**: {radar_result['status']} (Score: {radar_result['score']}, Reason: {'; '.join(radar_result['reasons'])})
        * **Sentiment**: VIX: {radar_result['vix']} | CNN Fear/Greed: {fng_score}
        * **Market Breadth**: {breadth_signal}
        * **Macro Data (FRED)**: {macro_hard_data}
        * **News & Prices**: {market_data}
        * **Current Date**: {today_date}

        ### Chain of Thought (Logic Framework)
        Before writing, perform the following logical deductions in the background:
        1.  **Traffic Light Verdict**: Check the Traffic Light System first. If "Red", set the tone to Defensive/Risk-Off immediately. If "Green", set to Aggressive/Risk-On.
        2.  **Cross-Validation**: News says "Bullish" but price dropped? Does this mean the news is already **Priced-in**, or is liquidity draining?
        3.  **Correlation Check**: Is the correlation between 10Y Yields (^TNX) and Tech (QQQ/NVDA) positive or negative? This determines if we are in a "Valuation Compression" (yields up, tech down) or "Earnings Bull" (yields up, tech up) phase.
        4.  **Risk Transmission**: Are there cracks in High Yield Bonds (HYG)? This is the gold standard for detecting "Recession Trades."
        5.  **Economic Weighting Correction**: **Remember the US is >80% Services.** If Manufacturing PMI is weak but Services PMI is strong, this characterizes a **Soft Landing**, not a recession. **Do not** fear-monger based on weak manufacturing unless Services also crack.
        6.  **Liquidity Verification (BTC vs. Yields)**: Check Bitcoin (BTC-USD) vs. 10Y Treasury (^TNX). If yields spike (usually bad for risk) but BTC remains resilient or makes new highs, the market is trading the "Fiat Debasement" or "Fiscal Deficit" logic, which supports hard assets (including Big Tech).
        7.  **Trump Trade Correction**: If news mentions tariffs, check if the Dollar (DXY) is strengthening. This is a direct hit to Emerging Markets (EEM/FXI).
        8.  **Hard vs. Soft Data**: Compare Sentiment (PMI) vs. Hard Data (Jobless Claims/Payrolls). If PMI is bad but Employment is strong, define it as a "Soft Landing."
        9.  **Sentiment Contrarian Check**: If CNN Fear & Greed shows "Extreme Greed ({fng_score})" and VIX is at lows, warn about **Complacency**. Good news may no longer drive prices up.
        10. **Time Decay Check**: 
            - Check the date of every news item.
            - Example: If today is Dec, and you see "Sept NFP data", ignore it or treat as background. **Do not** write it as a core driver.
            - **Focus only on marginal changes in the last 2 weeks.**
        11. **Inflation Stickiness (PCE vs. Core)**:
            - Check the spread between **PCE (Nominal)** and **Core PCE**.
            - If Nominal drops (oil down) but Core remains stubborn (>2.8%), define as "Sticky Inflation" (Higher for Longer).
            - If both drop, define as "Disinflation" (Bullish for cuts).
        12. **Rearview vs. Windshield (GDP vs. PMI)**:
            - **GDP is the Rearview Mirror**: If FRED Real GDP is strong (>2.5%) but ISM PMI drops below 48, you **must warn** that the economy is stalling. Do not be misled by old GDP data.
            - **Soft Landing Confirmation**: If GDP stays 1.5%-2.5% and Core PCE trends down, this is the perfect "Goldilocks" environment.

        ### Writing Constraints
        1.  **Tone**: Cold, objective, data-driven. No ambiguous filler like "the market might go up or down."
        2.  **Format**: Strictly follow the Markdown structure below.
        3.  **No Links**: Do not include any URLs.
        4.  **Time Adaptation**: Automatically adjust the analysis horizon based on the price changes and news timestamps provided.

        ### Report Structure
        > Output date (Format: YYYY-MM-DD) and subject (One sentence summary of the regime).

        # 🚦 Market Traffic Light Verdict
        > (Based on the Traffic Light score and reasons, provide a direct operational stance. Explain *why* it is Green/Yellow/Red.)

        # 📰 Core Narratives & Signal Noise Filter
        > **CIO Warning**: Filter for events occurring **only within the last 2 weeks** that genuinely shift expectations. If no major recent events, state "Currently in a data vacuum; market driven by sentiment/flows."
        > (**Instruction**: Activate "Noise Reduction Mode". Select only 3-5 key events driving asset pricing. Ignore noise. Output each item strictly in this format:)
        >
        > * **Core Event**: (One sentence summary of the fact).
        > * **Logic Transmission**: (Deep analysis of how this shifts expectations. E.g., Rate cut hopes dashed -> Valuation compression / Risk aversion -> Flows to Treasuries).
        > * **Pricing Impact**: [Bullish/Bearish: Specific Ticker].
        >
        > --- (Insert Divider) ---
        >
        > * **Core Event**: (Next item...)

        # 1. 🌡️ Market Breadth & Divergence
        > (Focus: Analyze the Market Breadth Signal provided. Is this a "Healthy Broad Rally" or a "Fake Index Prosperity" driven by a few giants? Combine with CNN Fear & Greed to judge crowding.)

        # 2. 🦅 Macro Liquidity Valve (Liquidity & Rates)
        > (This is the cornerstone. Analyze 10Y Treasury (^TNX), DXY, and JPY. Combine **Jobs/Inflation** with **Bitcoin/Bonds** logic.)
        > **Core Focus**:
        > * **Growth Quadrant**: Combine **Real GDP** (Baseline) vs. **PMI/Jobs** (Marginal Change). Are we in [Recovery / Overheating / Stagflation / Recession Scare]?
        >     - *If GDP strong + Inflation high -> Overheating (No Cut)*
        >     - *If GDP stable + Inflation down -> Soft Landing (Bullish)*
        > * **Inflation Nature**: Based on **Core PCE**, is inflation supply-side (Oil) or demand-side (Services)? This dictates the speed of cuts.
        > * **QT/QE Signal**: Is the Fed's balance sheet shrinking (QT)? Is the Reverse Repo (RRP) draining offsetting this?
        > * **Liquidity Thermometer**:
        >     - *Traditional*: Did 10Y Yields break key levels (e.g., 4.5%)?
        >     - *Crypto*: Is Bitcoin (BTC) acting as a risk-asset (dropping with Nasdaq) or a debasement hedge (rising despite yields)?

        # 3. 🤖 Tech Momentum Deconstruction
        > (Don't just look at price. Analyze the momentum of NVDA/MSFT/TSM. Is the current move "Fundamental" or "Short Squeeze/FOMO"? Check if SMH (Semis) is showing a top divergence.)

        # 4. ⚠️ Tail Risk Monitor
        > (Watch Credit Spreads—specifically HYG. If Stocks rise but HYG falls, this is a dangerous divergence. Combine with Oil (CL=F) and Gold (GLD) to check for "Stagflation" or "Geopolitical" invisible pricing.)

        5. 🎯 The CIO Verdict (Strategy)
        > (**Conclusion**. Based on the above, provide clear tactical advice:)
        > * **Current Macro Quadrant**: (e.g., Goldilocks / Stagflation / Recession Scare / Reflation)
        > * **Nasdaq 100 Decision**: (Specific guidance for QQQ/NDX: Is valuation "Overstretched" or "Justified"? Buy Dip / Trim / Trend Hold?)
        > * **Positioning**: (Aggressive / Defensive / Cash is King)
        > * **Top Long Idea**: (Specific Sector or Asset)
        > * **Core Hedge**: (What risk needs hedging?)
        > * **Key Monitor Level**: (e.g., If BTC breaks $XX, or 10Y Yield breaks X%)
        """

    try:
        response = model.generate_content(prompt)
        status_text.text(T['analysis_done'])
        st.success(T['success_msg'])
        st.markdown("---")
        st.markdown(response.text)
    except Exception as e:
        st.error(f"{T['error_gen']} {e}")

if st.button(T['start_btn'], type="primary"):
    run_analysis()