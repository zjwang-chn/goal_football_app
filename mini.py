import streamlit as st
import random
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
# 计算概率
def calculate_probabilities(odds):
    # 赔率转概率: 概率 = (所有赔率倒数和的倒数) / 赔率
    inverse_sum = sum(1.0 / odd for odd in odds.values())
    factor = 1.0 / inverse_sum
    probs = {goals: factor / odd for goals, odd in odds.items()}
    
    # 计算当前状态下无进球概率和有进球概率
    cumulative = 0.0
    no_goal_probs = {}
    goal_probs = {}
    for goals in sorted(probs.keys()):
        p = probs[goals]
        # 当前已经进了 goals 个球，现在不继续进球的概率
        if cumulative == 0:
            no_goal = p
        else:
            no_goal = p / (1 - cumulative)
        no_goal_probs[goals] = no_goal
        goal_probs[goals] = 1.0 - no_goal
        cumulative += p
    return probs, no_goal_probs, goal_probs
# 主队赔率
home_odds = {0:5, 1:2.75, 2:2.95, 3:4.8, 4:10, 5:20}
# 客队赔率
away_odds = {0:2.9, 1:2.25, 2:3.5, 3:8.2, 4:25, 5:50}
home_probs, home_no_goal, home_goal = calculate_probabilities(home_odds)
away_probs, away_no_goal, away_goal = calculate_probabilities(away_odds)
# 创建概率表格显示
def get_prob_table(probs, no_goal, goal):
    data = []
    for g in sorted(probs.keys()):
        data.append({
            "进球数": g,
            "赔率": home_odds[g] if g in home_odds else away_odds[g],
            "整场概率": round(probs[g], 9),
            "当前状态无进球概率": round(no_goal[g], 9),
            "当前状态有进球概率": round(goal[g], 9)
        })
    return pd.DataFrame(data)
home_df = get_prob_table(home_probs, home_no_goal, home_goal)
away_df = get_prob_table(away_probs, away_no_goal, away_goal)
# 单场模拟函数
def simulate_one_match():
    home_goals = 0
    away_goals = 0
    round_history = []
    rounds = 0
    # 第一轮主队先攻
    turn = "home"  # "home" 主队先攻, "away" 客队先攻
    
    while True:
        rounds += 1  # 每一轮进攻计数+1（不管结果如何都算一轮）
        home_scored = False
        away_scored = False
        finished = False
        
        if turn == "home":
            # 主队进攻
            r = random.random()
            no_goal_p = home_no_goal[home_goals]
            if r < no_goal_p:
                # 主队没进球，轮到客队
                r2 = random.random()
                no_goal_p2 = away_no_goal[away_goals]
                if r2 < no_goal_p2:
                    # 客队也没进球，比赛结束
                    finished = True
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
                    # 客队进球
                    away_goals += 1
                    away_scored = True
                    round_history.append({
                        "轮次": rounds,
                        "进攻方": "主队 -> 客队",
                        "主队随机数": round(r, 6),
                        "主队是否进球": "否",
                        "客队随机数": round(r2, 6),
                        "客队是否进球": "是",
                        "当前比分": f"{home_goals}-{away_goals}"
                    })
                    # 下一轮主队先攻
                    turn = "home"
            else:
                # 主队进球
                home_goals += 1
                home_scored = True
                round_history.append({
                    "轮次": rounds,
                    "进攻方": "主队",
                    "主队随机数": round(r, 6),
                    "主队是否进球": "是",
                    "客队随机数": "",
                    "客队是否进球": "",
                    "当前比分": f"{home_goals}-{away_goals}"
                })
                # 下一轮客队先攻
                turn = "away"
        else:
            # 客队进攻
            r = random.random()
            no_goal_p = away_no_goal[away_goals]
            if r < no_goal_p:
                # 客队没进球，轮到主队
                r2 = random.random()
                no_goal_p2 = home_no_goal[home_goals]
                if r2 < no_goal_p2:
                    # 主队也没进球，比赛结束
                    finished = True
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
                    # 主队进球
                    home_goals += 1
                    home_scored = True
                    round_history.append({
                        "轮次": rounds,
                        "进攻方": "客队 -> 主队",
                        "主队随机数": round(r2, 6),
                        "主队是否进球": "是",
                        "客队随机数": round(r, 6),
                        "客队是否进球": "否",
                        "当前比分": f"{home_goals}-{away_goals}"
                    })
                    # 下一轮客队先攻
                    turn = "away"
            else:
                # 客队进球
                away_goals += 1
                away_scored = True
                round_history.append({
                    "轮次": rounds,
                    "进攻方": "客队",
                    "主队随机数": "",
                    "主队是否进球": "",
                    "客队随机数": round(r, 6),
                    "客队是否进球": "是",
                    "当前比分": f"{home_goals}-{away_goals}"
                })
                # 下一轮主队先攻
                turn = "home"
        
        # 额外强制终止条件：无论如何双方进球上限都是5个，如果都已经进了5个，本轮结束后终止比赛
        # 这个是为了严格匹配概率表定义，防止无限循环
        if home_goals >= 5 and away_goals >= 5:
            finished = True
            break
    
    return {
        "final_score": f"{home_goals}-{away_goals}",
        "home_goals": home_goals,
        "away_goals": away_goals,
        "rounds": rounds,
        "history": pd.DataFrame(round_history)
    }
# 批量模拟
def simulate_matches(n):
    results = []
    for _ in range(n):
        res = simulate_one_match()
        results.append({
            "final_score": res["final_score"],
            "home_goals": res["home_goals"],
            "away_goals": res["away_goals"],
            "rounds": res["rounds"]
        })
    return pd.DataFrame(results)
# Streamlit 页面
st.set_page_config(page_title="迷你足球赛进球模拟", layout="wide")
st.title("⚽ 迷你足球赛进球模拟")
st.markdown("根据您提供的赔率和模拟规则进行蒙特卡洛模拟，支持单场详细轮次追踪和批量统计")
# 侧边栏显示概率表格
with st.expander("📊 查看主队概率表", expanded=False):
    st.dataframe(home_df, width='stretch')
with st.expander("📊 查看客队概率表", expanded=False):
    st.dataframe(away_df, width='stretch')
# 页面导航
page = st.radio("请选择功能", ["概率说明", "单场模拟", "批量模拟统计"])
if page == "概率说明":
    st.header("概率计算说明")
    st.markdown("""
根据老板提供的计算方法：
1. 赔率转概率公式：
$$ P(进球数k) = { {1 \over odds_k }  * { 1 \over \sum { 1 \over odds_i } } } $$
2. 当前已经进 $k$ 球的情况下，**不再进球的概率**：
$$ P(不再进球 | 已经进k球) = { P(总进球k) \over 1 - \sum_{i=0}^{k-1} P(总进球i) } $$
3. 当前已经进 $k$ 球的情况下，**继续进球的概率**：
$$ P(继续进球 | 已经进k球) = 1 - P(不再进球 | 已经进k球) $$
**修正后的逻辑要点：**
- ✅ 无论结果如何，每一轮**进攻流程走完都算1轮**，0-0结束第一轮就是1轮，统计结果会包含1 ✨
- ✅ 进球上限严格控制为5个，双方都达到5球后比赛立即结束，不会产生超过11轮的情况，完美解决概率矛盾点 🎯
- ✅ 5-0 或 0-5 这种一方达到上限另一方没达到的情况，会继续由另一方进攻，直到另一方达到上限或双方都不进球 ⚖️
""")
elif page == "单场模拟":
    st.header("🔍 单场比赛模拟（查看详细轮次）")
    if st.button("开始模拟"):
        result = simulate_one_match()
        st.subheader(f"最终比分: {result['final_score']}，总轮次: {result['rounds']}")
        st.markdown("### 每轮详细进攻记录")
        st.dataframe(result["history"], width='stretch')
elif page == "批量模拟统计":
    st.header("📈 批量模拟统计")
    col1, col2 = st.columns(2)
    with col1:
        n_simulations = st.number_input("模拟次数", min_value=100, max_value=100000, value=10000, step=100)
    with col2:
        st.write("")
        if st.button("开始批量模拟"):
            with st.spinner(f"正在模拟 {n_simulations} 场比赛..."):
                df = simulate_matches(int(n_simulations))
                st.success(f"模拟完成！共 {len(df)} 场比赛")
                
                # 比分统计
                score_counts = df.groupby(["home_goals", "away_goals"]).size().reset_index(name="次数")
                score_counts["频率(%)"] = (score_counts["次数"] / len(df) * 100).round(2)
                score_counts_pivot = score_counts.pivot(index="home_goals", columns="away_goals", values="频率(%)")
                score_counts_pivot = score_counts_pivot.fillna(0)
                
                # 轮次统计
                round_counts = df.groupby("rounds").size().reset_index(name="次数")
                round_counts["频率(%)"] = (round_counts["次数"] / len(df) * 100).round(2)
                
                st.subheader("比分概率分布 (单位: 频率 %)")
                st.dataframe(score_counts_pivot, width='stretch')
                
                st.subheader("总轮次概率分布")
                st.dataframe(round_counts, width='stretch')
                
                # 绘图
                fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
                # 轮次柱状图
                ax1.bar(round_counts["rounds"], round_counts["次数"])
                ax1.set_xlabel("总轮次")
                ax1.set_ylabel("次数")
                ax1.set_title("各轮次次数分布")
                ax1.set_xticks(np.arange(1, max(round_counts["rounds"])+1, 1))
                
                # 进球分布
                home_dist = df.groupby("home_goals").size() / len(df) * 100
                away_dist = df.groupby("away_goals").size() / len(df) * 100
                x = np.arange(6)
                width = 0.35
                ax2.bar(x - width/2, [home_dist.get(i, 0) for i in range(6)], width, label="主队进球")
                ax2.bar(x + width/2, [away_dist.get(i, 0) for i in range(6)], width, label="客队进球")
                ax2.set_xlabel("进球数")
                ax2.set_ylabel("频率 (%)")
                ax2.set_title("主客队进球数频率分布")
                ax2.set_xticks(x)
                ax2.legend()
                
                st.pyplot(fig)