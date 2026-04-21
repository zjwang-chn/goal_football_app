#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
足球比分模拟器 - 基于闯关概率模型 (Streamlit 交互版)
功能：主/客队独立进球模拟 → 比分分布统计 → 可视化分析
支持：直接概率粘贴 / 从12个赔率数据自动生成概率
"""

import streamlit as st
import numpy as np
import pandas as pd
import time
import re

# 尝试导入 plotly，若未安装则给出提示
try:
    import plotly.graph_objects as go
    import plotly.express as px
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    st.warning("⚠️ Plotly 未安装，部分图表将使用 Streamlit 原生图表。建议运行: pip install plotly")

# 页面配置
st.set_page_config(
    page_title="⚽ 足球比分模拟器",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义样式
st.markdown("""
<style>
    .main-header {
        font-size: 32px;
        font-weight: bold;
        color: #1F4E79;
        text-align: center;
        margin-bottom: 20px;
    }
    .sub-header {
        font-size: 20px;
        font-weight: 600;
        color: #2C3E50;
        margin-top: 15px;
        margin-bottom: 10px;
        border-bottom: 2px solid #e0e0e0;
        padding-bottom: 5px;
    }
    .metric-box {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 8px;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .metric-value {
        font-size: 28px;
        font-weight: bold;
        color: #1F4E79;
    }
    .metric-label {
        font-size: 14px;
        color: #6c757d;
    }
    input[type=number]::-webkit-inner-spin-button,
    input[type=number]::-webkit-outer-spin-button {
        -webkit-appearance: none;
        margin: 0;
    }
    input[type=number] {
        -moz-appearance: textfield;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-header">⚽ 足球比分模拟器 · 闯关概率模型</p>', unsafe_allow_html=True)

# ================= 侧边栏：参数设置（顺序调整） =================
st.sidebar.header("⚙️ 设置面板")

# ---------- 1. 模拟设置（置于顶部） ----------
st.sidebar.subheader("🔢 模拟设置")
sim_times = st.sidebar.selectbox(
    "选择模拟次数",
    options=[1000, 10000, 100000, 1000000],
    index=3  # 默认100万次
)

run_sim = st.sidebar.button("🚀 开始模拟", type="primary", use_container_width=True)

st.sidebar.markdown("---")

# ---------- 2. 参数设置（两种解析方式 + 手动输入） ----------
st.sidebar.subheader("📊 参数设置")

# --- 方法一：直接粘贴概率 (两列5行) ---
with st.sidebar.expander("📋 方法一：直接粘贴概率", expanded=False):
    st.caption("从Excel复制两列数据（主队|客队），每行一个概率对，共5行")
    paste_area_prob = st.text_area(
        "粘贴概率数据",
        placeholder="例如：\n0.14795 0.12345\n0.33488 0.29876\n0.47788 0.45678\n0.57448 0.54321\n0.64748 0.61234",
        height=150,
        key="paste_prob",
        label_visibility="collapsed"
    )
    if st.button("🔍 解析概率并填充", key="btn_parse_prob", use_container_width=True):
        lines = paste_area_prob.strip().split('\n')
        home_vals = []
        away_vals = []
        error_msg = None
        
        valid_lines = [line.strip() for line in lines if line.strip()]
        if len(valid_lines) < 5:
            error_msg = f"需要5行数据，当前只有 {len(valid_lines)} 行"
        else:
            for i, line in enumerate(valid_lines[:5]):
                parts = re.split(r'[,\s\t]+', line)
                parts = [p for p in parts if p]
                if len(parts) < 2:
                    error_msg = f"第{i+1}行数据不足两列"
                    break
                try:
                    h_val = float(parts[0])
                    a_val = float(parts[1])
                    if not (0 <= h_val <= 1) or not (0 <= a_val <= 1):
                        error_msg = f"第{i+1}行概率值必须在0~1之间"
                        break
                    home_vals.append(h_val)
                    away_vals.append(a_val)
                except ValueError:
                    error_msg = f"第{i+1}行包含非数字内容"
                    break
        
        if error_msg:
            st.error(f"解析失败：{error_msg}")
        else:
            for i in range(5):
                st.session_state[f"home_p_{i}"] = home_vals[i]
                st.session_state[f"away_p_{i}"] = away_vals[i]
            st.success("✅ 概率已填充，可点击开始模拟")
            st.rerun()

# --- 方法二：从赔率数据生成概率 (12个数字) ---
with st.sidebar.expander("📈 方法二：从赔率数据生成", expanded=False):
    st.caption("粘贴12个赔率数据（对应Excel的A2:A13），自动计算E列和J列概率")
    paste_area_odds = st.text_area(
        "粘贴赔率数据（12个数字，可用空格/逗号/换行分隔）",
        placeholder="例如：\n3.65 2.5 3.45 7 19 40 2.9 2.4 3.9 9.6 25 50\n或按行粘贴12个数字",
        height=120,
        key="paste_odds",
        label_visibility="collapsed"
    )
    if st.button("🔍 解析赔率并填充", key="btn_parse_odds", use_container_width=True):
        content = paste_area_odds.replace(',', ' ').replace('\n', ' ').replace('\t', ' ')
        parts = re.findall(r'[\d.]+', content)
        nums = []
        for p in parts:
            try:
                nums.append(float(p))
            except ValueError:
                pass
        
        error_msg = None
        if len(nums) < 12:
            error_msg = f"需要12个赔率数字，当前只解析到 {len(nums)} 个"
        else:
            home_odds = nums[:6]
            away_odds = nums[6:12]
            
            # 计算主队概率 (E2:E6)
            home_sum_inv = sum(1/o for o in home_odds)
            C_home = 1 / home_sum_inv if home_sum_inv != 0 else 0
            D_home = [C_home / o for o in home_odds[:5]]
            E_home = []
            cum_D = 0
            for d in D_home:
                e = d / (1 - cum_D) if (1 - cum_D) > 0 else 0
                E_home.append(e)
                cum_D += d
            
            # 计算客队概率 (J2:J6)
            away_sum_inv = sum(1/o for o in away_odds)
            C_away = 1 / away_sum_inv if away_sum_inv != 0 else 0
            D_away = [C_away / o for o in away_odds[:5]]
            E_away = []
            cum_D = 0
            for d in D_away:
                e = d / (1 - cum_D) if (1 - cum_D) > 0 else 0
                E_away.append(e)
                cum_D += d
            
            for i, val in enumerate(E_home + E_away):
                if not (0 <= val <= 1):
                    error_msg = f"计算出的概率超出0~1范围，请检查赔率数据"
                    break
            
            if error_msg:
                st.error(error_msg)
            else:
                for i in range(5):
                    st.session_state[f"home_p_{i}"] = E_home[i]
                    st.session_state[f"away_p_{i}"] = E_away[i]
                st.success("✅ 赔率已转换为概率并填充，可点击开始模拟")
                st.rerun()

# --- 手动输入区域（始终显示） ---
st.sidebar.subheader("🏠 主队进球概率")
home_probs = []
for i in range(5):
    col1, col2 = st.sidebar.columns([3, 2])
    with col1:
        st.markdown(f"主队 · 第{i+1}球概率")
    with col2:
        default_vals = [0.14795, 0.33488, 0.47788, 0.57448, 0.64748]
        key = f"home_p_{i}"
        if key not in st.session_state:
            st.session_state[key] = default_vals[i]
        p = st.number_input(
            f"home_input_{i}",
            min_value=0.0,
            max_value=1.0,
            value=st.session_state[key],
            format="%.5f",
            step=0.00001,
            label_visibility="collapsed",
            key=key
        )
        home_probs.append(p)

st.sidebar.subheader("🚀 客队进球概率")
away_probs = []
for i in range(5):
    col1, col2 = st.sidebar.columns([3, 2])
    with col1:
        st.markdown(f"客队 · 第{i+1}球概率")
    with col2:
        default_vals = [0.12345, 0.29876, 0.45678, 0.54321, 0.61234]
        key = f"away_p_{i}"
        if key not in st.session_state:
            st.session_state[key] = default_vals[i]
        p = st.number_input(
            f"away_input_{i}",
            min_value=0.0,
            max_value=1.0,
            value=st.session_state[key],
            format="%.5f",
            step=0.00001,
            label_visibility="collapsed",
            key=key
        )
        away_probs.append(p)

# ---------- 3. 规则说明（置于底部） ----------
st.sidebar.markdown("---")
st.sidebar.caption("""
**规则说明**  
- 每队独立模拟，最多进5球  
- 每次射门机会生成随机数(0~1)，≥概率则进球  
- 连续进球直至失败或进满5球  
- 比分组合统计后计算分布  
""")

# ================= 核心模拟函数 =================
def simulate_goals_vectorized(probs, n_sims):
    rand_vals = np.random.random((n_sims, 5))
    success = rand_vals >= np.array(probs)
    goals = np.zeros(n_sims, dtype=int)
    for i in range(n_sims):
        row = success[i]
        if np.all(row):
            goals[i] = 5
        else:
            goals[i] = np.argmin(row)
    return goals

def run_simulation(home_p, away_p, n_sims):
    start_time = time.time()
    home_goals = simulate_goals_vectorized(home_p, n_sims)
    away_goals = simulate_goals_vectorized(away_p, n_sims)
    
    results = pd.DataFrame({
        'home_goals': home_goals,
        'away_goals': away_goals
    })
    results['score'] = results['home_goals'].astype(str) + '-' + results['away_goals'].astype(str)
    results['total_goals'] = results['home_goals'] + results['away_goals']
    
    score_counts = results['score'].value_counts().reset_index()
    score_counts.columns = ['比分', '频次']
    score_counts['概率'] = score_counts['频次'] / n_sims
    score_counts['百分比'] = score_counts['概率'].apply(lambda x: f"{x:.4%}")
    
    home_win_prob = (results['home_goals'] > results['away_goals']).mean()
    draw_prob = (results['home_goals'] == results['away_goals']).mean()
    away_win_prob = (results['home_goals'] < results['away_goals']).mean()
    exp_home = results['home_goals'].mean()
    exp_away = results['away_goals'].mean()
    
    total_goals_dist = results['total_goals'].value_counts().sort_index()
    total_goals_df = pd.DataFrame({
        '总进球': total_goals_dist.index,
        '频次': total_goals_dist.values,
        '概率': total_goals_dist.values / n_sims
    })
    total_goals_df['百分比'] = total_goals_df['概率'].apply(lambda x: f"{x:.4%}")
    
    home_goal_dist = pd.Series(home_goals).value_counts().sort_index()
    away_goal_dist = pd.Series(away_goals).value_counts().sort_index()
    for g in range(6):
        if g not in home_goal_dist.index:
            home_goal_dist[g] = 0
        if g not in away_goal_dist.index:
            away_goal_dist[g] = 0
    home_goal_dist = home_goal_dist.sort_index()
    away_goal_dist = away_goal_dist.sort_index()
    
    elapsed = time.time() - start_time
    
    return {
        'score_counts': score_counts,
        'home_win_prob': home_win_prob,
        'draw_prob': draw_prob,
        'away_win_prob': away_win_prob,
        'exp_home': exp_home,
        'exp_away': exp_away,
        'total_goals_df': total_goals_df,
        'home_goal_dist': home_goal_dist,
        'away_goal_dist': away_goal_dist,
        'n_sims': n_sims,
        'elapsed': elapsed
    }

# ================= 主内容区域 =================
if 'sim_data' not in st.session_state:
    st.session_state.sim_data = None

if run_sim:
    with st.spinner(f"⏳ 正在进行 {sim_times:,} 次模拟，请稍候..."):
        data = run_simulation(home_probs, away_probs, sim_times)
        st.session_state.sim_data = data
    st.success(f"✅ 模拟完成！耗时 {data['elapsed']:.3f} 秒")

data = st.session_state.sim_data

if data is None:
    st.info("👈 请在左侧设置概率并点击 **开始模拟** 按钮")
    st.stop()

# ----------------- 1. 核心指标卡片 -----------------
st.markdown('<p class="sub-header">🎯 核心指标</p>', unsafe_allow_html=True)

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.markdown(f"""
    <div class="metric-box">
        <div class="metric-value">{data['home_win_prob']:.2%}</div>
        <div class="metric-label">🏠 主队胜率</div>
    </div>
    """, unsafe_allow_html=True)
with col2:
    st.markdown(f"""
    <div class="metric-box">
        <div class="metric-value">{data['draw_prob']:.2%}</div>
        <div class="metric-label">🤝 平局概率</div>
    </div>
    """, unsafe_allow_html=True)
with col3:
    st.markdown(f"""
    <div class="metric-box">
        <div class="metric-value">{data['away_win_prob']:.2%}</div>
        <div class="metric-label">🚀 客队胜率</div>
    </div>
    """, unsafe_allow_html=True)
with col4:
    st.markdown(f"""
    <div class="metric-box">
        <div class="metric-value">{data['exp_home']:.3f}</div>
        <div class="metric-label">⚽ 主队预期进球</div>
    </div>
    """, unsafe_allow_html=True)
with col5:
    st.markdown(f"""
    <div class="metric-box">
        <div class="metric-value">{data['exp_away']:.3f}</div>
        <div class="metric-label">⚽ 客队预期进球</div>
    </div>
    """, unsafe_allow_html=True)

# ----------------- 2. 主队/客队进球分布 -----------------
st.markdown('<p class="sub-header">📊 主队 / 客队进球分布</p>', unsafe_allow_html=True)

col_h, col_a = st.columns(2)
with col_h:
    home_dist_df = pd.DataFrame({
        '进球数': data['home_goal_dist'].index,
        '概率': data['home_goal_dist'].values / data['n_sims']
    })
    if PLOTLY_AVAILABLE:
        fig_h = px.bar(home_dist_df, x='进球数', y='概率', title='🏠 主队进球分布',
                       text=home_dist_df['概率'].apply(lambda x: f'{x:.2%}'))
        fig_h.update_traces(textposition='outside')
        fig_h.update_layout(yaxis_tickformat='.0%', height=400)
        st.plotly_chart(fig_h, use_container_width=True)
    else:
        st.bar_chart(home_dist_df.set_index('进球数')['概率'])

with col_a:
    away_dist_df = pd.DataFrame({
        '进球数': data['away_goal_dist'].index,
        '概率': data['away_goal_dist'].values / data['n_sims']
    })
    if PLOTLY_AVAILABLE:
        fig_a = px.bar(away_dist_df, x='进球数', y='概率', title='🚀 客队进球分布',
                       text=away_dist_df['概率'].apply(lambda x: f'{x:.2%}'))
        fig_a.update_traces(textposition='outside')
        fig_a.update_layout(yaxis_tickformat='.0%', height=400)
        st.plotly_chart(fig_a, use_container_width=True)
    else:
        st.bar_chart(away_dist_df.set_index('进球数')['概率'])

# ----------------- 3. 概率前十比分 & 总进球分布 -----------------
st.markdown('<p class="sub-header">🏆 概率前十比分 & 总进球分布</p>', unsafe_allow_html=True)

col_left, col_right = st.columns(2)
sorted_scores = data['score_counts'].sort_values('概率', ascending=False).reset_index(drop=True)

with col_left:
    top10 = sorted_scores.head(10).copy()
    if PLOTLY_AVAILABLE:
        fig_top = px.bar(top10, x='比分', y='概率', text='百分比',
                         title='出现概率最高的10个比分',
                         color='概率', color_continuous_scale='viridis')
        fig_top.update_traces(textposition='outside')
        fig_top.update_layout(yaxis_tickformat='.0%', height=450)
        st.plotly_chart(fig_top, use_container_width=True)
    else:
        st.dataframe(top10[['比分', '百分比']], use_container_width=True)
        st.bar_chart(top10.set_index('比分')['概率'])

with col_right:
    total_df = data['total_goals_df']
    if PLOTLY_AVAILABLE:
        fig_total = px.bar(total_df, x='总进球', y='概率', text='百分比',
                           title='全场总进球数概率分布',
                           color='概率', color_continuous_scale='oranges')
        fig_total.update_traces(textposition='outside')
        fig_total.update_layout(yaxis_tickformat='.0%', height=450)
        st.plotly_chart(fig_total, use_container_width=True)
    else:
        st.bar_chart(total_df.set_index('总进球')['概率'])

with st.expander("📋 查看总进球详细数据"):
    st.dataframe(data['total_goals_df'][['总进球', '频次', '百分比']], hide_index=True, use_container_width=True)

# ----------------- 4. 完整比分概率表 -----------------
st.markdown('<p class="sub-header">📋 完整比分概率表 (按概率降序)</p>', unsafe_allow_html=True)

sorted_scores['累计概率'] = sorted_scores['概率'].cumsum()
sorted_scores['累计百分比'] = sorted_scores['累计概率'].apply(lambda x: f"{x:.2%}")

st.dataframe(
    sorted_scores[['比分', '频次', '百分比', '累计百分比']],
    use_container_width=True,
    hide_index=True
)

# ----------------- 5. 比分分布热力图 -----------------
st.markdown('<p class="sub-header">🔥 比分分布热力图 (百分比标注)</p>', unsafe_allow_html=True)

heatmap_data = np.zeros((6, 6))
for _, row in data['score_counts'].iterrows():
    h, a = map(int, row['比分'].split('-'))
    heatmap_data[h, a] = row['概率'] * 100

if PLOTLY_AVAILABLE:
    fig = go.Figure(data=go.Heatmap(
        z=heatmap_data.T,
        x=['0', '1', '2', '3', '4', '5'],
        y=['0', '1', '2', '3', '4', '5'],
        colorscale='Blues',
        text=np.round(heatmap_data.T, 2),
        texttemplate='%{text}%',
        textfont={"size": 12},
        colorbar=dict(title="概率 (%)"),
        hovertemplate='主队 %{x} : 客队 %{y}<br>概率: %{z:.2f}%<extra></extra>'
    ))
    fig.update_layout(
        title='比分概率热力图 (%)',
        xaxis_title="主队进球",
        yaxis_title="客队进球",
        height=450,
        margin=dict(l=50, r=50, t=50, b=50)
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    hm_df = pd.DataFrame(heatmap_data, 
                         index=[f"主{i}" for i in range(6)], 
                         columns=[f"客{i}" for i in range(6)])
    st.dataframe(hm_df.style.format("{:.2f}%").background_gradient(cmap='Blues', axis=None))

st.markdown("---")
st.caption(f"模拟次数: {data['n_sims']:,} 次 | 基于闯关概率模型 · 每队最多5球")
