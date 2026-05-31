"""
足球投注价值分析 — Streamlit 集成页面
==========================================
将 betting_model.py 的分析逻辑适配到 FootballDataLoader 数据源。
数据流：
  1. loader.get_odds_for_match() → odds_to_probs() → 闯关概率 E[]
  2. E[] → 实际进球概率分布 {0:p0, 1:p1, ..., 5:p5}
  3. BettingModel(分布) → 联合矩阵 → 各玩法概率
  4. loader.get_*_odds() → 各玩法赔率 → EV 计算 → 推荐
"""

import streamlit as st
import pandas as pd
import numpy as np
import math
from typing import Dict, List, Tuple

# 复用现有的大小球分析模块（已包含正确亚洲盘口逻辑）
try:
    from streamlit_integration import (
        get_handicap_type,
        handicap_type_label,
        over_return,
        under_return,
    )
    _HAS_OU = True
except ImportError:
    _HAS_OU = False

try:
    import plotly.graph_objects as go
    import plotly.express as px
    _HAS_PLOTLY = True
except ImportError:
    _HAS_PLOTLY = False


# ============================================================
# 概率转换：闯关概率 → 实际进球分布
# ============================================================

def no_goal_probs_to_distribution(no_goal_E: List[float], max_goals: int = 5) -> Dict[int, float]:
    """
    将闯关概率模型中的 "不再进球概率" E[] 转换为实际进球概率分布。

    E[i] = P(在已进 i 球后不再进第 i+1 球)
    转换：
      P(0) = E[0]
      P(1) = (1-E[0]) × E[1]
      P(2) = (1-E[0])(1-E[1]) × E[2]
      ...
      P(5) = 剩余概率
    """
    dist = {}
    remaining = 1.0
    for i in range(max_goals):
        if i < len(no_goal_E):
            p = remaining * no_goal_E[i]
        else:
            p = 0.0
        dist[i] = p
        remaining -= p
    dist[max_goals] = remaining  # P(进 max_goals 球)
    return dist


# ============================================================
# 赔率转概率（复制自 x-football.py，避免循环导入）
# ============================================================

def odds_to_probs(odds_home: List[float], odds_away: List[float]) -> Tuple[List[float], List[float]]:
    """赔率转闯关概率（与 x-football.py 中完全一致）"""
    def calc_E(odds_list):
        sum_inv = sum(1 / o for o in odds_list[:6])
        if sum_inv == 0:
            return [0.0] * 5
        C = 1 / sum_inv
        D = [C / o for o in odds_list[:5]]
        E = []
        cum_D = 0
        for d in D:
            e = d / (1 - cum_D) if (1 - cum_D) > 0 else 0
            E.append(e)
            cum_D += d
        return E

    if len(odds_home) < 6:
        odds_home = odds_home + [1.0] * (6 - len(odds_home))
    if len(odds_away) < 6:
        odds_away = odds_away + [1.0] * (6 - len(odds_away))

    home_probs = calc_E(odds_home[:6])
    away_probs = calc_E(odds_away[:6])
    return home_probs, away_probs


# ============================================================
# 核心计算函数
# ============================================================

def calculate_ev(odds: float, probability: float) -> float:
    """简单 EV = odds × probability - 1"""
    return odds * probability - 1


def kelly_criterion(odds: float, probability: float) -> float:
    """Kelly 准则，上限 25%"""
    net = odds - 1
    if net <= 0 or probability <= 0 or probability >= 1:
        return 0.0
    return max(0.0, min((probability * net - (1 - probability)) / net, 0.25))


def compute_joint_matrix(home_probs: Dict[int, float],
                          away_probs: Dict[int, float],
                          max_goals: int = 6) -> Dict[str, float]:
    """计算联合比分概率矩阵 P(主=i, 客=j)"""
    joint = {}
    for hi in range(max_goals):
        for aj in range(max_goals):
            joint[f"{hi}-{aj}"] = home_probs.get(hi, 0) * away_probs.get(aj, 0)
    return joint


def compute_total_goals(joint_probs: Dict[str, float], max_goals: int = 6) -> Dict[int, float]:
    """计算总进球概率分布"""
    total = {}
    for hi in range(max_goals):
        for aj in range(max_goals):
            t = hi + aj
            total[t] = total.get(t, 0) + joint_probs.get(f"{hi}-{aj}", 0)
    return total


def compute_ft_probs(joint_probs: Dict[str, float], max_goals: int = 6) -> Dict[str, float]:
    """全场胜平负概率"""
    hw = sum(joint_probs[f"{i}-{j}"] for i in range(max_goals) for j in range(max_goals) if i > j)
    dr = sum(joint_probs[f"{i}-{j}"] for i in range(max_goals) for j in range(max_goals) if i == j)
    aw = sum(joint_probs[f"{i}-{j}"] for i in range(max_goals) for j in range(max_goals) if i < j)
    return {"home_win": hw, "draw": dr, "away_win": aw}

# ============================================================
# 正确比分赔率解析
# ============================================================

SCORE_LABELS = [
    "1-0","2-0","2-1","3-0","3-1","3-2","4-0","4-1","4-2","4-3",
    "0-1","0-2","1-2","0-3","1-3","2-3","0-4","1-4","2-4","3-4",
    "0-0","1-1","2-2","3-3","4-4","其他"
]

# 可被模型精确计算的比分（在6x6矩阵内的）
MODEL_SCORES = [
    "0-0","0-1","0-2","0-3","0-4","0-5",
    "1-0","1-1","1-2","1-3","1-4","1-5",
    "2-0","2-1","2-2","2-3","2-4","2-5",
    "3-0","3-1","3-2","3-3","3-4","3-5",
    "4-0","4-1","4-2","4-3","4-4","4-5",
    "5-0","5-1","5-2","5-3","5-4","5-5",
]


def parse_cs_odds(odds_list: List[float]) -> Dict[str, float]:
    """将 loader.get_correctscore_odds() 返回的26个赔率映射为比分->赔率字典"""
    if len(odds_list) < 26:
        odds_list = odds_list + [0.0] * (26 - len(odds_list))
    return {SCORE_LABELS[i]: odds_list[i] for i in range(26)}


# ============================================================
# 完整分析函数
# ============================================================

def run_betting_analysis(loader, match_id: str) -> dict:
    """
    对指定比赛运行完整投注价值分析。

    返回包含所有计算结果的字典。
    """
    # --- 1. 获取进球概率 ---
    home_odds_raw, away_odds_raw = loader.get_odds_for_match(match_id)
    if len(home_odds_raw) < 6:
        home_odds_raw = list(home_odds_raw) + [1.0] * (6 - len(home_odds_raw))
    if len(away_odds_raw) < 6:
        away_odds_raw = list(away_odds_raw) + [1.0] * (6 - len(away_odds_raw))

    # 使用本地定义的 odds_to_probs
    home_no_goal, away_no_goal = odds_to_probs(home_odds_raw[:6], away_odds_raw[:6])

    # 转换为实际概率分布
    home_dist = no_goal_probs_to_distribution(home_no_goal)
    away_dist = no_goal_probs_to_distribution(away_no_goal)

    # 预期进球
    exp_home = sum(k * v for k, v in home_dist.items())
    exp_away = sum(k * v for k, v in away_dist.items())

    # --- 2. 联合矩阵 & 全场概率 ---
    joint = compute_joint_matrix(home_dist, away_dist)
    total_g = compute_total_goals(joint)
    ft_probs = compute_ft_probs(joint)

    # --- 5. 获取各玩法赔率 ---
    ho, do_, ao = loader.get_windrawwin_odds(match_id)
    fh_ho, fh_do, fh_ao = loader.get_windrawwinfirsthalf_odds(match_id)
    oo, uo, li = loader.get_overunder_odds(match_id)
    handicap = li / 4.0 if li != 0 else 0.0
    hf = loader.get_halffull_odds(match_id)
    cs_raw = loader.get_correctscore_odds(match_id)
    cs_odds = parse_cs_odds(cs_raw)

    # --- 6. EV 计算 ---
    bets = []

    # 全场胜平负
    ft_keys = {"H": "home_win", "D": "draw", "A": "away_win"}
    ft_odds_map = {"H": ho, "D": do_, "A": ao}
    for k, pk in ft_keys.items():
        p = ft_probs[pk]
        ev = calculate_ev(ft_odds_map[k], p)
        bets.append({"选项": f"全场 {k}", "类别": "全场胜平负",
                     "赔率": ft_odds_map[k], "理论概率": p, "EV": ev})

    # 大小球（用 streamlit_integration 的已有计算，或重新计算）
    if _HAS_OU and handicap > 0:
        # 用 streamlit_integration 的 over_return/under_return 逐进球计算 EV
        goal_vals = sorted(total_g.keys())
        prob_vals = [total_g[g] for g in goal_vals]
        goal_labels = [str(g) for g in goal_vals]

        over_rets = [over_return(handicap, float(g), oo) for g in goal_vals]
        under_rets = [under_return(handicap, float(g), uo) for g in goal_vals]
        ev_over = sum(p * r for p, r in zip(prob_vals, over_rets)) - 1.0
        ev_under = sum(p * r for p, r in zip(prob_vals, under_rets)) - 1.0

        bets.append({"选项": f"大 {handicap:.2f}", "类别": "大小球",
                     "赔率": oo, "理论概率": 0, "EV": ev_over})
        bets.append({"选项": f"小 {handicap:.2f}", "类别": "大小球",
                     "赔率": uo, "理论概率": 0, "EV": ev_under})

    # 精确比分
    all_model_scores = {s: joint.get(s, 0) for s in MODEL_SCORES}
    listed_sum = sum(all_model_scores.get(s, 0) for s in cs_odds if s != "其他")
    remaining = max(0.0, 1.0 - listed_sum)

    for score, od in cs_odds.items():
        if od <= 0:
            continue
        if score == "其他":
            p = remaining
        else:
            p = all_model_scores.get(score, 0)
        ev = calculate_ev(od, p)
        bets.append({"选项": score, "类别": "精确比分",
                     "赔率": od, "理论概率": p, "EV": ev})

    # 排序
    bets.sort(key=lambda x: x["EV"], reverse=True)

    # 为每个投注添加 Kelly 比例
    for b in bets:
        b["Kelly"] = kelly_criterion(b["赔率"], b["理论概率"])

    return {
        "home_dist": home_dist,
        "away_dist": away_dist,
        "exp_home": exp_home,
        "exp_away": exp_away,
        "exp_total": exp_home + exp_away,
        "joint_probs": joint,
        "total_goals": total_g,
        "ft_probs": ft_probs,
        "bets": bets,
        "handicap": handicap,
        "over_odds": oo,
        "under_odds": uo,
    }


# ============================================================
# Streamlit 页面渲染
# ============================================================

def render_betting_value_page(loader, match_id: str):
    """渲染投注价值分析页面"""
    st.markdown('<p class="main-header">📈 投注价值分析</p>', unsafe_allow_html=True)

    with st.spinner("⏳ 计算各玩法理论概率与期望值..."):
        result = run_betting_analysis(loader, match_id)

    # ========== 核心 KPI ==========
    st.markdown("### 🎯 核心指标")
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("主队预期进球", f"{result['exp_home']:.3f}")
    with col2:
        st.metric("客队预期进球", f"{result['exp_away']:.3f}")
    with col3:
        st.metric("总预期进球", f"{result['exp_total']:.3f}")
    with col4:
        st.metric("主胜概率", f"{result['ft_probs']['home_win']:.2%}")
    with col5:
        st.metric("客胜概率", f"{result['ft_probs']['away_win']:.2%}")

    # ========== 全场胜平负 ==========
    st.markdown("### 🏆 全场胜平负")
    ft = result['ft_probs']
    ho, do_, ao = loader.get_windrawwin_odds(match_id)
    cols = st.columns(3)
    for i, (k, lbl) in enumerate([("H","主胜"), ("D","平局"), ("A","客胜")]):
        odds = [ho, do_, ao][i]
        p = [ft['home_win'], ft['draw'], ft['away_win']][i]
        ev = calculate_ev(odds, p)
        with cols[i]:
            delta_color = "normal" if ev > 0 else "inverse"
            st.metric(lbl, f"{p:.2%}", delta=f"EV {ev*100:+.2f}% 赔率{odds:.2f}",
                      delta_color=delta_color)

    # ========== 大小球 ==========
    if result['handicap'] > 0:
        st.markdown(f"### 📏 大小球（盘口 {result['handicap']:.2f}）")
        hcp_t = get_handicap_type(result['handicap'])
        st.caption(f"类型：{handicap_type_label(result['handicap'])}")

        # 大球/小球 EV 卡片
        over_ev = [b['EV'] for b in result['bets']
                   if b['类别'] == '大小球' and b['选项'].startswith('大')]
        under_ev = [b['EV'] for b in result['bets']
                    if b['类别'] == '大小球' and b['选项'].startswith('小')]

        cols = st.columns(2)
        with cols[0]:
            ev_o = over_ev[0] if over_ev else -999
            dc = "normal" if ev_o > 0 else "inverse"
            st.metric(f"大球 @ {result['over_odds']:.3f}", f"{'✅ +EV' if ev_o > 0 else '❌ -EV'}",
                      delta=f"EV {ev_o*100:+.2f}%", delta_color=dc)
        with cols[1]:
            ev_u = under_ev[0] if under_ev else -999
            dc = "normal" if ev_u > 0 else "inverse"
            st.metric(f"小球 @ {result['under_odds']:.3f}", f"{'✅ +EV' if ev_u > 0 else '❌ -EV'}",
                      delta=f"EV {ev_u*100:+.2f}%", delta_color=dc)

        # 大小球仅显示 EV 摘要（完整分析面板在"总进球"页面）
        hcp_desc = f"{result['handicap']:.2f}（{handicap_type_label(result['handicap'])}）"
        st.caption(f"盘口 {hcp_desc} · 详细分析请查看「总进球」页面")

    # ========== 全场价值排行 ==========
    st.markdown("### 📊 价值投注排行（全部玩法）")
    positive = [b for b in result['bets'] if b['EV'] > 0]
    all_bets = result['bets']

    tab1, tab2 = st.tabs(["全量排行（按EV降序）", f"正EV机会（{len(positive)}个）"])
    with tab1:
        df_all = pd.DataFrame(all_bets)
        df_all.insert(0, '排名', range(1, len(df_all) + 1))
        df_display = df_all[['排名', '选项', '类别', '赔率', '理论概率', 'EV', 'Kelly']].copy()

        # 格式化
        df_display['理论概率'] = df_display['理论概率'].apply(
            lambda x: f"{x:.4%}" if isinstance(x, float) and x > 0 else "-")
        df_display['EV'] = df_display['EV'].apply(lambda x: f"{x*100:+.2f}%")
        df_display['Kelly'] = df_display['Kelly'].apply(lambda x: f"{x*100:.2f}%" if x > 0 else "-")

        # 上色
        def color_ev(val):
            if isinstance(val, str) and val.startswith('+'):
                return 'color: #16a34a; font-weight: bold'
            return 'color: #dc2626'

        styled = df_display.style.map(color_ev, subset=['EV'])
        st.dataframe(styled, use_container_width=True, hide_index=True,
                     height=min(40 + len(df_display) * 35, 600))

    with tab2:
        if positive:
            df_pos = pd.DataFrame(positive)
            df_pos.insert(0, '排名', range(1, len(df_pos) + 1))
            dp = df_pos[['排名', '选项', '类别', '赔率', '理论概率', 'EV', 'Kelly']].copy()
            dp['理论概率'] = dp['理论概率'].apply(
                lambda x: f"{x:.4%}" if isinstance(x, float) and x > 0 else "-")
            dp['EV'] = dp['EV'].apply(lambda x: f"{x*100:+.2f}%")
            dp['Kelly'] = dp['Kelly'].apply(lambda x: f"{x*100:.2f}%" if x > 0 else "-")
            st.dataframe(dp, use_container_width=True, hide_index=True)
            st.success(f"发现 {len(positive)} 个正EV机会！")
        else:
            st.warning("所有投注选项均为负EV，未发现价值投注机会。")

    # ========== 精确比分 Top 10 ==========
    st.markdown("### 🎯 精确比分（Top 10 高赔付）")
    cs_bets = [b for b in result['bets'] if b['类别'] == '精确比分']
    cs_by_ev = sorted(cs_bets, key=lambda x: x['EV'], reverse=True)[:10]
    if cs_by_ev:
        df_cs = pd.DataFrame(cs_by_ev)
        df_cs.insert(0, '排名', range(1, len(df_cs) + 1))
        dc = df_cs[['排名', '选项', '赔率', '理论概率', 'EV', 'Kelly']].copy()
        dc['理论概率'] = dc['理论概率'].apply(
            lambda x: f"{x:.4%}" if isinstance(x, float) and x > 0 else "-")
        dc['EV'] = dc['EV'].apply(lambda x: f"{x*100:+.2f}%")
        dc['Kelly'] = dc['Kelly'].apply(lambda x: f"{x*100:.2f}%" if x > 0 else "-")
        styled_cs = dc.style.map(color_ev, subset=['EV'])
        st.dataframe(styled_cs, use_container_width=True, hide_index=True)

    # 理性提醒
    st.markdown("---")
    st.caption(
        "⚠️ **博彩有风险，投注需谨慎！** 本文仅为数学分析参考，不构成实际投注建议。"
        "模型假设主客队进球独立，实际可能存在相关性。"
    )
