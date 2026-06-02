"""
=============================================================================
Streamlit 大小球分析可视化集成代码
=============================================================================
使用方法：
1. 将此文件放到你的 Streamlit 应用同级目录下
2. 在页面文件顶部添加:  from streamlit_integration import render_over_under_analysis
3. 替换原 "总进球" page 代码为下方内容

或者直接复制下方 `elif page == "总进球":` 代码块到你的主应用中。
=============================================================================
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

# ======================== 计算引擎 ========================

def get_handicap_type(hcp: float) -> str:
    """判断盘口类型：整数盘、半数盘、四分之一球盘"""
    f = hcp % 1
    if abs(f) < 0.01:
        return 'integer'
    if abs(f - 0.5) < 0.01:
        return 'half'
    if abs(f - 0.25) < 0.01 or abs(f - 0.75) < 0.01:
        return 'quarter'
    return 'other'


def handicap_type_label(hcp: float) -> str:
    labels = {'integer': '整数盘', 'half': '半数盘', 'quarter': '四分之一球盘', 'other': '特殊'}
    return labels.get(get_handicap_type(hcp), '未知')


def over_return_single(hcp: float, goals: float, odds: float) -> float:
    """单一子盘口的 大球 返还倍数"""
    t = get_handicap_type(hcp)
    if t == 'integer':
        if goals > hcp + 0.0001:
            return odds
        if abs(goals - hcp) < 0.0001:
            return 1.0
        return 0.0
    if t == 'half':
        return odds if goals > hcp + 0.0001 else 0.0
    return 0.0


def under_return_single(hcp: float, goals: float, odds: float) -> float:
    """单一子盘口的 小球 返还倍数"""
    t = get_handicap_type(hcp)
    if t == 'integer':
        if goals < hcp - 0.0001:
            return odds
        if abs(goals - hcp) < 0.0001:
            return 1.0
        return 0.0
    if t == 'half':
        return odds if goals < hcp - 0.0001 else 0.0
    return 0.0


def over_return(hcp: float, goals: float, odds: float) -> float:
    """大球 总返还倍数（含四分之一球盘的平分结算）"""
    t = get_handicap_type(hcp)
    if t == 'quarter':
        lower = hcp - 0.25
        upper = hcp + 0.25
        return (0.5 * over_return_single(lower, goals, odds) +
                0.5 * over_return_single(upper, goals, odds))
    return over_return_single(hcp, goals, odds)


def under_return(hcp: float, goals: float, odds: float) -> float:
    """小球 总返还倍数（含四分之一球盘的平分结算）"""
    t = get_handicap_type(hcp)
    if t == 'quarter':
        lower = hcp - 0.25
        upper = hcp + 0.25
        return (0.5 * under_return_single(lower, goals, odds) +
                0.5 * under_return_single(upper, goals, odds))
    return under_return_single(hcp, goals, odds)


def _over_result_type(hcp: float, goals: float) -> str:
    """大球方向的结果判定（不涉及赔率），返回 'win' / 'push' / 'lose'"""
    t = get_handicap_type(hcp)
    if t == 'integer':
        if goals > hcp + 0.0001:
            return 'win'
        if abs(goals - hcp) < 0.0001:
            return 'push'
        return 'lose'
    if t == 'half':
        return 'win' if goals > hcp + 0.0001 else 'lose'
    return 'lose'


def _under_result_type(hcp: float, goals: float) -> str:
    """小球方向的结果判定（不涉及赔率），返回 'win' / 'push' / 'lose'"""
    t = get_handicap_type(hcp)
    if t == 'integer':
        if goals < hcp - 0.0001:
            return 'win'
        if abs(goals - hcp) < 0.0001:
            return 'push'
        return 'lose'
    if t == 'half':
        return 'win' if goals < hcp - 0.0001 else 'lose'
    return 'lose'


_RESULT_MAP = {'win': '赢', 'push': '走水', 'lose': '输'}


def over_return_desc(hcp: float, goals: float) -> str:
    """大球结果描述：赢/输/走水/赢一半/输一半"""
    t = get_handicap_type(hcp)
    if t == 'quarter':
        lower = hcp - 0.25
        upper = hcp + 0.25
        parts = [
            _RESULT_MAP[_over_result_type(lower, goals)],
            _RESULT_MAP[_over_result_type(upper, goals)],
        ]
        return '/'.join(parts)
    return _RESULT_MAP[_over_result_type(hcp, goals)]


def under_return_desc(hcp: float, goals: float) -> str:
    """小球结果描述：赢/输/走水/赢一半/输一半"""
    t = get_handicap_type(hcp)
    if t == 'quarter':
        lower = hcp - 0.25
        upper = hcp + 0.25
        parts = [
            _RESULT_MAP[_under_result_type(lower, goals)],
            _RESULT_MAP[_under_result_type(upper, goals)],
        ]
        return '/'.join(parts)
    return _RESULT_MAP[_under_result_type(hcp, goals)]


def calc_fair_odds(hcp: float, prob_values: list, goal_labels: list) -> tuple:
    """
    计算大球和小球的公平赔率
    返回: (fair_over, fair_under)
    """
    over_win_coeff = 0.0   # Σ p * (赔率系数) — 赢的时候赔率全额计入
    over_push_sum = 0.0    # Σ p * (走水返还，与赔率无关)
    under_win_coeff = 0.0
    under_push_sum = 0.0

    t = get_handicap_type(hcp)

    for label, p in zip(goal_labels, prob_values):
        g = 7 if label == '7+' else float(label)

        if t == 'quarter':
            lower = hcp - 0.25
            upper = hcp + 0.25
            lt = get_handicap_type(lower)
            ut = get_handicap_type(upper)

            # Over coefficients
            l_win = 1 if ((lt == 'integer' and g > lower + 0.0001) or
                          (lt == 'half' and g > lower + 0.0001)) else 0
            l_push = 1 if (lt == 'integer' and abs(g - lower) < 0.0001) else 0
            u_win = 1 if ((ut == 'integer' and g > upper + 0.0001) or
                          (ut == 'half' and g > upper + 0.0001)) else 0
            u_push = 1 if (ut == 'integer' and abs(g - upper) < 0.0001) else 0

            over_win_coeff += p * 0.5 * (l_win + u_win)
            over_push_sum += p * 0.5 * (l_push + u_push)

            # Under coefficients
            l_win = 1 if ((lt == 'integer' and g < lower - 0.0001) or
                          (lt == 'half' and g < lower - 0.0001)) else 0
            l_push = 1 if (lt == 'integer' and abs(g - lower) < 0.0001) else 0
            u_win = 1 if ((ut == 'integer' and g < upper - 0.0001) or
                          (ut == 'half' and g < upper - 0.0001)) else 0
            u_push = 1 if (ut == 'integer' and abs(g - upper) < 0.0001) else 0

            under_win_coeff += p * 0.5 * (l_win + u_win)
            under_push_sum += p * 0.5 * (l_push + u_push)
        else:
            is_int = t == 'integer'
            o_win = (is_int and g > hcp + 0.0001) or (not is_int and g > hcp + 0.0001)
            o_push = is_int and abs(g - hcp) < 0.0001
            u_win = (is_int and g < hcp - 0.0001) or (not is_int and g < hcp - 0.0001)
            u_push = is_int and abs(g - hcp) < 0.0001

            if o_win:
                over_win_coeff += p
            if o_push:
                over_push_sum += p
            if u_win:
                under_win_coeff += p
            if u_push:
                under_push_sum += p

    fair_over = (1 - over_push_sum) / over_win_coeff if over_win_coeff > 0 else float('inf')
    fair_under = (1 - under_push_sum) / under_win_coeff if under_win_coeff > 0 else float('inf')
    fair_over_prob = 1.0 / fair_over   # 公平概率 = 1/公平赔率
    fair_under_prob = 1.0 / fair_under
    return fair_over, fair_under, fair_over_prob, fair_under_prob


# ======================== 可视化渲染函数 ========================

def _parse_goal(label) -> float:
    """将进球标签转为数值，处理 '7+', '7', 7 等情况"""
    s = str(label).strip()
    if s in ('7+', '7以上', '7球以上'):
        return 7.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def render_over_under_analysis(
    total_df: pd.DataFrame,
    over_odds: float,
    under_odds: float,
    handicap: float
):
    """
    主渲染函数 — 在 Streamlit 中绘制完整的大小球分析可视化

    参数:
        total_df: 包含 '总进球', '概率数值', '百分比' 列的 DataFrame
        over_odds: 大球赔率
        under_odds: 小球赔率
        handicap: 基准线（盘口）
    """
    # ===== 1. 数据准备 =====
    total_df = total_df.copy()

    # 提取概率数值（处理百分比字符串或纯数值）
    if '概率数值' not in total_df.columns:
        if '百分比' in total_df.columns:
            total_df['概率数值'] = total_df['百分比'].apply(
                lambda x: float(str(x).rstrip('%')) / 100.0
            )
        elif '概率' in total_df.columns:
            total_df['概率数值'] = pd.to_numeric(total_df['概率'], errors='coerce').fillna(0.0)

    prob_values = total_df['概率数值'].values  # 小数 (0.035, 0.117 ...)

    # 提取进球标签，兼容 '7+' 或纯数字 7
    goal_labels_raw = total_df['总进球'].values
    goal_labels_str = [str(g) for g in goal_labels_raw]  # 统一为字符串
    goal_values = [_parse_goal(g) for g in goal_labels_str]

    # 期望进球数
    expected_goals = sum(g * p for g, p in zip(goal_values, prob_values))

    # 累计概率
    cum_probs = np.cumsum(prob_values)

    hcp = handicap
    hcp_type = get_handicap_type(hcp)
    hcp_type_label = handicap_type_label(hcp)

    # ===== 2. 逐进球结算表 =====
    over_returns = []
    under_returns = []
    over_descs = []
    under_descs = []

    for g in goal_values:
        over_returns.append(over_return(hcp, g, over_odds))
        under_returns.append(under_return(hcp, g, under_odds))
        over_descs.append(over_return_desc(hcp, g))
        under_descs.append(under_return_desc(hcp, g))

    # ===== 3. EV 计算 =====
    ev_over = sum(p * r for p, r in zip(prob_values, over_returns)) - 1.0
    ev_under = sum(p * r for p, r in zip(prob_values, under_returns)) - 1.0

    # ===== 4. 公平赔率 =====
    fair_over, fair_under, fair_over_prob, fair_under_prob = calc_fair_odds(hcp, prob_values.tolist(), goal_labels_str)

    # ===== 5. 隐含概率 & 抽水 =====
    implied_over = 1.0 / over_odds
    implied_under = 1.0 / under_odds
    overround_pct = (implied_over + implied_under) * 100.0

    # =================================================================
    #                        开始渲染 UI
    # =================================================================

    st.markdown("### 📊 深度分析面板")

    # ----- 5.0 基准数据 -----
    st.markdown("#### 基准数据")

    col_b1, col_b2, col_b3, col_b4, col_b5 = st.columns(5)
    with col_b1:
        hcp_label = f"{hcp:.2f}"
        st.markdown(f'<div class="metric-box"><div class="metric-value">{hcp_label}</div><div class="metric-label">🏠 大小球盘口</div></div>', unsafe_allow_html=True)
    with col_b2:
        st.markdown(f'<div class="metric-box"><div class="metric-value">{over_odds:.3f}</div><div class="metric-label">🤝 大球赔率</div></div>', unsafe_allow_html=True)
    with col_b3:
        st.markdown(f'<div class="metric-box"><div class="metric-value">{under_odds:.3f}</div><div class="metric-label">🚀 小球赔率</div></div>', unsafe_allow_html=True)
    with col_b4:
        st.markdown(f'<div class="metric-box"><div class="metric-value">{fair_over_prob:.2%}</div><div class="metric-label">⚽ 大球公平概率</div></div>', unsafe_allow_html=True)
    with col_b5:
        st.markdown(f'<div class="metric-box"><div class="metric-value">{fair_under_prob:.2%}</div><div class="metric-label">⚽ 小球公平概率</div></div>', unsafe_allow_html=True)
    
    # ----- 5.1 期望值（EV）分析 -----
    st.markdown("#### 期望值（EV）分析")

    ev_col1, ev_col2, ev_col3, ev_col4 = st.columns(4)
    with ev_col1:
        ev_over_pct = ev_over
        delta_color = "inverse" if ev_over_pct < 0 else "normal"
    #    st.metric("大球 EV", f"{ev_over_pct:.2f}%", delta_color=delta_color)
        st.markdown(f'<div class="metric-box"><div class="metric-value">{ev_over_pct:.2%}</div><div class="metric-label">🏠 大球 EV</div></div>', unsafe_allow_html=True)
    with ev_col2:
        ev_under_pct = ev_under
        delta_color = "inverse" if ev_under_pct < 0 else "normal"
    #    st.metric("小球 EV", f"{ev_under_pct:.2f}%", delta_color=delta_color)
        st.markdown(f'<div class="metric-box"><div class="metric-value">{ev_under_pct:.2%}</div><div class="metric-label">🏠 小球 EV</div></div>', unsafe_allow_html=True)
    with ev_col3:
    #    st.metric("大球公平赔率", f"{fair_over:.3f}" if fair_over != float('inf') else "∞")
        st.markdown(f'<div class="metric-box"><div class="metric-value">{fair_over:.3f}</div><div class="metric-label">🏠 大球公平赔率</div></div>', unsafe_allow_html=True)
    with ev_col4:
    #    st.metric("小球公平赔率", f"{fair_under:.3f}" if fair_under != float('inf') else "∞")
        st.markdown(f'<div class="metric-box"><div class="metric-value">{fair_under:.3f}</div><div class="metric-label">🏠 小球公平赔率</div></div>', unsafe_allow_html=True)

    # EV 条形图
    fig_ev = go.Figure()
    ev_labels = [f'大球 {hcp} @ {over_odds}', f'小球 {hcp} @ {under_odds}']
    ev_vals = [ev_over_pct, ev_under_pct]
    ev_colors = ['#e63946' if v < 0 else '#2ec4b6' for v in ev_vals]

    fig_ev.add_trace(go.Bar(
        x=ev_vals,
        y=ev_labels,
        orientation='h',
        marker_color=ev_colors,
        text=[f"{v:+.2f}%" for v in ev_vals],
        textposition='outside',
        hovertemplate='%{y}: %{x:.2f}%<extra></extra>'
    ))
    fig_ev.update_layout(
        height=180,
        margin=dict(l=0, r=0, t=10, b=0),
        xaxis=dict(title='期望净收益 (%)'),
        yaxis=dict(title=None),
        hovermode='y',
        bargap=0.3,
    )
    # 加零线
    fig_ev.add_vline(x=0, line_dash="dash", line_color="#94a3b8", line_width=1)
    st.plotly_chart(fig_ev, use_container_width=True)

    # EV 计算过程
    with st.expander("📝 EV 计算过程"):
        over_formula = " + ".join(
            f"{p*100:.1f}%×{r:.3f}" for p, r in zip(prob_values, over_returns)
        )
        under_formula = " + ".join(
            f"{p*100:.1f}%×{r:.3f}" for p, r in zip(prob_values, under_returns)
        )
        st.markdown(f"""
**大球 EV** = {over_formula} − 1 = **{ev_over_pct:.2f}%**

**小球 EV** = {under_formula} − 1 = **{ev_under_pct:.2f}%**

**隐含概率：** 大球 {implied_over:.1%} + 小球 {implied_under:.1%} = **{overround_pct:.1f}%**（抽水 {overround_pct - 100:.1f}%）
        """)
    
    # ----- 5.2 概览指标 -----
    st.markdown("#### 概览指标")
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("期望进球数", f"{expected_goals:.2f}")
    with col2:
        mode_idx = np.argmax(prob_values)
        mode_label = goal_labels_str[mode_idx]
        st.metric("最可能进球", mode_label)
    with col3:
        st.metric("P(≥4球)", f"{sum(prob_values[4:]):.1%}")
    with col4:
        st.metric("P(≤2球)", f"{sum(prob_values[:3]):.1%}")
    with col5:
        st.metric("P(=3球)", f"{prob_values[3]:.1%}" if len(prob_values) > 3 else "N/A")

    # ----- 5.3 盘口结算明细 -----
    st.markdown(f"#### 盘口结算明细：{hcp}（{hcp_type_label}）")
    st.caption(f"大球 @ {over_odds:.3f}  /  小球 @ {under_odds:.3f}")

    settle_df = pd.DataFrame({
        '进球': goal_labels_str,
        '概率': [f"{p*100:.1f}%" for p in prob_values],
        '大球结算': over_descs,
        '大球返还': [f"{r:.3f}" for r in over_returns],
        '小球结算': under_descs,
        '小球返还': [f"{r:.3f}" for r in under_returns],
    })

    # 高亮突出行（概率 > 10%）
    def highlight_settle(row):
        idx = row.name
        pct = prob_values[idx]
        if pct > 0.10:
            return ['background-color: #fffbeb'] * len(row)
        return [''] * len(row)

    st.dataframe(
        settle_df.style.apply(highlight_settle, axis=1),
        use_container_width=True,
        hide_index=True,
        height=min(60 + len(settle_df) * 38, 400)
    )

    if hcp_type == 'quarter':
        lower = hcp - 0.25
        upper = hcp + 0.25
        st.caption(
            f"💡 四分之一球盘：投注额平分为两份，分别按 {lower}（{handicap_type_label(lower)}）"
            f"和 {upper}（{handicap_type_label(upper)}）结算。"
        )

    # ----- 5.4 概率分布图 -----
    st.markdown("#### 进球概率分布")
    fig_dist = go.Figure()

    colors = ['#94a3b8'] * 8
    # 高亮模式（>10%）
    for i, p in enumerate(prob_values):
        if p > 0.10:
            colors[i] = '#4361ee'
    # 高亮众数
    colors[mode_idx] = '#f59e0b'

    fig_dist.add_trace(go.Bar(
        x=goal_labels_str,
        y=prob_values * 100,  # 转为百分比显示
        marker_color=colors,
        text=[f"{v:.1f}%" for v in prob_values * 100],
        textposition='outside',
        hovertemplate='%{x}: %{y:.1f}%<extra></extra>'
    ))
    fig_dist.update_layout(
        height=280,
        margin=dict(l=0, r=0, t=10, b=0),
        yaxis=dict(title='概率 (%)', range=[0, max(prob_values) * 100 * 1.25]),
        xaxis=dict(title='总进球'),
        hovermode='x',
        bargap=0.3,
    )
    st.plotly_chart(fig_dist, use_container_width=True)

    # ----- 5.5 赔率对比图 -----
    st.markdown("#### 赔率对比：市场 vs 公平")
    fig_odds = go.Figure()

    fig_odds.add_trace(go.Bar(
        name='市场赔率',
        x=['大球', '小球'],
        y=[over_odds, under_odds],
        marker_color='#94a3b8',
        text=[f"{over_odds:.3f}", f"{under_odds:.3f}"],
        textposition='outside',
    ))
    fig_odds.add_trace(go.Bar(
        name='公平赔率',
        x=['大球', '小球'],
        y=[fair_over if fair_over != float('inf') else over_odds * 1.5,
           fair_under if fair_under != float('inf') else under_odds * 1.5],
        marker_color='#4361ee',
        text=[f"{fair_over:.3f}" if fair_over != float('inf') else "∞",
              f"{fair_under:.3f}" if fair_under != float('inf') else "∞"],
        textposition='outside',
    ))
    fig_odds.update_layout(
        height=240,
        margin=dict(l=0, r=0, t=10, b=0),
        yaxis=dict(title='赔率', range=[0, max(over_odds, under_odds, fair_over if fair_over != float('inf') else 0, fair_under if fair_under != float('inf') else 0) * 1.25]),
        barmode='group',
        bargap=0.25,
        bargroupgap=0.1,
        hovermode='x',
    )
    st.plotly_chart(fig_odds, use_container_width=True)

    # ----- 5.6 投注建议 -----
    st.markdown("#### 💡 投注建议")

    # 判断哪边更优（损失更小或盈利更大）
    if ev_over_pct >= ev_under_pct:
        better_side = "大球"
        better_ev = ev_over_pct
        better_odds = over_odds
        better_color = "#e63946"
    else:
        better_side = "小球"
        better_ev = ev_under_pct
        better_odds = under_odds
        better_color = "#2ec4b6"

    if ev_over_pct < 0 and ev_under_pct < 0:
        # 双方都为负
        st.warning(
            f"**双方均为负期望值（-EV）**\n\n"
            f"大球 EV = {ev_over_pct:.2f}%　|　小球 EV = {ev_under_pct:.2f}%\n\n"
            f"博彩公司抽水约 **{overround_pct - 100:.1f}%**。无论投哪边，长期来看都会亏损。"
        )
        st.info(
            f"**如果必须选择：偏好 {better_side}**\n\n"
            f"{better_side} 期望损失（{better_ev:.2f}%）"
            f"{'明显小于' if abs(ev_over_pct - ev_under_pct) > 1 else '略小于'}另一方向"
            f"（差异 {abs(ev_over_pct - ev_under_pct):.2f}%）。\n\n"
            + ("进球分布呈右偏形态，高进球概率集中，大球相对有利。"
               if better_side == "大球"
               else "进球偏向低端，小球概率优势明显。")
        )
    else:
        # 有正 EV 的一边
        st.success(
            f"**✅ 正 EV 机会！偏好 {better_side}**\n\n"
            f"{better_side} 期望收益 **+{better_ev:.2f}%**，赔率 {better_odds:.3f}\n\n"
            f"市场定价低于真实概率，存在价值投注机会。"
        )

    # 额外策略提示（四分之一球盘）
    if hcp_type == 'quarter':
        lower = hcp - 0.25
        upper = hcp + 0.25
        near_int = round(hcp)
        # 找整数进球概率
        near_int_prob = 0.0
        for label, p in zip(goal_labels_str, prob_values):
            g = _parse_goal(label)
            if abs(g - near_int) < 0.01:
                near_int_prob = p
                break

        st.info(
            f"**四分之一球盘策略**\n\n"
            f"当前盘口 {hcp}，拆分结算为 {lower} / {upper}。\n\n"
            f"若整数盘 **{near_int}** 进球概率 ({near_int_prob:.1%}) 较高，"
            f"整数盘走水退本金的特性可大幅降低风险。"
        )

    # 理性提醒
    st.caption(
        "⚠️ **博彩有风险，投注需谨慎！** 本文仅为数学分析参考，不构成实际投注建议。"
    )
