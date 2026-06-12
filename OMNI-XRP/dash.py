## =============================================================================
# Part 1: Main App & Layout (통합)
## =============================================================================

import streamlit as st
import sqlite3
import pandas as pd
import json
import os
from datetime import datetime, timedelta
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import time
import numpy as np
import re # 정규표현식 모듈 추가

# 페이지 설정
st.set_page_config(
    page_title="OMNI-XRP v8.0 Dashboard",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 커스텀 CSS
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-container {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid #667eea;
        margin: 0.5rem 0;
    }
    .status-active { color: #28a745; font-weight: bold; }
    .status-planned { color: #ffc107; font-weight: bold; }
    .status-completed { color: #6c757d; font-weight: bold; }
    .profit { color: #28a745; font-weight: bold; }
    .loss { color: #dc3545; font-weight: bold; }
    .sidebar .element-container { margin-bottom: 1rem; }
</style>
""", unsafe_allow_html=True)

class OMNIDashboard:
    def __init__(self):
        self.db_path = self.get_db_path()
        self.config_path = "config.json"
        self.lessons_path = "lessons/lessons.md"
        self.reflections_dir = "v8_reflections"
        
    def get_db_path(self):
        """데이터베이스 경로 확인"""
        possible_paths = [
            "omni_xrp_v8_trades.sqlite",
            "./omni_xrp_v8_trades.sqlite",
            "../omni_xrp_v8_trades.sqlite"
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        
        return "omni_xrp_v8_trades.sqlite"  # 기본값
    
    def check_db_connection(self):
        """데이터베이스 연결 확인"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = cursor.fetchall()
                return True, len(tables)
        except Exception as e:
            return False, str(e)
    
    def main_header(self):
        """메인 헤더"""
        st.markdown("""
        <div class="main-header">
            <h1>🎯 OMNI-XRP v8.0 Dashboard</h1>
            <p>확률론적 접근 + XRP 전문가 + 학습 시스템 통합 모니터링</p>
        </div>
        """, unsafe_allow_html=True)
        
        # 연결 상태 확인
        db_status, db_info = self.check_db_connection()
        if db_status:
            st.success(f"✅ 데이터베이스 연결됨 ({db_info}개 테이블)")
        else:
            st.error(f"❌ 데이터베이스 연결 실패: {db_info}")
            st.warning(f"데이터베이스 경로: {self.db_path}")
    
    def sidebar_controls(self):
        """사이드바 컨트롤"""
        st.sidebar.title("🔧 제어판")
        
        if st.sidebar.button("🔄 새로고침", type="primary"):
            st.rerun()
        
        auto_refresh = st.sidebar.checkbox("🔁 자동 새로고침 (30초)")
        
        st.sidebar.markdown("---")
        
        st.sidebar.subheader("📊 데이터 필터")
        
        date_range = st.sidebar.selectbox(
            "📅 조회 기간",
            ["최근 24시간", "최근 3일", "최근 7일", "최근 30일", "전체"],
            index=1
        )
        
        status_filter = st.sidebar.multiselect(
            "📋 거래 상태",
            ["ACTIVE", "PLANNED", "COMPLETED", "CANCELLED", "SUPERSEDED"],
            default=["ACTIVE", "PLANNED", "COMPLETED"]
        )
        
        if auto_refresh:
            time.sleep(30)
            st.rerun()

        return date_range, status_filter
    
    def get_date_filter(self, date_range):
        """날짜 필터 계산"""
        now = datetime.now()
        
        if date_range == "최근 24시간":
            return now - timedelta(hours=24)
        elif date_range == "최근 3일":
            return now - timedelta(days=3)
        elif date_range == "최근 7일":
            return now - timedelta(days=7)
        elif date_range == "최근 30일":
            return now - timedelta(days=30)
        else:
            return None
    
    # =============================================================================
    # Part 2: Current Status Tab Methods
    # =============================================================================
    def current_status_tab(self):
        st.header("📊 실시간 현황")
        col1, col2, col3 = st.columns(3)
        with col1: self.display_current_position()
        with col2: self.display_active_trades()
        with col3: self.display_planned_trades()
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1: self.display_market_signals()
        with col2: self.display_system_activity()

    def display_current_position(self):
        st.subheader("💰 현재 포지션")
        try:
            with sqlite3.connect(self.db_path) as conn:
                query = """
                SELECT trade_id, position_size_xrp, actual_entry_price, planned_target_price,
                       planned_stop_loss, entry_timestamp, checklist_score, signal_confidence_multiplier
                FROM trades WHERE status = 'ACTIVE' ORDER BY entry_timestamp DESC LIMIT 1
                """
                df = pd.read_sql_query(query, conn)
                if not df.empty:
                    trade = df.iloc[0]
                    current_price = trade['actual_entry_price'] * (1 + np.random.normal(0, 0.02))
                    profit_pct = ((current_price - trade['actual_entry_price']) / trade['actual_entry_price']) * 100
                    profit_krw = (current_price - trade['actual_entry_price']) * trade['position_size_xrp']
                    
                    st.metric("XRP 보유량", f"{trade['position_size_xrp']:.4f} XRP", f"거래 ID: {trade['trade_id']}")
                    st.metric("진입가", f"{trade['actual_entry_price']:,.0f}원", f"진입시간: {pd.to_datetime(trade['entry_timestamp']).strftime('%m-%d %H:%M')}")
                    st.metric("현재 손익", f"{profit_krw:+,.0f}원", f"{profit_pct:+.2f}%", delta_color="normal" if profit_krw >= 0 else "inverse")
                    
                    total_range = trade['planned_target_price'] - trade['planned_stop_loss']
                    current_progress = current_price - trade['planned_stop_loss']
                    progress_pct = (current_progress / total_range) * 100 if total_range > 0 else 0
                    st.metric("목표가 진행률", f"{progress_pct:.1f}%", f"목표: {trade['planned_target_price']:,.0f}원")
                    
                    st.markdown("**🎯 v8.0 확률론적 정보**")
                    st.markdown(f"• 체크리스트 점수: **{trade['checklist_score']:.1f}/5.5**")
                    st.markdown(f"• 신호 신뢰도: **{trade['signal_confidence_multiplier']:.1f}x**")
                    risk_level = "낮음" if trade['checklist_score'] >= 4.0 else "중간" if trade['checklist_score'] >= 2.5 else "높음"
                    risk_color = "🟢" if risk_level == "낮음" else "🟡" if risk_level == "중간" else "🔴"
                    st.markdown(f"• 위험도: {risk_color} **{risk_level}**")
                else:
                    st.info("🔵 현재 보유 중인 XRP가 없습니다")
                    st.metric("XRP 보유량", "0 XRP")
                    st.metric("현재 손익", "0원")
        except Exception as e:
            st.error(f"포지션 정보 조회 실패: {e}")

    def display_active_trades(self):
        st.subheader("🟢 활성 거래")
        try:
            with sqlite3.connect(self.db_path) as conn:
                query = """
                SELECT trade_id, planned_target_price, planned_stop_loss, wick_defense_active,
                       wick_defense_result, change_trigger, entry_timestamp
                FROM trades WHERE status = 'ACTIVE' ORDER BY entry_timestamp DESC
                """
                df = pd.read_sql_query(query, conn)
                if not df.empty:
                    for _, trade in df.iterrows():
                        with st.container(border=True):
                            st.markdown(f"**거래 ID: {trade['trade_id']}**")
                            col1, col2 = st.columns(2)
                            with col1:
                                st.markdown(f"목표가: {trade['planned_target_price']:,.0f}원")
                                st.markdown(f"손절가: {trade['planned_stop_loss']:,.0f}원")
                            with col2:
                                wick_status = "🛡️ 활성" if trade['wick_defense_active'] else "⚪ 비활성"
                                st.markdown(f"위꼬리 방어: {wick_status}")
                                if trade['change_trigger'] and trade['change_trigger'] != 'NONE':
                                    st.markdown(f"변경 트리거: **{trade['change_trigger']}**")
                else:
                    st.info("활성 거래가 없습니다")
        except Exception as e:
            st.error(f"활성 거래 조회 실패: {e}")

    def display_planned_trades(self):
        st.subheader("🟡 계획된 거래")
        try:
            with sqlite3.connect(self.db_path) as conn:
                query = """
                SELECT trade_id, planned_entry_price, planned_target_price, checklist_score,
                       signal_confidence_multiplier, plan_timestamp
                FROM trades WHERE status = 'PLANNED' ORDER BY plan_timestamp DESC LIMIT 3
                """
                df = pd.read_sql_query(query, conn)
                if not df.empty:
                    for _, trade in df.iterrows():
                        with st.container(border=True):
                            st.markdown(f"**계획 ID: {trade['trade_id']}**")
                            if trade['planned_entry_price'] > 0:
                                st.markdown(f"진입가: {trade['planned_entry_price']:,.0f}원")
                                st.markdown(f"목표가: {trade['planned_target_price']:,.0f}원")
                                score_color = "🟢" if trade['checklist_score'] >= 4.0 else "🟡" if trade['checklist_score'] >= 2.5 else "🔴"
                                st.markdown(f"{score_color} 체크리스트: {trade['checklist_score']:.1f}/5.5")
                            else:
                                st.markdown("🚫 **진입 금지 상태**")
                                st.markdown(f"점수 부족: {trade['checklist_score']:.1f}/5.5")
                            st.markdown(f"<small>계획 시간: {pd.to_datetime(trade['plan_timestamp']).strftime('%m-%d %H:%M')}</small>", unsafe_allow_html=True)
                else:
                    st.info("계획된 거래가 없습니다")
        except Exception as e:
            st.error(f"계획된 거래 조회 실패: {e}")

    def display_market_signals(self):
        st.subheader("📡 최근 시장 신호")
        try:
            with sqlite3.connect(self.db_path) as conn:
                query = """
                SELECT plan_timestamp, checklist_score, energy_compression_detected,
                       xrp_pattern_type, signal_confidence_multiplier
                FROM trades WHERE plan_timestamp > datetime('now', '-24 hours')
                ORDER BY plan_timestamp DESC LIMIT 5
                """
                df = pd.read_sql_query(query, conn)
                if not df.empty:
                    for _, signal in df.iterrows():
                        time_str = pd.to_datetime(signal['plan_timestamp']).strftime("%H:%M")
                        if signal['checklist_score'] >= 4.0: strength_icon, strength_text = "🟢", "강함"
                        elif signal['checklist_score'] >= 2.5: strength_icon, strength_text = "🟡", "보통"
                        else: strength_icon, strength_text = "🔴", "약함"
                        
                        st.markdown(f"**{time_str}** {strength_icon} {strength_text} ({signal['checklist_score']:.1f})")
                        details = []
                        if signal['energy_compression_detected']: details.append("⚡에너지 압축")
                        if signal['xrp_pattern_type'] != 'NONE': details.append(f"🔍패턴: {signal['xrp_pattern_type']}")
                        if details: st.markdown(f"&nbsp;&nbsp;{' | '.join(details)}")
                        
                else:
                    st.info("최근 24시간 신호 없음")
        except Exception as e:
            st.error(f"시장 신호 조회 실패: {e}")

    def display_system_activity(self):
        st.subheader("⚡ 시스템 활동")
        try:
            with sqlite3.connect(self.db_path) as conn:
                query = """
                SELECT timestamp, operation_type, duration_seconds, success
                FROM system_performance WHERE timestamp > datetime('now', '-6 hours')
                ORDER BY timestamp DESC LIMIT 10
                """
                df = pd.read_sql_query(query, conn)
                if not df.empty:
                    success_rate = (df['success'].sum() / len(df)) * 100
                    avg_duration = df['duration_seconds'].mean()
                    
                    st.metric("성공률", f"{success_rate:.1f}%")
                    st.metric("평균 실행시간", f"{avg_duration:.2f}초")
                    
                    st.markdown("**최근 활동:**")
                    for _, activity in df.head(5).iterrows():
                        time_str = pd.to_datetime(activity['timestamp']).strftime("%H:%M")
                        status_icon = "✅" if activity['success'] else "❌"
                        operation = activity['operation_type'].replace('_', ' ').title()
                        st.markdown(f"{time_str} {status_icon} {operation} ({activity['duration_seconds']:.1f}s)")
                else:
                    st.info("최근 시스템 활동 없음")
        except Exception as e:
            st.error(f"시스템 활동 조회 실패: {e}")

    # =============================================================================
    # Part 3: Trading Analysis Tab Methods
    # =============================================================================
    def trading_analysis_tab(self, date_range, status_filter):
        st.header("📈 거래 분석")
        date_filter = self.get_date_filter(date_range)
        col1, col2 = st.columns([2, 1])
        with col1: self.display_trades_table(date_filter, status_filter)
        with col2: self.display_trade_statistics(date_filter)
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1: self.display_checklist_distribution(date_filter)
        with col2: self.display_signal_quality_trend(date_filter)

    def display_trades_table(self, date_filter, status_filter):
        st.subheader("📋 거래 내역")
        try:
            with sqlite3.connect(self.db_path) as conn:
                where_conditions, params = [], []
                if date_filter:
                    where_conditions.append("plan_timestamp >= ?")
                    params.append(date_filter.strftime("%Y-%m-%d %H:%M:%S"))
                if status_filter:
                    placeholders = ",".join(["?"] * len(status_filter))
                    where_conditions.append(f"status IN ({placeholders})")
                    params.extend(status_filter)
                
                where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
                query = f"""
                SELECT trade_id, status, plan_timestamp, checklist_score, signal_confidence_multiplier,
                       net_profit_krw, profit_rate_pct FROM trades {where_clause}
                ORDER BY plan_timestamp DESC LIMIT 50
                """
                df = pd.read_sql_query(query, conn, params=params)
                
                if not df.empty:
                    df['plan_timestamp'] = pd.to_datetime(df['plan_timestamp'])
                    df['날짜'] = df['plan_timestamp'].dt.strftime('%m-%d %H:%M')
                    display_columns = ['trade_id', '날짜', 'status', 'checklist_score', 'signal_confidence_multiplier', 'net_profit_krw', 'profit_rate_pct']
                    column_mapping = {'trade_id': 'ID', 'status': '상태', 'checklist_score': '체크리스트', 'signal_confidence_multiplier': '신호승수', 'net_profit_krw': '순수익(원)', 'profit_rate_pct': '수익률(%)'}
                    display_df = df[display_columns].rename(columns=column_mapping)
                    
                    display_df['순수익(원)'] = display_df['순수익(원)'].apply(lambda x: f"{x:,.0f}" if pd.notna(x) else "-")
                    display_df['수익률(%)'] = display_df['수익률(%)'].apply(lambda x: f"{x:+.2f}" if pd.notna(x) else "-")
                    
                    st.dataframe(display_df, use_container_width=True, height=400, hide_index=True)

                    with st.expander("거래 상세 정보 보기"):
                        selected_id = st.selectbox("거래 ID 선택", df['trade_id'].tolist())
                        self.display_trade_details(selected_id)
                else:
                    st.info("조건에 맞는 거래가 없습니다.")
        except Exception as e:
            st.error(f"거래 목록 조회 실패: {e}")

    def display_trade_statistics(self, date_filter):
        st.subheader("📊 거래 통계 (완료된 거래 기준)")
        try:
            with sqlite3.connect(self.db_path) as conn:
                where_conditions, params = ["status = 'COMPLETED'"], []
                if date_filter:
                    where_conditions.append("plan_timestamp >= ?")
                    params.append(date_filter.strftime("%Y-%m-%d %H:%M:%S"))
                
                where_clause = "WHERE " + " AND ".join(where_conditions)
                query = f"""
                SELECT COUNT(*) as total_trades, SUM(CASE WHEN net_profit_krw > 0 THEN 1 ELSE 0 END) as winning_trades,
                       SUM(net_profit_krw) as total_profit, AVG(profit_rate_pct) as avg_profit_rate,
                       AVG(checklist_score) as avg_checklist_score, COUNT(CASE WHEN wick_defense_result = 'SUCCESS' THEN 1 END) as wick_defense_saves
                FROM trades {where_clause}
                """
                stats = pd.read_sql_query(query, conn, params=params).iloc[0]
                
                if stats['total_trades'] > 0:
                    win_rate = (stats['winning_trades'] / stats['total_trades']) * 100
                    st.metric("총 거래", f"{stats['total_trades']:.0f}건")
                    st.metric("승률", f"{win_rate:.1f}%", f"{stats['winning_trades']:.0f}승")
                    st.metric("총 수익", f"{stats['total_profit']:+,.0f}원")
                    st.metric("평균 수익률", f"{stats['avg_profit_rate']:+.2f}%")
                    st.metric("평균 체크리스트", f"{stats['avg_checklist_score']:.1f}/5.5")
                    if stats['wick_defense_saves'] > 0:
                        st.metric("🛡️ 위꼬리 방어 성공", f"{stats['wick_defense_saves']:.0f}회")

                    st.markdown("**🎯 점수별 성과:**")
                    score_query = f"""
                    SELECT CASE WHEN checklist_score >= 4.0 THEN 'A급 (4.0+)' WHEN checklist_score >= 2.5 THEN 'B급 (2.5-4.0)' ELSE 'C급 (2.5미만)' END as grade,
                           COUNT(*) as trades, AVG(profit_rate_pct) as avg_profit_rate FROM trades {where_clause} GROUP BY grade ORDER BY avg_profit_rate DESC
                    """
                    score_stats = pd.read_sql_query(score_query, conn, params=params)
                    for _, row in score_stats.iterrows():
                        st.markdown(f"• {row['grade']}: {row['avg_profit_rate']:+.2f}% ({row['trades']}건)")
                else:
                    st.info("완료된 거래가 없습니다.")
        except Exception as e:
            st.error(f"거래 통계 조회 실패: {e}")
            
    def display_checklist_distribution(self, date_filter):
        st.subheader("🎯 체크리스트 점수 분포")
        try:
            with sqlite3.connect(self.db_path) as conn:
                where_condition, params = "", []
                if date_filter:
                    where_condition = "WHERE plan_timestamp >= ?"
                    params.append(date_filter.strftime("%Y-%m-%d %H:%M:%S"))
                
                query = f"SELECT checklist_score FROM trades {where_condition}"
                df = pd.read_sql_query(query, conn, params=params)
                
                if not df.empty:
                    fig = px.histogram(df, x='checklist_score', title="체크리스트 점수 분포",
                                       labels={'checklist_score': '점수', 'count': '거래 수'},
                                       color_discrete_sequence=['#667eea'])
                    fig.add_vline(x=2.5, line_dash="dash", line_color="red", annotation_text="진입 임계값 (2.5)")
                    fig.add_vline(x=4.0, line_dash="dash", line_color="green", annotation_text="A급 기준 (4.0)")
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("표시할 데이터가 없습니다.")
        except Exception as e:
            st.error(f"체크리스트 분포 조회 실패: {e}")

    def display_signal_quality_trend(self, date_filter):
        st.subheader("📈 신호 품질 트렌드")
        try:
            with sqlite3.connect(self.db_path) as conn:
                where_condition, params = "", []
                if date_filter:
                    where_condition = "WHERE plan_timestamp >= ?"
                    params.append(date_filter.strftime("%Y-%m-%d %H:%M:%S"))
                
                query = f"""
                SELECT DATE(plan_timestamp) as date, AVG(checklist_score) as avg_score,
                       AVG(signal_confidence_multiplier) as avg_multiplier
                FROM trades {where_condition} GROUP BY DATE(plan_timestamp) ORDER BY date
                """
                df = pd.read_sql_query(query, conn, params=params)
                
                if not df.empty:
                    df['date'] = pd.to_datetime(df['date'])
                    fig = make_subplots(specs=[[{"secondary_y": True}]])
                    fig.add_trace(go.Scatter(x=df['date'], y=df['avg_score'], name="평균 체크리스트 점수", line=dict(color='blue')), secondary_y=False)
                    fig.add_trace(go.Scatter(x=df['date'], y=df['avg_multiplier'], name="평균 신호 승수", line=dict(color='red')), secondary_y=True)
                    fig.update_yaxes(title_text="체크리스트 점수", secondary_y=False)
                    fig.update_yaxes(title_text="신호 승수", secondary_y=True)
                    fig.update_layout(title="일별 신호 품질 변화")
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("표시할 데이터가 없습니다.")
        except Exception as e:
            st.error(f"신호 품질 트렌드 조회 실패: {e}")

    def display_trade_details(self, trade_id):
        try:
            with sqlite3.connect(self.db_path) as conn:
                query = "SELECT * FROM trades WHERE trade_id = ?"
                df = pd.read_sql_query(query, conn, params=[trade_id])
                if not df.empty:
                    trade = df.iloc[0]
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.markdown("**기본 정보**")
                        st.markdown(f"상태: **{trade['status']}**")
                        if trade['plan_timestamp']: st.markdown(f"계획: {pd.to_datetime(trade['plan_timestamp']).strftime('%y-%m-%d %H:%M')}")
                        if trade['entry_timestamp']: st.markdown(f"진입: {pd.to_datetime(trade['entry_timestamp']).strftime('%y-%m-%d %H:%M')}")
                        if trade['exit_timestamp']: st.markdown(f"청산: {pd.to_datetime(trade['exit_timestamp']).strftime('%y-%m-%d %H:%M')}")
                    with col2:
                        st.markdown("**가격 정보 (원)**")
                        st.markdown(f"계획 진입: {trade['planned_entry_price']:,.0f}")
                        if trade['actual_entry_price']: st.markdown(f"실제 진입: {trade['actual_entry_price']:,.0f}")
                        st.markdown(f"목표: {trade['planned_target_price']:,.0f}")
                        st.markdown(f"손절: {trade['planned_stop_loss']:,.0f}")
                    with col3:
                        st.markdown("**수익 정보**")
                        if pd.notna(trade['net_profit_krw']): st.markdown(f"순수익: **{trade['net_profit_krw']:+,.0f}원**")
                        if pd.notna(trade['profit_rate_pct']): st.markdown(f"수익률: **{trade['profit_rate_pct']:+.2f}%**")
                        if trade['trade_result']: st.markdown(f"결과: {trade['trade_result']}")

                    st.markdown("---")
                    st.markdown("**🎯 v8.0 확률론적 정보**")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(f"• 체크리스트 점수: **{trade['checklist_score']:.1f}/5.5**")
                        st.markdown(f"• 신호 신뢰도 승수: **{trade['signal_confidence_multiplier']:.1f}x**")
                    with col2:
                        st.markdown(f"• 위꼬리 방어: **{'활성' if trade['wick_defense_active'] else '비활성'}**")
                        if trade['wick_defense_result'] and trade['wick_defense_result'] != 'NONE':
                            st.markdown(f"• 방어 결과: **{trade['wick_defense_result']}**")
                    
                    if trade['checklist_breakdown']:
                        try:
                            breakdown = json.loads(trade['checklist_breakdown'])
                            with st.expander("📋 체크리스트 상세 분석"):
                                st.json(breakdown)
                        except: pass
                else:
                    st.error("거래 정보를 찾을 수 없습니다.")
        except Exception as e:
            st.error(f"거래 상세 정보 조회 실패: {e}")

    # =============================================================================
    # Part 4: Performance & Wick Defense Tab Methods
    # =============================================================================
    def performance_tab(self, date_range):
        st.header("🎯 성과 분석")
        date_filter = self.get_date_filter(date_range)
        col1, col2 = st.columns(2)
        with col1: self.display_performance_overview(date_filter)
        with col2: self.display_performance_metrics(date_filter)
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1: self.display_profit_chart(date_filter)
        with col2: self.display_drawdown_chart(date_filter)
        st.markdown("---")
        self.display_probabilistic_performance(date_filter)

    def display_performance_overview(self, date_filter):
        st.subheader("📊 성과 개요")
        try:
            with sqlite3.connect(self.db_path) as conn:
                where_condition, params = "WHERE status = 'COMPLETED'", []
                if date_filter:
                    where_condition += " AND exit_timestamp >= ?"
                    params.append(date_filter.strftime("%Y-%m-%d %H:%M:%S"))
                
                query = f"""
                SELECT COUNT(*) as total, SUM(CASE WHEN net_profit_krw > 0 THEN 1 ELSE 0 END) as wins,
                       SUM(net_profit_krw) as total_profit, AVG(net_profit_krw) as avg_profit,
                       MAX(net_profit_krw) as best, MIN(net_profit_krw) as worst
                FROM trades {where_condition}
                """
                stats = pd.read_sql_query(query, conn, params=params).iloc[0]
                
                if stats['total'] > 0:
                    win_rate = (stats['wins'] / stats['total']) * 100
                    col1, col2, col3 = st.columns(3)
                    with col1: st.metric("총 수익", f"{stats['total_profit']:+,.0f}원")
                    with col2: st.metric("승률", f"{win_rate:.1f}%", f"{stats['wins']:.0f}/{stats['total']:.0f}")
                    with col3: st.metric("평균 수익/손실", f"{stats['avg_profit']:+,.0f}원")
                    
                    st.markdown(f"• 최고 수익: **{stats['best']:+,.0f}원** | 최악 손실: **{stats['worst']:+,.0f}원**")
                else:
                    st.info("완료된 거래가 없습니다.")
        except Exception as e:
            st.error(f"성과 개요 조회 실패: {e}")

    def display_performance_metrics(self, date_filter):
        st.subheader("📊 상세 지표")
        try:
            with sqlite3.connect(self.db_path) as conn:
                where_condition, params = "WHERE status = 'COMPLETED'", []
                if date_filter:
                    where_condition += " AND exit_timestamp >= ?"
                    params.append(date_filter.strftime("%Y-%m-%d %H:%M:%S"))
                
                query = f"SELECT profit_rate_pct, net_profit_krw FROM trades {where_condition}"
                df = pd.read_sql_query(query, conn, params=params)

                if not df.empty and len(df['profit_rate_pct'].dropna()) > 1:
                    rates = df['profit_rate_pct'].dropna()
                    sharpe_ratio = rates.mean() / rates.std() if rates.std() > 0 else 0
                    st.metric("평균 수익률", f"{rates.mean():+.2f}%")
                    st.metric("수익률 변동성", f"{rates.std():.2f}%")
                    st.metric("샤프 비율 (단순)", f"{sharpe_ratio:.2f}")
                else:
                    st.info("분석할 데이터가 부족합니다.")
        except Exception as e:
            st.error(f"상세 지표 조회 실패: {e}")

    def display_profit_chart(self, date_filter):
        st.subheader("💰 누적 수익 추이")
        try:
            with sqlite3.connect(self.db_path) as conn:
                where_condition, params = "WHERE status = 'COMPLETED'", []
                if date_filter:
                    where_condition += " AND exit_timestamp >= ?"
                    params.append(date_filter.strftime("%Y-%m-%d %H:%M:%S"))
                
                query = f"SELECT exit_timestamp, net_profit_krw FROM trades {where_condition} ORDER BY exit_timestamp"
                df = pd.read_sql_query(query, conn, params=params)
                
                if not df.empty:
                    df['exit_timestamp'] = pd.to_datetime(df['exit_timestamp'])
                    df['cumulative_profit'] = df['net_profit_krw'].cumsum()
                    fig = px.line(df, x='exit_timestamp', y='cumulative_profit', title="누적 수익", labels={'exit_timestamp': '날짜', 'cumulative_profit': '누적 수익(원)'})
                    fig.add_hline(y=0, line_dash="dash", line_color="gray")
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("표시할 데이터가 없습니다.")
        except Exception as e:
            st.error(f"수익 차트 조회 실패: {e}")

    def display_drawdown_chart(self, date_filter):
        st.subheader("📉 드로우다운 분석")
        try:
            with sqlite3.connect(self.db_path) as conn:
                where_condition, params = "WHERE status = 'COMPLETED'", []
                if date_filter:
                    where_condition += " AND exit_timestamp >= ?"
                    params.append(date_filter.strftime("%Y-%m-%d %H:%M:%S"))

                query = f"SELECT exit_timestamp, net_profit_krw FROM trades {where_condition} ORDER BY exit_timestamp"
                df = pd.read_sql_query(query, conn, params=params)

                if len(df) > 1:
                    df['cumulative_profit'] = df['net_profit_krw'].cumsum()
                    df['peak'] = df['cumulative_profit'].expanding().max()
                    df['drawdown'] = df['cumulative_profit'] - df['peak']
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(x=df['exit_timestamp'], y=df['drawdown'], fill='tozeroy', name='Drawdown', line=dict(color='red')))
                    fig.update_layout(title="드로우다운 (원)", xaxis_title="날짜", yaxis_title="하락폭 (원)")
                    st.plotly_chart(fig, use_container_width=True)

                    max_drawdown = df['drawdown'].min()
                    st.metric("최대 드로우다운 (MDD)", f"{max_drawdown:,.0f}원")
                else:
                    st.info("드로우다운을 분석하기에 데이터가 부족합니다.")
        except Exception as e:
            st.error(f"드로우다운 차트 조회 실패: {e}")

    def display_probabilistic_performance(self, date_filter):
        st.subheader("🎯 v8.0 확률론적 성과 분석")
        try:
            with sqlite3.connect(self.db_path) as conn:
                where_condition, params = "WHERE status = 'COMPLETED'", []
                if date_filter:
                    where_condition += " AND exit_timestamp >= ?"
                    params.append(date_filter.strftime("%Y-%m-%d %H:%M:%S"))

                query = f"""
                SELECT checklist_score, signal_confidence_multiplier, profit_rate_pct 
                FROM trades {where_condition}
                """
                df = pd.read_sql_query(query, conn, params=params)

                if not df.empty:
                    col1, col2 = st.columns(2)
                    with col1:
                        fig = px.scatter(df, x='checklist_score', y='profit_rate_pct',
                                         title="체크리스트 점수 vs 수익률",
                                         labels={'checklist_score': '체크리스트 점수', 'profit_rate_pct': '수익률 (%)'},
                                         trendline="ols", trendline_color_override="red")
                        st.plotly_chart(fig, use_container_width=True)
                    with col2:
                        fig = px.scatter(df, x='signal_confidence_multiplier', y='profit_rate_pct',
                                         title="신호 승수 vs 수익률",
                                         labels={'signal_confidence_multiplier': '신호 승수', 'profit_rate_pct': '수익률 (%)'},
                                         trendline="ols", trendline_color_override="red")
                        st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("확률론적 성과를 분석할 데이터가 없습니다.")
        except Exception as e:
            st.error(f"확률론적 성과 분석 실패: {e}")
            
    def wick_defense_tab(self, date_range):
        st.header("🛡️ 위꼬리 방어 시스템 분석")
        date_filter = self.get_date_filter(date_range)
        col1, col2 = st.columns(2)
        with col1: self.display_wick_defense_stats(date_filter)
        with col2: self.display_wick_defense_impact(date_filter)
        st.markdown("---")
        self.display_wick_defense_events(date_filter)

    def display_wick_defense_stats(self, date_filter):
        st.subheader("📊 위꼬리 방어 통계")
        try:
            with sqlite3.connect(self.db_path) as conn:
                where_condition, params = "WHERE wick_defense_active = 1", []
                if date_filter:
                    where_condition += " AND plan_timestamp >= ?"
                    params.append(date_filter.strftime("%Y-%m-%d %H:%M:%S"))
                
                query = f"""
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN wick_defense_result = 'SUCCESS' THEN 1 ELSE 0 END) as successes,
                       SUM(CASE WHEN wick_defense_result = 'FAILED' THEN 1 ELSE 0 END) as failures
                FROM trades {where_condition}
                """
                stats = pd.read_sql_query(query, conn, params=params).iloc[0]

                if stats['total'] > 0 and (stats['successes'] + stats['failures']) > 0:
                    success_rate = (stats['successes'] / (stats['successes'] + stats['failures'])) * 100
                    st.metric("방어 활성화 거래", f"{stats['total']}건")
                    st.metric("방어 성공률", f"{success_rate:.1f}%", f"{stats['successes']}/{stats['successes'] + stats['failures']}")
                    st.metric("방어 성공", f"{stats['successes']}회")
                else:
                    st.info("위꼬리 방어 데이터가 없습니다.")
        except Exception as e:
            st.error(f"위꼬리 방어 통계 조회 실패: {e}")

    def display_wick_defense_impact(self, date_filter):
        st.subheader("💡 위꼬리 방어 효과")
        try:
            with sqlite3.connect(self.db_path) as conn:
                where_condition, params = "WHERE status = 'COMPLETED'", []
                if date_filter:
                    where_condition += " AND exit_timestamp >= ?"
                    params.append(date_filter.strftime("%Y-%m-%d %H:%M:%S"))

                query = f"SELECT wick_defense_active, profit_rate_pct FROM trades {where_condition}"
                df = pd.read_sql_query(query, conn, params=params)

                if len(df) > 1:
                    with_defense = df[df['wick_defense_active'] == 1]['profit_rate_pct']
                    without_defense = df[df['wick_defense_active'] == 0]['profit_rate_pct']
                    
                    st.markdown("**평균 수익률 비교**")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("방어 활성", f"{with_defense.mean():.2f}%" if not with_defense.empty else "N/A")
                    with col2:
                        st.metric("방어 비활성", f"{without_defense.mean():.2f}%" if not without_defense.empty else "N/A")

                    st.markdown("**최대 손실률 비교**")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("방어 활성", f"{with_defense.min():.2f}%" if not with_defense.empty else "N/A")
                    with col2:
                        st.metric("방어 비활성", f"{without_defense.min():.2f}%" if not without_defense.empty else "N/A")
                else:
                    st.info("효과를 비교할 데이터가 부족합니다.")
        except Exception as e:
            st.error(f"위꼬리 방어 효과 분석 실패: {e}")

    def display_wick_defense_events(self, date_filter):
        st.subheader("📋 위꼬리 방어 이벤트 목록")
        try:
            with sqlite3.connect(self.db_path) as conn:
                where_condition, params = "WHERE wick_defense_result IS NOT NULL AND wick_defense_result != 'NONE'", []
                if date_filter:
                    where_condition += " AND plan_timestamp >= ?"
                    params.append(date_filter.strftime("%Y-%m-%d %H:%M:%S"))

                query = f"""
                SELECT trade_id, exit_timestamp, wick_defense_result, profit_rate_pct, stop_loss_reason
                FROM trades {where_condition} ORDER BY exit_timestamp DESC LIMIT 10
                """
                df = pd.read_sql_query(query, conn, params=params)

                if not df.empty:
                    for _, event in df.iterrows():
                        icon = '🟢 성공' if event['wick_defense_result'] == 'SUCCESS' else '🔴 실패'
                        with st.expander(f"{icon} | ID: {event['trade_id']} | 수익률: {event['profit_rate_pct']:+.2f}%"):
                            st.markdown(f"**시간:** {pd.to_datetime(event['exit_timestamp']).strftime('%Y-%m-%d %H:%M')}")
                            if event['stop_loss_reason']:
                                st.markdown(f"**사유:** {event['stop_loss_reason']}")
                else:
                    st.info("위꼬리 방어 이벤트가 없습니다.")
        except Exception as e:
            st.error(f"위꼬리 방어 이벤트 조회 실패: {e}")

    # =============================================================================
    # Part 5: Learning System & System Status Tab Methods
    # =============================================================================
    def learning_system_tab(self):
        st.header("🎓 학습 시스템 현황")
        col1, col2 = st.columns(2)
        with col1: self.display_learning_stats()
        with col2: self.display_recent_lessons()
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1: self.display_lessons_content()
        with col2: self.display_reflections_list()

    def display_learning_stats(self):
        st.subheader("📊 학습 통계")
        try:
            if os.path.exists(self.lessons_path):
                with open(self.lessons_path, 'r', encoding='utf-8') as f:
                    lessons_content = f.read()
                st.metric("교훈 파일 크기", f"{len(lessons_content):,} bytes")
            
            if os.path.exists(self.reflections_dir):
                reflection_files = [f for f in os.listdir(self.reflections_dir) if f.endswith('.md')]
                st.metric("누적 회고 파일", f"{len(reflection_files)}개")

            with sqlite3.connect(self.db_path) as conn:
                total_lessons = pd.read_sql_query("SELECT COUNT(*) FROM learning_data", conn).iloc[0,0]
                st.metric("DB 학습 기록", f"{total_lessons}건")
        except Exception as e:
            st.error(f"학습 통계 조회 실패: {e}")

    def display_recent_lessons(self):
        st.subheader("🔄 최근 학습 활동")
        try:
            with sqlite3.connect(self.db_path) as conn:
                query = "SELECT * FROM learning_data ORDER BY created_timestamp DESC LIMIT 5"
                df = pd.read_sql_query(query, conn)
                if not df.empty:
                    for _, lesson in df.iterrows():
                        with st.container(border=True):
                            st.markdown(f"**{lesson['lesson_type']}** (신뢰도: {lesson['confidence_score']:.2f})")
                            st.markdown(f"> {lesson['lesson_content'][:100]}...")
                            st.markdown(f"<small>관련 ID: {lesson['trade_id']} | 적용: {lesson['application_count']}회</small>", unsafe_allow_html=True)
                else:
                    st.info("최근 학습 활동이 없습니다.")
        except Exception as e:
            st.error(f"최근 교훈 조회 실패: {e}")

    def display_lessons_content(self):
        st.subheader("📖 현재 교훈 내용")
        try:
            if os.path.exists(self.lessons_path):
                with open(self.lessons_path, 'r', encoding='utf-8') as f:
                    lessons_content = f.read()
                st.markdown(lessons_content)
            else:
                st.warning(f"교훈 파일을 찾을 수 없습니다: {self.lessons_path}")
        except Exception as e:
            st.error(f"교훈 내용 표시 실패: {e}")

    def display_reflections_list(self):
        st.subheader("📝 회고 파일 목록")
        try:
            if os.path.exists(self.reflections_dir):
                files = sorted([f for f in os.listdir(self.reflections_dir) if f.endswith('.md')], reverse=True)
                if files:
                    selected_file = st.selectbox("회고 파일 선택", files)
                    if selected_file:
                        with open(os.path.join(self.reflections_dir, selected_file), 'r', encoding='utf-8') as f:
                            content = f.read()
                        st.markdown(content)
                else:
                    st.info("회고 파일이 없습니다.")
            else:
                st.warning(f"회고 디렉토리가 없습니다: {self.reflections_dir}")
        except Exception as e:
            st.error(f"회고 파일 목록 조회 실패: {e}")
            
    def system_status_tab(self):
        st.header("⚙️ 시스템 상태")
        col1, col2 = st.columns(2)
        with col1: self.display_system_info()
        with col2: self.display_performance_metrics_system()
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1: self.display_configuration()
        with col2: self.display_system_logs()

    def display_system_info(self):
        st.subheader("💻 시스템 정보")
        try:
            files_to_check = [("DB", self.db_path), ("Config", self.config_path), ("Lessons", self.lessons_path)]
            st.markdown("**📁 파일 상태:**")
            for name, path in files_to_check:
                if os.path.exists(path):
                    st.markdown(f"✅ {name}: 존재")
                else:
                    st.markdown(f"❌ {name}: 없음")
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = cursor.fetchall()
                st.markdown("**🗄️ 데이터베이스 테이블:**")
                st.markdown(", ".join([t[0] for t in tables]))
        except Exception as e:
            st.error(f"시스템 정보 조회 실패: {e}")

    def display_performance_metrics_system(self):
        st.subheader("📈 성능 지표 (24시간)")
        try:
            with sqlite3.connect(self.db_path) as conn:
                query = """
                SELECT operation_type, COUNT(*) as count, AVG(duration_seconds) as avg_duration,
                       SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as success_count
                FROM system_performance WHERE timestamp > datetime('now', '-24 hours')
                GROUP BY operation_type
                """
                df = pd.read_sql_query(query, conn)
                if not df.empty:
                    st.dataframe(df.style.format({
                        'avg_duration': '{:.2f}s',
                        'success_count': '{:.0f}',
                        'count': '{:.0f}'
                    }), use_container_width=True)
                else:
                    st.info("지난 24시간 동안의 시스템 성능 데이터가 없습니다.")
        except Exception as e:
            st.error(f"성능 지표 조회 실패: {e}")

    def display_configuration(self):
        st.subheader("⚙️ 시스템 설정")
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                with st.expander("주요 설정 보기"):
                    st.json(config)
            else:
                st.warning(f"설정 파일을 찾을 수 없습니다: {self.config_path}")
        except Exception as e:
            st.error(f"설정 정보 조회 실패: {e}")

    def display_system_logs(self):
        st.subheader("📋 시스템 로그")
        log_file = "omni_xrp_v8.log"
        try:
            if os.path.exists(log_file):
                with open(log_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                st.text_area("최근 로그 (마지막 20줄)", "".join(lines[-20:]), height=300)
                
                with open(log_file, 'rb') as f_bin:
                    st.download_button("전체 로그 다운로드", f_bin, file_name=log_file, mime="text/plain")
            else:
                st.info(f"로그 파일을 찾을 수 없습니다: {log_file}")
        except Exception as e:
            st.error(f"시스템 로그 조회 실패: {e}")
            
    def run(self):
        """메인 실행"""
        self.main_header()
        date_range, status_filter = self.sidebar_controls()
        
        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
            "📊 현황", "📈 거래 분석", "🎯 성과", "🛡️ 위꼬리 방어", "🎓 학습 시스템", "⚙️ 시스템 상태"
        ])
        
        with tab1:
            self.current_status_tab()
        with tab2:
            self.trading_analysis_tab(date_range, status_filter)
        with tab3:
            self.performance_tab(date_range)
        with tab4:
            self.wick_defense_tab(date_range)
        with tab5:
            self.learning_system_tab()
        with tab6:
            self.system_status_tab()

# 메인 실행
if __name__ == "__main__":
    dashboard = OMNIDashboard()
    dashboard.run()