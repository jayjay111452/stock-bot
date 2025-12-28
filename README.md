📡 Stock-Bot: 您的美股 AI 全景决策雷达
Powered by Google Gemini 3.0 Pro | 宏观·广度·情绪·轮动

📖 项目简介

这不是一个简单的股价行情板。

Stock-Bot 是一个机构视角的智能金融决策系统。它像一位不知疲倦的宏观对冲基金经理，利用 Google Gemini 3.0 Pro 的推理能力，结合实时市场数据与经济新闻 (Yahoo Finance) 、官方经济硬数据 (FRED)，为您提供从宏观情绪到微观资金流向的全维度分析。

它不只告诉你“发生了什么”，更通过独创的**“红绿灯系统”和“广度背离模型”**，助你判断“现在该进攻还是防守”。

✨ 核心功能亮点 (New Features)

1. 🚦 市场全景红绿灯 (Market Traffic Light System)

“一秒看懂市场状态：进攻、震荡还是避险？”

告别复杂的K线分析，系统通过多因子模型自动生成红绿灯信号：

趋势 (Trend): 自动判定 SPY 是否站稳 50 日生命线。

结构 (Structure): 监测市场广度，警惕指数虚假繁荣。

流向 (Flow): 追踪资金是在攻击“科技/工业”，还是躲进“公用/必选消费”。

情绪 (Sentiment): 结合 VIX 恐慌指数与贪婪指数进行逆向风控。

2. 🐊 市场广度与“鳄鱼嘴”监测 (Breadth & Divergence)

“识别牛市陷阱的核武器”

独家可视化图表，实时对比 标普500市值加权 (SPY) 与 等权重 (RSP) 的走势：

拒绝虚胖： 当 SPY 创新高但 RSP 下跌（形成“鳄鱼嘴”背离）时，系统会发出高危预警。

捕捉反转： 识别资金从“七巨头”向中小盘轮动的早期信号。

3. 🧠 顶会级 AI 投资内参 (The AI CIO)

“像 Bridgewater (桥水) 风格一样思考”

内置经过深度调优的 Gemini 3.0 Pro Prompt，扮演一位极度理性的首席投资官 (CIO)：

自动降噪： 从海量新闻中过滤噪音，只关注真正改变资产定价的事件。

逻辑推演： 分析美债收益率、美元与纳指之间的二阶联动关系。

实战建议： 根据红绿灯状态，给出具体的“仓位管理”与“对冲策略”建议。

4. 🔢 联储硬核数据直连 (Direct FRED Integration)

直连 圣路易斯联储 (FRED) API，获取未经修饰的 Real GDP、Core PCE、初请失业金 等一手数据。

AI 自动交叉验证“官方数据”与“市场叙事”是否存在偏差 (Price-in Check)。

5. 📊 行业轮动热力图 (Sector Rotation)

通过 Matplotlib 绘制动态条形图，直观展示过去 20 个交易日内，华尔街资金正在涌入哪些板块。

🛠️ 技术栈 (Tech Stack)

核心引擎: Python 3.10+

前端框架: Streamlit (极速构建数据大屏)

AI 模型: Google Gemini 3.0 Pro (通过 Google AI Studio API)

数据源:

yfinance (实时行情)

fredapi (美联储宏观数据)

feedparser (Google News 聚合)

可视化: matplotlib (专业金融绘图)

⚠️ 免责声明

本工具生成的分析报告基于 AI 模型推理与历史数据，仅供参考，不构成任何投资建议。金融市场风险巨大，请独立决策，盈亏自负。

Created by JayJay | Designed for the Intelligent Investor
