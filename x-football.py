#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
足球比分模拟器 - 精简版 (优化版)
基于闯关概率模型 (Streamlit 多页面版)
功能：主/客队独立进球模拟 → 比分分布统计 → 可视化分析
自动从GitHub加载预设XML数据，赔率自动转概率
轮次模拟页面：基于动态概率的回合制模拟（规则已升级：每轮比较par值决定进攻顺序）
"""

import streamlit as st
import numpy as np
import pandas as pd
import time
import xml.etree.ElementTree as ET
import requests
from typing import Dict, List, Optional, Tuple
import random
import math
import datetime
import gc
import io

# 导入 plotly
try:
    import plotly.graph_objects as go
    import plotly.express as px
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    st.warning("⚠️ Plotly 未安装，部分图表将使用 Streamlit 原生图表。建议运行: pip install plotly")

# ================= 常量定义 =================
MAX_GOALS = 5  # 最大进球数（根据赔率表定义）

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

    def get_halffull_odds(self, match_id: str) -> Dict[str, float]:
        if match_id in self.halffull:
            return self.halffull[match_id]
        return {f: 0.0 for f in ["hh","hd","ha","dh","dd","da","ah","ad","aa"]}

    def get_windrawwinfirsthalf_odds(self, match_id: str) -> Tuple[float, float, float]:
        if match_id in self.windrawwinfirsthalf:
            data = self.windrawwinfirsthalf[match_id]
            return data.get("ho", 0.0), data.get("do", 0.0), data.get("ao", 0.0)
        return 0.0, 0.0, 0.0

    def get_winodds_info(self, match_id: str) -> Dict:
        if match_id in self.winodds:
            return self.winodds[match_id]
        return {"g": "", "gg": 0.0, "ho": 0.0, "ao": 0.0, "var": []}

# ================= 赔率转概率 =================
def odds_to_probs(odds_home: List[float], odds_away: List[float]) -> Tuple[List[float], List[float]]:
    def calc_E(odds_list):
        sum_inv = sum(1 / o for o in odds_list[:6])  # 确保只取前6个
        if sum_inv == 0:
            return [0.0] * 5
        C = 1 / sum_inv
        D = [C / o for o in odds_list[:5]]  # 只取前5个
        E = []
        cum_D = 0
        for d in D:
            e = d / (1 - cum_D) if (1 - cum_D) > 0 else 0
            E.append(e)
            cum_D += d
        return E

    # 确保odds长度至少为6
    if len(odds_home) < 6:
        odds_home = odds_home + [1.0] * (6 - len(odds_home))
    if len(odds_away) < 6:
        odds_away = odds_away + [1.0] * (6 - len(odds_away))

    home_probs = calc_E(odds_home[:6])  # 明确传入前6个
    away_probs = calc_E(odds_away[:6])  # 明确传入前6个

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

# ================= 轮次模拟模型 =================
def calculate_probabilities(odds_list):
    inv_sum = sum(1.0 / o for o in odds_list)
    factor = 1.0 / inv_sum
    probs = [factor / o for o in odds_list]
    no_goal_probs = []
    cum = 0.0
    for p in probs:
        if cum == 0:
            no_goal = p
        else:
            no_goal = p / (1 - cum)
        no_goal_probs.append(no_goal)
        cum += p
    par_list = []
    for ng in no_goal_probs:
        ng_safe = max(ng, 1e-10)
        if ng >= 1.0:
            par = 0.0
        else:
            par = -math.log(ng_safe)
        par_list.append(par)
    return probs, no_goal_probs, par_list

def simulate_one_match(home_no_goal_probs, home_par, away_no_goal_probs, away_par):
    home_goals = 0
    away_goals = 0
    round_history = []
    rounds = 0
    rand = random.random

    while True:
        rounds += 1
        p_home = home_par[home_goals]
        p_away = away_par[away_goals]
        if p_home > p_away:
            attacker = "home"
        elif p_away > p_home:
            attacker = "away"
        else:
            attacker = "home"

        if attacker == "home":
            r = rand()
            if r < home_no_goal_probs[home_goals]:
                r2 = rand()
                if r2 < away_no_goal_probs[away_goals]:
                    round_history.append({
                        "轮次": rounds,
                        "进攻方": "主队 -> 客队",
                        "主队随机数": round(r, 6),
                        "主队是否进球": "否",
                        "客队随机数": round(r2, 6),
                        "客队是否进球": "否",
                        "当前比分": f"{home_goals}-{away_goals}"
                    })
                    break
                else:
                    away_goals += 1
                    round_history.append({
                        "轮次": rounds,
                        "进攻方": "主队 -> 客队",
                        "主队随机数": round(r, 6),
                        "主队是否进球": "否",
                        "客队随机数": round(r2, 6),
                        "客队是否进球": "是",
                        "当前比分": f"{home_goals}-{away_goals}"
                    })
            else:
                home_goals += 1
                round_history.append({
                    "轮次": rounds,
                    "进攻方": "主队",
                    "主队随机数": round(r, 6),
                    "主队是否进球": "是",
                    "客队随机数": "",
                    "客队是否进球": "",
                    "当前比分": f"{home_goals}-{away_goals}"
                })
        else:
            r = rand()
            if r < away_no_goal_probs[away_goals]:
                r2 = rand()
                if r2 < home_no_goal_probs[home_goals]:
                    round_history.append({
                        "轮次": rounds,
                        "进攻方": "客队 -> 主队",
                        "主队随机数": round(r2, 6),
                        "主队是否进球": "否",
                        "客队随机数": round(r, 6),
                        "客队是否进球": "否",
                        "当前比分": f"{home_goals}-{away_goals}"
                    })
                    break
                else:
                    home_goals += 1
                    round_history.append({
                        "轮次": rounds,
                        "进攻方": "客队 -> 主队",
                        "主队随机数": round(r2, 6),
                        "主队是否进球": "是",
                        "客队随机数": round(r, 6),
                        "客队是否进球": "否",
                        "当前比分": f"{home_goals}-{away_goals}"
                    })
            else:
                away_goals += 1
                round_history.append({
                    "轮次": rounds,
                    "进攻方": "客队",
                    "主队随机数": "",
                    "主队是否进球": "",
                    "客队随机数": round(r, 6),
                    "客队是否进球": "是",
                    "当前比分": f"{home_goals}-{away_goals}"
                })

        if home_goals >= MAX_GOALS or away_goals >= MAX_GOALS:
            break

    return {
        "final_score": f"{home_goals}-{away_goals}",
        "home_goals": home_goals,
        "away_goals": away_goals,
        "rounds": rounds,
        "history": pd.DataFrame(round_history)
    }

def simulate_matches(home_no_goal_probs, home_par, away_no_goal_probs, away_par, n, progress_bar=None):
    results = []
    for i in range(n):
        res = simulate_one_match(home_no_goal_probs, home_par, away_no_goal_probs, away_par)
        results.append({
            "final_score": res["final_score"],
            "home_goals": res["home_goals"],
            "away_goals": res["away_goals"],
            "rounds": res["rounds"]
        })
        if progress_bar is not None:
            progress_bar.progress((i + 1) / n, text=f"模拟进度: {i+1}/{n}")
    return pd.DataFrame(results)


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
    .sticky-header {
        position: sticky;
        top: 0;
        background-color: white;
        z-index: 100;
        padding: 10px 0 5px 0;
        border-bottom: 1px solid #ddd;
        margin-bottom: 20px;
    }
    .stRadio > div {
        flex-direction: row;
        gap: 20px;
    }
    .highlight-row {
        background-color: #d4edda !important;
    }
</style>
""", unsafe_allow_html=True)

# ================= 自动加载XML数据 (无TTL缓存) =================
@st.cache_resource
def load_xml_from_github():
    base_url = "https://raw.githubusercontent.com/52483588/xml/refs/heads/main/"
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

# ================= 全局辅助函数 =================
def update_probs_from_match_id(match_id):
    """根据比赛ID更新session_state中的概率值"""
    home_odds, away_odds = loader.get_odds_for_match(match_id)
    if not home_odds or len(home_odds) < 6:
        home_odds = [1.0] * 6
    if not away_odds or len(away_odds) < 6:
        away_odds = [1.0] * 6
    home_probs, away_probs = odds_to_probs(home_odds, away_odds)
    if len(home_probs) < 5:
        home_probs = home_probs + [0.0] * (5 - len(home_probs))
    if len(away_probs) < 5:
        away_probs = away_probs + [0.0] * (5 - len(away_probs))
    for i in range(5):
        st.session_state[f"home_p_{i}"] = home_probs[i] if i < len(home_probs) else 0.0
        st.session_state[f"away_p_{i}"] = away_probs[i] if i < len(away_probs) else 0.0

# ================= 构建联赛 -> 比赛ID映射 =================
@st.cache_data(ttl=3600)
def get_league_match_map(_loader):
    """从 odds_config 中构建 联赛名 -> 比赛ID列表 的字典，按联赛名排序，每个联赛内按ID数字排序"""
    league_map = {}
    for match_id, cfg in _loader.odds_config.items():
        league = cfg.get("st", "未分类")
        league_map.setdefault(league, []).append(match_id)
    # 对每个联赛内的ID进行排序（数字排序）
    for league in league_map:
        league_map[league] = sorted(league_map[league], key=lambda x: int(x) if x.isdigit() else x)
    # 返回按联赛名排序的字典
    return dict(sorted(league_map.items()))

league_match_map = get_league_match_map(loader)
st.session_state['league_match_map'] = league_match_map

# 初始化会话状态
for i in range(5):
    if f"home_p_{i}" not in st.session_state:
        st.session_state[f"home_p_{i}"] = 0.0
    if f"away_p_{i}" not in st.session_state:
        st.session_state[f"away_p_{i}"] = 0.0

# 初始化选中的比赛ID（取第一个联赛的第一个比赛）
if "selected_match_id" not in st.session_state:
    first_league = list(league_match_map.keys())[0]
    first_match = league_match_map[first_league][0]
    st.session_state.selected_match_id = first_match

# 确保当前选中的 match_id 有效（可能因为数据刷新而变化）
current_mid = st.session_state.selected_match_id
valid = False
for league, ids in league_match_map.items():
    if current_mid in ids:
        valid = True
        break
if not valid:
    first_league = list(league_match_map.keys())[0]
    st.session_state.selected_match_id = league_match_map[first_league][0]

# 更新概率（如果全为0则执行一次）
if all(st.session_state[f"home_p_{i}"] == 0.0 for i in range(5)):
    update_probs_from_match_id(st.session_state.selected_match_id)

if 'sim_data' not in st.session_state:
    st.session_state.sim_data = None

# 新增：分析记录库（存储核心+轮次合并记录）
if 'analysis_records' not in st.session_state:
    st.session_state.analysis_records = []

def update_or_add_core_record(match_id: str, core_data: dict) -> None:
    """
    更新或添加核心模拟记录（基础模拟部分）
    core_data 应包含:
        - home_win_prob, draw_prob, away_win_prob (数值)
        - exp_home, exp_away (数值)
        - exp_ho, exp_do, exp_ao (数值)
    """
    # 获取比赛基本信息
    basic = loader.get_match_basic_info(match_id)
    gt_raw = basic.get("gt", "")
    if gt_raw and len(gt_raw) >= 14 and gt_raw[4:6].isdigit():
        formatted_gt = f"{gt_raw[:4]}-{gt_raw[4:6]}-{gt_raw[6:8]} {gt_raw[9:]}"
    else:
        formatted_gt = gt_raw or "未知"
    st_name = basic.get("st", "未知")
    sh = basic.get("sh", "未知")
    sa = basic.get("sa", "未知")

    # 查找是否已有该比赛的记录
    existing_index = None
    for i, rec in enumerate(st.session_state.analysis_records):
        if rec.get("match_id") == match_id:
            existing_index = i
            break

    new_record = {
        "match_id": match_id,
        "时间": formatted_gt,
        "赛事": st_name,
        "主队": sh,
        "客队": sa,
        "主胜概率": f"{core_data['home_win_prob']:.2%}",
        "平局概率": f"{core_data['draw_prob']:.2%}",
        "客胜概率": f"{core_data['away_win_prob']:.2%}",
        "主队预期进球": f"{core_data['exp_home']:.3f}",
        "客队预期进球": f"{core_data['exp_away']:.3f}",
        "期望赔付(主胜)": f"{core_data['exp_ho']:.4f}",
        "期望赔付(平局)": f"{core_data['exp_do']:.4f}",
        "期望赔付(客胜)": f"{core_data['exp_ao']:.4f}",
        "轮次>10%": "待模拟",
        "记录时间": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    if existing_index is not None:
        # 更新现有记录，但保留原有的轮次字段（如果不为待模拟）
        old_record = st.session_state.analysis_records[existing_index]
        old_record.update(new_record)
        if old_record.get("轮次>10%") != "待模拟":
            new_record["轮次>10%"] = old_record["轮次>10%"]
        st.session_state.analysis_records[existing_index] = new_record
    else:
        st.session_state.analysis_records.append(new_record)

def update_rounds_record(match_id: str, high_prob_rounds: List[int]) -> None:
    """更新指定比赛的轮次字段"""
    round_str = ", ".join(map(str, high_prob_rounds)) if high_prob_rounds else "无"
    for rec in st.session_state.analysis_records:
        if rec.get("match_id") == match_id:
            rec["轮次>10%"] = round_str
            rec["记录时间"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            break

# ================= 顶部固定区域 =================
with st.container():
    st.markdown('<div class="sticky-header">', unsafe_allow_html=True)
    page = st.radio(
        "选择页面",
        ["首页", "赔率一览", "总进球", "比分", "轮次模拟", "分析记录库"],
        horizontal=True,
        label_visibility="collapsed",
        key="page_nav"
    )
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

    # ---- 联赛 + 比赛ID 联动选择 ----
    league_map = st.session_state.get('league_match_map', {})
    if not league_map:
        st.error("联赛数据缺失，请检查 odds_config.xml")
        st.stop()

    # 确认当前选中的 match_id 属于哪个联赛
    current_mid = st.session_state.selected_match_id
    current_league = None
    for league, ids in league_map.items():
        if current_mid in ids:
            current_league = league
            break
    if current_league is None:
        first_league = list(league_map.keys())[0]
        current_mid = league_map[first_league][0]
        st.session_state.selected_match_id = current_mid
        current_league = first_league
        update_probs_from_match_id(current_mid)

    selected_league = st.selectbox(
        "选择联赛",
        options=list(league_map.keys()),
        index=list(league_map.keys()).index(current_league),
        key="league_selector"
    )
    match_ids_in_league = league_map[selected_league]
    if st.session_state.selected_match_id not in match_ids_in_league:
        st.session_state.selected_match_id = match_ids_in_league[0]
        update_probs_from_match_id(st.session_state.selected_match_id)

    selected_match_id = st.selectbox(
        "选择比赛",
        options=match_ids_in_league,
        format_func=lambda mid: f"{mid} - {loader.get_match_basic_info(mid).get('sh', '?')} vs {loader.get_match_basic_info(mid).get('sa', '?')}",
        index=match_ids_in_league.index(st.session_state.selected_match_id),
        key="match_id_selector_new"
    )
    if selected_match_id != st.session_state.selected_match_id:
        st.session_state.selected_match_id = selected_match_id
        update_probs_from_match_id(selected_match_id)
        st.rerun()
    # ---------------------------------

    st.markdown('</div>', unsafe_allow_html=True)

# ================= 侧边栏 =================
st.sidebar.header("⚙️ 设置面板")
st.sidebar.subheader("🔢 模拟设置")
sim_times = 1000000
run_sim = st.sidebar.button("🚀 开始模拟", type="primary", use_container_width=True)
if st.sidebar.button("🔄 刷新数据源", use_container_width=True):
    st.cache_resource.clear()
    st.cache_data.clear()
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.caption("""
**规则说明**  
- 每队独立模拟，最多进5球  
- 每次射门机会生成随机数(0~1)，≥概率则进球  
- 连续进球直至失败或进满5球  
- 比分组合统计后计算分布  
""")

# ================= 执行基础模拟 =================
if run_sim:
    home_probs = [st.session_state[f"home_p_{i}"] for i in range(5)]
    away_probs = [st.session_state[f"away_p_{i}"] for i in range(5)]
    with st.spinner(f"⏳ 正在进行 {sim_times:,} 次模拟，请稍候..."):
        data = run_simulation(home_probs, away_probs, sim_times)
        st.session_state.sim_data = data

        # --- 核心数据记录到分析库 ---
        match_id = st.session_state.selected_match_id
        ho, do, ao = loader.get_windrawwin_odds(match_id)
        core = {
            "home_win_prob": data['home_win_prob'],
            "draw_prob": data['draw_prob'],
            "away_win_prob": data['away_win_prob'],
            "exp_home": data['exp_home'],
            "exp_away": data['exp_away'],
            "exp_ho": data['home_win_prob'] * ho,
            "exp_do": data['draw_prob'] * do,
            "exp_ao": data['away_win_prob'] * ao,
        }
        update_or_add_core_record(match_id, core)
        # ---

    st.success(f"✅ 模拟完成！耗时 {data['elapsed']:.3f} 秒，核心结果已添加到「分析记录库」。")

# ================= 页面内容 =================
# 从 session state 获取模拟结果（可能为 None）
data = st.session_state.sim_data

if page == "首页":
    st.markdown('<p class="main-header">⚽ 足球比分模拟器 · 闯关概率模型</p>', unsafe_allow_html=True)
    if data is None:
        st.info("👈 请在左侧点击 **开始模拟** 按钮生成结果")
        st.stop()

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

    st.markdown('<p class="sub-header">📊 胜平负概率与赔付</p>', unsafe_allow_html=True)
    match_id = st.session_state.selected_match_id
    ho, do, ao = loader.get_windrawwin_odds(match_id)
    probs = [data['home_win_prob'], data['draw_prob'], data['away_win_prob']]
    odds = [ho, do, ao]
    payouts = [probs[i] * odds[i] for i in range(3)]
    df_win = pd.DataFrame({
        "项目": ["概率", "赔率", "期望赔付 (概率×赔率)"],
        "主胜": [f"{probs[0]:.2%}", f"{odds[0]:.2f}", f"{payouts[0]:.4f}"],
        "平局": [f"{probs[1]:.2%}", f"{odds[1]:.2f}", f"{payouts[1]:.4f}"],
        "客胜": [f"{probs[2]:.2%}", f"{odds[2]:.2f}", f"{payouts[2]:.4f}"]
    })
    st.dataframe(df_win, use_container_width=True, hide_index=True)

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
    st.caption(f"模拟次数: {data['n_sims']:,} 次 ")

elif page == "赔率一览":
    st.markdown('<p class="main-header">📋 赔率一览</p>', unsafe_allow_html=True)
    match_id = st.session_state.selected_match_id

    st.markdown('<p class="sub-header">🏟️ 比赛信息 (odds_config.xml)</p>', unsafe_allow_html=True)
    basic = loader.get_match_basic_info(match_id)
    df_info = pd.DataFrame([{
        "时间": basic.get("gt", ""),
        "赛事": basic.get("st", ""),
        "主队": basic.get("sh", ""),
        "客队": basic.get("sa", "")
    }])
    st.dataframe(df_info, use_container_width=True, hide_index=True)

    st.markdown('<p class="sub-header">⚽ 进球数赔率 (numberofgoals.xml)</p>', unsafe_allow_html=True)
    home_odds, away_odds = loader.get_odds_for_match(match_id)
    df_goals = pd.DataFrame({
        "进球数": list(range(6)),
        "主队赔率": home_odds,
        "客队赔率": away_odds
    })
    st.dataframe(df_goals, use_container_width=True, hide_index=True)

    st.markdown('<p class="sub-header">🎯 正确比分 & 半全场赔率</p>', unsafe_allow_html=True)
    col_left, col_right = st.columns(2)

    with col_left:
        cs_odds = loader.get_correctscore_odds(match_id)
        cs_labels = [
            "1-0","2-0","2-1","3-0","3-1","3-2","4-0","4-1","4-2","4-3",
            "0-1","0-2","1-2","0-3","1-3","2-3","0-4","1-4","2-4","3-4",
            "0-0","1-1","2-2","3-3","4-4","其他"
        ]
        if len(cs_odds) < 26:
            cs_odds = cs_odds + [0.0] * (26 - len(cs_odds))
        df_cs = pd.DataFrame({"比分": cs_labels, "赔率": cs_odds[:26]})
        st.dataframe(df_cs, use_container_width=True, hide_index=True)

    with col_right:
        hf = loader.get_halffull_odds(match_id)
        half_full_labels = [
            "胜胜(hh)", "胜平(hd)", "胜负(ha)",
            "平胜(dh)", "平平(dd)", "平负(da)",
            "负胜(ah)", "负平(ad)", "负负(aa)"
        ]
        ordered_keys = ["hh", "hd", "ha", "dh", "dd", "da", "ah", "ad", "aa"]
        hf_values = [hf.get(k, 0.0) for k in ordered_keys]
        df_hf = pd.DataFrame({"选项": half_full_labels, "赔率": hf_values})
        st.dataframe(df_hf, use_container_width=True, hide_index=True)

    st.markdown('<p class="sub-header">📏 大小球 & 胜平负赔率 & 上半场胜平负</p>', unsafe_allow_html=True)
    col_ou, col_win, col_fh = st.columns(3)

    with col_ou:
        oo, uo, li = loader.get_overunder_odds(match_id)
        df_ou = pd.DataFrame({"项目": ["大球(oo)", "小球(uo)", "临界值(li/4)"], "数值": [oo, uo, li/4]})
        st.dataframe(df_ou, use_container_width=True, hide_index=True)

    with col_win:
        ho, do, ao = loader.get_windrawwin_odds(match_id)
        df_win = pd.DataFrame({"项目": ["主胜(ho)", "平局(do)", "客胜(ao)"], "赔率": [ho, do, ao]})
        st.dataframe(df_win, use_container_width=True, hide_index=True)

    with col_fh:
        hh, dh, ah = loader.get_windrawwinfirsthalf_odds(match_id)
        df_fh = pd.DataFrame({"项目": ["主胜(ho)", "平局(do)", "客胜(ao)"], "赔率": [hh, dh, ah]})
        st.dataframe(df_fh, use_container_width=True, hide_index=True)

    st.markdown('<p class="sub-header">🎲 让球赔率 (winodds.xml)</p>', unsafe_allow_html=True)
    wo = loader.get_winodds_info(match_id)
    var_str = ", ".join(wo["var"]) if wo["var"] else ""
    gg_transformed = (wo["gg"] / 4.0) - 0.25 if wo["gg"] != 0 else 0.0
    df_wo = pd.DataFrame({
        "项目": ["让球(g)", "让球赔率(gg)", "主队(ho)", "客队(ao)", "变量(var)"],
        "数值": [wo["g"], f"{gg_transformed:.2f}", wo["ho"], wo["ao"], var_str]
    })
    st.dataframe(df_wo, use_container_width=True, hide_index=True)

elif page == "总进球":
    st.markdown('<p class="main-header">⚽ 总进球分布 & 大小球分析</p>', unsafe_allow_html=True)
    if data is None:
        st.info("请先在首页完成模拟，再查看总进球页面。")
        st.stop()
    match_id = st.session_state.selected_match_id
    oo, uo, li = loader.get_overunder_odds(match_id)
    X = li / 4.0 if li != 0 else 0.0
    st.markdown(f"**大小球临界值 X = li/4 = {X:.2f}** &nbsp;&nbsp; 大球赔率 = {oo:.2f} &nbsp;&nbsp; 小球赔率 = {uo:.2f}")

    total_df = data['total_goals_df'].copy()
    total_df['概率数值'] = total_df['概率']

    def calc_size_new(row):
        goals = row['总进球']
        prob = row['概率数值']
        z = goals - X
        if z <= -0.5:
            return -1.0 * prob * uo
        elif -0.5 < z < -0.25:
            return -0.5 * prob * (uo + 1)
        elif -0.25 <= z < 0:
            return -0.5 * prob * (uo + 1)
        elif z == 0:
            return 0.0
        elif 0 < z <= 0.25:
            return 0.5 * prob * (oo + 1)
        elif 0.25 < z < 0.5:
            return 0.5 * prob * (oo + 1)
        else:
            return 1.0 * prob * oo

    total_df['大小'] = total_df.apply(calc_size_new, axis=1)

    total_row = pd.DataFrame({
        '总进球': ['总计'],
        '频次': [total_df['频次'].sum()],
        '概率': [total_df['概率数值'].sum()],
        '百分比': [f"{total_df['概率数值'].sum():.2%}"],
        '概率数值': [total_df['概率数值'].sum()],
        '大小': [total_df['大小'].sum()]
    })
    total_df_display = pd.concat([total_df, total_row], ignore_index=True)
    display_df = total_df_display[['总进球','频次','百分比','大小']].copy()
    display_df['大小'] = display_df['大小'].apply(lambda x: f"{x:.4f}")
    st.dataframe(display_df, use_container_width=True, hide_index=True)

elif page == "比分":
    st.markdown('<p class="main-header">📊 比分详情 & 净胜球</p>', unsafe_allow_html=True)
    if data is None:
        st.info("请先在首页完成模拟，再查看比分页面。")
        st.stop()
    match_id = st.session_state.selected_match_id
    cs_odds = loader.get_correctscore_odds(match_id)

    base_scores = ["1-0","2-0","2-1","3-0","3-1","3-2","4-0","4-1","4-2","4-3",
                   "0-1","0-2","1-2","0-3","1-3","2-3","0-4","1-4","2-4","3-4"]
    draw_scores = ["0-0","1-1","2-2","3-3","4-4"]
    fixed_scores = base_scores + draw_scores + ["其他"]

    odds_mapping = {}
    for i, score in enumerate(base_scores[:10]):
        odds_mapping[score] = cs_odds[i] if i < len(cs_odds) else 0.0
    for i, score in enumerate(base_scores[10:]):
        odds_mapping[score] = cs_odds[10 + i] if 10+i < len(cs_odds) else 0.0
    for j, score in enumerate(draw_scores):
        odds_mapping[score] = cs_odds[20 + j] if 20+j < len(cs_odds) else 0.0
    other_odds = cs_odds[25] if len(cs_odds) > 25 else 0.0
    odds_mapping["其他"] = other_odds

    prob_dict = dict(zip(data['score_counts']['比分'], data['score_counts']['概率']))
    rows = []
    for score in fixed_scores:
        if score == "其他":
            continue
        prob = prob_dict.pop(score, 0.0)
        h, a = map(int, score.split('-'))
        net = h - a
        rows.append({
            "比分": score,
            "净胜球": net,
            "概率": prob,
            "赔率": odds_mapping.get(score, 0.0),
            "赔付": prob * odds_mapping.get(score, 0.0)
        })
    other_prob = sum(prob_dict.values())
    rows.append({
        "比分": "其他",
        "净胜球": "-",
        "概率": other_prob,
        "赔率": odds_mapping.get("其他", 0.0),
        "赔付": other_prob * odds_mapping.get("其他", 0.0)
    })
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

elif page == "轮次模拟":
    st.markdown('<p class="main-header">⏱️ 轮次模拟（回合制进攻 · 基于 par 值决定顺序）</p>', unsafe_allow_html=True)
    match_id = st.session_state.selected_match_id
    home_odds, away_odds = loader.get_odds_for_match(match_id)

    _, home_no_goal, home_par = calculate_probabilities(home_odds)
    _, away_no_goal, away_par = calculate_probabilities(away_odds)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**🏠 主队进球数赔率与参数**")
        home_df = pd.DataFrame({
            '进球数': list(range(6)),
            '赔率': home_odds,
            '不再进球概率': home_no_goal,
            'par值 (-ln)': home_par
        })
        home_df['不再进球概率'] = home_df['不再进球概率'].apply(lambda x: f"{x:.4%}")
        home_df['par值 (-ln)'] = home_df['par值 (-ln)'].apply(lambda x: f"{x:.4f}")
        st.dataframe(home_df, use_container_width=True, hide_index=True)
    with col2:
        st.markdown("**✈️ 客队进球数赔率与参数**")
        away_df = pd.DataFrame({
            '进球数': list(range(6)),
            '赔率': away_odds,
            '不再进球概率': away_no_goal,
            'par值 (-ln)': away_par
        })
        away_df['不再进球概率'] = away_df['不再进球概率'].apply(lambda x: f"{x:.4%}")
        away_df['par值 (-ln)'] = away_df['par值 (-ln)'].apply(lambda x: f"{x:.4f}")
        st.dataframe(away_df, use_container_width=True, hide_index=True)

    st.markdown("---")
    col_n, col_btn = st.columns([2, 1])
    with col_n:
        n_round_sims = st.number_input("模拟次数", min_value=100, max_value=100000, value=10000, step=1000)
    with col_btn:
        run_round_sim = st.button("🚀 开始轮次模拟", type="primary", use_container_width=True)

    if run_round_sim:
        progress_bar = st.progress(0, text="初始化...")
        with st.spinner(f"⏳ 正在进行 {n_round_sims:,} 次轮次模拟..."):
            df_results = simulate_matches(home_no_goal, home_par, away_no_goal, away_par, n_round_sims, progress_bar=progress_bar)
        progress_bar.empty()

        # --- 计算高概率轮次并更新到分析记录库 ---
        round_counts = df_results.groupby("rounds").size().reset_index(name="次数")
        round_counts["概率"] = round_counts["次数"] / n_round_sims
        high_prob_rounds = round_counts[round_counts["概率"] >= 0.1]["rounds"].tolist()
        update_rounds_record(match_id, high_prob_rounds)
        # -------------------------------------------------

        st.success(f"✅ 模拟完成！共模拟 {n_round_sims:,} 场，轮次数据已同步到分析记录库。")

        st.markdown('<p class="sub-header">📊 比分分布</p>', unsafe_allow_html=True)
        score_counts = df_results.groupby(["home_goals", "away_goals"]).size().reset_index(name="次数")
        score_counts["概率"] = score_counts["次数"] / n_round_sims
        score_counts["百分比"] = score_counts["概率"].apply(lambda x: f"{x:.4%}")
        score_counts["比分"] = score_counts["home_goals"].astype(str) + "-" + score_counts["away_goals"].astype(str)
        col_left, col_right = st.columns([1, 2])
        with col_left:
            st.dataframe(score_counts[["比分", "次数", "百分比"]], use_container_width=True, hide_index=True)
        with col_right:
            if PLOTLY_AVAILABLE:
                top_scores = score_counts.sort_values("概率", ascending=False).head(15)
                fig = px.bar(top_scores, x="比分", y="概率", text="百分比", title="比分概率分布（前15）")
                fig.update_traces(textposition='outside')
                fig.update_layout(yaxis_tickformat='.0%', height=400)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.bar_chart(score_counts.set_index("比分")["概率"])

        st.markdown('<p class="sub-header">🔄 轮次数分布</p>', unsafe_allow_html=True)
        # 重新计算round_counts（或者使用上面的）
        round_counts = df_results.groupby("rounds").size().reset_index(name="次数")
        round_counts["概率"] = round_counts["次数"] / n_round_sims
        round_counts["百分比"] = round_counts["概率"].apply(lambda x: f"{x:.4%}")
        col_left2, col_right2 = st.columns([1, 2])
        with col_left2:
            def highlight_prob(row):
                if row["概率"] >= 0.1:
                    return ["background-color: #d4edda" for _ in row]
                else:
                    return ["" for _ in row]
            styled_df = round_counts.style.apply(highlight_prob, axis=1).format({"概率": "{:.4%}"})
            st.dataframe(styled_df, use_container_width=True, hide_index=True)
        with col_right2:
            if PLOTLY_AVAILABLE:
                fig2 = px.bar(round_counts, x="rounds", y="概率", text="百分比", title="轮次数概率分布")
                fig2.update_traces(textposition='outside')
                fig2.update_layout(yaxis_tickformat='.0%', height=400)
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.bar_chart(round_counts.set_index("rounds")["概率"])

        st.markdown('<p class="sub-header">🎯 单场模拟示例（最新一场）</p>', unsafe_allow_html=True)
        example = simulate_one_match(home_no_goal, home_par, away_no_goal, away_par)
        st.dataframe(example["history"], use_container_width=True, hide_index=True)
        st.info(f"🏆 示例最终比分: 主队 {example['home_goals']} - {example['away_goals']} 客队")

elif page == "分析记录库":
    st.markdown('<p class="main-header">📋 分析记录库</p>', unsafe_allow_html=True)

    if not st.session_state.analysis_records:
        st.info("暂无记录。请在「首页」运行百万次模拟（核心数据）并在「轮次模拟」页面运行模拟（轮次数据），结果将自动合并到同一条记录。")
    else:
        # 提取显示用的字段（不包含 match_id）
        display_records = []
        for rec in st.session_state.analysis_records:
            display_records.append({
                "时间": rec.get("时间", ""),
                "赛事": rec.get("赛事", ""),
                "主队": rec.get("主队", ""),
                "客队": rec.get("客队", ""),
                "主胜概率": rec.get("主胜概率", ""),
                "平局概率": rec.get("平局概率", ""),
                "客胜概率": rec.get("客胜概率", ""),
                "主队预期进球": rec.get("主队预期进球", ""),
                "客队预期进球": rec.get("客队预期进球", ""),
                "期望赔付(主胜)": rec.get("期望赔付(主胜)", ""),
                "期望赔付(平局)": rec.get("期望赔付(平局)", ""),
                "期望赔付(客胜)": rec.get("期望赔付(客胜)", ""),
                "轮次>10%": rec.get("轮次>10%", "待模拟"),
                "记录时间": rec.get("记录时间", "")
            })
        df = pd.DataFrame(display_records)

        # 筛选与排序
        col_f1, col_f2, col_f3 = st.columns([2, 2, 1])
        with col_f1:
            if "赛事" in df.columns:
                leagues = sorted(df["赛事"].unique())
                selected_leagues = st.multiselect("筛选联赛", options=leagues, default=leagues)
                if selected_leagues:
                    df = df[df["赛事"].isin(selected_leagues)]
        with col_f2:
            sort_col = st.selectbox("排序依据", options=["记录时间", "主胜概率", "平局概率", "客胜概率", "期望赔付(主胜)"])
            ascending = st.checkbox("升序", value=False)
            if sort_col in ["主胜概率", "平局概率", "客胜概率"]:
                df_sorted = df.copy()
                df_sorted[sort_col + "_数值"] = df_sorted[sort_col].str.rstrip('%').astype(float)
                df_sorted = df_sorted.sort_values(sort_col + "_数值", ascending=ascending)
                df = df_sorted.drop(columns=[sort_col + "_数值"])
            elif sort_col == "期望赔付(主胜)":
                df_sorted = df.copy()
                df_sorted[sort_col + "_数值"] = df_sorted[sort_col].astype(float)
                df_sorted = df_sorted.sort_values(sort_col + "_数值", ascending=ascending)
                df = df_sorted.drop(columns=[sort_col + "_数值"])
            else:
                df = df.sort_values(sort_col, ascending=ascending)
        with col_f3:
            if st.button("🗑️ 清空所有记录", use_container_width=True):
                st.session_state.analysis_records = []
                st.rerun()

        # 额外选项：只显示完整记录（轮次不是“待模拟”）
        show_only_complete = st.checkbox("仅显示完整记录（已有轮次数据）", value=False)
        if show_only_complete:
            df = df[df["轮次>10%"] != "待模拟"]

        st.dataframe(df, use_container_width=True, hide_index=True)

        # 导出 CSV
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 导出为 CSV",
            data=csv,
            file_name=f"analysis_records_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
        )

st.markdown("---")
st.caption("数据基于闯关概率模型模拟生成，实际结果可能因随机性有所波动。")