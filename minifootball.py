#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
足球比分模拟器 - 精简版
基于闯关概率模型 (Streamlit 多页面版)
功能：主/客队独立进球模拟 → 比分分布统计 → 可视化分析
自动从GitHub加载预设XML数据，赔率自动转概率
"""
import streamlit as st
import numpy as np
import pandas as pd
import time
import xml.etree.ElementTree as ET
import requests
from typing import Dict, List, Optional, Tuple

# 导入 plotly
try:
    import plotly.graph_objects as go
    import plotly.express as px
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    st.warning("⚠️ Plotly 未安装，部分图表将使用 Streamlit 原生图表。建议运行: pip install plotly")

# ================= XML 解析模块 =================
def parse_numberofgoals(xml_content: str) -> Tuple[Dict[str, Dict], List[str]]:
    root = ET.fromstring(xml_content)
    result = {}
    ordered_ids = []
    for fixture in root.findall(".//Fixture"):
        match_id = fixture.get("id")
        if not match_id:
            continue
        ordered_ids.append(match_id)
        data = {}
        for i in range(1, 7):
            key = f"h{i}"
            val = fixture.get(key)
            if val is not None:
                try:
                    data[key] = float(val)
                except ValueError:
                    data[key] = 0.0
            else:
                data[key] = 0.0
        for i in range(1, 7):
            key = f"a{i}"
            val = fixture.get(key)
            if val is not None:
                try:
                    data[key] = float(val)
                except ValueError:
                    data[key] = 0.0
            else:
                data[key] = 0.0
        result[match_id] = data
    return result, ordered_ids

def parse_correctscore(xml_content: str) -> Dict[str, Dict]:
    root = ET.fromstring(xml_content)
    result = {}
    for fixture in root.findall(".//Fixture"):
        match_id = fixture.get("id")
        if not match_id:
            continue
        data = {}
        for i in range(1, 11):
            data[f"h{i}"] = float(fixture.get(f"h{i}", 0.0))
        for i in range(1, 11):
            data[f"a{i}"] = float(fixture.get(f"a{i}", 0.0))
        for i in range(11, 17):
            data[f"o{i}"] = float(fixture.get(f"o{i}", 0.0))
        result[match_id] = data
    return result

def parse_halffull(xml_content: str) -> Dict[str, Dict]:
    root = ET.fromstring(xml_content)
    result = {}
    fields = ["hh","hd","ha","dh","dd","da","ah","ad","aa"]
    for fixture in root.findall(".//Fixture"):
        match_id = fixture.get("id")
        if not match_id:
            continue
        data = {}
        for f in fields:
            val = fixture.get(f)
            data[f] = float(val) if val is not None else 0.0
        result[match_id] = data
    return result

def parse_odds_config(xml_content: str) -> Dict[str, Dict]:
    root = ET.fromstring(xml_content)
    result = {}
    fields = ["gt","st","sh","sa"]
    for fixture in root.findall(".//Fixture"):
        match_id = fixture.get("id")
        if not match_id:
            continue
        data = {}
        for f in fields:
            val = fixture.get(f)
            if val is not None:
                data[f] = val
            else:
                data[f] = None
        result[match_id] = data
    return result

def parse_overunder(xml_content: str) -> Dict[str, Dict]:
    root = ET.fromstring(xml_content)
    result = {}
    fields = ["oo","uo","li"]
    for fixture in root.findall(".//Fixture"):
        match_id = fixture.get("id")
        if not match_id:
            continue
        data = {}
        for f in fields:
            val = fixture.get(f)
            data[f] = float(val) if val is not None else 0.0
        result[match_id] = data
    return result

def parse_windrawwin(xml_content: str) -> Dict[str, Dict]:
    root = ET.fromstring(xml_content)
    result = {}
    fields = ["ho","do","ao"]
    for fixture in root.findall(".//Fixture"):
        match_id = fixture.get("id")
        if not match_id:
            continue
        data = {}
        for f in fields:
            val = fixture.get(f)
            data[f] = float(val) if val is not None else 0.0
        result[match_id] = data
    return result

def parse_windrawwinfirsthalf(xml_content: str) -> Dict[str, Dict]:
    return parse_windrawwin(xml_content)

def parse_winodds(xml_content: str) -> Dict[str, Dict]:
    root = ET.fromstring(xml_content)
    result = {}
    for fixture in root.findall(".//Fixture"):
        match_id = fixture.get("id")
        if not match_id:
            continue
        data = {}
        data["g"] = fixture.get("g", "")
        data["gg"] = float(fixture.get("gg", 0.0))
        data["ho"] = float(fixture.get("ho", 0.0))
        data["ao"] = float(fixture.get("ao", 0.0))
        var_val = fixture.get("var", "")
        if var_val and var_val.strip():
            data["var"] = [v.strip() for v in var_val.split(",")]
        else:
            data["var"] = []
        result[match_id] = data
    return result

class FootballDataLoader:
    def __init__(self):
        self.numberofgoals = {}
        self.correctscore = {}
        self.halffull = {}
        self.odds_config = {}
        self.overunder = {}
        self.windrawwin = {}
        self.windrawwinfirsthalf = {}
        self.winodds = {}
        self.ordered_ids = []
        self.all_ids = set()

    def load_from_dict(self, file_dict: Dict[str, str]):
        for filename, content in file_dict.items():
            if "numberofgoals" in filename:
                ng_data, ordered = parse_numberofgoals(content)
                self.numberofgoals = ng_data
                self.ordered_ids = ordered
                self.all_ids.update(ng_data.keys())
            elif "correctscore" in filename:
                self.correctscore = parse_correctscore(content)
            elif "halffull" in filename:
                self.halffull = parse_halffull(content)
            elif "odds_config" in filename:
                self.odds_config = parse_odds_config(content)
            elif "overunder" in filename:
                self.overunder = parse_overunder(content)
            elif "windrawwin" in filename and "firsthalf" not in filename:
                self.windrawwin = parse_windrawwin(content)
            elif "windrawwinfirsthalf" in filename:
                self.windrawwinfirsthalf = parse_windrawwinfirsthalf(content)
            elif "winodds" in filename:
                self.winodds = parse_winodds(content)

    def get_odds_for_match(self, match_id: str) -> Tuple[List[float], List[float]]:
        if match_id not in self.numberofgoals:
            return [1.0]*6, [1.0]*6
        data = self.numberofgoals[match_id]
        home_odds = [data.get(f"h{i}", 1.0) for i in range(1, 7)]
        away_odds = [data.get(f"a{i}", 1.0) for i in range(1, 7)]
        return home_odds, away_odds

    def get_match_basic_info(self, match_id: str) -> Dict[str, Optional[str]]:
        if match_id not in self.odds_config:
            return {"gt": None, "st": None, "sh": None, "sa": None}
        cfg = self.odds_config[match_id]
        return {
            "gt": cfg.get("gt"),
            "st": cfg.get("st"),
            "sh": cfg.get("sh"),
            "sa": cfg.get("sa")
        }

    def get_windrawwin_odds(self, match_id: str) -> Tuple[float, float, float]:
        if match_id in self.windrawwin:
            data = self.windrawwin[match_id]
            return data.get("ho", 0.0), data.get("do", 0.0), data.get("ao", 0.0)
        return 0.0, 0.0, 0.0

    def get_overunder_odds(self, match_id: str) -> Tuple[float, float, float]:
        if match_id in self.overunder:
            data = self.overunder[match_id]
            return data.get("oo", 0.0), data.get("uo", 0.0), data.get("li", 0.0)
        return 0.0, 0.0, 0.0

    def get_correctscore_odds(self, match_id: str) -> List[float]:
        if match_id not in self.correctscore:
            return [0.0]*26
        data = self.correctscore[match_id]
        odds = []
        for i in range(1, 11):
            odds.append(data.get(f"h{i}", 0.0))
        for i in range(1, 11):
            odds.append(data.get(f"a{i}", 0.0))
        for i in range(11, 17):
            odds.append(data.get(f"o{i}", 0.0))
        return odds

# ================= 赔率转概率 =================
def odds_to_probs(odds_home: List[float], odds_away: List[float]) -> Tuple[List[float], List[float]]:
    def calc_E(odds_list):
        sum_inv = sum(1/o for o in odds_list)
        C = 1 / sum_inv if sum_inv != 0 else 0
        D = [C / o for o in odds_list[:5]]
        E = []
        cum_D = 0
        for d in D:
            e = d / (1 - cum_D) if (1 - cum_D) > 0 else 0
            E.append(e)
            cum_D += d
        return E
    home_probs = calc_E(odds_home[:6])
    away_probs = calc_E(odds_away[:6])
    return home_probs, away_probs

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

# ================= 页面配置 =================
st.set_page_config(
    page_title="足球比分模拟器",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main-header { font-size: 32px; font-weight: bold; color: #1F4E79; text-align: center; margin-bottom: 20px; }
    .sub-header { font-size: 20px; font-weight: 600; color: #2C3E50; margin-top: 15px; margin-bottom: 10px; border-bottom: 2px solid #e0e0e0; padding-bottom: 5px; }
    .metric-box { background-color: #f8f9fa; padding: 15px; border-radius: 8px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .metric-value { font-size: 28px; font-weight: bold; color: #1F4E79; }
    .metric-label { font-size: 14px; color: #6c757d; }
    /* 固定顶部区域 */
    .sticky-header {
        position: sticky;
        top: 0;
        background-color: white;
        z-index: 100;
        padding: 10px 0 5px 0;
        border-bottom: 1px solid #ddd;
        margin-bottom: 20px;
    }
    /* 水平单选按钮样式 */
    .stRadio > div {
        flex-direction: row;
        gap: 20px;
    }
</style>
""", unsafe_allow_html=True)

# ================= 自动加载XML数据 =================
@st.cache_resource(show_spinner=False)
def load_xml_from_github():
    base_url = "https://raw.githubusercontent.com/52483588/goal_football_app/refs/heads/main/"
    files = [
        "numberofgoals.xml",
        "odds_config.xml",
        "correctscore.xml",
        "halffull.xml",
        "overunder.xml",
        "windrawwin.xml",
        "windrawwinfirsthalf.xml",
        "winodds.xml"
    ]
    xml_files_content = {}
    for filename in files:
        url = base_url + filename
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                xml_files_content[filename] = resp.text
            else:
                st.error(f"❌ {filename} 加载失败 (HTTP {resp.status_code})")
                return None
        except Exception as e:
            st.error(f"❌ {filename} 请求异常: {e}")
            return None
    if len(xml_files_content) >= 8:
        loader = FootballDataLoader()
        loader.load_from_dict(xml_files_content)
        return loader
    else:
        st.error("部分文件加载失败，请检查网络后刷新页面重试。")
        return None

with st.spinner("正在从 GitHub 加载比赛数据，请稍候..."):
    loader = load_xml_from_github()

if loader is None:
    st.stop()

# 初始化会话状态
for i in range(5):
    if f"home_p_{i}" not in st.session_state:
        st.session_state[f"home_p_{i}"] = 0.0
    if f"away_p_{i}" not in st.session_state:
        st.session_state[f"away_p_{i}"] = 0.0

if "selected_match_id" not in st.session_state or st.session_state.selected_match_id not in loader.ordered_ids:
    if loader.ordered_ids:
        st.session_state.selected_match_id = loader.ordered_ids[0]
    else:
        st.error("未找到任何比赛ID，请检查数据源。")
        st.stop()

# 自动转换赔率
def update_probs_from_match_id(match_id):
    home_odds, away_odds = loader.get_odds_for_match(match_id)
    home_probs, away_probs = odds_to_probs(home_odds, away_odds)
    for i in range(5):
        st.session_state[f"home_p_{i}"] = home_probs[i]
        st.session_state[f"away_p_{i}"] = away_probs[i]

if all(st.session_state[f"home_p_{i}"] == 0.0 for i in range(5)):
    update_probs_from_match_id(st.session_state.selected_match_id)

# ================= 顶部固定区域（导航 + 基本信息 + ID选择） =================
with st.container():
    st.markdown('<div class="sticky-header">', unsafe_allow_html=True)
    
    # 水平导航（使用 radio 实现）
    page = st.radio(
        "选择页面",
        ["首页", "胜平负", "总进球", "比分"],
        horizontal=True,
        label_visibility="collapsed",
        key="page_nav"
    )
    
    # 比赛基本信息（水平分布）
    basic = loader.get_match_basic_info(st.session_state.selected_match_id)
    col1, col2, col3, col4 = st.columns(4)
    gt_raw = basic.get("gt")
    if gt_raw and len(gt_raw) >= 15 and gt_raw[4:6].isdigit():
        formatted_gt = f"{gt_raw[:4]}-{gt_raw[4:6]}-{gt_raw[6:8]} {gt_raw[9:]}"
    else:
        formatted_gt = gt_raw or "未提供"
    with col1:
        st.markdown(f"**🕒 时间**<br>{formatted_gt}", unsafe_allow_html=True)
    with col2:
        st.markdown(f"**🏆 赛事**<br>{basic.get('st', '未提供')}", unsafe_allow_html=True)
    with col3:
        st.markdown(f"**🏠 主队**<br>{basic.get('sh', '未提供')}", unsafe_allow_html=True)
    with col4:
        st.markdown(f"**✈️ 客队**<br>{basic.get('sa', '未提供')}", unsafe_allow_html=True)
    
    # 比赛ID选择框（自动触发概率转换）
    selected_id = st.selectbox(
        "选择比赛ID",
        options=loader.ordered_ids,
        index=loader.ordered_ids.index(st.session_state.selected_match_id),
        key="match_id_selector"
    )
    if selected_id != st.session_state.selected_match_id:
        st.session_state.selected_match_id = selected_id
        update_probs_from_match_id(selected_id)
        st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)

# ================= 侧边栏 =================
st.sidebar.header("⚙️ 设置面板")
st.sidebar.subheader("🔢 模拟设置")
sim_times = 1000000
run_sim = st.sidebar.button("🚀 开始模拟", type="primary", use_container_width=True)
st.sidebar.markdown("---")
st.sidebar.caption("""
**规则说明**  
- 每队独立模拟，最多进5球  
- 每次射门机会生成随机数(0~1)，≥概率则进球  
- 连续进球直至失败或进满5球  
- 比分组合统计后计算分布  
""")

# ================= 执行模拟 =================
if 'sim_data' not in st.session_state:
    st.session_state.sim_data = None

if run_sim:
    home_probs = [st.session_state[f"home_p_{i}"] for i in range(5)]
    away_probs = [st.session_state[f"away_p_{i}"] for i in range(5)]
    with st.spinner(f"⏳ 正在进行 {sim_times:,} 次模拟，请稍候..."):
        data = run_simulation(home_probs, away_probs, sim_times)
        st.session_state.sim_data = data
    st.success(f"✅ 模拟完成！耗时 {data['elapsed']:.3f} 秒")

data = st.session_state.sim_data

# ================= 根据页面显示不同内容 =================
if page == "首页":
    st.markdown('<p class="main-header">⚽ 足球比分模拟器 · 闯关概率模型</p>', unsafe_allow_html=True)
    if data is None:
        st.info("👈 请在左侧点击 **开始模拟** 按钮生成结果")
        st.stop()
    
    # 核心指标
    st.markdown('<p class="sub-header">🎯 核心指标</p>', unsafe_allow_html=True)
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.markdown(f'<div class="metric-box"><div class="metric-value">{data["home_win_prob"]:.2%}</div><div class="metric-label">🏠 主队胜率</div></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="metric-box"><div class="metric-value">{data["draw_prob"]:.2%}</div><div class="metric-label">🤝 平局概率</div></div>', unsafe_allow_html=True)
    with col3:
        st.markdown(f'<div class="metric-box"><div class="metric-value">{data["away_win_prob"]:.2%}</div><div class="metric-label">🚀 客队胜率</div></div>', unsafe_allow_html=True)
    with col4:
        st.markdown(f'<div class="metric-box"><div class="metric-value">{data["exp_home"]:.3f}</div><div class="metric-label">⚽ 主队预期进球</div></div>', unsafe_allow_html=True)
    with col5:
        st.markdown(f'<div class="metric-box"><div class="metric-value">{data["exp_away"]:.3f}</div><div class="metric-label">⚽ 客队预期进球</div></div>', unsafe_allow_html=True)
    
    # 主客队进球分布
    st.markdown('<p class="sub-header">📊 主队 / 客队进球分布</p>', unsafe_allow_html=True)
    col_h, col_a = st.columns(2)
    with col_h:
        home_dist_df = pd.DataFrame({'进球数': data['home_goal_dist'].index, '概率': data['home_goal_dist'].values / data['n_sims']})
        if PLOTLY_AVAILABLE:
            fig_h = px.bar(home_dist_df, x='进球数', y='概率', title='🏠 主队进球分布', text=home_dist_df['概率'].apply(lambda x: f'{x:.2%}'))
            fig_h.update_traces(textposition='outside')
            fig_h.update_layout(yaxis_tickformat='.0%', height=400)
            st.plotly_chart(fig_h, use_container_width=True)
        else:
            st.bar_chart(home_dist_df.set_index('进球数')['概率'])
    with col_a:
        away_dist_df = pd.DataFrame({'进球数': data['away_goal_dist'].index, '概率': data['away_goal_dist'].values / data['n_sims']})
        if PLOTLY_AVAILABLE:
            fig_a = px.bar(away_dist_df, x='进球数', y='概率', title='🚀 客队进球分布', text=away_dist_df['概率'].apply(lambda x: f'{x:.2%}'))
            fig_a.update_traces(textposition='outside')
            fig_a.update_layout(yaxis_tickformat='.0%', height=400)
            st.plotly_chart(fig_a, use_container_width=True)
        else:
            st.bar_chart(away_dist_df.set_index('进球数')['概率'])
    
    # 概率前十比分 & 总进球分布
    st.markdown('<p class="sub-header">🏆 概率前十比分 & 总进球分布</p>', unsafe_allow_html=True)
    col_left, col_right = st.columns(2)
    sorted_scores = data['score_counts'].sort_values('概率', ascending=False).reset_index(drop=True)
    with col_left:
        top10 = sorted_scores.head(10).copy()
        if PLOTLY_AVAILABLE:
            fig_top = px.bar(top10, x='比分', y='概率', text='百分比', title='出现概率最高的10个比分', color='概率', color_continuous_scale='viridis')
            fig_top.update_traces(textposition='outside')
            fig_top.update_layout(yaxis_tickformat='.0%', height=450)
            st.plotly_chart(fig_top, use_container_width=True)
        else:
            st.dataframe(top10[['比分', '百分比']], use_container_width=True)
            st.bar_chart(top10.set_index('比分')['概率'])
    with col_right:
        total_df = data['total_goals_df']
        if PLOTLY_AVAILABLE:
            fig_total = px.bar(total_df, x='总进球', y='概率', text='百分比', title='全场总进球数概率分布', color='概率', color_continuous_scale='oranges')
            fig_total.update_traces(textposition='outside')
            fig_total.update_layout(yaxis_tickformat='.0%', height=450)
            st.plotly_chart(fig_total, use_container_width=True)
        else:
            st.bar_chart(total_df.set_index('总进球')['概率'])
    
    # 比分分布热力图
    st.markdown('<p class="sub-header">🔥 比分分布热力图 (百分比标注)</p>', unsafe_allow_html=True)
    heatmap_data = np.zeros((6, 6))
    for _, row in data['score_counts'].iterrows():
        h, a = map(int, row['比分'].split('-'))
        heatmap_data[h, a] = row['概率'] * 100
    if PLOTLY_AVAILABLE:
        fig = go.Figure(data=go.Heatmap(z=heatmap_data.T, x=['0','1','2','3','4','5'], y=['0','1','2','3','4','5'], colorscale='Blues', text=np.round(heatmap_data.T,2), texttemplate='%{text}%', textfont={"size":12}, colorbar=dict(title="概率 (%)"), hovertemplate='主队 %{x} : 客队 %{y}<br>概率: %{z:.2f}%<extra></extra>'))
        fig.update_layout(title='比分概率热力图 (%)', xaxis_title="主队进球", yaxis_title="客队进球", height=450)
        st.plotly_chart(fig, use_container_width=True)
    else:
        hm_df = pd.DataFrame(heatmap_data, index=[f"主{i}" for i in range(6)], columns=[f"客{i}" for i in range(6)])
        st.dataframe(hm_df.style.format("{:.2f}%").background_gradient(cmap='Blues', axis=None))
    st.caption(f"模拟次数: {data['n_sims']:,} 次 | 基于闯关概率模型 · 每队最多5球")

elif page == "胜平负":
    st.markdown('<p class="main-header">⚽ 足球比分模拟器 · 闯关概率模型之胜平负</p>', unsafe_allow_html=True)
    if data is None:
        st.info("请先在首页完成模拟，再查看胜平负页面。")
        st.stop()
    match_id = st.session_state.selected_match_id
    ho, do, ao = loader.get_windrawwin_odds(match_id)
    probs = [data['home_win_prob'], data['draw_prob'], data['away_win_prob']]
    odds = [ho, do, ao]
    payouts = [probs[i] * odds[i] for i in range(3)]
    df_win = pd.DataFrame({"项目": ["概率", "赔率", "赔付 (概率×赔率)"], "主胜": [f"{probs[0]:.2%}", f"{odds[0]:.2f}", f"{payouts[0]:.4f}"], "平局": [f"{probs[1]:.2%}", f"{odds[1]:.2f}", f"{payouts[1]:.4f}"], "客胜": [f"{probs[2]:.2%}", f"{odds[2]:.2f}", f"{payouts[2]:.4f}"]})
    st.dataframe(df_win, use_container_width=True, hide_index=True)
    if PLOTLY_AVAILABLE:
        fig = px.bar(x=["主胜","平局","客胜"], y=payouts, text=[f"{p:.4f}" for p in payouts], labels={'x':'结果','y':'期望赔付'}, title='各结果期望赔付对比', color=["主胜","平局","客胜"], color_discrete_sequence=['#2ecc71','#f39c12','#e74c3c'])
        fig.update_traces(textposition='outside')
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.bar_chart(pd.DataFrame({'赔付':payouts}, index=["主胜","平局","客胜"]))

elif page == "总进球":
    st.markdown('<p class="main-header">⚽ 足球比分模拟器 · 闯关概率模型之总进球</p>', unsafe_allow_html=True)
    if data is None:
        st.info("请先在首页完成模拟，再查看总进球页面。")
        st.stop()
    match_id = st.session_state.selected_match_id
    oo, uo, li = loader.get_overunder_odds(match_id)
    X = li / 4.0 if li != 0 else 0.0
    total_df = data['total_goals_df'].copy()
    total_df['概率数值'] = total_df['概率']
    def calc_size(row):
        goals = row['总进球']
        prob = row['概率数值']
        if goals > X:
            return oo * prob
        elif goals == X:
            return 0.0
        else:
            return uo * prob * -1
    total_df['大小'] = total_df.apply(calc_size, axis=1)
    total_row = pd.DataFrame({'总进球':['总计'], '频次':[total_df['频次'].sum()], '概率':[total_df['概率数值'].sum()], '百分比':[f"{total_df['概率数值'].sum():.2%}"], '概率数值':[total_df['概率数值'].sum()], '大小':[total_df['大小'].sum()]})
    total_df = pd.concat([total_df, total_row], ignore_index=True)
    display_df = total_df[['总进球','频次','百分比','大小']].copy()
    display_df['大小'] = display_df['大小'].apply(lambda x: f"{x:.4f}")
    st.markdown(f"**大小球临界值 X = li/4 = {X:.2f}**")
    st.dataframe(display_df, use_container_width=True, hide_index=True)
    if PLOTLY_AVAILABLE and len(total_df) > 1:
        plot_df = total_df[total_df['总进球'] != '总计'].copy()
        fig = px.bar(plot_df, x='总进球', y='大小', title='大小球期望值 (正为大球，负为小球)', text=plot_df['大小'].apply(lambda x: f"{x:.3f}"))
        fig.update_traces(textposition='outside')
        st.plotly_chart(fig, use_container_width=True)

elif page == "比分":
    st.markdown('<p class="main-header">⚽ 足球比分模拟器 · 闯关概率模型之比分</p>', unsafe_allow_html=True)
    if data is None:
        st.info("请先在首页完成模拟，再查看比分页面。")
        st.stop()
    match_id = st.session_state.selected_match_id
    cs_odds = loader.get_correctscore_odds(match_id)
    fixed_scores = ["1-0","2-0","2-1","3-0","3-1","3-2","4-0","4-1","4-2","4-3","0-1","0-2","1-2","0-3","1-3","2-3","0-4","1-4","2-4","3-4","0-0","1-1","2-2","3-3","4-4","其他"]
    odds_mapping = {}
    for i, score in enumerate(fixed_scores[:20]):
        if i < 10:
            odds_mapping[score] = cs_odds[i]
        else:
            odds_mapping[score] = cs_odds[10 + (i-10)]
    for j, score in enumerate(["0-0","1-1","2-2","3-3","4-4"]):
        odds_mapping[score] = cs_odds[20 + j] if 20+j < len(cs_odds) else 0.0
    odds_mapping["其他"] = cs_odds[25] if len(cs_odds) > 25 else 0.0
    prob_dict = dict(zip(data['score_counts']['比分'], data['score_counts']['概率']))
    rows = []
    other_prob = 0.0
    for score in fixed_scores:
        if score == "其他":
            continue
        prob = prob_dict.pop(score, 0.0)
        rows.append({"比分":score, "概率":prob, "赔率":odds_mapping.get(score,0.0), "赔付":prob * odds_mapping.get(score,0.0)})
    other_prob = sum(prob_dict.values())
    rows.append({"比分":"其他", "概率":other_prob, "赔率":odds_mapping.get("其他",0.0), "赔付":other_prob * odds_mapping.get("其他",0.0)})
    df_scores = pd.DataFrame(rows)
    df_scores['概率'] = df_scores['概率'].apply(lambda x: f"{x:.4%}")
    df_scores['赔率'] = df_scores['赔率'].apply(lambda x: f"{x:.2f}" if x != 0 else "-")
    df_scores['赔付'] = df_scores['赔付'].apply(lambda x: f"{x:.4f}")
    if st.button("📊 按赔付值从大到小排序"):
        sorted_rows = sorted(rows, key=lambda x: x['赔付'], reverse=True)
        df_scores = pd.DataFrame(sorted_rows)
        df_scores['概率'] = df_scores['概率'].apply(lambda x: f"{x:.4%}")
        df_scores['赔率'] = df_scores['赔率'].apply(lambda x: f"{x:.2f}" if x != 0 else "-")
        df_scores['赔付'] = df_scores['赔付'].apply(lambda x: f"{x:.4f}")
    st.dataframe(df_scores, use_container_width=True, hide_index=True)

st.markdown("---")
st.caption("数据基于闯关概率模型模拟生成，实际结果可能因随机性有所波动。")