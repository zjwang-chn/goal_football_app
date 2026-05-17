#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
c.py - 足球比分分析展示应用（Streamlit）
功能：
- 读取 b.py 生成的 analysis_output.json 文件
- 展示比赛分析记录表，支持筛选、排序、导出 CSV
- 显示数据更新时间、模拟参数等统计信息
- 胜赔付、平赔付、负赔付高于平均赔付时高亮显示（黄色背景+黑色加粗）
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


@st.cache_data(ttl=600)
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


def highlight_payout_style(df):
    """
    使用 pandas.DataFrame.style 实现条件格式化
    对胜赔付、平赔付、负赔付三列，高于平均赔付时用黄色背景+黑色加粗高亮
    """
    # 创建样式DataFrame（与原始DataFrame形状相同，初始化为空样式）
    styles = pd.DataFrame('', index=df.index, columns=df.columns)

    # 确保需要比较的列存在且为数值类型
    payout_cols = ['胜赔付', '平赔付', '负赔付']
    avg_col = '平均赔付'

    for col in payout_cols:
        if col in df.columns and avg_col in df.columns:
            # 转换为数值类型（原数据可能为字符串如 "0.9098"）
            try:
                values = pd.to_numeric(df[col], errors='coerce')
                avg_values = pd.to_numeric(df[avg_col], errors='coerce')

                # 找到高于平均赔付的行
                mask = (values > avg_values) & (~values.isna()) & (~avg_values.isna())

                # 设置样式：黄色背景，黑色加粗字体
                styles.loc[mask, col] = 'background-color: #ffeb3b; font-weight: bold; color: #000000;'
            except Exception:
                pass

    return styles


def main():
    st.markdown('<p class="main-header">⚽ 足球分析记录库</p>', unsafe_allow_html=True)

    data = load_data()
    if data is None:
        st.warning(f"未找到 `{DATA_DIR}/` 目录下的 JSON 数据文件。请先运行 b.py 生成分析结果。")
        st.info("**b.py** 会从 GitHub 获取最新赔率并模拟生成数据，通常由 GitHub Actions 定时执行。")
        return

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

    if st.sidebar.button("🔄 强制刷新数据（从文件重新加载）"):
        load_data.clear()
        st.rerun()

    if "赛事" in df.columns:
        leagues = sorted(df["赛事"].unique())
        selected_leagues = st.sidebar.multiselect(
            "选择联赛", options=leagues, default=leagues
        )
        if selected_leagues:
            df = df[df["赛事"].isin(selected_leagues)]

    search_term = st.sidebar.text_input("🔎 搜索主队/客队", value="")
    if search_term:
        mask = df["主队"].str.contains(search_term, case=False) | df["客队"].str.contains(search_term, case=False)
        df = df[mask]

    sort_col = st.sidebar.selectbox(
        "排序依据",
        options=["记录时间", "胜概率", "平概率", "负概率", "胜赔付", "平赔付", "负赔付", "主进球", "客进球"]
    )
    ascending = st.sidebar.checkbox("升序", value=False)

    # 排序逻辑
    df_sorted = df.copy()
    if sort_col in ["胜概率", "平概率", "负概率"]:
        df_sorted[sort_col + "_数值"] = df_sorted[sort_col].str.rstrip('%').astype(float)
        df_sorted = df_sorted.sort_values(sort_col + "_数值", ascending=ascending)
        df_sorted = df_sorted.drop(columns=[sort_col + "_数值"])
    elif sort_col in ["胜赔付", "平赔付", "负赔付", "主进球", "客进球"]:
        df_sorted[sort_col + "_数值"] = df_sorted[sort_col].astype(float)
        df_sorted = df_sorted.sort_values(sort_col + "_数值", ascending=ascending)
        df_sorted = df_sorted.drop(columns=[sort_col + "_数值"])
    elif sort_col == "记录时间":
        df_sorted = df_sorted.sort_values(sort_col, ascending=ascending)

    # ========== 应用高亮样式（核心修改） ==========
    # 使用 pandas.DataFrame.style 实现条件格式化
    styled_df = df_sorted.style.apply(highlight_payout_style, axis=None)

    # 注意：style.apply 的 axis=None 表示对整个DataFrame应用函数
    # 如果遇到性能问题，可以改为逐个列应用：
    # styled_df = df_sorted.style
    # for col in ['胜赔付', '平赔付', '负赔付']:
    #     styled_df = styled_df.apply(lambda x: highlight_payout_style(x, col), subset=[col])

    # ========== 结果展示 ==========
    st.markdown('<p class="sub-header">📋 比赛分析记录</p>', unsafe_allow_html=True)
    st.caption(f"当前显示 {len(df_sorted)} 条记录（共 {len(records)} 条）")

    # 使用 styled_df 替代 df_sorted，不再需要额外的显示列
    st.dataframe(
        styled_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "match_id": st.column_config.TextColumn("比赛ID", width="small"),
            "时间": st.column_config.TextColumn("时间", width=None),
            "赛事": st.column_config.TextColumn("赛事", width=None),
            "主队": st.column_config.TextColumn("主队", width=None),
            "客队": st.column_config.TextColumn("客队", width=None),
            "胜概率": st.column_config.TextColumn("胜概率", width=None),
            "平概率": st.column_config.TextColumn("平概率", width=None),
            "负概率": st.column_config.TextColumn("负概率", width=None),
            "主进球": st.column_config.TextColumn("主进球", width=None),
            "客进球": st.column_config.TextColumn("客进球", width=None),
            "胜赔付": st.column_config.TextColumn("胜赔付", width="small"),
            "平赔付": st.column_config.TextColumn("平赔付", width="small"),
            "负赔付": st.column_config.TextColumn("负赔付", width="small"),
            "平均赔付": st.column_config.TextColumn("平均赔付", width="small"),
            "轮次>10%": st.column_config.TextColumn("高概率总进球", width=None),
            "记录时间": st.column_config.TextColumn("记录时间", width=None),
        }
    )

    # ========== 简单统计 ==========
    with st.expander("📈 简单统计（基于当前筛选结果）"):
        col_win, col_draw, col_loss = st.columns(3)
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
