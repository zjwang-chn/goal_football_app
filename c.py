#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
c.py - 足球比分分析展示应用（Streamlit）
功能：
- 读取 b.py 生成的 analysis_output.json 文件
- 展示比赛分析记录表，支持筛选、排序、导出 CSV
- 显示数据更新时间、模拟参数等统计信息
"""

import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime

# 页面配置
st.set_page_config(
    page_title="足球分析记录库",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 数据文件目录
DATA_DIR = "data"

# 页面样式
st.markdown("""
<style>
    .main-header { font-size: 32px; font-weight: bold; color: #1F4E79; text-align: center; margin-bottom: 10px; }
    .sub-header { font-size: 20px; font-weight: 600; color: #2C3E50; margin-top: 15px; margin-bottom: 10px; border-bottom: 2px solid #e0e0e0; padding-bottom: 5px; }
    .metric-box { background-color: #f8f9fa; padding: 15px; border-radius: 8px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .metric-value { font-size: 28px; font-weight: bold; color: #1F4E79; }
    .metric-label { font-size: 14px; color: #6c757d; }
</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=600)  # 缓存10分钟
def load_data():
    """加载 data/ 目录下所有 JSON 文件，合并 records 返回；若无有效文件则返回 None"""
    if not os.path.isdir(DATA_DIR):
        return None
    json_files = sorted(
        [f for f in os.listdir(DATA_DIR) if f.endswith(".json")],
        key=lambda f: os.path.getmtime(os.path.join(DATA_DIR, f))
    )
    if not json_files:
        return None

    all_records = []
    # 取所有文件中最新的生成时间作为元信息
    latest_generated_at = ""
    total_processed = 0
    simulation_count = 0

    for fname in json_files:
        fpath = os.path.join(DATA_DIR, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                records = data.get("records", [])
                all_records.extend(records)
                # 元信息取最新文件的值
                gen_at = data.get("generated_at", "")
                if gen_at > latest_generated_at:
                    latest_generated_at = gen_at
                    total_processed = data.get("total_processed", 0)
                    simulation_count = data.get("simulation_count", 0)
        except Exception as e:
            st.warning(f"读取文件 {fname} 失败: {e}")
            continue

    if not all_records:
        return None

    return {
        "generated_at": latest_generated_at,
        "total_processed": total_processed,
        "simulation_count": simulation_count,
        "records": all_records,
    }

def main():
    st.markdown('<p class="main-header">⚽ 足球比分分析记录库</p>', unsafe_allow_html=True)

    data = load_data()
    if data is None:
        st.warning(f"未找到 `{DATA_DIR}/` 目录下的 JSON 数据文件。请先运行 b.py 生成分析结果。")
        st.info("**b.py** 会从 GitHub 获取最新赔率并模拟生成数据，通常由 GitHub Actions 定时执行。")
        return

    # 元信息展示
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📅 数据生成时间", data.get("generated_at", "未知"))
    with col2:
        st.metric("📊 比赛场次", data.get("total_processed", 0))
    with col3:
        sim_n = data.get("simulation_params", {}).get("n_sims", "?")
        try:
            sim_n_display = f"{int(sim_n):,}"
        except (ValueError, TypeError):
            sim_n_display = str(sim_n)
        st.metric("🎲 模拟次数", sim_n_display)

    stop_reason = data.get("stop_reason")
    if stop_reason:
        st.info(f"⏹️ 停止原因: {stop_reason}")

    records = data.get("records", [])
    if not records:
        st.info("暂无任何比赛记录。")
        return

    df = pd.DataFrame(records)

    # ========== 筛选与排序侧边栏 ==========
    st.sidebar.header("🔍 数据筛选")

    # 强制刷新按钮
    if st.sidebar.button("🔄 强制刷新数据（从文件重新加载）"):
        load_data.clear()   # 清除缓存
        st.rerun()          # 重新运行脚本，立即生效

    # 联赛筛选
    if "赛事" in df.columns:
        leagues = sorted(df["赛事"].unique())
        selected_leagues = st.sidebar.multiselect(
            "选择联赛", options=leagues, default=leagues
        )
        if selected_leagues:
            df = df[df["赛事"].isin(selected_leagues)]

    # 搜索框（主队/客队）
    search_term = st.sidebar.text_input("🔎 搜索主队/客队", value="")
    if search_term:
        mask = df["主队"].str.contains(search_term, case=False) | df["客队"].str.contains(search_term, case=False)
        df = df[mask]

    # 排序
    sort_col = st.sidebar.selectbox(
        "排序依据",
        options=["记录时间", "胜概率", "平概率", "负概率", "胜赔付", "平赔付", "负赔付", "主进球", "客进球"]
    )
    ascending = st.sidebar.checkbox("升序", value=False)

    # 对于百分比列，需要转为数值排序
    if sort_col in ["胜概率", "平概率", "负概率"]:
        df_sorted = df.copy()
        df_sorted[sort_col + "_数值"] = df_sorted[sort_col].str.rstrip('%').astype(float)
        df_sorted = df_sorted.sort_values(sort_col + "_数值", ascending=ascending)
        df_sorted = df_sorted.drop(columns=[sort_col + "_数值"])
    elif sort_col in ["胜赔付", "平赔付", "负赔付", "主进球", "客进球"]:
        df_sorted = df.copy()
        df_sorted[sort_col + "_数值"] = df_sorted[sort_col].astype(float)
        df_sorted = df_sorted.sort_values(sort_col + "_数值", ascending=ascending)
        df_sorted = df_sorted.drop(columns=[sort_col + "_数值"])
    elif sort_col == "记录时间":
        df_sorted = df.sort_values(sort_col, ascending=ascending)
    else:
        df_sorted = df

    # ========== 结果展示 ==========
    st.markdown('<p class="sub-header">📋 比赛分析记录</p>', unsafe_allow_html=True)

    # 显示记录数
    st.caption(f"当前显示 {len(df_sorted)} 条记录（共 {len(records)} 条）")

    # 数据表格（使用 st.dataframe 支持交互排序、搜索）
    st.dataframe(
        df_sorted,
        use_container_width=True,
        hide_index=True,
        column_config={
            "match_id": "比赛ID",
            "时间": st.column_config.TextColumn("时间", width="medium"),
            "赛事": "赛事",
            "主队": "主队",
            "客队": "客队",
            "胜概率": st.column_config.TextColumn("胜概率", width="small"),
            "平概率": st.column_config.TextColumn("平概率", width="small"),
            "负概率": st.column_config.TextColumn("负概率", width="small"),
            "主进球": "主进球",
            "客进球": "客进球",
            "胜赔付": "胜赔付",
            "平赔付": "平赔付",
            "负赔付": "负赔付",
            "轮次>10%": "高概率总进球(>10%)",
            "记录时间": "记录时间",
        }
    )

    # ========== 可选：简单统计 ==========
    with st.expander("📈 简单统计（基于当前筛选结果）"):
        col_win, col_draw, col_loss = st.columns(3)
        # 将百分比字符串转为数值
        try:
            avg_home = df_sorted["胜概率"].str.rstrip('%').astype(float).mean()
            avg_draw = df_sorted["平概率"].str.rstrip('%').astype(float).mean()
            avg_away = df_sorted["负概率"].str.rstrip('%').astype(float).mean()
            with col_win:
                st.metric("平均主胜概率", f"{avg_home:.2f}%")
            with col_draw:
                st.metric("平均平局概率", f"{avg_draw:.2f}%")
            with col_loss:
                st.metric("平均客胜概率", f"{avg_away:.2f}%")
        except:
            st.info("无法计算平均值（数据格式问题）")

    # ========== 导出 CSV ==========
    csv_data = df_sorted.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 导出当前筛选结果为 CSV",
        data=csv_data,
        file_name=f"analysis_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
        use_container_width=True
    )

if __name__ == "__main__":
    main()