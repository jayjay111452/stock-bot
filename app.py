import streamlit as st
import numpy as np
import plotly.graph_objects as go
from scipy.interpolate import interp1d
from solver import TFTPoissonSolver
import time

st.set_page_config(layout="wide", page_title="Oxide TFT HD")

st.title("Oxide TFT Simulation (Stacked Buffer Model)")

# --- Sidebar ---
st.sidebar.header("1. 器件结构 (Structure)")
struct_type = st.sidebar.selectbox(
    "偏置模式",
    ('Double Gate', 'Single Gate (Top)', 'Single Gate (Bottom)', 'Source-Gated Bottom')
)

st.sidebar.header("2. 几何尺寸 (Geometry)")
col_lw = st.sidebar.columns(2)
with col_lw[0]:
    L_um = st.number_input("沟道长度 L (um)", value=2.0)
with col_lw[1]:
    W_um = st.number_input("沟道宽度 W (um)", value=10.0)

st.sidebar.subheader("Buffer Layer (Bottom)")
col1, col2 = st.sidebar.columns(2)
with col1:
    t_sin_nm = st.number_input("SiN 厚度 (nm)", value=100.0)
    eps_sin = st.number_input("SiN 介电常数", value=7.0)
with col2:
    t_buf_sio_nm = st.number_input("Buf SiO 厚度 (nm)", value=100.0)
    eps_buf_sio = st.number_input("Buf SiO 介电常数", value=3.9)

st.sidebar.subheader("Active & GI Layer")
col3, col4 = st.sidebar.columns(2)
with col3:
    t_igzo_nm = st.number_input("IGZO层厚度 (nm)", value=50.0)
with col4:
    t_gi_nm = st.number_input("GI层 (Top SiO) 厚度 (nm)", value=100.0)
    
col5, col6 = st.sidebar.columns(2)
with col5:
    eps_igzo = st.number_input("IGZO 介电常数", value=10.0)
with col6:
    eps_gi = st.number_input("GI 介电常数", value=3.9)

st.sidebar.subheader("Source/Drain Resistance")
col_sd1, col_sd2 = st.sidebar.columns(2)
with col_sd1:
    L_source_um = st.number_input("源极长度 (um)", value=1.0, min_value=0.0)
    Rs_sheet = st.number_input("源极方块电阻 (Ω/sq)", value=3000.0, format="%.1f")
with col_sd2:
    L_drain_um = st.number_input("漏极长度 (um)", value=1.0, min_value=0.0)
    Rd_sheet = st.number_input("漏极方块电阻 (Ω/sq)", value=3000.0, format="%.1f")

st.sidebar.header("3. 网格设置 (Mesh Setting)")
ny_igzo = st.sidebar.slider("IGZO层 Y轴网格点数 (Max 1000)", 100, 1000, 400)
nx = st.sidebar.slider("X轴网格点数 (Max 200)", 20, 200, 50)

st.sidebar.header("4. 电压偏置 (Bias)")
col_bias1, col_bias2 = st.sidebar.columns(2)
with col_bias1:
    v_tg = st.number_input("顶栅 Vtg (V)", min_value=-10.0, max_value=20.0, value=10.0, step=0.1, format="%.2f")
    v_bg = st.number_input("底栅 Vbg (V)", min_value=-10.0, max_value=20.0, value=10.0, step=0.1, format="%.2f")
with col_bias2:
    v_ds = st.number_input("漏极 Vds (V)", min_value=0.0, max_value=20.0, value=5.0, step=0.1, format="%.2f")

if st.sidebar.button("开始仿真 (RUN)", type="primary"):
    with st.spinner(f"正在计算... (IGZO层物理网格点: {ny_igzo})"):
        solver = TFTPoissonSolver(
            length=L_um,
            width=W_um,
            t_buf_sin=t_sin_nm/1000.0, eps_buf_sin=eps_sin,
            t_buf_sio=t_buf_sio_nm/1000.0, eps_buf_sio=eps_buf_sio,
            t_igzo=t_igzo_nm/1000.0, eps_igzo=eps_igzo, nd_igzo=1e16,
            t_gi=t_gi_nm/1000.0, eps_gi=eps_gi,
            L_source=L_source_um, Rs_sheet=Rs_sheet,
            L_drain=L_drain_um, Rd_sheet=Rd_sheet,
            structure_type=struct_type,
            nx=nx, 
            ny=ny_igzo 
        )
        
        start = time.time()
        phi, n_conc, E, vd_eff, ids = solver.solve(v_top_gate_bias=v_tg, v_ds=v_ds, v_bot_gate_bias=v_bg)
        elapsed = time.time() - start
        
        st.success(f"计算完成，耗时 {elapsed:.3f}秒 | 有效Vd = {vd_eff:.4f}V | Ids = {ids:.2e}A")
        
        # --- 物理级重采样渲染 ---
        y_phys_cm = solver.y
        x_phys_cm = solver.x
        
        # 1. 提取 IGZO 区域
        # 注意：现在的 IGZO 起始位置变成了 SiN + Buf_SiO 的总厚度
        total_buf_nm = t_sin_nm + t_buf_sio_nm
        
        tol = 1e-10
        y_igzo_start = total_buf_nm / 1e7
        y_igzo_end = (total_buf_nm + t_igzo_nm) / 1e7
        
        idx_igzo = np.where((y_phys_cm >= y_igzo_start - tol) & 
                            (y_phys_cm <= y_igzo_end + tol))[0]
        
        y_igzo_subset = y_phys_cm[idx_igzo]
        phi_igzo_subset = phi[idx_igzo, :]
        
        target_render_ny = 800
        y_hd_cm = np.linspace(y_igzo_subset.min(), y_igzo_subset.max(), target_render_ny)
        
        # 3. 插值电势 (Potential) - 使用 Quadratic 保证平滑
        f_phi = interp1d(y_igzo_subset, phi_igzo_subset, axis=0, kind='quadratic')
        phi_hd = f_phi(y_hd_cm)
        
        # 4. 重算载流子 (Physics)
        v_ch_hd = np.zeros_like(phi_hd)
        for i in range(len(x_phys_cm)):
            v_ch_hd[:, i] = vd_eff * (i / (len(x_phys_cm)-1))
            
        n_hd = solver.calculate_n_from_phi(phi_hd, v_ch_hd)
        n_log_hd = np.log10(n_hd + 1e-30)
        
        # 5. 绘图数据准备
        x_plot = x_phys_cm * 1e4
        # 绘图时 Y 轴归零到 IGZO 界面还是保留绝对坐标? 
        # 这里保留绝对厚度便于观察层结构位置
        y_plot = y_hd_cm * 1e7
        
        z_min, z_max = np.nanmin(n_log_hd), np.nanmax(n_log_hd)
        tick_vals = np.arange(np.floor(z_min), np.ceil(z_max)+0.1, 0.5)
        tick_text = [f"1e{v:.1f}" for v in tick_vals]

        tab1, tab2, tab3 = st.tabs(["载流子浓度 (Carrier)", "垂直切面 (Cut)", "电场分布 (E-Field)"])
        
        with tab1:
            st.subheader("电子浓度 (cm^-3)")
            fig = go.Figure(data=go.Heatmap(
                x=x_plot, y=y_plot, z=n_log_hd,
                colorscale='Jet',
                zsmooth='best', 
                colorbar=dict(title='Concentration', tickvals=tick_vals, ticktext=tick_text),
                hovertemplate='Y: %{y:.2f} nm<br>n: 1e%{z:.2f}<extra></extra>'
            ))
            fig.update_layout(height=500, yaxis_title="IGZO Thickness (nm from Substrate)")
            st.plotly_chart(fig, use_container_width=True)
            
        with tab2:
            st.subheader("垂直切面 (Vertical Profile)")
            mid = n_hd.shape[1] // 2
            fig2 = go.Figure(go.Scatter(x=y_plot, y=n_hd[:, mid], mode='lines', name='n', line=dict(width=3)))
            fig2.update_layout(yaxis_type="log", yaxis_title="n (cm^-3)", xaxis_title="Thickness (nm)")
            st.plotly_chart(fig2, use_container_width=True)
            
        with tab3:
            st.subheader("电场分布 (V/cm)")
            E_subset = E[idx_igzo, :]
            f_E = interp1d(y_igzo_subset, E_subset, axis=0, kind='quadratic')
            E_hd = f_E(y_hd_cm)
            
            fig3 = go.Figure(go.Heatmap(
                x=x_plot, y=y_plot, z=E_hd, colorscale='Hot', zsmooth='best',
                colorbar=dict(title='Field (V/cm)', tickformat='.1e')
            ))
            st.plotly_chart(fig3, use_container_width=True)