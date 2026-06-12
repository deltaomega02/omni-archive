import streamlit as st
import sqlite3
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pyupbit
from datetime import datetime, timedelta
import json
import os
from dotenv import load_dotenv
import numpy as np
import re  # 정규표현식 (회고 파싱용)

# 환경 변수 로드
load_dotenv()

# Streamlit 페이지 설정
st.set_page_config(
    page_title="OMNI-XRP Real Dashboard",
    page_icon="🎯",
    layout="wide"
)

# 개선된 글라스모피즘 스타일 CSS - 가독성 중심
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: #1a1a1a;
    }
    
    .main-header {
        background: rgba(255, 255, 255, 0.95);
        backdrop-filter: blur(20px);
        border: 2px solid rgba(255, 255, 255, 0.8);
        border-radius: 20px;
        padding: 2rem;
        text-align: center;
        margin-bottom: 2rem;
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.15);
        color: #1a1a1a;
    }
    
    .glass-metric {
        background: rgba(255, 255, 255, 0.9);
        backdrop-filter: blur(20px);
        border: 2px solid rgba(255, 255, 255, 0.8);
        border-radius: 15px;
        padding: 1.5rem;
        margin: 0.5rem 0;
        box-shadow: 0 8px 25px rgba(0, 0, 0, 0.1);
        transition: all 0.3s ease;
        color: #1a1a1a;
    }
    
    .glass-metric:hover {
        transform: translateY(-3px);
        box-shadow: 0 12px 35px rgba(0, 0, 0, 0.2);
        background: rgba(255, 255, 255, 0.95);
    }
    
    .profit {
        color: #00b894;
        font-weight: 700;
        text-shadow: 0 2px 4px rgba(0, 184, 148, 0.3);
    }
    
    .loss {
        color: #e74c3c;
        font-weight: 700;
        text-shadow: 0 2px 4px rgba(231, 76, 60, 0.3);
    }
    
    .neutral {
        color: #2980b9;
        font-weight: 600;
    }
    
    .big-number {
        font-size: 2.5rem;
        font-weight: 700;
        margin: 0.5rem 0;
        text-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    }
    
    .small-text {
        font-size: 0.9rem;
        color: #666;
        font-weight: 500;
    }
    
    .status-badge {
        padding: 6px 14px;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        color: white;
    }
    
    .status-planned {
        background: linear-gradient(45deg, #f39c12, #e67e22);
        box-shadow: 0 4px 15px rgba(243, 156, 18, 0.3);
    }
    
    .status-active {
        background: linear-gradient(45deg, #27ae60, #2ecc71);
        box-shadow: 0 4px 15px rgba(39, 174, 96, 0.3);
    }
    
    .status-completed {
        background: linear-gradient(45deg, #3498db, #2980b9);
        box-shadow: 0 4px 15px rgba(52, 152, 219, 0.3);
    }
    
    .neon-glow {
        color: #2c3e50;
        text-shadow: 0 2px 10px rgba(44, 62, 80, 0.3);
        animation: subtle-glow 3s ease-in-out infinite alternate;
    }
    
    @keyframes subtle-glow {
        from {
            text-shadow: 0 2px 10px rgba(44, 62, 80, 0.3);
        }
        to {
            text-shadow: 0 2px 15px rgba(44, 62, 80, 0.5);
        }
    }
    
    .section-title {
        color: #2c3e50;
        font-size: 1.8rem;
        font-weight: 700;
        margin-bottom: 1rem;
        text-shadow: 0 2px 8px rgba(44, 62, 80, 0.2);
    }
    
    .nav-tabs {
        display: flex;
        justify-content: center;
        gap: 1rem;
        margin-bottom: 2rem;
        flex-wrap: wrap;
    }
    
    .refresh-btn {
        position: fixed;
        bottom: 2rem;
        right: 2rem;
        background: linear-gradient(45deg, #667eea, #764ba2);
        color: white;
        border: none;
        border-radius: 50%;
        width: 60px;
        height: 60px;
        font-size: 1.5rem;
        cursor: pointer;
        box-shadow: 0 8px 25px rgba(102, 126, 234, 0.4);
        transition: all 0.3s ease;
        z-index: 1000;
    }
    
    .refresh-btn:hover {
        transform: scale(1.1) rotate(180deg);
        box-shadow: 0 12px 35px rgba(102, 126, 234, 0.6);
    }
    
    /* 포지션 현황 전용 스타일 */
    .position-header {
        background: rgba(255, 255, 255, 0.95);
        backdrop-filter: blur(25px);
        border: 3px solid rgba(255, 255, 255, 0.9);
        border-radius: 25px;
        padding: 3rem;
        margin: 2rem 0;
        box-shadow: 0 15px 50px rgba(0, 0, 0, 0.15);
        color: #1a1a1a;
        text-align: center;
    }
    
    .position-pnl {
        background: rgba(255, 255, 255, 0.95);
        backdrop-filter: blur(20px);
        border: 2px solid rgba(255, 255, 255, 0.9);
        border-radius: 20px;
        padding: 3rem;
        margin: 2rem 0;
        text-align: center;
        box-shadow: 0 12px 40px rgba(0, 0, 0, 0.1);
        color: #1a1a1a;
    }
    
    /* 빈 포지션 스타일 */
    .empty-position {
        background: rgba(255, 255, 255, 0.9);
        backdrop-filter: blur(25px);
        border: 2px solid rgba(255, 255, 255, 0.8);
        border-radius: 25px;
        padding: 4rem;
        margin: 2rem 0;
        text-align: center;
        box-shadow: 0 12px 40px rgba(0, 0, 0, 0.1);
        color: #7f8c8d;
    }
    
    /* Streamlit 기본 요소 스타일 재정의 */
    .stSelectbox > div > div {
        background-color: rgba(255, 255, 255, 0.9);
        color: #1a1a1a;
        border: 2px solid rgba(255, 255, 255, 0.8);
        border-radius: 10px;
    }
    
    .stButton > button {
        background: rgba(255, 255, 255, 0.9);
        color: #1a1a1a;
        border: 2px solid rgba(255, 255, 255, 0.8);
        border-radius: 10px;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        background: rgba(255, 255, 255, 0.95);
        transform: translateY(-2px);
        box-shadow: 0 8px 25px rgba(0, 0, 0, 0.1);
    }
    
    /* 데이터프레임 테이블 스타일 */
    .dataframe {
        background-color: rgba(255, 255, 255, 0.95);
        color: #1a1a1a;
        border-radius: 10px;
        overflow: hidden;
    }
    
    .dataframe th {
        background-color: #34495e;
        color: white;
        font-weight: 600;
        padding: 12px;
        text-align: center;
    }
    
    .dataframe td {
        padding: 10px;
        border-bottom: 1px solid rgba(52, 73, 94, 0.1);
        text-align: center;
    }
    
    .dataframe tr:hover {
        background-color: rgba(52, 152, 219, 0.1);
    }
</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=10)
def get_xrp_price():
    """XRP 현재가 조회"""
    try:
        current_price = pyupbit.get_current_price("KRW-XRP")
        df_day = pyupbit.get_ohlcv("KRW-XRP", interval="day", count=2)
        
        if df_day is not None and len(df_day) >= 2:
            prev_close = df_day['close'].iloc[-2]
            change_price = current_price - prev_close
            change_rate = (change_price / prev_close) * 100
        else:
            change_price = 0
            change_rate = 0
        
        df_minute = pyupbit.get_ohlcv("KRW-XRP", interval="minute1", count=1440)
        volume_24h = df_minute['volume'].sum() if df_minute is not None else 0
        
        return {
            'current_price': current_price,
            'change_rate': change_rate,
            'change_price': change_price,
            'volume': volume_24h
        }
    except Exception as e:
        st.error(f"가격 조회 실패: {e}")
        return None

@st.cache_data(ttl=30)
def get_upbit_balance():
    """업비트 잔고 조회"""
    try:
        access_key = os.getenv("UPBIT_ACCESS_KEY")
        secret_key = os.getenv("UPBIT_SECRET_KEY")
        
        if not access_key or not secret_key:
            return {"error": "API 키가 설정되지 않았습니다. .env 파일을 확인하세요."}
            
        upbit = pyupbit.Upbit(access_key, secret_key)
        
        try:
            balances = upbit.get_balances()
            if balances is None:
                return {"error": "API 키가 유효하지 않거나 권한이 부족합니다."}
        except Exception as api_error:
            return {"error": f"업비트 API 호출 실패: {str(api_error)}"}
        
        result = {"KRW": 0, "XRP": 0, "XRP_avg": 0, "total_krw_value": 0}
        
        for balance in balances:
            if balance['currency'] == 'KRW':
                result['KRW'] = float(balance['balance'])
            elif balance['currency'] == 'XRP':
                result['XRP'] = float(balance['balance'])
                result['XRP_avg'] = float(balance['avg_buy_price']) if balance['avg_buy_price'] else 0
        
        price_data = get_xrp_price()
        if price_data and result['XRP'] > 0:
            result['total_krw_value'] = result['KRW'] + (result['XRP'] * price_data['current_price'])
        else:
            result['total_krw_value'] = result['KRW']
                
        return result
    except Exception as e:
        return {"error": f"잔고 조회 중 오류 발생: {str(e)}"}

def get_db_connection():
    """DB 연결"""
    try:
        conn = sqlite3.connect('omni_xrp_trades.sqlite')
        return conn
    except Exception as e:
        st.error(f"DB 연결 실패: {e}")
        return None

@st.cache_data(ttl=30)
def get_all_trades():
    """모든 거래 조회"""
    conn = get_db_connection()
    if not conn:
        return pd.DataFrame()
    
    try:
        query = """
        SELECT 
            trade_id, status, plan_timestamp, entry_timestamp, exit_timestamp,
            planned_entry_price, planned_target_price, planned_stop_loss,
            actual_entry_price, actual_exit_price, position_size_xrp,
            trade_result, net_profit_krw, profit_rate_pct,
            entry_reason, target_reason, stop_loss_reason
        FROM trades 
        ORDER BY plan_timestamp DESC
        """
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    except Exception as e:
        st.error(f"거래 데이터 조회 실패: {e}")
        conn.close()
        return pd.DataFrame()

def get_total_pnl():
    """총 손익 계산 (실현 + 미실현)"""
    try:
        # 1. 실현 손익 계산
        df = get_all_trades()
        completed = df[df['status'] == 'COMPLETED'].copy()
        
        if completed.empty:
            realized_pnl = 0
        else:
            completed['net_profit_krw'] = pd.to_numeric(completed['net_profit_krw'], errors='coerce').fillna(0)
            realized_pnl = completed['net_profit_krw'].sum()
        
        # 2. 미실현 손익 계산 (DB의 활성 거래 기준)
        active = df[df['status'] == 'ACTIVE'].copy()
        unrealized_pnl = 0
        current_xrp_amount = 0
        
        price_data = get_xrp_price()
        current_price = price_data['current_price'] if price_data else 0
        
        if not active.empty and current_price > 0:
            for _, trade in active.iterrows():
                if (pd.notna(trade['actual_entry_price']) and 
                    pd.notna(trade['position_size_xrp']) and 
                    trade['actual_entry_price'] > 0 and 
                    trade['position_size_xrp'] > 0):
                    
                    trade_unrealized = (current_price - trade['actual_entry_price']) * trade['position_size_xrp']
                    unrealized_pnl += trade_unrealized
                    current_xrp_amount += trade['position_size_xrp']
        
        # 3. 업비트 실제 잔고 확인 (보정용)
        balance_data = get_upbit_balance()
        if ('error' not in balance_data and 
            balance_data['XRP'] > 0 and 
            balance_data['XRP_avg'] > 0 and 
            current_price > 0):
            
            # 실제 잔고 기반 미실현 손익
            actual_unrealized = (current_price - balance_data['XRP_avg']) * balance_data['XRP']
            
            # DB와 실제 잔고가 다르면 실제 잔고 우선
            if abs(balance_data['XRP'] - current_xrp_amount) > 0.0001:  # 소수점 오차 고려
                unrealized_pnl = actual_unrealized
                current_xrp_amount = balance_data['XRP']
        
        total_pnl = realized_pnl + unrealized_pnl
        
        return {
            'realized_pnl': realized_pnl,
            'unrealized_pnl': unrealized_pnl,
            'total_pnl': total_pnl,
            'current_xrp_amount': current_xrp_amount,
            'current_price': current_price
        }
        
    except Exception as e:
        st.error(f"손익 계산 중 오류: {e}")
        return {
            'realized_pnl': 0,
            'unrealized_pnl': 0,
            'total_pnl': 0,
            'current_xrp_amount': 0,
            'current_price': 0
        }

def calculate_total_performance():
    """전체 성과 계산"""
    df = get_all_trades()
    if df.empty:
        return None
    
    completed = df[df['status'] == 'COMPLETED'].copy()
    if completed.empty:
        return {
            'total_trades': 0,
            'win_trades': 0,
            'win_rate': 0,
            'total_profit': 0,
            'avg_profit_rate': 0,
            'max_profit': 0,
            'max_loss': 0
        }
    
    completed['net_profit_krw'] = pd.to_numeric(completed['net_profit_krw'], errors='coerce').fillna(0)
    completed['profit_rate_pct'] = pd.to_numeric(completed['profit_rate_pct'], errors='coerce').fillna(0)
    
    win_trades = len(completed[completed['net_profit_krw'] > 0])
    total_trades = len(completed)
    
    return {
        'total_trades': total_trades,
        'win_trades': win_trades,
        'win_rate': (win_trades / total_trades * 100) if total_trades > 0 else 0,
        'total_profit': completed['net_profit_krw'].sum(),
        'avg_profit_rate': completed['profit_rate_pct'].mean(),
        'max_profit': completed['profit_rate_pct'].max(),
        'max_loss': completed['profit_rate_pct'].min()
    }

def render_header():
    """헤더 렌더링"""
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("""
        <div class="main-header">
            <h1 class="neon-glow">🎯 OMNI-XRP 실시간 대시보드</h1>
            <p style="font-size: 1.2rem; margin-top: 1rem; color: #34495e;">AI 기반 XRP 자동매매 시스템 모니터링</p>
        </div>
        """, unsafe_allow_html=True)

def render_navigation():
    """네비게이션 탭 (AI판단, 회고록 탭 추가)"""
    if 'current_tab' not in st.session_state:
        st.session_state.current_tab = '대시보드'
    
    # 탭 목록에 'AI판단', '회고록' 추가
    tabs = ['대시보드', '활성거래', '성과분석', '차트', 'AI판단', '회고록', '히스토리']
    
    cols = st.columns(len(tabs))
    for i, tab in enumerate(tabs):
        with cols[i]:
            icon_map = {
                '대시보드': '📊', '활성거래': '⚡', '성과분석': '📈', 
                '차트': '📊', 'AI판단': '🧠', '회고록': '📚', '히스토리': '📋'
            }
            if st.button(f"{icon_map[tab]} {tab}", key=f"tab_{tab}"):
                st.session_state.current_tab = tab
    
    return st.session_state.current_tab

def render_current_position():
    """현재 포지션 상황 - 가독성 개선된 버전"""
    # 데이터 가져오기
    balance_data = get_upbit_balance()
    price_data = get_xrp_price()
    df = get_all_trades()
    active_trades = df[df['status'] == 'ACTIVE'].copy()
    
    current_price = price_data['current_price'] if price_data else 0
    
    # 포지션이 있는 경우
    if (balance_data and 'error' not in balance_data and 
        balance_data['XRP'] > 0 and balance_data['XRP_avg'] > 0 and current_price > 0):
        
        xrp_amount = balance_data['XRP']
        avg_price = balance_data['XRP_avg']
        current_value = xrp_amount * current_price
        unrealized_pnl = (current_price - avg_price) * xrp_amount
        unrealized_rate = (current_price - avg_price) / avg_price * 100
        
        # 활성 거래에서 목표가 찾기
        target_price = None
        target_display = "미설정"
        expected_return = "목표가 없음"
        
        if not active_trades.empty:
            # 가장 최근 거래의 목표가 가져오기
            latest_active = active_trades.sort_values('plan_timestamp', ascending=False).iloc[0]
            
            if pd.notna(latest_active['planned_target_price']):
                target_price = latest_active['planned_target_price']
                target_display = f"{target_price:,.0f}원"
                expected_return = f"예상 수익률: {((target_price - avg_price) / avg_price * 100):+.1f}%"
        
        # 수익/손실 색상
        pnl_color = "#00b894" if unrealized_pnl >= 0 else "#e74c3c"
        
        # 헤더
        st.markdown("""
        <div class="position-header">
            <h1 style="color: #2c3e50; font-size: 2.5rem; margin-bottom: 2rem;">
                🎯 현재 포지션 현황
            </h1>
        </div>
        """, unsafe_allow_html=True)
        
        # 3개 정보 박스 (평단가, 현재가, 목표가)
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown(f"""
            <div class="glass-metric">
                <div class="small-text">💰 평균 매수가</div>
                <div style="font-size: 3.5rem; font-weight: 700; color: #2980b9; 
                           text-shadow: 0 2px 8px rgba(41, 128, 185, 0.3); margin: 1rem 0;">
                    {avg_price:,.0f}원
                </div>
                <div class="small-text">{xrp_amount:.4f} XRP 보유</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div class="glass-metric">
                <div class="small-text">📈 현재가</div>
                <div style="font-size: 3.5rem; font-weight: 700; color: #2c3e50; 
                           text-shadow: 0 2px 8px rgba(44, 62, 80, 0.3); margin: 1rem 0;">
                    {current_price:,.0f}원
                </div>
                <div class="small-text">현재 시장가</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown(f"""
            <div class="glass-metric">
                <div class="small-text">🎯 목표가</div>
                <div style="font-size: 3.5rem; font-weight: 700; color: #00b894; 
                           text-shadow: 0 2px 8px rgba(0, 184, 148, 0.3); margin: 1rem 0;">
                    {target_display}
                </div>
                <div class="small-text">{expected_return}</div>
            </div>
            """, unsafe_allow_html=True)
        
        # 현재 손익 (가장 크게)
        st.markdown(f"""
        <div class="position-pnl">
            <div style="font-size: 1.5rem; color: #34495e; margin-bottom: 1rem;">💎 현재 손익</div>
            <div style="font-size: 5rem; font-weight: 700; color: {pnl_color}; 
                       text-shadow: 0 2px 10px {pnl_color}50; 
                       margin: 1rem 0;">
                {unrealized_pnl:+,.0f}원
            </div>
            <div style="font-size: 2rem; font-weight: 600; color: {pnl_color}; 
                       margin-bottom: 1rem;">
                {unrealized_rate:+.2f}%
            </div>
            <div style="font-size: 1.2rem; color: #7f8c8d;">
                현재 포지션 가치: {current_value:,.0f}원
            </div>
        </div>
        """, unsafe_allow_html=True)
        
    else:
        # 포지션이 없는 경우
        price_text = f"{current_price:,.0f}원" if current_price > 0 else "가격 조회 실패"
        
        st.markdown(f"""
        <div class="empty-position">
            <h1 style="color: #7f8c8d; font-size: 3rem; margin-bottom: 1rem;">
                🌙 현재 포지션 없음
            </h1>
            <p style="font-size: 1.5rem; margin-bottom: 2rem;">
                새로운 거래 기회를 기다리고 있습니다
            </p>
            <div style="font-size: 1.2rem; color: #95a5a6;">
                현재가: {price_text}
            </div>
        </div>
        """, unsafe_allow_html=True)

def render_market_status():
    """추가 시장 정보"""
    st.markdown('<h2 class="section-title">📊 시장 정보</h2>', unsafe_allow_html=True)
    
    price_data = get_xrp_price()
    balance_data = get_upbit_balance()
    pnl_data = get_total_pnl()
    
    if price_data:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            change_class = "profit" if price_data['change_rate'] > 0 else "loss" if price_data['change_rate'] < 0 else "neutral"
            st.markdown(f"""
            <div class="glass-metric">
                <div class="small-text">📈 24시간 변동</div>
                <div class="big-number {change_class}">
                    {price_data['change_rate']:+.2f}%
                </div>
                <div class="small-text">{price_data['change_price']:+,.0f}원</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div class="glass-metric">
                <div class="small-text">📊 24시간 거래량</div>
                <div class="big-number neutral">{price_data['volume']:,.0f}</div>
                <div class="small-text">XRP</div>
            </div>
            """, unsafe_allow_html=True)
            
        with col3:
            st.markdown(f"""
            <div class="glass-metric">
                <div class="small-text">✅ 실현 손익</div>
                <div class="big-number {'profit' if pnl_data['realized_pnl'] > 0 else 'loss' if pnl_data['realized_pnl'] < 0 else 'neutral'}">
                    {pnl_data['realized_pnl']:+,.0f}원
                </div>
                <div class="small-text">확정된 수익</div>
            </div>
            """, unsafe_allow_html=True)
            
        with col4:
            if balance_data and 'error' not in balance_data:
                st.markdown(f"""
                <div class="glass-metric">
                    <div class="small-text">💼 총 자산</div>
                    <div class="big-number neutral">{balance_data.get('total_krw_value', 0):,.0f}원</div>
                    <div class="small-text">
                        현금: {balance_data['KRW']:,.0f}원
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                error_msg = balance_data.get('error', '알 수 없는 오류') if balance_data else 'API 연결 실패'
                st.markdown(f"""
                <div class="glass-metric">
                    <div class="small-text">⚠️ 잔고 조회 실패</div>
                    <div style="font-size: 0.8rem; color: #e74c3c;">{error_msg}</div>
                    <div class="small-text">API 키를 확인하세요</div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.error("XRP 가격 정보를 불러올 수 없습니다.")

def render_active_trades():
    """활성 거래 현황"""
    st.markdown('<h2 class="section-title">⚡ 활성 거래 현황</h2>', unsafe_allow_html=True)
    
    df = get_all_trades()
    if df.empty:
        st.info("거래 데이터가 없습니다.")
        return
    
    active_trades = df[df['status'].isin(['PLANNED', 'ACTIVE'])].copy()
    
    if active_trades.empty:
        st.markdown("""
        <div class="glass-metric">
            <div style="text-align: center; padding: 2rem;">
                <h3 style="color: #2980b9;">🌙 현재 활성화된 거래가 없습니다</h3>
                <p style="color: #7f8c8d;">새로운 거래 기회를 기다리는 중...</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
        return
    
    price_data = get_xrp_price()
    current_price = price_data['current_price'] if price_data else 0
    
    for _, trade in active_trades.iterrows():
        status_class = f"status-{trade['status'].lower()}"
        
        with st.container():
            st.markdown(f"""
            <div class="glass-metric">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                    <h3 style="margin: 0; color: #2c3e50;">거래 #{trade['trade_id']}</h3>
                    <span class="status-badge {status_class}">{trade['status']}</span>
                </div>
            """, unsafe_allow_html=True)
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown("**📊 가격 정보**")
                st.write(f"계획 진입가: {trade['planned_entry_price']:,.0f}원")
                st.write(f"목표가: {trade['planned_target_price']:,.0f}원")
                st.write(f"손절가: {trade['planned_stop_loss']:,.0f}원")
                
                if pd.notna(trade['actual_entry_price']):
                    st.markdown(f"**실제 진입가: {trade['actual_entry_price']:,.0f}원**")
            
            with col2:
                st.markdown("**⏰ 시간 정보**")
                st.write(f"계획: {trade['plan_timestamp']}")
                if pd.notna(trade['entry_timestamp']):
                    st.write(f"진입: {trade['entry_timestamp']}")
                if pd.notna(trade['position_size_xrp']):
                    st.markdown(f"**포지션: {trade['position_size_xrp']:.4f} XRP**")
            
            with col3:
                st.markdown("**💰 현재 손익**")
                if trade['status'] == 'ACTIVE' and pd.notna(trade['actual_entry_price']) and current_price > 0:
                    unrealized_pnl = (current_price - trade['actual_entry_price']) * trade['position_size_xrp']
                    unrealized_rate = (current_price - trade['actual_entry_price']) / trade['actual_entry_price'] * 100
                    
                    st.write(f"현재가: {current_price:,.0f}원")
                    if unrealized_pnl > 0:
                        st.markdown(f"**<span style='color: #00b894'>미실현 손익: +{unrealized_pnl:,.0f}원 (+{unrealized_rate:.2f}%)</span>**", unsafe_allow_html=True)
                    else:
                        st.markdown(f"**<span style='color: #e74c3c'>미실현 손익: {unrealized_pnl:,.0f}원 ({unrealized_rate:.2f}%)</span>**", unsafe_allow_html=True)
                else:
                    st.write("진입 대기 중...")
            
            st.markdown("</div>", unsafe_allow_html=True)

def render_performance():
    """성과 분석"""
    st.markdown('<h2 class="section-title">📈 거래 성과 분석</h2>', unsafe_allow_html=True)
    
    perf = calculate_total_performance()
    if not perf or perf['total_trades'] == 0:
        st.markdown("""
        <div class="glass-metric">
            <div style="text-align: center; padding: 2rem;">
                <h3 style="color: #2980b9;">📊 아직 완료된 거래가 없습니다</h3>
                <p style="color: #7f8c8d;">첫 거래 완료 후 성과가 표시됩니다</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
        return
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class="glass-metric">
            <div class="small-text">📊 총 거래 횟수</div>
            <div class="big-number neutral">{perf['total_trades']}</div>
            <div class="small-text">승리: {perf['win_trades']}회</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        win_rate_class = "profit" if perf['win_rate'] >= 60 else "loss" if perf['win_rate'] < 40 else "neutral"
        st.markdown(f"""
        <div class="glass-metric">
            <div class="small-text">🎯 승률</div>
            <div class="big-number {win_rate_class}">{perf['win_rate']:.1f}%</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        profit_class = "profit" if perf['total_profit'] > 0 else "loss"
        st.markdown(f"""
        <div class="glass-metric">
            <div class="small-text">💰 총 수익</div>
            <div class="big-number {profit_class}">{perf['total_profit']:+,.0f}원</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        avg_class = "profit" if perf['avg_profit_rate'] > 0 else "loss"
        st.markdown(f"""
        <div class="glass-metric">
            <div class="small-text">📈 평균 수익률</div>
            <div class="big-number {avg_class}">{perf['avg_profit_rate']:+.2f}%</div>
        </div>
        """, unsafe_allow_html=True)
    
    # 누적 수익 차트
    df = get_all_trades()
    completed = df[df['status'] == 'COMPLETED'].copy()
    
    if not completed.empty:
        completed = completed.sort_values('plan_timestamp')
        completed['net_profit_krw'] = pd.to_numeric(completed['net_profit_krw'], errors='coerce').fillna(0)
        completed['cumulative_profit'] = completed['net_profit_krw'].cumsum()
        completed['trade_number'] = range(1, len(completed) + 1)
        
        fig = go.Figure()
        
        # 누적 수익 라인
        fig.add_trace(go.Scatter(
            x=completed['trade_number'],
            y=completed['cumulative_profit'],
            mode='lines+markers',
            name='누적 수익',
            line=dict(color='#00b894', width=3, shape='spline'),
            marker=dict(size=10, color='#00b894', symbol='circle'),
            fill='tozeroy',
            fillcolor='rgba(0, 184, 148, 0.1)'
        ))
        
        # 개별 거래 수익 막대 차트
        colors = ['#00b894' if profit > 0 else '#e74c3c' for profit in completed['net_profit_krw']]
        fig.add_trace(go.Bar(
            x=completed['trade_number'],
            y=completed['net_profit_krw'],
            name='개별 수익',
            marker_color=colors,
            opacity=0.6,
            yaxis='y2'
        ))
        
        fig.update_layout(
            title={
                'text': "📊 누적 거래 수익 추이",
                'x': 0.5,
                'font': {'size': 20, 'color': '#2c3e50'}
            },
            xaxis_title="거래 번호",
            yaxis_title="누적 수익 (원)",
            yaxis2=dict(
                title="개별 수익 (원)",
                overlaying='y',
                side='right'
            ),
            height=500,
            plot_bgcolor='rgba(255,255,255,0.9)',
            paper_bgcolor='rgba(255,255,255,0.9)',
            font=dict(color='#2c3e50'),
            showlegend=True,
            legend=dict(
                x=0.02,
                y=0.98,
                bgcolor='rgba(255,255,255,0.9)',
                bordercolor='rgba(44, 62, 80, 0.2)',
                borderwidth=1
            )
        )
        
        # 그리드 스타일
        fig.update_xaxes(
            gridcolor='rgba(44, 62, 80, 0.1)',
            zerolinecolor='rgba(44, 62, 80, 0.2)'
        )
        fig.update_yaxes(
            gridcolor='rgba(44, 62, 80, 0.1)',
            zerolinecolor='rgba(44, 62, 80, 0.2)'
        )
        
        st.plotly_chart(fig, use_container_width=True)

def render_decision_reasoning():
    """판단 이유 상세 분석 탭 - 0으로 나누기 오류 수정"""
    st.markdown('<h2 class="section-title">🧠 AI 판단 분석</h2>', unsafe_allow_html=True)
    
    # 최근 거래 계획들 조회
    df = get_all_trades()
    if df.empty:
        st.markdown("""
        <div class="glass-metric">
            <div style="text-align: center; padding: 2rem;">
                <h3 style="color: #2980b9;">🤖 아직 AI 판단 기록이 없습니다</h3>
                <p style="color: #7f8c8d;">첫 전략 수립 후 AI의 판단 근거가 표시됩니다</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
        return
    
    # 필터링 옵션
    col1, col2 = st.columns([1, 1])
    with col1:
        status_filter = st.selectbox(
            "거래 상태 필터",
            ["전체", "PLANNED", "ACTIVE", "COMPLETED", "CANCELLED"],
            index=0
        )
    with col2:
        limit_trades = st.selectbox(
            "표시할 거래 수",
            [5, 10, 20, 50],
            index=1
        )
    
    # 데이터 필터링
    if status_filter != "전체":
        filtered_df = df[df['status'] == status_filter].head(limit_trades)
    else:
        filtered_df = df.head(limit_trades)
    
    # 각 거래별 판단 근거 표시
    for idx, trade in filtered_df.iterrows():
        with st.expander(f"🎯 거래 #{trade['trade_id']} - {trade['status']} ({trade['plan_timestamp']})", expanded=False):
            
            col1, col2 = st.columns([1, 1])
            
            with col1:
                st.markdown("### 📊 가격 전략")
                
                # 🔥 핵심 수정: 진입가가 0인 경우 특별 처리
                if trade['planned_entry_price'] == 0:
                    st.markdown("**⚠️ 진입가: 0원 (XRP 보유 중 - 추가 진입 불가)**")
                    st.markdown("**📋 전략 유형: 포지션 관리 전용**")
                else:
                    st.write(f"**진입가**: {trade['planned_entry_price']:,.0f}원")
                
                st.write(f"**목표가**: {trade['planned_target_price']:,.0f}원")
                st.write(f"**손절가**: {trade['planned_stop_loss']:,.0f}원")
                
                if pd.notna(trade['actual_entry_price']) and trade['actual_entry_price'] > 0:
                    st.markdown(f"**실제 진입가: {trade['actual_entry_price']:,.0f}원**")
                
                if pd.notna(trade['actual_exit_price']):
                    st.write(f"**실제 매도가**: {trade['actual_exit_price']:,.0f}원")
                    
                if pd.notna(trade['net_profit_krw']):
                    profit_color = "🟢" if trade['net_profit_krw'] > 0 else "🔴"
                    st.write(f"**최종 손익**: {profit_color} {trade['net_profit_krw']:+,.0f}원 ({trade['profit_rate_pct']:+.2f}%)")
            
            with col2:
                st.markdown("### 🧠 AI 판단 근거")
                
                # 진입 전략 근거
                if pd.notna(trade['entry_reason']):
                    st.markdown("**🎯 진입 전략 근거:**")
                    st.info(trade['entry_reason'])
                
                # 목표가 설정 근거
                if pd.notna(trade['target_reason']):
                    st.markdown("**🎯 목표가 설정 근거:**")
                    st.success(trade['target_reason'])
                
                # 손절가 설정 근거
                if pd.notna(trade['stop_loss_reason']):
                    st.markdown("**🛡️ 리스크 관리 근거:**")
                    st.warning(trade['stop_loss_reason'])
            
            # 거래 결과가 있는 경우 성과 분석 (🔥 핵심 수정 부분)
            if trade['status'] == 'COMPLETED':
                st.markdown("### 📈 거래 성과 분석")
                col3, col4, col5 = st.columns(3)
                
                with col3:
                    # 🔥 0으로 나누기 방지 + 포지션 관리 전용 거래 처리
                    if (pd.notna(trade['actual_entry_price']) and 
                        pd.notna(trade['planned_entry_price']) and 
                        trade['planned_entry_price'] > 0 and
                        trade['actual_entry_price'] > 0):
                        
                        plan_accuracy = abs(trade['actual_entry_price'] - trade['planned_entry_price']) / trade['planned_entry_price'] * 100
                        st.metric("진입가 정확도", f"{100-plan_accuracy:.1f}%")
                        
                    elif trade['planned_entry_price'] == 0:
                        st.metric("진입가 정확도", "포지션 관리 전용")
                        st.caption("보유 중이어서 진입 없음")
                    else:
                        st.metric("진입가 정확도", "계산 불가")
                        st.caption("데이터 부족")
                
                with col4:
                    # 🔥 목표가 달성률 계산 전 안전 검증
                    if (pd.notna(trade['net_profit_krw']) and 
                        pd.notna(trade['actual_exit_price']) and 
                        pd.notna(trade['planned_target_price']) and 
                        trade['planned_target_price'] > 0 and
                        trade['net_profit_krw'] > 0):
                        
                        target_achievement = trade['actual_exit_price'] / trade['planned_target_price'] * 100
                        st.metric("목표가 달성률", f"{target_achievement:.1f}%")
                        
                    elif pd.notna(trade['net_profit_krw']) and trade['net_profit_krw'] <= 0:
                        st.metric("결과", "손절 실행")
                        st.caption("목표가 미달성")
                    else:
                        st.metric("목표가 달성률", "계산 불가")
                        st.caption("데이터 부족")
                
                with col5:
                    # 보유 기간 계산
                    if pd.notna(trade['entry_timestamp']) and pd.notna(trade['exit_timestamp']):
                        try:
                            entry_time = pd.to_datetime(trade['entry_timestamp'])
                            exit_time = pd.to_datetime(trade['exit_timestamp'])
                            holding_hours = (exit_time - entry_time).total_seconds() / 3600
                            
                            if holding_hours < 1:
                                holding_display = f"{holding_hours*60:.0f}분"
                            elif holding_hours < 24:
                                holding_display = f"{holding_hours:.1f}시간"
                            else:
                                holding_display = f"{holding_hours/24:.1f}일"
                            st.metric("보유 기간", holding_display)
                        except:
                            st.metric("보유 기간", "계산 불가")
                    else:
                        st.metric("보유 기간", "데이터 없음")
                        
            # 🔥 추가: 포지션 관리 전용 거래 설명
            elif trade['planned_entry_price'] == 0:
                st.markdown("### 💡 포지션 관리 전용 거래")
                st.info("""
                이 거래는 **XRP 보유 중 상태**에서 생성된 포지션 관리 전용 계획입니다.
                
                **특징:**
                - 새로운 매수 없음 (진입가 = 0)
                - 기존 보유 XRP의 목표가/손절가 조정
                - 시장 상황 변화에 따른 매도 전략 최적화
                """)

def render_reflection_records():
    """회고록 탭 - 모든 회고 기록 확인"""
    st.markdown('<h2 class="section-title">📚 OMNI-XRP 회고록</h2>', unsafe_allow_html=True)
    
    # Reflection.md 파일 확인
    if not os.path.exists('Reflection.md'):
        st.markdown("""
        <div class="glass-metric">
            <div style="text-align: center; padding: 2rem;">
                <h3 style="color: #2980b9;">📖 아직 회고 기록이 없습니다</h3>
                <p style="color: #7f8c8d;">첫 거래 완료 후 AI의 상세한 회고 분석이 기록됩니다</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
        return
    
    try:
        # Reflection.md 파일 읽기
        with open('Reflection.md', 'r', encoding='utf-8') as f:
            reflection_content = f.read()
        
        if not reflection_content.strip():
            st.info("회고 파일이 비어있습니다.")
            return
        
        # 파일 정보 표시
        file_stats = os.stat('Reflection.md')
        file_size = file_stats.st_size / 1024  # KB
        last_modified = datetime.fromtimestamp(file_stats.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("📄 파일 크기", f"{file_size:.1f} KB")
        with col2:
            st.metric("📅 최종 수정", last_modified)
        with col3:
            reflection_count = len(re.findall(r'## 🔍 거래 ID \d+ 회고 분석', reflection_content))
            st.metric("📝 회고 기록 수", f"{reflection_count}개")
        
        # 필터링 옵션
        col1, col2 = st.columns([2, 1])
        with col1:
            search_term = st.text_input("🔍 검색어 입력 (거래 ID, 키워드 등)", placeholder="예: 거래 ID 5, 매도 타이밍, 교훈")
        with col2:
            view_mode = st.selectbox("표시 모드", ["전체 보기", "요약만 보기", "최근 5개만"])
        
        # 검색 및 필터링
        display_content = reflection_content
        
        if search_term:
            # 검색어가 포함된 섹션만 추출
            sections = re.split(r'(## 🔍 거래 ID \d+ 회고 분석[^\n]*)', reflection_content)
            filtered_sections = []
            
            for i in range(1, len(sections), 2):  # 홀수 인덱스가 헤더
                if i+1 < len(sections):
                    header = sections[i]
                    content = sections[i+1]
                    if search_term.lower() in (header + content).lower():
                        filtered_sections.extend([header, content])
            
            if filtered_sections:
                display_content = ''.join(filtered_sections)
            else:
                st.warning(f"'{search_term}'에 대한 검색 결과가 없습니다.")
                return
        
        # 표시 모드에 따른 처리
        if view_mode == "최근 5개만":
            sections = re.split(r'(## 🔍 거래 ID \d+ 회고 분석[^\n]*)', display_content)
            if len(sections) > 11:  # 헤더+내용 쌍 5개 = 10개 + 맨앞 빈문자열
                display_content = ''.join(sections[:11])
        
        # 탭으로 구분
        tab1, tab2, tab3 = st.tabs(["📖 전체 회고록", "📊 통계 분석", "💡 핵심 교훈"])
        
        with tab1:
            if view_mode == "요약만 보기":
                # 각 회고의 핵심 교훈만 추출
                st.markdown("### 📋 회고 요약")
                lessons = extract_key_lessons_from_reflections(display_content)
                for lesson in lessons:
                    st.markdown(f"- {lesson}")
            else:
                # 전체 회고 내용 마크다운으로 표시
                st.markdown(display_content)
        
        with tab2:
            # 회고 통계 분석
            render_reflection_statistics(reflection_content)
        
        with tab3:
            # 핵심 교훈 추출 및 표시
            render_key_lessons(reflection_content)
            
    except Exception as e:
        st.error(f"회고 파일 읽기 중 오류: {e}")

def extract_key_lessons_from_reflections(content):
    """회고 내용에서 핵심 교훈 추출"""
    lessons = []
    
    # 다양한 교훈 패턴 찾기
    lesson_patterns = [
        r'핵심 학습 포인트[:\s]*([^\n]+)',
        r'교훈[:\s]*([^\n]+)',
        r'개선점[:\s]*([^\n]+)',
        r'다음 거래[:\s]*([^\n]+)',
        r'학습된 점[:\s]*([^\n]+)',
        r'중요한 깨달음[:\s]*([^\n]+)'
    ]
    
    for pattern in lesson_patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        lessons.extend(matches)
    
    # 중복 제거 및 정리
    unique_lessons = []
    seen = set()
    for lesson in lessons:
        lesson_clean = lesson.strip()
        if lesson_clean and lesson_clean not in seen and len(lesson_clean) > 10:
            unique_lessons.append(lesson_clean)
            seen.add(lesson_clean)
    
    return unique_lessons[:10]  # 최대 10개까지

def render_reflection_statistics(content):
    """회고 통계 분석"""
    st.markdown("### 📊 회고 분석 통계")
    
    # 거래 ID별 분석
    trade_ids = re.findall(r'거래 ID (\d+)', content)
    
    # 키워드 빈도 분석
    keywords = ['수익', '손실', '매도', '매수', '타이밍', '전략', '리스크', '교훈']
    keyword_counts = {}
    
    for keyword in keywords:
        count = len(re.findall(keyword, content, re.IGNORECASE))
        keyword_counts[keyword] = count
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**📈 분석된 거래 수**")
        st.metric("총 회고 거래", len(set(trade_ids)))
        
        st.markdown("**🔤 주요 키워드 빈도**")
        for keyword, count in sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True):
            if count > 0:
                st.write(f"• {keyword}: {count}회")
    
    with col2:
        # 성공/실패 패턴 분석
        success_indicators = ['수익', '성공', '목표', '달성']
        failure_indicators = ['손실', '실패', '손절', '하락']
        
        success_count = sum(len(re.findall(word, content, re.IGNORECASE)) for word in success_indicators)
        failure_count = sum(len(re.findall(word, content, re.IGNORECASE)) for word in failure_indicators)
        
        st.markdown("**💰 성과 관련 언급**")
        st.metric("긍정적 언급", success_count)
        st.metric("부정적 언급", failure_count)
        
        if success_count + failure_count > 0:
            positive_ratio = success_count / (success_count + failure_count) * 100
            st.metric("긍정 비율", f"{positive_ratio:.1f}%")

def render_key_lessons(content):
    """핵심 교훈 정리 및 표시"""
    st.markdown("### 💡 축적된 핵심 교훈")
    
    lessons = extract_key_lessons_from_reflections(content)
    
    if not lessons:
        st.info("추출된 핵심 교훈이 없습니다.")
        return
    
    # 카테고리별 분류
    categories = {
        "진입 전략": ["진입", "매수", "타이밍"],
        "매도 전략": ["매도", "목표", "익절"],
        "리스크 관리": ["손절", "리스크", "위험"],
        "시장 분석": ["분석", "지표", "신호"],
        "일반 교훈": []
    }
    
    categorized_lessons = {cat: [] for cat in categories}
    
    for lesson in lessons:
        categorized = False
        for category, keywords in categories.items():
            if category == "일반 교훈":
                continue
            if any(keyword in lesson for keyword in keywords):
                categorized_lessons[category].append(lesson)
                categorized = True
                break
        
        if not categorized:
            categorized_lessons["일반 교훈"].append(lesson)
    
    # 카테고리별 표시
    for category, category_lessons in categorized_lessons.items():
        if category_lessons:
            st.markdown(f"#### {category}")
            for lesson in category_lessons:
                st.markdown(f"• {lesson}")
            st.markdown("---")
    
    # 교훈 검색
    st.markdown("#### 🔍 교훈 검색")
    lesson_search = st.text_input("교훈 내용 검색", placeholder="검색할 키워드 입력")
    
    if lesson_search:
        matching_lessons = [lesson for lesson in lessons if lesson_search.lower() in lesson.lower()]
        if matching_lessons:
            st.markdown("**검색 결과:**")
            for lesson in matching_lessons:
                st.success(lesson)
        else:
            st.warning("검색 결과가 없습니다.")

def render_trade_history():
    """거래 히스토리"""
    st.markdown('<h2 class="section-title">📋 거래 히스토리</h2>', unsafe_allow_html=True)
    
    df = get_all_trades()
    if df.empty:
        st.markdown("""
        <div class="glass-metric">
            <div style="text-align: center; padding: 2rem;">
                <h3 style="color: #2980b9;">📝 거래 기록이 없습니다</h3>
                <p style="color: #7f8c8d;">첫 거래 시작 후 기록이 표시됩니다</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
        return
    
    # 상태별 필터
    status_filter = st.selectbox(
        "상태 필터",
        ["전체", "PLANNED", "ACTIVE", "COMPLETED", "CANCELLED"],
        index=0
    )
    
    if status_filter != "전체":
        filtered_df = df[df['status'] == status_filter].copy()
    else:
        filtered_df = df.copy()
    
    # 표시할 데이터 준비
    def format_status(status):
        status_class = f"status-{status.lower()}"
        return f'<span class="status-badge {status_class}">{status}</span>'
    
    def format_profit(profit, rate):
        if pd.isna(profit) or pd.isna(rate):
            return "-"
        if profit > 0:
            return f'<span style="color: #00b894; font-weight: bold">+{profit:,.0f}원 (+{rate:.2f}%)</span>'
        else:
            return f'<span style="color: #e74c3c; font-weight: bold">{profit:,.0f}원 ({rate:.2f}%)</span>'
    
    def format_price(price):
        if pd.isna(price):
            return "-"
        return f"{price:,.0f}원"
    
    # 데이터 포맷팅
    for idx, row in filtered_df.iterrows():
        filtered_df.at[idx, 'status_formatted'] = format_status(row['status'])
        filtered_df.at[idx, 'profit_display'] = format_profit(row['net_profit_krw'], row['profit_rate_pct'])
        filtered_df.at[idx, 'planned_entry_formatted'] = format_price(row['planned_entry_price'])
        filtered_df.at[idx, 'actual_entry_formatted'] = format_price(row['actual_entry_price'])
        filtered_df.at[idx, 'actual_exit_formatted'] = format_price(row['actual_exit_price'])
    
    # 테이블 생성
    if not filtered_df.empty:
        # 컬럼 선택 및 이름 변경
        show_columns = {
            'trade_id': '거래ID',
            'status_formatted': '상태',
            'plan_timestamp': '계획시간',
            'planned_entry_formatted': '계획진입가',
            'actual_entry_formatted': '실제진입가',
            'actual_exit_formatted': '매도가',
            'trade_result': '결과',
            'profit_display': '손익'
        }
        
        display_df = filtered_df[list(show_columns.keys())].copy()
        display_df.columns = list(show_columns.values())
        
        # 스타일이 적용된 테이블
        st.markdown(f"""
        <div class="glass-metric">
            <div style="overflow-x: auto;">
                {display_df.to_html(escape=False, index=False, classes='dataframe')}
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.info(f"{status_filter} 상태의 거래가 없습니다.")

def render_price_chart():
    """가격 차트"""
    st.markdown('<h2 class="section-title">📊 XRP 가격 차트</h2>', unsafe_allow_html=True)
    
    # 시간대 선택
    timeframe_options = {
        "5분": "minute5",
        "15분": "minute15", 
        "1시간": "minute60",
        "4시간": "minute240",
        "일봉": "day"
    }
    
    col1, col2 = st.columns([1, 3])
    with col1:
        selected_tf = st.selectbox("시간대", list(timeframe_options.keys()), index=2)
    with col2:
        show_trades = st.checkbox("거래 포인트 표시", value=True)
    
    interval = timeframe_options[selected_tf]
    
    try:
        # OHLCV 데이터 조회
        df_ohlcv = pyupbit.get_ohlcv("KRW-XRP", interval=interval, count=200)
        
        if df_ohlcv is not None and not df_ohlcv.empty:
            # 캔들스틱 차트
            fig = go.Figure()
            
            # 캔들스틱 추가
            fig.add_trace(go.Candlestick(
                x=df_ohlcv.index,
                open=df_ohlcv['open'],
                high=df_ohlcv['high'],
                low=df_ohlcv['low'],
                close=df_ohlcv['close'],
                name='XRP/KRW',
                increasing_line_color='#00b894',
                decreasing_line_color='#e74c3c'
            ))
            
            # 거래 포인트 표시
            if show_trades:
                trades_df = get_all_trades()
                completed_trades = trades_df[trades_df['status'] == 'COMPLETED'].copy()
                
                for _, trade in completed_trades.iterrows():
                    if pd.notna(trade['entry_timestamp']) and pd.notna(trade['exit_timestamp']):
                        try:
                            entry_time = pd.to_datetime(trade['entry_timestamp'])
                            exit_time = pd.to_datetime(trade['exit_timestamp'])
                            
                            # 매수 포인트
                            fig.add_trace(go.Scatter(
                                x=[entry_time],
                                y=[trade['actual_entry_price']],
                                mode='markers',
                                marker=dict(
                                    symbol='triangle-up', 
                                    size=15, 
                                    color='#3498db',
                                    line=dict(width=2, color='white')
                                ),
                                name=f'매수 #{trade["trade_id"]}',
                                showlegend=False,
                                hovertemplate=f'<b>매수 #{trade["trade_id"]}</b><br>가격: {trade["actual_entry_price"]:,.0f}원<br>시간: %{{x}}<extra></extra>'
                            ))
                            
                            # 매도 포인트
                            color = '#00b894' if trade['net_profit_krw'] > 0 else '#e74c3c'
                            fig.add_trace(go.Scatter(
                                x=[exit_time],
                                y=[trade['actual_exit_price']],
                                mode='markers',
                                marker=dict(
                                    symbol='triangle-down', 
                                    size=15, 
                                    color=color,
                                    line=dict(width=2, color='white')
                                ),
                                name=f'매도 #{trade["trade_id"]}',
                                showlegend=False,
                                hovertemplate=f'<b>매도 #{trade["trade_id"]}</b><br>가격: {trade["actual_exit_price"]:,.0f}원<br>수익: {trade["net_profit_krw"]:+,.0f}원<br>시간: %{{x}}<extra></extra>'
                            ))
                        except:
                            continue
            
            # 차트 레이아웃
            fig.update_layout(
                title={
                    'text': f"XRP/KRW {selected_tf} 차트",
                    'x': 0.5,
                    'font': {'size': 20, 'color': '#2c3e50'}
                },
                xaxis_title="시간",
                yaxis_title="가격 (원)",
                height=700,
                plot_bgcolor='rgba(255,255,255,0.9)',
                paper_bgcolor='rgba(255,255,255,0.9)',
                font=dict(color='#2c3e50'),
                xaxis_rangeslider_visible=False,
                showlegend=False
            )
            
            # 그리드 스타일
            fig.update_xaxes(
                gridcolor='rgba(44, 62, 80, 0.1)',
                zerolinecolor='rgba(44, 62, 80, 0.2)'
            )
            fig.update_yaxes(
                gridcolor='rgba(44, 62, 80, 0.1)',
                zerolinecolor='rgba(44, 62, 80, 0.2)'
            )
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.error("차트 데이터를 불러올 수 없습니다.")
            
    except Exception as e:
        st.error(f"차트 생성 실패: {e}")
        
        # 기본 현재가라도 표시
        try:
            current_price = pyupbit.get_current_price("KRW-XRP")
            if current_price:
                st.metric("현재 XRP 가격", f"{current_price:,.0f}원")
        except:
            st.error("현재가 조회도 실패했습니다.")

def check_api_keys():
    """API 키 확인"""
    openai_key = os.getenv("OPENAI_API_KEY")
    upbit_access = os.getenv("UPBIT_ACCESS_KEY") 
    upbit_secret = os.getenv("UPBIT_SECRET_KEY")
    
    missing_keys = []
    if not openai_key:
        missing_keys.append("OPENAI_API_KEY")
    if not upbit_access:
        missing_keys.append("UPBIT_ACCESS_KEY")
    if not upbit_secret:
        missing_keys.append("UPBIT_SECRET_KEY")
    
    return missing_keys

def main():
    """메인 함수 (모든 탭 기능 통합)"""
    # API 키 확인
    missing_keys = check_api_keys()
    
    if missing_keys:
        st.error("🚨 API 키가 설정되지 않았습니다!")
        st.markdown(f"""
        ### 설정이 필요한 API 키:
        {' '.join([f'- **{key}**' for key in missing_keys])}
        
        ### 설정 방법:
        1. 프로젝트 폴더에 `.env` 파일 생성
        2. 다음 내용 추가:
        ```
        OPENAI_API_KEY=your_openai_api_key
        UPBIT_ACCESS_KEY=your_upbit_access_key
        UPBIT_SECRET_KEY=your_upbit_secret_key
        ```
        3. 대시보드 재시작
        
        ### 업비트 API 키 발급:
        1. [업비트 프로](https://upbit.com/mypage/open_api_management) 접속
        2. Open API 관리 → API 키 발급
        3. 권한: 자산조회, 주문조회, 주문하기 체크
        4. 발급받은 키를 .env 파일에 입력
        """)
        return
    
    # 헤더
    render_header()
    
    # 네비게이션
    current_tab = render_navigation()
    
    # 새로고침 버튼 (우하단 고정)
    st.markdown("""
    <button class="refresh-btn" onclick="window.location.reload()">🔄</button>
    """, unsafe_allow_html=True)
    
    # 탭별 컨텐츠 렌더링 (AI판단, 회고록 탭 추가)
    if current_tab == '대시보드':
        render_current_position()  # 가장 중요한 포지션 정보를 최상단에
        st.markdown("---")
        render_market_status()      # 추가 시장 정보
        st.markdown("---")
        render_active_trades()      # 활성 거래
    elif current_tab == '활성거래':
        render_current_position()  # 활성거래 탭에서도 포지션 정보 표시
        st.markdown("---")
        render_active_trades()
    elif current_tab == '성과분석':
        render_performance()
    elif current_tab == '차트':
        render_price_chart()
    elif current_tab == 'AI판단':          # 🆕 새로 추가
        render_decision_reasoning()
    elif current_tab == '회고록':          # 🆕 새로 추가
        render_reflection_records()
    elif current_tab == '히스토리':
        render_trade_history()
    
    # 마지막 업데이트 시간 (하단 중앙)
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.markdown(f"""
        <div style="text-align: center; color: #7f8c8d; font-size: 0.9rem;">
            ⏰ 마지막 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </div>
        """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()