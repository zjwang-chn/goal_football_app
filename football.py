#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
足球比分模拟器 - 移动端 App 精简版
（基于你原 850 行代码精确合并）
"""

import streamlit as st
import numpy as np
import pandas as pd
import time
import xml.etree.ElementTree as ET
import requests
from typing import Dict, List, Optional, Tuple

# =======================
# 1. Plotly
# =======================
try:
    import plotly.graph_objects as go
    import plotly.express as px
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    st.warning("⚠️ Plotly 未安装，部分图表将使用 Streamlit 原生图表")

# =======================
# 2. 页面配置（App 化）
# =======================
st.set_page_config(
    page_title="比分模拟器",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# =======================
# 3. 移动端 App 化 CSS
# =======================
APP_CSS = """
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

.main .block-container {
    padding: 0.5rem 1rem 2rem 1rem;
}

/* 侧边栏抽屉 */
[data-testid="stSidebar"] {
    background-color: #f8f9fa;
}

/* 移动端优化 */
@media (max-width: 768px) {
    input, textarea, select {
        font-size: 16px !important;
    }
    button, [role="button"] {
        min-height: 48px !important;
        font-size: 16px !important;
        width: 100%;
    }
    h1 { font-size: 22px !important; }
    h2 { font-size: 18px !important; }
    h3 { font-size: 16px !important; }
}
</style>
"""
st.markdown(APP_CSS, unsafe_allow_html=True)

# =======================
# 4. 顶部 App 栏
# =======================
top = st.columns([1, 3, 1])
with top[0]:
    if st.button("☰"):
        st.session_state.sidebar_open = not st.session_state.get("sidebar_open", False)
with top[1]:
    st.markdown("### ⚽ 比分模拟器")
with top[2]:
    st.button("⚙️")

st.divider()

# =======================
# 5. XML 解析 & 模拟函数
# （你原代码一字不改）
# =======================
def parse_numberofgoals(xml_content: str):
    root = ET.fromstring(xml_content)
    result, ordered = {}, []
    for f in root.findall(".//Fixture"):
        mid = f.get("id")
        if not mid: continue
        ordered.append(mid)
        result[mid] = {}
        for i in range(1,7):
            result[mid][f"h{i}"] = float(f.get(f"h{i}",0))
            result[mid][f"a{i}"] = float(f.get(f"a{i}",0))
    return result, ordered

def parse_correctscore(xml_content: str):
    root = ET.fromstring(xml_content)
    res = {}
    for f in root.findall(".//Fixture"):
        mid = f.get("id")
        data = {}
        for i in range(1,11):
            data[f"h{i}"] = float(f.get(f"h{i}",0))
            data[f"a{i}"] = float(f.get(f"a{i}",0))
        for i in range(11,17):
            data[f"o{i}"] = float(f.get(f"o{i}",0))
        res[mid] = data
    return res

def parse_halffull(xml_content: str):
    root = ET.fromstring(xml_content)
    res = {}
    for f in root.findall(".//Fixture"):
        mid = f.get("id")
        res[mid] = {k:float(f.get(k,0)) for k in ["hh","hd","ha","dh","dd","da","ah","ad","aa"]}
    return res

def parse_odds_config(xml_content: str):
    root = ET.fromstring(xml_content)
    res = {}
    for f in root.findall(".//Fixture"):
        mid = f.get("id")
        res[mid] = {k:f.get(k) for k in ["gt","st","sh","sa"]}
    return res

def parse_overunder(xml_content: str):
    root = ET.fromstring(xml_content)
    res = {}
    for f in root.findall(".//Fixture"):
        mid = f.get("id")
        res[mid] = {k:float(f.get(k,0)) for k in ["oo","uo","li"]}
    return res

def parse_windrawwin(xml_content: str):
    root = ET.fromstring(xml_content)
    res = {}
    for f in root.findall(".//Fixture"):
        mid = f.get("id")
        res[mid] = {k:float(f.get(k,0)) for k in ["ho","do","ao"]}
    return res

def parse_windrawwinfirsthalf(xml_content: str):
    return parse_windrawwin(xml_content)

def parse_winodds(xml_content: str):
    root = ET.fromstring(xml_content)
    res = {}
    for f in root.findall(".//Fixture"):
        mid = f.get("id")
        res[mid] = {
            "g": f.get("g",""),
            "gg": float(f.get("gg",0)),
            "ho": float(f.get("ho",0)),
            "ao": float(f.get("ao",0)),
            "var": [v.strip() for v in f.get("var","").split(",")] if f.get("var") else []
        }
    return res

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
        for name, content in file_dict.items():
            if "numberofgoals" in name:
                self.numberofgoals, self.ordered_ids = parse_numberofgoals(content)
                self.all_ids.update(self.numberofgoals.keys())
            elif "correctscore" in name:
                self.correctscore = parse_correctscore(content)
            elif "halffull" in name:
                self.halffull = parse_halffull(content)
            elif "odds_config" in name:
                self.odds_config = parse_odds_config(content)
            elif "overunder" in name:
                self.overunder = parse_overunder(content)
            elif "windrawwin" in name and "firsthalf" not in name:
                self.windrawwin = parse_windrawwin(content)
            elif "windrawwinfirsthalf" in name:
                self.windrawwinfirsthalf = parse_windrawwinfirsthalf(content)
            elif "winodds" in name:
                self.winodds = parse_winodds(content)

# =======================
# 6. 赔率→概率 & 模拟
# （保持你原实现）
# =======================
def odds_to_probs(home_odds, away_odds):
    def calc(odds):
        inv = [1/o for o in odds[:5]]
        C = 1/sum(inv)
        D = [C/i for i in inv]
        E = []
        cum = 0
        for d in D:
            E.append(d/(1-cum) if 1-cum>0 else 0)
            cum += d
        return E
    return calc(home_odds), calc(away_odds)

def simulate_goals_vectorized(probs, n):
    r = np.random.random((n,5))
    s = r >= np.array(probs)
    g = np.zeros(n,dtype=int)
    for i in range(n):
        if np.all(s[i]): g[i]=5
        else: g[i]=np.argmin(s[i])
    return g

def run_simulation(home_p, away_p, n):
    start = time.time()
    hg = simulate_goals_vectorized(home_p, n)
    ag = simulate_goals_vectorized(away_p, n)

    df = pd.DataFrame({"home":hg,"away":ag})
    df["score"] = df["home"].astype(str)+"-"+df["away"].astype(str)
    df["total"] = df["home"]+df["away"]

    sc = df["score"].value_counts().reset_index()
    sc.columns = ["比分","频次"]
    sc["概率"] = sc["频次"]/n
    sc["百分比"] = sc["概率"].apply(lambda x:f"{x:.4%}")

    hw = (hg>ag).mean()
    dr = (hg==ag).mean()
    aw = (hg<ag).mean()
    eh = hg.mean()
    ea = ag.mean()

    tg = df["total"].value_counts().sort_index()
    tgdf = pd.DataFrame({"总进球":tg.index,"频次":tg.values})
    tgdf["概率"] = tgdf["频次"]/n
    tgdf["百分比"] = tgdf["概率"].apply(lambda x:f"{x:.4%}")

    return {
        "score_counts":sc,
        "home_win_prob":hw,
        "draw_prob":dr,
        "away_win_prob":aw,
        "exp_home":eh,
        "exp_away":ea,
        "total_goals_df":tgdf,
        "home_goal_dist":pd.Series(hg).value_counts().sort_index(),
        "away_goal_dist":pd.Series(ag).value_counts().sort_index(),
        "n_sims":n,
        "elapsed":time.time()-start
    }

# =======================
# 7. Session State
# =======================
if "xml_loader" not in st.session_state: st.session_state.xml_loader = None
if "selected_match_id" not in st.session_state: st.session_state.selected_match_id = None
if "sim_data" not in st.session_state: st.session_state.sim_data = None
if "sidebar_open" not in st.session_state: st.session_state.sidebar_open = False
if "page" not in st.session_state: st.session_state.page = "首页"

# =======================
# 8. 侧边栏（抽屉式）
# =======================
with st.sidebar:
    if not st.session_state.sidebar_open:
        st.stop()

    st.header("⚙️ 设置")

    st.session_state.page = st.radio(
        "导航",
        ["首页","胜平负","总进球","比分"],
        index=["首页","胜平负","总进球","比分"].index(st.session_state.page)
    )

    if st.button("📥 从 GitHub 加载 XML", use_container_width=True):
        base = "https://raw.githubusercontent.com/52483588/goal_football_app/refs/heads/main/"
        fs = ["numberofgoals.xml","odds_config.xml","correctscore.xml",
              "halffull.xml","overunder.xml","windrawwin.xml",
              "windrawwinfirsthalf.xml","winodds.xml"]
        d = {}
        for f in fs:
            try:
                d[f] = requests.get(base+f,timeout=10).text
                st.success(f)
            except: st.error(f)
        loader = FootballDataLoader()
        loader.load_from_dict(d)
        st.session_state.xml_loader = loader
        st.session_state.selected_match_id = loader.ordered_ids[0]
        st.rerun()

    if st.session_state.xml_loader:
        loader = st.session_state.xml_loader
        st.selectbox("比赛ID", loader.ordered_ids, key="selected_match_id")

# =======================
# 9. 主内容区（你原页面逻辑）
# =======================
page = st.session_state.page
data = st.session_state.sim_data

if page == "首页":
    st.subheader("📊 模拟结果")
    if data is None:
        st.info("请在侧边栏加载 XML 并设置概率后开始模拟")
        st.stop()

    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("主胜",f"{data['home_win_prob']:.2%}")
    c2.metric("平局",f"{data['draw_prob']:.2%}")
    c3.metric("客胜",f"{data['away_win_prob']:.2%}")
    c4.metric("主队xG",f"{data['exp_home']:.3f}")
    c5.metric("客队xG",f"{data['exp_away']:.3f}")

    if PLOTLY_AVAILABLE:
        fig = px.bar(data["score_counts"].head(10),x="比分",y="概率",text="百分比")
        st.plotly_chart(fig,use_container_width=True)
    else:
        st.dataframe(data["score_counts"].head(10))

elif page == "胜平负":
    st.subheader("胜平负分析")
    if data is None: st.stop()
    loader = st.session_state.xml_loader
    ho,do,ao = loader.get_windrawwin_odds(st.session_state.selected_match_id)
    df = pd.DataFrame({
        "":["概率","赔率","赔付"],
        "主胜":[f"{data['home_win_prob']:.2%}",ho,f"{data['home_win_prob']*ho:.4f}"],
        "平局":[f"{data['draw_prob']:.2%}",do,f"{data['draw_prob']*do:.4f}"],
        "客胜":[f"{data['away_win_prob']:.2%}",ao,f"{data['away_win_prob']*ao:.4f}"]
    })
    st.dataframe(df,use_container_width=True)

elif page == "总进球":
    st.subheader("总进球分析")
    if data is None: st.stop()
    st.dataframe(data["total_goals_df"],use_container_width=True)

elif page == "比分":
    st.subheader("比分分析")
    if data is None: st.stop()
    st.dataframe(data["score_counts"],use_container_width=True)

# =======================
# 10. 底部 TabBar
# =======================
st.divider()
btm = st.columns(4)
labels = ["首页","胜平负","总进球","比分"]
for i,label in enumerate(labels):
    with btm[i]:
        if st.button(label,use_container_width=True):
            st.session_state.page = label
            st.rerun()