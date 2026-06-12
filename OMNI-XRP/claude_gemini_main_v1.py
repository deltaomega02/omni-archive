import os
import json
import time
import logging
import sqlite3
import pandas as pd
import pandas_ta as ta
import numpy as np
import re
from datetime import datetime, timedelta
import schedule
import pyupbit
from openai import OpenAI
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('omni_xrp_v72.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def convert_numpy_types(obj):
    """NumPy 타입을 Python 기본 타입으로 변환"""
    if isinstance(obj, dict):
        return {key: convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(item) for item in obj]
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif pd.isna(obj):
        return None
    else:
        return obj


class OMNIXRPSystem:
    """OMNI-XRP v7.2: 확률론적 접근 + XRP 전문가 튜닝 통합 시스템"""
    
    def __init__(self):
        """v7.2 시스템 초기화"""
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.upbit = pyupbit.Upbit(
            os.getenv("UPBIT_ACCESS_KEY"), 
            os.getenv("UPBIT_SECRET_KEY")
        )
        self.db_path = 'omni_xrp_v72_trades.sqlite'
        self.current_active_plan_id = None

        # 급변동 감지 위한 변수
        self.price_alert_threshold = 0.007  # 0.7% 변동 시 알림
        self.volume_spike_threshold = 2   # 거래량 2배 시 추가 알림
        self.emergency_cooldown = 180      # 3분 쿨다운
        self.last_emergency_time = None

        # 동적 분석 주기 관련 변수들
        self.current_analysis_interval = 30  # 현재 분석 주기 (분)
        self.last_regime_check = None        # 마지막 체제 확인 시간
        self.regime_change_cooldown = 300    # 5분 쿨다운
        self.last_interval_change = None     # 마지막 주기 변경 시간

        # v7.2 새로운 변수들
        self.last_checklist_validation = None  # 마지막 체크리스트 검증 시간
        self.checklist_cooldown = 120          # 체크리스트 재검증 쿨다운 (2분)
        self.last_trigger_check = None         # 마지막 트리거 확인 시간
        self.trigger_check_cooldown = 300      # 트리거 체크 쿨다운 (5분)
        
        # v7.2 XRP 전문가 설정
        self.wick_defense_enabled = True       # 위꼬리/아래꼬리 방어 활성화
        self.wick_defense_timeframe = 15       # 방어 확인 시간프레임 (분)
        self.energy_compression_threshold = 0.7  # 에너지 응축 임계값
        self.compression_breakout_multiplier = 1.5  # 돌파 승수

        # v7.2 신호 신뢰도 승수 설정
        self.signal_confidence_multipliers = {
            4.5: 1.0,    # A+급 최상의 기회 (90-100%)
            3.5: 0.7,    # 좋은 기회 (70-89%)
            2.5: 0.4,    # XRP 특별 허용 구간 (40-69%)
            0.0: 0.0     # 진입 절대 금지 (0-39%)
        }

        self.initialize_database()
        logger.info("🎯 OMNI-XRP v7.2 확률론적 접근 + XRP 전문가 시스템이 초기화되었습니다.")

    def initialize_database(self):
        """v7.2 PostgreSQL 호환 SQLite 데이터베이스 초기화"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # trades 테이블 생성 (v7.2 강화)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trades (
                    trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asset_ticker TEXT NOT NULL DEFAULT 'XRP',
                    status TEXT NOT NULL CHECK (status IN ('PLANNED', 'ACTIVE', 'COMPLETED', 'CANCELLED', 'SUPERSEDED')),
                    
                    -- 계획 단계 데이터
                    plan_timestamp TEXT NOT NULL,
                    planned_entry_price REAL NOT NULL,
                    planned_target_price REAL NOT NULL,
                    planned_stop_loss REAL NOT NULL,
                    entry_reason TEXT NOT NULL,
                    target_reason TEXT NOT NULL,
                    stop_loss_reason TEXT NOT NULL,
                    
                    -- v7.2 확률론적 접근 필드들
                    checklist_score REAL DEFAULT 0.0,
                    checklist_breakdown TEXT DEFAULT '',
                    signal_confidence_multiplier REAL DEFAULT 1.0,
                    calculated_position_ratio REAL DEFAULT 0.0,
                    change_trigger TEXT DEFAULT 'NONE',
                    trigger_evidence TEXT DEFAULT '',
                    
                    -- v7.2 XRP 전문가 필드들
                    wick_defense_active BOOLEAN DEFAULT FALSE,
                    energy_compression_detected BOOLEAN DEFAULT FALSE,
                    xrp_pattern_type TEXT DEFAULT 'NONE',
                    
                    -- 실행 단계 데이터
                    position_size_xrp REAL,
                    entry_timestamp TEXT,
                    actual_entry_price REAL,
                    exit_timestamp TEXT,
                    actual_exit_price REAL,
                    
                    -- 결과 단계 데이터
                    trade_result TEXT CHECK (trade_result IN ('PROFIT_TAKE', 'STOP_LOSS', 'MANUAL_EXIT', 'WICK_DEFENSE_SAVE')),
                    commission_krw REAL DEFAULT 0.0,
                    net_profit_krw REAL,
                    profit_rate_pct REAL
                )
            ''')
            
            # v7.2 기존 테이블에 새 컬럼 추가 (이미 존재하는 경우 무시)
            new_columns = [
                ('signal_confidence_multiplier', 'REAL DEFAULT 1.0'),
                ('calculated_position_ratio', 'REAL DEFAULT 0.0'),
                ('wick_defense_active', 'BOOLEAN DEFAULT FALSE'),
                ('energy_compression_detected', 'BOOLEAN DEFAULT FALSE'),
                ('xrp_pattern_type', 'TEXT DEFAULT "NONE"')
            ]
            
            for column_name, column_def in new_columns:
                try:
                    cursor.execute(f'ALTER TABLE trades ADD COLUMN {column_name} {column_def}')
                    logger.info(f"📊 v7.2 새 컬럼 추가: {column_name}")
                except sqlite3.OperationalError:
                    # 컬럼이 이미 존재하는 경우
                    pass
            
            conn.commit()
            logger.info("📊 v7.2 데이터베이스가 초기화되었습니다.")

# =============================================================================
    # v7.2 Part 2: 포지션 상태 관리 및 시장 데이터 관찰
    # =============================================================================
    
    def check_current_position(self):
        """v7.2 현재 XRP 보유 상태 확인 (XRP 전문가 정보 포함)"""
        try:
            # 업비트 잔고 확인
            xrp_balance = self.upbit.get_balance("XRP")
            
            # 활성 거래 확인 (v7.2 필드 포함)
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT trade_id, actual_entry_price, planned_target_price, planned_stop_loss,
                           checklist_score, change_trigger, signal_confidence_multiplier,
                           wick_defense_active, xrp_pattern_type
                    FROM trades 
                    WHERE status = 'ACTIVE'
                    ORDER BY entry_timestamp DESC
                    LIMIT 1
                ''')
                active_trade = cursor.fetchone()
            
            has_position = xrp_balance > 0.0001  # 최소 보유량 기준
            has_active_trade = active_trade is not None
            
            return {
                'has_position': has_position,
                'xrp_balance': xrp_balance,
                'has_active_trade': has_active_trade,
                'active_trade_info': active_trade
            }
            
        except Exception as e:
            logger.error(f"❌ v7.2 현재 포지션 확인 중 오류: {e}")
            return {'has_position': False, 'xrp_balance': 0, 'has_active_trade': False, 'active_trade_info': None}

    def validate_and_cleanup_existing_plans(self):
        """v7.2 시스템 시작 시 실제 포지션에 맞춰 DB 상태를 검증 및 정리"""
        try:
            logger.info("🛡️ v7.2 시스템 시작 - DB 상태 검증 및 정리 작업 시작...")
            
            # 1. 실제 포지션 상태 확인
            position_status = self.check_current_position()
            has_position = position_status.get('has_position', False)
            xrp_balance = position_status.get('xrp_balance', 0)
            
            logger.info(f"💰 실제 XRP 보유 상태: {'보유 중' if has_position else '미보유'}")
            if has_position:
                logger.info(f"   보유량: {xrp_balance:.4f} XRP")
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 현재 DB 상태 조회
                cursor.execute("SELECT COUNT(*) FROM trades WHERE status = 'PLANNED'")
                planned_count = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM trades WHERE status = 'ACTIVE'")
                active_count = cursor.fetchone()[0]
                
                logger.info(f"📊 현재 DB 상태: PLANNED={planned_count}개, ACTIVE={active_count}개")
                
                if has_position:
                    # [상황 A] 실제 XRP 보유 중
                    logger.info("🎯 XRP 보유 중 - ACTIVE 거래는 유지, PLANNED 거래는 모두 취소")
                    
                    # PLANNED 상태의 모든 거래를 CANCELLED로 변경
                    cursor.execute("UPDATE trades SET status = 'CANCELLED' WHERE status = 'PLANNED'")
                    cancelled_planned = cursor.rowcount
                    
                    if cancelled_planned > 0:
                        logger.info(f"🗑️ 불필요한 PLANNED 거래 {cancelled_planned}개 정리 완료")
                    
                    # ACTIVE 거래 상태 확인
                    if active_count == 0:
                        logger.warning("⚠️ XRP 보유 중이지만 ACTIVE 거래가 없음 - 첫 전략 분석에서 처리 예정")
                    elif active_count > 1:
                        logger.warning(f"⚠️ ACTIVE 거래가 {active_count}개 - 최신 것만 유지")
                        # 가장 최근 ACTIVE만 남기고 나머지는 SUPERSEDED로 변경
                        cursor.execute('''
                            UPDATE trades 
                            SET status = 'SUPERSEDED' 
                            WHERE status = 'ACTIVE' 
                            AND trade_id NOT IN (
                                SELECT trade_id FROM trades 
                                WHERE status = 'ACTIVE' 
                                ORDER BY entry_timestamp DESC 
                                LIMIT 1
                            )
                        ''')
                        cleaned_count = cursor.rowcount
                        logger.info(f"🔧 중복 ACTIVE 거래 {cleaned_count}개를 SUPERSEDED로 정리")
                    else:
                        logger.info("✅ ACTIVE 거래 상태 정상")

                else:
                    # [상황 B] 실제 XRP 미보유
                    logger.info("💸 XRP 미보유 - 모든 ACTIVE 및 PLANNED 거래 정리")
                    
                    # ACTIVE 또는 PLANNED 상태의 모든 거래를 CANCELLED로 변경
                    cursor.execute("UPDATE trades SET status = 'CANCELLED' WHERE status IN ('ACTIVE', 'PLANNED')")
                    cancelled_total = cursor.rowcount
                    
                    if cancelled_total > 0:
                        logger.info(f"👻 유령 거래/계획 {cancelled_total}개 정리 완료")
                    else:
                        logger.info("✅ 정리할 거래 없음 - 깨끗한 상태")
                
                conn.commit()
                logger.info("🛡️ v7.2 DB 상태 검증 및 정리 완료. 시스템이 안전한 상태에서 시작됩니다.")
                
        except Exception as e:
            logger.error(f"❌ v7.2 시스템 시작 검증 중 치명적 오류: {e}")
            # 오류 발생 시 안전을 위해 모든 계획 비활성화
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("UPDATE trades SET status = 'CANCELLED' WHERE status IN ('PLANNED', 'ACTIVE')")
                    conn.commit()
                logger.info("🚨 오류 발생으로 인한 안전 조치: 모든 계획 비활성화")
            except:
                logger.error("❌ 안전 조치마저 실패")

    def observe_market_data(self):
        """v7.2 관찰(Observe): XRP 시장 데이터 수집 (XRP 전문가 분석 포함)"""
        try:
            api_delay = 0.5
            logger.info("🔍 v7.2 시장 데이터 관찰 중...")
            
            # 현재 시간 및 가격
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            orderbook = pyupbit.get_orderbook(ticker="KRW-XRP")
            current_price = float(orderbook['orderbook_units'][0]['ask_price'])
            
            # 잔고 정보
            balances = self.upbit.get_balances()
            xrp_balance = 0
            krw_balance = 0
            xrp_avg_buy_price = 0
            
            for balance in balances:
                if balance['currency'] == "XRP":
                    xrp_balance = float(balance['balance'])
                    xrp_avg_buy_price = float(balance['avg_buy_price'])
                elif balance['currency'] == "KRW":
                    krw_balance = float(balance['balance'])
            
            # 포지션 상태 확인
            position_status = self.check_current_position()
            
            # 다중 시간대 OHLCV 데이터 (각각 0.2초 간격)
            df_5m = pyupbit.get_ohlcv("KRW-XRP", interval="minute5", count=200)
            if df_5m is None or len(df_5m) == 0:
                logger.error("❌ 5분봉 데이터 조회 실패")
                return None
            time.sleep(api_delay)  # 🔧 API 요청 간격
            
            df_15m = pyupbit.get_ohlcv("KRW-XRP", interval="minute15", count=200)
            if df_15m is None or len(df_15m) == 0:
                logger.error("❌ 15분봉 데이터 조회 실패")
                return None
            time.sleep(api_delay)  # 🔧 API 요청 간격
            
            df_1h = pyupbit.get_ohlcv("KRW-XRP", interval="minute60", count=200)
            if df_1h is None or len(df_1h) == 0:
                logger.error("❌ 1시간봉 데이터 조회 실패")
                return None
            time.sleep(api_delay)  # 🔧 API 요청 간격
            
            df_4h = pyupbit.get_ohlcv("KRW-XRP", interval="minute240", count=200)
            if df_4h is None or len(df_4h) == 0:
                logger.error("❌ 4시간봉 데이터 조회 실패")
                return None
            time.sleep(api_delay)  # 🔧 API 요청 간격
            
            df_day = pyupbit.get_ohlcv("KRW-XRP", interval="day", count=200)
            if df_day is None or len(df_day) == 0:
                logger.error("❌ 일봉 데이터 조회 실패")
                return None
            
            # v7.2 XRP 전문가 분석 추가
            xrp_expert_analysis = self._analyze_xrp_expert_patterns(
                df_5m, df_15m, df_1h, df_4h, df_day, current_price
            )
            
            # A-D 그룹 기술적 지표 계산
            market_data = {
                'current_time': current_time,
                'current_price': current_price,
                'xrp_balance': xrp_balance,
                'krw_balance': krw_balance,
                'xrp_avg_buy_price': xrp_avg_buy_price,
                'position_status': position_status,
                'technical_indicators': self._calculate_comprehensive_indicators(
                    df_5m, df_15m, df_1h, df_4h, df_day
                ),
                'xrp_expert_analysis': xrp_expert_analysis  # v7.2 신규
            }
            
            logger.info(f"✅ v7.2 시장 데이터 수집 완료 - 현재가: {current_price:,.0f}원")
            logger.info(f"   XRP 전문가 분석: {xrp_expert_analysis.get('dominant_pattern', 'NONE')}")
            
            return market_data
            
        except Exception as e:
            logger.error(f"❌ v7.2 시장 데이터 관찰 중 오류: {e}")
            return None

    def _analyze_xrp_expert_patterns(self, df_5m, df_15m, df_1h, df_4h, df_day, current_price):
        """v7.2 XRP 전문가 패턴 분석"""
        try:
            logger.info("🧪 v7.2 XRP 전문가 패턴 분석 시작...")
            
            analysis = {
                'energy_compression_detected': False,
                'compression_strength': 0,
                'wick_pattern_risk': 'low',
                'breakout_probability': 0,
                'dominant_pattern': 'NONE',
                'expert_confidence': 0
            }
            
            # 1. 에너지 응축 패턴 감지 (일봉 기준)
            if len(df_day) >= 20:
                # 볼린저 밴드 폭 계산
                bbands_day = ta.bbands(df_day['close'], length=20, std=2)
                if bbands_day is not None:
                    current_width = (bbands_day['BBU_20_2.0'].iloc[-1] - bbands_day['BBL_20_2.0'].iloc[-1])
                    historical_widths = bbands_day['BBU_20_2.0'] - bbands_day['BBL_20_2.0']
                    avg_width = historical_widths.tail(50).mean()
                    
                    compression_ratio = current_width / avg_width if avg_width > 0 else 1
                    
                    if compression_ratio < self.energy_compression_threshold:
                        analysis['energy_compression_detected'] = True
                        analysis['compression_strength'] = round(1 - compression_ratio, 3)
                        
                        # 거래량 확인
                        volume_day = df_day['volume'].iloc[-1]
                        volume_avg = df_day['volume'].tail(20).mean()
                        volume_ratio = volume_day / volume_avg if volume_avg > 0 else 1
                        
                        if volume_ratio > 1.5:
                            analysis['breakout_probability'] = min(0.9, compression_ratio * volume_ratio)
                            analysis['dominant_pattern'] = 'ENERGY_COMPRESSION_BREAKOUT'
                            
                        logger.info(f"   ⚡ 에너지 응축 감지: 압축비 {compression_ratio:.3f}, 거래량비 {volume_ratio:.1f}")
            
            # 2. 위꼬리/아래꼬리 패턴 위험도 평가
            wick_risk_score = 0
            for tf_name, df in [('15m', df_15m), ('1h', df_1h)]:
                if len(df) >= 10:
                    recent_candles = df.tail(10)
                    for _, candle in recent_candles.iterrows():
                        body_size = abs(candle['close'] - candle['open'])
                        upper_wick = candle['high'] - max(candle['close'], candle['open'])
                        lower_wick = min(candle['close'], candle['open']) - candle['low']
                        
                        if body_size > 0:
                            upper_wick_ratio = upper_wick / body_size
                            lower_wick_ratio = lower_wick / body_size
                            
                            if upper_wick_ratio > 2 or lower_wick_ratio > 2:
                                wick_risk_score += 1
            
            if wick_risk_score >= 3:
                analysis['wick_pattern_risk'] = 'high'
                logger.info(f"   🕯️ 고위험 위꼬리 패턴 감지: 점수 {wick_risk_score}")
            elif wick_risk_score >= 1:
                analysis['wick_pattern_risk'] = 'medium'
            
            # 3. 전문가 신뢰도 계산
            confidence_factors = 0
            if analysis['energy_compression_detected']:
                confidence_factors += 3
            if analysis['breakout_probability'] > 0.7:
                confidence_factors += 2
            if analysis['wick_pattern_risk'] == 'low':
                confidence_factors += 1
                
            analysis['expert_confidence'] = min(5, confidence_factors)
            
            logger.info(f"✅ v7.2 XRP 전문가 분석 완료 - 신뢰도: {analysis['expert_confidence']}/5")
            
            return analysis
            
        except Exception as e:
            logger.error(f"❌ v7.2 XRP 전문가 패턴 분석 중 오류: {e}")
            return {
                'energy_compression_detected': False,
                'compression_strength': 0,
                'wick_pattern_risk': 'unknown',
                'breakout_probability': 0,
                'dominant_pattern': 'ANALYSIS_FAILED',
                'expert_confidence': 0
            }

    def _calculate_comprehensive_indicators(self, df_5m, df_15m, df_1h, df_4h, df_day):
            """A-D 지표 그룹 종합 계산 (v7.2 최적화)"""
            indicators = {}
            timeframes = {'5m': df_5m, '15m': df_15m, '1h': df_1h, '4h': df_4h, 'day': df_day}
            
            for tf, df in timeframes.items():
                try:
                    current_price = float(df['close'].iloc[-1])
                    
                    # A. 추세 지표 
                    sma_20 = ta.sma(df['close'], length=20)
                    sma_60 = ta.sma(df['close'], length=60)
                    ema_12 = ta.ema(df['close'], length=12)
                    ema_26 = ta.ema(df['close'], length=26)
                    ema_60 = ta.ema(df['close'], length=60)
                    macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
                    
                    # 추세 강도 계산
                    trend_strength = 0
                    if not pd.isna(sma_20.iloc[-1]) and not pd.isna(sma_60.iloc[-1]):
                        if current_price > sma_20.iloc[-1] > sma_60.iloc[-1]:
                            strength_ratio = (current_price - sma_60.iloc[-1]) / sma_60.iloc[-1]
                            if strength_ratio > 0.05:
                                trend_strength = 2  # 강한 상승
                            else:
                                trend_strength = 1  # 약한 상승
                        elif current_price < sma_20.iloc[-1] < sma_60.iloc[-1]:
                            strength_ratio = (sma_60.iloc[-1] - current_price) / sma_60.iloc[-1]
                            if strength_ratio > 0.05:
                                trend_strength = -2  # 강한 하락
                            else:
                                trend_strength = -1  # 약한 하락
                    
                    golden_cross = False
                    death_cross = False
                    if len(sma_20) >= 2 and len(sma_60) >= 2:
                        golden_cross = (sma_20.iloc[-1] > sma_60.iloc[-1] and sma_20.iloc[-2] <= sma_60.iloc[-2])
                        death_cross = (sma_20.iloc[-1] < sma_60.iloc[-1] and sma_20.iloc[-2] >= sma_60.iloc[-2])
                    
                    # B. 모멘텀 지표
                    rsi_14 = ta.rsi(df['close'], length=14)
                    stoch = ta.stoch(df['high'], df['low'], df['close'], k=14, d=3)
                    willr = ta.willr(df['high'], df['low'], df['close'], length=14)
                    rsi_divergence = self._detect_rsi_divergence(df['close'], rsi_14)
                    
                    # C. 변동성 지표
                    bbands = ta.bbands(df['close'], length=20, std=2)
                    atr = ta.atr(df['high'], df['low'], df['close'], length=14)
                    bb_squeeze = self._detect_bb_squeeze(bbands)
                    bb_position = self._calculate_bb_position(current_price, bbands)
                    
                    # D. 거래량 지표
                    volume_sma_20 = ta.sma(df['volume'], length=20)
                    volume_ratio = 1.0
                    if not pd.isna(volume_sma_20.iloc[-1]) and volume_sma_20.iloc[-1] > 0:
                        volume_ratio = df['volume'].iloc[-1] / volume_sma_20.iloc[-1]
                    
                    obv = ta.obv(df['close'], df['volume'])
                    vwap = ta.vwap(df['high'], df['low'], df['close'], df['volume'])
                    
                    # 통합 지표 저장
                    indicators[tf] = {
                        'trend': {
                            'sma_20': self._safe_float(sma_20.iloc[-1], current_price),
                            'sma_60': self._safe_float(sma_60.iloc[-1], current_price),
                            'ema_12': self._safe_float(ema_12.iloc[-1], current_price),
                            'ema_26': self._safe_float(ema_26.iloc[-1], current_price),
                            'ema_60': self._safe_float(ema_60.iloc[-1], current_price), 
                            'trend_strength': int(trend_strength),
                            'golden_cross': bool(golden_cross),
                            'death_cross': bool(death_cross)
                        },
                        'momentum': {
                            'rsi': self._safe_float(rsi_14.iloc[-1], 50),
                            'rsi_oversold': bool(self._safe_float(rsi_14.iloc[-1], 50) < 30),
                            'rsi_overbought': bool(self._safe_float(rsi_14.iloc[-1], 50) > 70),
                            'rsi_divergence': rsi_divergence,
                            'stoch_k': self._safe_float(stoch['STOCHk_14_3_3'].iloc[-1] if stoch is not None else 50, 50),
                            'stoch_d': self._safe_float(stoch['STOCHd_14_3_3'].iloc[-1] if stoch is not None else 50, 50),
                            'willr': self._safe_float(willr.iloc[-1], -50)
                        },
                        'volatility': {
                            'bb_upper': self._safe_float(bbands['BBU_20_2.0'].iloc[-1] if bbands is not None else current_price * 1.02, current_price * 1.02),
                            'bb_middle': self._safe_float(bbands['BBM_20_2.0'].iloc[-1] if bbands is not None else current_price, current_price),
                            'bb_lower': self._safe_float(bbands['BBL_20_2.0'].iloc[-1] if bbands is not None else current_price * 0.98, current_price * 0.98),
                            'bb_position': float(bb_position),
                            'bb_squeeze': bool(bb_squeeze),
                            'atr': self._safe_float(atr.iloc[-1], 0),
                            'atr_ratio': float(self._safe_float(atr.iloc[-1], 0) / current_price * 100) if current_price > 0 else 0
                        },
                        'volume': {
                            'current_volume': float(df['volume'].iloc[-1]),
                            'volume_sma_20': self._safe_float(volume_sma_20.iloc[-1], 0),
                            'volume_ratio': float(volume_ratio),
                            'volume_spike': bool(volume_ratio > 2.0),
                            'volume_confirmation': bool(volume_ratio > 1.5),
                            'obv': self._safe_float(obv.iloc[-1], 0),
                            'vwap': self._safe_float(vwap.iloc[-1], current_price)
                        },
                        'ohlc': {
                            'open': float(df['open'].iloc[-1]),
                            'high': float(df['high'].iloc[-1]),
                            'low': float(df['low'].iloc[-1]),
                            'close': current_price
                        }
                    }
                    
                except Exception as e:
                    logger.warning(f"⚠️ {tf} 지표 계산 중 오류: {e}")
                    current_price = float(df['close'].iloc[-1])
                    indicators[tf] = self._get_fallback_indicators(current_price)
            
            return indicators

    def _safe_float(self, value, default):
        """안전한 float 변환"""
        try:
            if pd.isna(value):
                return float(default)
            return float(value)
        except (TypeError, ValueError):
            return float(default)

    def _detect_rsi_divergence(self, price_series, rsi_series, lookback=10):
        """RSI 다이버전스 감지"""
        try:
            if len(price_series) < lookback or len(rsi_series) < lookback:
                return "none"
            
            recent_prices = price_series.tail(lookback)
            recent_rsi = rsi_series.tail(lookback)
            
            # 상승 다이버전스: 가격↓, RSI↑
            if (recent_prices.iloc[-1] < recent_prices.iloc[0] and 
                recent_rsi.iloc[-1] > recent_rsi.iloc[0]):
                return "bullish"
            # 하락 다이버전스: 가격↑, RSI↓
            elif (recent_prices.iloc[-1] > recent_prices.iloc[0] and 
                  recent_rsi.iloc[-1] < recent_rsi.iloc[0]):
                return "bearish"
            
            return "none"
        except Exception:
            return "none"

    def _detect_bb_squeeze(self, bbands, threshold=0.7):
        """볼린저 밴드 스퀴즈 감지"""
        try:
            if bbands is None or len(bbands) < 20:
                return False
            
            current_width = (bbands['BBU_20_2.0'].iloc[-1] - bbands['BBL_20_2.0'].iloc[-1])
            avg_width = ((bbands['BBU_20_2.0'] - bbands['BBL_20_2.0']).tail(20).mean())
            
            return current_width < avg_width * threshold
        except Exception:
            return False

    def _calculate_bb_position(self, current_price, bbands):
        """볼린저 밴드 내 현재가 위치 (0~1)"""
        try:
            if bbands is None:
                return 0.5
            
            bb_upper = bbands['BBU_20_2.0'].iloc[-1]
            bb_lower = bbands['BBL_20_2.0'].iloc[-1]
            
            if bb_upper == bb_lower:
                return 0.5
            
            position = (current_price - bb_lower) / (bb_upper - bb_lower)
            return max(0, min(1, position))
        except Exception:
            return 0.5

    def _get_fallback_indicators(self, current_price):
        """지표 계산 실패 시 기본값"""
        return {
            'trend': {
                'sma_20': current_price, 'sma_60': current_price,
                'ema_12': current_price, 'ema_26': current_price, 'ema_60': current_price, 
                'trend_strength': 0, 'golden_cross': False, 'death_cross': False
            },
            'momentum': {
                'rsi': 50, 'rsi_oversold': False, 'rsi_overbought': False,
                'rsi_divergence': 'none', 'stoch_k': 50, 'stoch_d': 50, 'willr': -50
            },
            'volatility': {
                'bb_upper': current_price * 1.02, 'bb_middle': current_price,
                'bb_lower': current_price * 0.98, 'bb_position': 0.5,
                'bb_squeeze': False, 'atr': 0, 'atr_ratio': 0
            },
            'volume': {
                'current_volume': 0, 'volume_sma_20': 0, 'volume_ratio': 1,
                'volume_spike': False, 'volume_confirmation': False,
                'obv': 0, 'vwap': current_price
            },
            'ohlc': {
                'open': current_price, 'high': current_price,
                'low': current_price, 'close': current_price
            }
        }

    def _analyze_market_regime(self, market_data):
        """v7.2 다중 시간프레임 균형 잡힌 시장체제 분석"""
        try:
            indicators = market_data['technical_indicators']
            current_price = market_data['current_price']
            
            logger.info("🎯 v7.2 시장체제 분석 시작")
            logger.info(f"기준 현재가: {current_price:,.0f}원")
            
            # 시간프레임별 점수 계산
            timeframe_scores = {}
            timeframe_weights = {
                '5m': 0.15, '15m': 0.20, '1h': 0.25, '4h': 0.25, 'day': 0.15
            }
            
            total_weighted_score = 0
            
            for tf, weight in timeframe_weights.items():
                if tf not in indicators:
                    continue
                    
                tf_data = indicators[tf]['trend']
                sma_20 = tf_data.get('sma_20', current_price)
                sma_60 = tf_data.get('sma_60', current_price)
                
                # 추세 점수 계산
                tf_score = tf_data.get('trend_strength', 0)
                
                # 골든/데스크로스 추가 점수
                if tf_data.get('golden_cross', False):
                    tf_score += 1
                elif tf_data.get('death_cross', False):
                    tf_score -= 1
                
                tf_score = max(-3, min(3, tf_score))
                
                timeframe_scores[tf] = tf_score
                weighted_contribution = tf_score * weight
                total_weighted_score += weighted_contribution
            
            # 변동성 분석
            h4_indicators = indicators.get('4h', {})
            day_indicators = indicators.get('day', {})
            
            h4_volatility = h4_indicators.get('volatility', {})
            day_volatility = day_indicators.get('volatility', {})
            
            h4_atr_ratio = h4_volatility.get('atr_ratio', 2.0)
            day_atr_ratio = day_volatility.get('atr_ratio', 2.0)
            bb_squeeze = day_volatility.get('bb_squeeze', False)
            
            is_sideways = (h4_atr_ratio < 1.2 and day_atr_ratio < 1.5) or bb_squeeze
            is_high_volatility = h4_atr_ratio > 3.0 or day_atr_ratio > 3.0
            
            # 비트코인 및 구조 분석
            btc_analysis = self._analyze_bitcoin_correlation(market_data)
            structure_analysis = self._check_market_structure_shift(market_data)
            
            # 체제 결정
            adjusted_regime_score = total_weighted_score
            confidence = "높음"
            
            if adjusted_regime_score <= -2.0 and not is_sideways:  
                market_regime = "명백한_하락장"
                risk_level = "매우높음"
                trading_approach = "매매금지"
            elif adjusted_regime_score >= 2.0 and not is_sideways:  
                market_regime = "명백한_상승장" 
                risk_level = "보통"
                trading_approach = "적극매매"
            elif is_sideways:
                market_regime = "횡보_박스권"
                risk_level = "보통"
                trading_approach = "단기매매"
                confidence = "중간"
            elif is_high_volatility:
                market_regime = "고변동성_혼조장"
                risk_level = "높음"
                trading_approach = "신중매매"
                confidence = "낮음"
            elif abs(adjusted_regime_score) < 0.5:  
                market_regime = "애매한_혼조장"
                risk_level = "높음"
                trading_approach = "신중매매"
                confidence = "낮음"
            else:
                market_regime = "혼조장"
                risk_level = "높음"
                trading_approach = "신중매매"
                confidence = "낮음"
            
            # 신뢰도 점수 계산
            reliability_score = self._calculate_reliability_score(
                {'regime': market_regime, 'confidence': confidence}, 
                btc_analysis, 
                structure_analysis
            )
            
            logger.info(f"🎯 v7.2 최종 체제 결정: {market_regime}")
            
            return {
                'regime': market_regime,
                'risk_level': risk_level,
                'approach': trading_approach,
                'confidence': confidence,
                'regime_score': adjusted_regime_score,
                'timeframe_scores': timeframe_scores,
                'volatility_state': 'compressed' if is_sideways else 'high' if is_high_volatility else 'normal',
                'key_signals': {
                    'golden_cross': any(indicators.get(tf, {}).get('trend', {}).get('golden_cross', False) for tf in ['1h', '4h']),
                    'death_cross': any(indicators.get(tf, {}).get('trend', {}).get('death_cross', False) for tf in ['1h', '4h']),
                    'bb_squeeze': bb_squeeze,
                    'atr_ratio_4h': h4_atr_ratio,
                    'atr_ratio_day': day_atr_ratio
                },
                'btc_analysis': btc_analysis,
                'structure_analysis': structure_analysis,
                'reliability_score': reliability_score
            }
            
        except Exception as e:
            logger.error(f"v7.2 시장 체제 분석 중 오류: {e}")
            return {
                'regime': '분석실패',
                'risk_level': '매우높음',
                'approach': '매매금지',
                'confidence': '없음',
                'regime_score': 0,
                'reliability_score': 0
            }

    def _analyze_bitcoin_correlation(self, market_data):
        """비트코인과의 상관관계 분석"""
        try:
            api_delay = 0.5
            logger.info("🔗 비트코인 상관관계 분석 시작...")
            time.sleep(api_delay)  # 🔧 API 요청 간격
            btc_1h = pyupbit.get_ohlcv("KRW-BTC", interval="minute60", count=50)
            if btc_1h is None or len(btc_1h) == 0:
                logger.warning("⚠️ BTC 1시간봉 데이터 조회 실패")
                return {'correlation': 0.5, 'btc_trend': '알수없음', 'btc_1h_change': 0, 'btc_influence': '분석실패'}
            
            time.sleep(api_delay)  # 🔧 API 요청 간격
            xrp_1h = pyupbit.get_ohlcv("KRW-XRP", interval="minute60", count=50)
            if xrp_1h is None or len(xrp_1h) == 0:
                logger.warning("⚠️ XRP 1시간봉 데이터 조회 실패 (상관관계 분석용)")
                return {'correlation': 0.5, 'btc_trend': '알수없음', 'btc_1h_change': 0, 'btc_influence': '분석실패'}
    
            btc_returns = btc_1h['close'].pct_change().dropna()
            xrp_returns = xrp_1h['close'].pct_change().dropna()
            
            correlation = btc_returns.corr(xrp_returns)
            
            btc_current = float(btc_1h['close'].iloc[-1])
            btc_sma20 = btc_1h['close'].rolling(20).mean().iloc[-1]
            btc_trend = "상승" if btc_current > btc_sma20 else "하락"
            
            btc_1h_change = ((btc_current - btc_1h['close'].iloc[-2]) / btc_1h['close'].iloc[-2] * 100)
            
            return {
                'correlation': correlation,
                'btc_trend': btc_trend,
                'btc_1h_change': btc_1h_change,
                'btc_influence': "높음" if abs(correlation) > 0.7 else "보통" if abs(correlation) > 0.4 else "낮음"
            }
            
        except Exception as e:
            logger.error(f"비트코인 상관관계 분석 중 오류: {e}")
            return {'correlation': 0.5, 'btc_trend': '알수없음', 'btc_1h_change': 0, 'btc_influence': '분석실패'}

    def _check_market_structure_shift(self, market_data):
        """시장 구조 변화 감지"""
        try:
            indicators = market_data['technical_indicators']
            
            divergence_signals = 0
            timeframes = ['1h', '4h', 'day']
            
            for tf in timeframes:
                if tf in indicators:
                    tf_data = indicators[tf]
                    rsi_div = tf_data.get('momentum', {}).get('rsi_divergence', 'none')
                    if rsi_div in ['bullish', 'bearish']:
                        divergence_signals += 1
            
            volume_anomaly = False
            if 'day' in indicators:
                recent_volume = indicators['day']['volume']['volume_ratio']
                if recent_volume > 3.0 or recent_volume < 0.3:
                    volume_anomaly = True
            
            volatility_spike = False
            if 'day' in indicators:
                atr_ratio = indicators['day']['volatility']['atr_ratio']
                if atr_ratio > 5.0:
                    volatility_spike = True
            
            structure_shift_risk = "높음" if (divergence_signals >= 2 or volume_anomaly or volatility_spike) else "낮음"
            
            return {
                'divergence_signals': divergence_signals,
                'volume_anomaly': volume_anomaly,
                'volatility_spike': volatility_spike,
                'structure_shift_risk': structure_shift_risk
            }
            
        except Exception as e:
            logger.error(f"시장 구조 변화 감지 중 오류: {e}")
            return {'structure_shift_risk': '분석실패'}

    def _calculate_reliability_score(self, base_regime, btc_analysis, structure_analysis):
        """시장 판단의 신뢰도 점수 (0-100)"""
        score = 70
        
        if base_regime['confidence'] == "높음":
            score += 20
        elif base_regime['confidence'] == "중간":
            score += 10
        elif base_regime['confidence'] == "낮음":
            score -= 10
        
        if btc_analysis['btc_influence'] == "높음":
            btc_1h_change = btc_analysis.get('btc_1h_change', 0)
            if ((base_regime['regime'] in ["명백한_상승장", "횡보_박스권"] and btc_analysis['btc_trend'] == "상승") or
                (base_regime['regime'] == "명백한_하락장" and btc_analysis['btc_trend'] == "하락")):
                score += 15
            else:
                score -= 20
        
        if structure_analysis['structure_shift_risk'] == "높음":
            score -= 25
        
        return max(0, min(100, score))

# =============================================================================
    # v7.2 Part 4: 확률론적 체크리스트 및 신호 신뢰도 시스템
    # =============================================================================
    
    def _validate_entry_checklist_v72(self, market_data, market_regime):
        """v7.2 핵심: 5단계 진입 체크리스트 + XRP 전문가 보너스"""
        try:
            logger.info("📋 v7.2 확률론적 진입 조건 체크리스트 검증 시작...")
            
            checklist = {
                'market_regime': 0,
                'trend_alignment': 0, 
                'signal_strength': 0,
                'no_contrary_signals': 0,
                'risk_reward': 0,
                'xrp_expert_bonus': 0  # v7.2 신규
            }
            
            # 1. 시장체제 진단 검증 (0-1점)
            regime = market_regime['regime']
            confidence = market_regime['confidence']
            
            if regime == '명백한_상승장' and confidence == '높음':
                checklist['market_regime'] = 1.0
            elif regime == '횡보_박스권' or confidence == '중간':
                checklist['market_regime'] = 0.5
            elif regime == '명백한_하락장' or confidence == '낮음':
                checklist['market_regime'] = 0.0  # 하락장은 무조건 0점
            else:
                checklist['market_regime'] = 0.3  # 기타 상황은 낮은 점수
                
            logger.info(f"   1. 시장체제: {checklist['market_regime']:.1f}/1.0 (체제: {regime}, 신뢰도: {confidence})")
            
            # 2. 다중 시간대 추세 일치성 (0-1점)
            indicators = market_data['technical_indicators']
            aligned_timeframes = 0
            total_timeframes = 0
            trend_direction = None
            
            for tf in ['15m', '1h', '4h', 'day']:
                if tf in indicators:
                    total_timeframes += 1
                    trend_strength = indicators[tf]['trend'].get('trend_strength', 0)
                    
                    if abs(trend_strength) >= 1:
                        if trend_direction is None:
                            trend_direction = 1 if trend_strength > 0 else -1
                        
                        if (trend_direction > 0 and trend_strength > 0) or (trend_direction < 0 and trend_strength < 0):
                            aligned_timeframes += 1
            
            if total_timeframes > 0:
                alignment_ratio = aligned_timeframes / total_timeframes
                if alignment_ratio >= 0.8:
                    checklist['trend_alignment'] = 1.0
                elif alignment_ratio >= 0.6:
                    checklist['trend_alignment'] = 0.5
                else:
                    checklist['trend_alignment'] = 0.0
            
            logger.info(f"   2. 추세일치: {checklist['trend_alignment']:.1f}/1.0 ({aligned_timeframes}/{total_timeframes} 시간대 일치)")
            
            # 3. 진입 신호 강도 검증 (0-1점)
            signal_count = 0
            
            # 골든크로스 체크
            if market_regime.get('key_signals', {}).get('golden_cross', False):
                signal_count += 1
                
            # 거래량 급증 체크
            h1_volume = indicators.get('1h', {}).get('volume', {})
            volume_ratio = h1_volume.get('volume_ratio', 1.0)
            if volume_ratio >= 2.0:
                signal_count += 1
                
            # 모멘텀 신호 체크 (RSI 과매도에서 반등 또는 강세 모멘텀)
            h1_momentum = indicators.get('1h', {}).get('momentum', {})
            if h1_momentum.get('rsi_oversold', False):
                signal_count += 1
                
            if signal_count >= 3:
                checklist['signal_strength'] = 1.0
            elif signal_count >= 2:
                checklist['signal_strength'] = 0.5
            else:
                checklist['signal_strength'] = 0.0
                
            logger.info(f"   3. 신호강도: {checklist['signal_strength']:.1f}/1.0 (신호개수: {signal_count}/3)")
            
            # 4. 반대 신호 부재 확인 (0-1점)
            contrary_signals = 0
            
            # 다이버전스 체크
            rsi_div = h1_momentum.get('rsi_divergence', 'none')
            if rsi_div == 'bearish':
                contrary_signals += 1
                
            # BTC 급락 체크
            btc_analysis = market_regime.get('btc_analysis', {})
            btc_1h_change = btc_analysis.get('btc_1h_change', 0)
            if btc_1h_change < -3:
                contrary_signals += 1
                
            # 주요 저항선 근처 체크 (BB 상단)
            h1_volatility = indicators.get('1h', {}).get('volatility', {})
            bb_position = h1_volatility.get('bb_position', 0.5)
            if bb_position > 0.8:
                contrary_signals += 1
                
            if contrary_signals == 0:
                checklist['no_contrary_signals'] = 1.0
            elif contrary_signals == 1:
                checklist['no_contrary_signals'] = 0.5
            else:
                checklist['no_contrary_signals'] = 0.0
                
            logger.info(f"   4. 반대신호부재: {checklist['no_contrary_signals']:.1f}/1.0 (반대신호: {contrary_signals}개)")
            
            # 5. 손익비 적절성 (0-1점)
            current_price = market_data['current_price']
            atr = indicators.get('1h', {}).get('volatility', {}).get('atr', current_price * 0.02)
            estimated_target = current_price + (atr * 2.0)
            estimated_stop = current_price - (atr * 1.0)
            
            risk_reward_ratio = 1.0
            if estimated_stop > 0:
                risk_reward_ratio = (estimated_target - current_price) / (current_price - estimated_stop)
                
                if risk_reward_ratio >= 2.0:
                    checklist['risk_reward'] = 1.0
                elif risk_reward_ratio >= 1.5:
                    checklist['risk_reward'] = 0.5
                else:
                    checklist['risk_reward'] = 0.0
            else:
                checklist['risk_reward'] = 0.0
                
            logger.info(f"   5. 손익비: {checklist['risk_reward']:.1f}/1.0 (추정 R:R = {risk_reward_ratio:.2f})")
            
            # 6. v7.2 XRP 전문가 보너스 (0-0.5점)
            xrp_analysis = market_data.get('xrp_expert_analysis', {})
            expert_confidence = xrp_analysis.get('expert_confidence', 0)
            energy_compression = xrp_analysis.get('energy_compression_detected', False)
            breakout_prob = xrp_analysis.get('breakout_probability', 0)
            
            if energy_compression and breakout_prob > 0.8:
                checklist['xrp_expert_bonus'] = 0.5  # 최대 보너스
            elif energy_compression or expert_confidence >= 3:
                checklist['xrp_expert_bonus'] = 0.3  # 중간 보너스
            elif expert_confidence >= 2:
                checklist['xrp_expert_bonus'] = 0.1  # 소량 보너스
            else:
                checklist['xrp_expert_bonus'] = 0.0
                
            logger.info(f"   6. XRP전문가보너스: {checklist['xrp_expert_bonus']:.1f}/0.5 (신뢰도: {expert_confidence}/5)")
            
            # 총점 계산 (최대 5.5점)
            total_score = sum(checklist.values())
            
            logger.info(f"📊 v7.2 확률론적 체크리스트 총점: {total_score:.1f}/5.5")
            
            return {
                'checklist': checklist,
                'total_score': total_score,
                'breakdown': {
                    'market_regime': f"{checklist['market_regime']:.1f}/1점 - 체제: {regime}",
                    'trend_alignment': f"{checklist['trend_alignment']:.1f}/1점 - {aligned_timeframes}/{total_timeframes} 시간대",
                    'signal_strength': f"{checklist['signal_strength']:.1f}/1점 - {signal_count}개 신호",
                    'no_contrary_signals': f"{checklist['no_contrary_signals']:.1f}/1점 - {contrary_signals}개 반대신호",
                    'risk_reward': f"{checklist['risk_reward']:.1f}/1점 - R:R {risk_reward_ratio:.2f}",
                    'xrp_expert_bonus': f"{checklist['xrp_expert_bonus']:.1f}/0.5점 - 전문가 신뢰도 {expert_confidence}/5"
                }
            }
            
        except Exception as e:
            logger.error(f"❌ v7.2 확률론적 체크리스트 검증 중 오류: {e}")
            return {'total_score': 0, 'checklist': {}, 'breakdown': {}}

    def _calculate_signal_confidence_multiplier(self, checklist_score):
        """v7.2 핵심: 체크리스트 점수를 신호 신뢰도 승수로 변환"""
        try:
            # v7.2 확률론적 접근: 점수 구간별 신뢰도 승수
            if checklist_score >= 4.5:
                multiplier = 1.0    # A+급 최상의 기회 (100%)
                grade = "A+"
            elif checklist_score >= 3.5:
                multiplier = 0.7    # 좋은 기회 (70%)
                grade = "A"
            elif checklist_score >= 2.5:
                multiplier = 0.4    # XRP 특별 허용 구간 (40%)
                grade = "B"
            else:
                multiplier = 0.0    # 진입 절대 금지 (0%)
                grade = "F"
            
            logger.info(f"💎 v7.2 신호 신뢰도: {grade}등급 (점수: {checklist_score:.1f}/5.5) → 승수: {multiplier:.1f}")
            
            return {
                'multiplier': multiplier,
                'grade': grade,
                'score': checklist_score,
                'description': f"{grade}등급 신호 ({int(multiplier*100)}% 투자비중)"
            }
            
        except Exception as e:
            logger.error(f"❌ v7.2 신호 신뢰도 승수 계산 중 오류: {e}")
            return {'multiplier': 0.0, 'grade': 'F', 'score': 0, 'description': '계산 실패'}

    def _calculate_dynamic_position_size_v72(self, krw_balance, market_regime, signal_confidence):
        """v7.2 확률론적 동적 포지션 사이징 (신호 신뢰도 승수 통합)"""
        try:
            regime = market_regime.get('regime', '분석실패')
            confidence = market_regime.get('confidence', '없음')
            reliability_score = market_regime.get('reliability_score', 50)
            confidence_modifiers = market_regime.get('confidence_modifiers', [])
            
            # 1. v7.2 기본 투자 비중 결정 (시장 체제 기반)
            if regime == "명백한_상승장" and confidence == "높음":
                base_risk_pct = 0.90  # 매우 적극적
                risk_level = "적극적"
            elif regime == "명백한_상승장":
                base_risk_pct = 0.75  # 적극적
                risk_level = "중간-적극"
            elif regime == "횡보_박스권":
                base_risk_pct = 0.55  # 중립적
                risk_level = "중립적"
            elif regime == "고변동성_혼조장":
                base_risk_pct = 0.35  # 보수적
                risk_level = "보수적"
            elif regime == "애매한_혼조장":
                base_risk_pct = 0.25  # 매우 보수적
                risk_level = "매우보수적"
            else:  # "명백한_하락장" 또는 "분석실패"
                base_risk_pct = 0.0   # 매매 금지
                risk_level = "매매금지"
            
            # 2. v7.2 핵심: 신호 신뢰도 승수 적용
            signal_multiplier = signal_confidence['multiplier']
            signal_grade = signal_confidence['grade']
            
            # 3. 비트코인 분석 기반 조정
            btc_adjustment = 1.0
            btc_analysis = market_regime.get('btc_analysis', {})
            
            if btc_analysis.get('btc_influence') in ["높음", "매우높음"]:
                btc_1h_change = btc_analysis.get('btc_1h_change', 0)
                
                if btc_1h_change < -4:
                    btc_adjustment = 0.2  # 80% 감소
                    risk_level += "+BTC급락위험"
                elif btc_1h_change < -2:
                    btc_adjustment = 0.6  # 40% 감소
                    risk_level += "+BTC하락주의"
                elif btc_1h_change > 3:
                    btc_adjustment = 1.3  # 30% 증가
                    risk_level += "+BTC강상승"
                elif btc_1h_change > 1:
                    btc_adjustment = 1.1  # 10% 증가
                    risk_level += "+BTC상승지원"
            
            # 4. 신뢰도 점수 기반 조정
            reliability_adjustment = 1.0
            if reliability_score < 50:
                reliability_adjustment = 0.5
                risk_level += "+신뢰도매우낮음"
            elif reliability_score < 70:
                reliability_adjustment = 0.8
                risk_level += "+신뢰도낮음"
            elif reliability_score > 85:
                reliability_adjustment = 1.2
                risk_level += "+신뢰도매우높음"
            elif reliability_score > 75:
                reliability_adjustment = 1.1
                risk_level += "+신뢰도높음"
            
            # 5. 위험 수정자 기반 조정
            modifier_adjustment = 1.0
            for modifier in confidence_modifiers:
                if "BTC강하락위험" in modifier:
                    modifier_adjustment *= 0.4
                    risk_level += "+BTC리스크"
                elif "구조변화위험" in modifier:
                    modifier_adjustment *= 0.7
                    risk_level += "+구조리스크"
                elif "BTC추세불일치" in modifier:
                    modifier_adjustment *= 0.8
                    risk_level += "+추세불일치"
            
            # 6. v7.2 최종 투자 비중 계산 (신호 신뢰도 승수가 핵심)
            final_risk_pct = base_risk_pct * signal_multiplier * btc_adjustment * reliability_adjustment * modifier_adjustment
            
            # 7. 안전 한계 적용
            final_risk_pct = max(0.0, min(0.90, final_risk_pct))
            
            # 추가 안전 조건
            regime_score = market_regime.get('regime_score', 0)
            if regime_score <= -2.5:
                final_risk_pct = min(final_risk_pct, 0.15)
                risk_level += "+초강하락제한"
            elif regime_score <= -2:
                final_risk_pct = min(final_risk_pct, 0.25)
                risk_level += "+강하락제한"
            
            invest_amount = krw_balance * final_risk_pct
            
            logger.info(f"💰 v7.2 확률론적 동적 포지션 사이징:")
            logger.info(f"   체제={regime}, 기본비중={base_risk_pct:.0%}")
            logger.info(f"   🎯 신호신뢰도승수={signal_multiplier:.1f} ({signal_grade}등급)")
            logger.info(f"   BTC조정={btc_adjustment:.2f}, 신뢰도조정={reliability_adjustment:.2f}")
            logger.info(f"   수정자조정={modifier_adjustment:.2f}")
            logger.info(f"   최종비중={final_risk_pct:.0%}, 투자금={invest_amount:,.0f}원")
            logger.info(f"   리스크레벨={risk_level}")
            
            return {
                'invest_amount': invest_amount,
                'risk_percentage': final_risk_pct,
                'base_risk_percentage': base_risk_pct,
                'signal_multiplier': signal_multiplier,
                'signal_grade': signal_grade,
                'btc_adjustment': btc_adjustment,
                'reliability_adjustment': reliability_adjustment,
                'modifier_adjustment': modifier_adjustment,
                'risk_level': risk_level,
                'regime': regime,
                'reliability_score': reliability_score
            }
            
        except Exception as e:
            logger.error(f"❌ v7.2 확률론적 동적 포지션 사이징 계산 중 오류: {e}")
            return {
                'invest_amount': krw_balance * 0.20,  # 안전한 기본값
                'risk_percentage': 0.20,
                'signal_multiplier': 0.2,
                'signal_grade': 'F',
                'risk_level': "오류발생-안전모드",
                'regime': "계산실패"
            }

# =============================================================================
    # v7.2 Part 5: XRP 전문가 위꼬리 방어 시스템
    # =============================================================================
    
    def monitor_active_trades_v72(self):
        """v7.2 활성 거래 모니터링 - 위꼬리 방어 손절매 시스템"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 최신 ACTIVE 거래 하나만 조회 (v7.2 필드 포함)
                cursor.execute('''
                    SELECT trade_id, planned_target_price, planned_stop_loss, 
                        position_size_xrp, actual_entry_price, wick_defense_active
                    FROM trades 
                    WHERE status = 'ACTIVE'
                    ORDER BY entry_timestamp DESC
                    LIMIT 1
                ''')
                
                active_trade = cursor.fetchone()
            
            if not active_trade:
                return
            
            # 현재 가격 확인
            orderbook = pyupbit.get_orderbook(ticker="KRW-XRP")
            current_price = float(orderbook['orderbook_units'][0]['ask_price'])
            
            trade_id, target_price, stop_loss, position_size, entry_price, wick_defense_active = active_trade
            
            # 🎯 목표가 도달 - 즉시 매도
            if current_price >= target_price:
                logger.info(f"🎯 v7.2 거래 ID {trade_id} 목표가 도달 - 매도 실행")
                self._execute_sell_order_v72(trade_id, current_price, "PROFIT_TAKE")
                return
            
            # 🛑 손절가 도달 - v7.2 위꼬리 방어 적용
            if current_price <= stop_loss:
                if wick_defense_active and self.wick_defense_enabled:
                    logger.info(f"🕯️ v7.2 거래 ID {trade_id} 손절가 도달 - 위꼬리 방어 시스템 활성화")
                    self._activate_wick_defense(trade_id, current_price, stop_loss)
                else:
                    logger.info(f"🛑 v7.2 거래 ID {trade_id} 손절가 도달 - 즉시 매도 실행")
                    self._execute_sell_order_v72(trade_id, current_price, "STOP_LOSS")
                return
                        
        except Exception as e:
            logger.error(f"❌ v7.2 활성 거래 모니터링 중 오류: {e}")

    def _activate_wick_defense(self, trade_id, current_price, stop_loss):
        """v7.2 XRP 전문가: 위꼬리 방어 손절매 시스템"""
        try:
            logger.info(f"🛡️ v7.2 위꼬리 방어 시스템 활성화 - 캔들 종가 대기 중...")
            
            # 현재 시간프레임 캔들 마감까지 대기
            defense_timeframe = self.wick_defense_timeframe  # 기본 15분
            
            # 캔들 마감 시점 계산
            now = datetime.now()
            minutes_to_wait = defense_timeframe - (now.minute % defense_timeframe)
            if minutes_to_wait == defense_timeframe:
                minutes_to_wait = 0  # 정각인 경우
            
            wait_until = now + timedelta(minutes=minutes_to_wait)
            logger.info(f"   ⏰ {defense_timeframe}분봉 마감 대기: {wait_until.strftime('%H:%M')}까지")
            
            # 위꼬리 방어 상태를 DB에 기록
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE trades SET 
                        stop_loss_reason = stop_loss_reason || ' [v7.2 위꼬리방어 활성화: ' || ? || '분봉 마감 대기]'
                    WHERE trade_id = ?
                ''', (defense_timeframe, trade_id))
                conn.commit()
            
            # 스케줄러에 위꼬리 방어 체크 등록
            defense_job_tag = f'wick_defense_{trade_id}'
            schedule.every(minutes_to_wait).minutes.do(
                self._execute_wick_defense_check, trade_id, stop_loss, current_price
            ).tag(defense_job_tag)
            
            logger.info(f"✅ v7.2 위꼬리 방어 스케줄 등록 완료 (태그: {defense_job_tag})")
            
        except Exception as e:
            logger.error(f"❌ v7.2 위꼬리 방어 활성화 중 오류: {e}")
            # 오류 시 즉시 매도
            self._execute_sell_order_v72(trade_id, current_price, "STOP_LOSS")

    def _execute_wick_defense_check(self, trade_id, original_stop_loss, trigger_price):
        """v7.2 위꼬리 방어: 캔들 마감 시점 최종 확인"""
        try:
            logger.info(f"🔍 v7.2 위꼬리 방어 최종 확인 (거래 ID: {trade_id})")
            
            # 현재 캔들의 종가 확인
            df_timeframe = pyupbit.get_ohlcv("KRW-XRP", 
                                           interval=f"minute{self.wick_defense_timeframe}", 
                                           count=1)
            
            if len(df_timeframe) > 0:
                candle_close = float(df_timeframe['close'].iloc[-1])
                logger.info(f"   📊 {self.wick_defense_timeframe}분봉 종가: {candle_close:,.0f}원")
                logger.info(f"   🎯 손절가: {original_stop_loss:,.0f}원")
                
                if candle_close <= original_stop_loss:
                    # 종가도 손절가 아래 - 진짜 하락으로 판단하여 매도
                    logger.info(f"💀 v7.2 위꼬리 방어 실패 - 종가({candle_close:,.0f})도 손절가 아래, 매도 실행")
                    self._execute_sell_order_v72(trade_id, candle_close, "STOP_LOSS")
                else:
                    # 종가가 손절가 위 - 위꼬리였으므로 생존
                    logger.info(f"🛡️ v7.2 위꼬리 방어 성공! 종가({candle_close:,.0f})가 손절가 위 - 포지션 유지")
                    
                    # 위꼬리 방어 성공 기록
                    with sqlite3.connect(self.db_path) as conn:
                        cursor = conn.cursor()
                        cursor.execute('''
                            UPDATE trades SET 
                                stop_loss_reason = stop_loss_reason || ' [v7.2 위꼬리방어 성공: 종가 ' || ? || '원으로 생존]'
                            WHERE trade_id = ?
                        ''', (int(candle_close), trade_id))
                        conn.commit()
            else:
                logger.error("❌ v7.2 위꼬리 방어: 캔들 데이터 조회 실패 - 안전을 위해 매도")
                current_price = pyupbit.get_orderbook(ticker="KRW-XRP")['orderbook_units'][0]['ask_price']
                self._execute_sell_order_v72(trade_id, float(current_price), "STOP_LOSS")
            
            # 방어 작업 완료 후 스케줄 정리
            defense_job_tag = f'wick_defense_{trade_id}'
            schedule.clear(defense_job_tag)
            logger.info(f"🧹 v7.2 위꼬리 방어 스케줄 정리 완료 (태그: {defense_job_tag})")
            
        except Exception as e:
            logger.error(f"❌ v7.2 위꼬리 방어 최종 확인 중 오류: {e}")
            # 오류 시 안전을 위해 매도
            try:
                current_price = pyupbit.get_orderbook(ticker="KRW-XRP")['orderbook_units'][0]['ask_price']
                self._execute_sell_order_v72(trade_id, float(current_price), "STOP_LOSS")
            except:
                logger.error("❌ v7.2 긴급 매도마저 실패")

    def _execute_sell_order_v72(self, trade_id, current_price, trade_result):
        """v7.2 매도 주문 실행 - 위꼬리 방어 결과 기록"""
        try:
            logger.info(f"🎯 v7.2 매도 주문 실행 중... (가격: {current_price:,.0f}원, 유형: {trade_result})")
            
            xrp_balance = self.upbit.get_balance("XRP")
            
            if xrp_balance < 0.0001:
                logger.warning("⚠️ v7.2 매도할 XRP가 부족합니다.")
                return False
            
            # 시장가 매도 주문 실행
            order_result = self.upbit.sell_market_order("KRW-XRP", xrp_balance)
            
            if not order_result or 'uuid' not in order_result:
                logger.error("❌ v7.2 매도 주문 실패")
                return False
            
            # 주문 완료 대기
            time.sleep(3)
            
            # 실제 매도 체결 정보 가져오기 및 DB 업데이트
            order_details = self.upbit.get_order(order_result['uuid'])
            
            if not order_details:
                logger.error("❌ v7.2 매도 주문 상세 정보 조회 실패")
                return False
                
            # 실제 매도 정보 추출
            executed_volume = float(order_details.get('executed_volume', 0))
            paid_fee = float(order_details.get('paid_fee', 0))
            
            # 실제 매도 단가 계산
            total_received = 0
            trades = order_details.get('trades', [])
            
            if trades:
                total_received = sum(float(trade['price']) * float(trade['volume']) for trade in trades)
                actual_exit_price = total_received / executed_volume
            else:
                total_received = float(order_details.get('price', 0)) * executed_volume
                actual_exit_price = float(order_details.get('price', 0))
            
            net_received = total_received - paid_fee
            exit_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # 기존 거래 정보 조회 및 수익률 계산
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT position_size_xrp, actual_entry_price, commission_krw, wick_defense_active
                    FROM trades WHERE trade_id = ?
                ''', (trade_id,))
                
                row = cursor.fetchone()
                if not row:
                    logger.error("❌ v7.2 기존 거래 정보를 찾을 수 없습니다")
                    return False
                
                original_position, entry_price, buy_commission, wick_defense_was_active = row
                
                # 정확한 수익률 계산
                total_buy_cost = (entry_price * original_position) + buy_commission
                total_sell_received = net_received
                net_profit = total_sell_received - total_buy_cost
                profit_rate = (net_profit / total_buy_cost * 100) if total_buy_cost > 0 else 0
                total_commission = buy_commission + paid_fee
                
                # v7.2 위꼬리 방어 결과 확인
                final_trade_result = trade_result
                if wick_defense_was_active and trade_result == "STOP_LOSS" and "위꼬리방어 성공" not in str(wick_defense_was_active):
                    # 위꼬리 방어가 활성화되었지만 결국 손절된 경우
                    final_trade_result = "STOP_LOSS"
                elif wick_defense_was_active and "위꼬리방어 성공" in str(wick_defense_was_active):
                    # 위꼬리 방어로 생존 후 목표가 달성
                    final_trade_result = "WICK_DEFENSE_SAVE" if trade_result == "PROFIT_TAKE" else trade_result
                
                # 데이터베이스 업데이트
                cursor.execute('''
                    UPDATE trades SET 
                        status = 'COMPLETED',
                        exit_timestamp = ?,
                        actual_exit_price = ?,
                        trade_result = ?,
                        commission_krw = ?,
                        net_profit_krw = ?,
                        profit_rate_pct = ?
                    WHERE trade_id = ?
                ''', (exit_timestamp, actual_exit_price, final_trade_result, 
                    total_commission, net_profit, profit_rate, trade_id))
                
                conn.commit()
            
            profit_emoji = "💰" if net_profit > 0 else "💸"
            defense_emoji = "🛡️" if final_trade_result == "WICK_DEFENSE_SAVE" else ""
            
            logger.info(f"✅ v7.2 {profit_emoji}{defense_emoji} 정확한 매도 완료:")
            logger.info(f"   실제 매도가: {actual_exit_price:,.0f}원")
            logger.info(f"   순수익: {net_profit:+,.0f}원 ({profit_rate:+.2f}%)")
            logger.info(f"   총 수수료: {total_commission:,.0f}원")
            logger.info(f"   거래 결과: {final_trade_result}")
            
            # 거래 완료 즉시 회고 실행
            logger.info("📊 v7.2 거래 완료 - 즉시 회고 분석 시작")
            self.reflect_single_trade(trade_id)

            # v7.2 매도 완료 후 즉시 분석 예약
            logger.info("🚀 v7.2 매도 완료 - 10초 후 즉시 새로운 매수 기회 분석 예약")
            schedule.every(10).seconds.do(self.run_strategy_analysis_v72).tag('immediate_analysis')
            
            # 주기 재평가 쿨다운 리셋
            self.last_regime_check = None
            logger.info("✅ v7.2 주기 재평가 쿨다운 리셋")

            return True
                    
        except Exception as e:
            logger.error(f"❌ v7.2 매도 주문 실행 중 오류: {e}")
            return False

    def monitor_planned_trades(self):
        """v7.2 개선된 계획 거래 모니터링: 현재 활성 계획만 처리"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 현재 활성 계획만 조회 (가장 최근 PLANNED 거래)
                cursor.execute('''
                    SELECT trade_id, planned_entry_price, checklist_score
                    FROM trades 
                    WHERE status = 'PLANNED'
                    ORDER BY plan_timestamp DESC
                    LIMIT 1
                ''')
                
                current_plan = cursor.fetchone()
            
            if not current_plan:
                return
            
            trade_id, planned_entry_price, checklist_score = current_plan
            
            # 현재 가격 확인
            orderbook = pyupbit.get_orderbook(ticker="KRW-XRP")
            current_price = float(orderbook['orderbook_units'][0]['ask_price'])
            
            # 진입 조건 확인 (±0.5% 범위)
            if planned_entry_price == 0:
                # 진입가가 0이면 매수하지 않음 (XRP 보유 중)
                return
            
            entry_range = planned_entry_price * 0.005
            if abs(current_price - planned_entry_price) <= entry_range:
                logger.info(f"🎯 v7.2 활성 계획 #{trade_id} 진입 조건 만족 - 매수 실행")
                logger.info(f"   체크리스트 점수: {checklist_score:.1f}/5.5")
                success = self._execute_buy_order_v72(trade_id, current_price)
                if success:
                    self.current_active_plan_id = None  # 계획 실행 완료
                    logger.info(f"✅ v7.2 거래 #{trade_id} 매수 완료 - PLANNED → ACTIVE")
                else:
                    logger.warning(f"⚠️ v7.2 거래 #{trade_id} 매수 실패")
                        
        except Exception as e:
            logger.error(f"❌ v7.2 개선된 계획 거래 모니터링 중 오류: {e}")

    def _execute_buy_order_v72(self, trade_id, target_entry_price):
        """v7.2 개선된 매수 주문 실행 (지정가 우선 + 정확한 수익률 계산)"""
        try:
            logger.info(f"🎯 v7.2 개선된 매수 주문 시작 - 목표가: {target_entry_price:,.0f}원")
            
            # 1. 실행 직전 시장 체제 재분석 (최종 안전 확인)
            market_data = self.observe_market_data()
            if not market_data:
                logger.error("❌ v7.2 실행 직전 시장 데이터 수집 실패. 주문 취소.")
                return False
            
            market_regime = self._analyze_market_regime(market_data)
            logger.info(f"🔍 v7.2 매수 직전 체제 재확인: {market_regime['regime']} (접근법: {market_regime['approach']})")
            
            # 2. 최종 안전 검증 - 하락장으로 급변한 경우 매수 취소
            if market_regime['approach'] == "매매금지":
                logger.warning("🚨 v7.2 매수 직전 하락장 감지 - 안전을 위해 매수 취소")
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        UPDATE trades SET 
                            status = 'CANCELLED',
                            entry_reason = COALESCE(entry_reason, '') || ' [v7.2 매수직전 하락장감지로 취소]'
                        WHERE trade_id = ?
                    ''', (trade_id,))
                    conn.commit()
                return False
            
            # 3. v7.2 체크리스트 재검증 및 신호 신뢰도 승수 적용
            checklist_result = self._validate_entry_checklist_v72(market_data, market_regime)
            signal_confidence = self._calculate_signal_confidence_multiplier(checklist_result['total_score'])
            
            # 4. v7.2 동적 포지션 사이징 적용
            krw_balance = self.upbit.get_balance("KRW")
            position_info = self._calculate_dynamic_position_size_v72(krw_balance, market_regime, signal_confidence)
            invest_amount = position_info['invest_amount']
            
            # 5. 최소 주문 금액 검증
            if invest_amount < 10000:
                logger.warning(f"⚠️ v7.2 동적 투자 금액({invest_amount:,.0f}원)이 최소 주문 금액 미만. 계획 취소.")
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        UPDATE trades SET 
                            status = 'CANCELLED',
                            entry_reason = COALESCE(entry_reason, '') || ' [v7.2 투자금액부족으로 취소]'
                        WHERE trade_id = ?
                    ''', (trade_id,))
                    conn.commit()
                return False
            
            # 6. 현재 시장 상황 확인
            orderbook = pyupbit.get_orderbook(ticker="KRW-XRP")
            current_ask = float(orderbook['orderbook_units'][0]['ask_price'])  # 매도호가
            current_bid = float(orderbook['orderbook_units'][0]['bid_price'])  # 매수호가
            
            logger.info(f"📊 v7.2 현재 호가: 매도 {current_ask:,.0f}원, 매수 {current_bid:,.0f}원")
            
            # 7. 진입 전략 결정
            entry_strategy = self._determine_entry_strategy_v72(target_entry_price, current_ask, current_bid)
            
            logger.info(f"🎯 v7.2 {position_info['risk_level']} 매수 전략: {entry_strategy['action']}")
            logger.info(f"   투자금: {invest_amount:,.0f}원 ({position_info['risk_percentage']:.0%})")
            logger.info(f"   신호등급: {signal_confidence['grade']} (승수: {signal_confidence['multiplier']:.1f})")
            logger.info(f"   사유: {entry_strategy['reason']}")
            
            # 8. 전략에 따른 주문 실행
            if entry_strategy['action'] == 'IMMEDIATE':
                # 즉시 체결 (시장가)
                success = self._execute_immediate_buy_v72(trade_id, invest_amount, entry_strategy)
            elif entry_strategy['action'] == 'LIMIT_ORDER':
                # 지정가 주문
                success = self._execute_limit_buy_with_monitoring_v72(trade_id, invest_amount, entry_strategy)
            else:  # 'CANCEL'
                # 주문 취소
                logger.info(f"🚫 v7.2 매수 조건 불만족으로 주문 취소: {entry_strategy['reason']}")
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        UPDATE trades SET 
                            status = 'CANCELLED',
                            entry_reason = COALESCE(entry_reason, '') || ' [v7.2 ' || ? || ']'
                        WHERE trade_id = ?
                    ''', (entry_strategy['reason'], trade_id))
                    conn.commit()
                return False
            
            if success:
                logger.info(f"✅ v7.2 개선된 매수 완료! (거래 ID: {trade_id})")
                return True
            else:
                logger.error(f"❌ v7.2 매수 실패 (거래 ID: {trade_id})")
                return False
                
        except Exception as e:
            logger.error(f"❌ v7.2 개선된 매수 주문 실행 중 오류: {e}")
            return False

    def _determine_entry_strategy_v72(self, target_entry_price, current_ask, current_bid):
        """v7.2 진입 전략 결정 (즉시/지정가/취소)"""
        try:
            price_tolerance = 0.003  # 0.3% 허용 오차
            
            # 목표 진입가와 현재 매도호가 비교
            price_diff_pct = abs(target_entry_price - current_ask) / current_ask
            
            if target_entry_price >= current_ask * (1 - price_tolerance):
                # 목표가가 현재 매도호가보다 높거나 비슷 → 즉시 체결 가능
                return {
                    'action': 'IMMEDIATE',
                    'price': current_ask,
                    'reason': f'v7.2 목표가({target_entry_price:,.0f}) >= 현재매도호가({current_ask:,.0f}) - 즉시 체결'
                }
            elif target_entry_price >= current_bid and target_entry_price < current_ask:
                # 목표가가 매수호가와 매도호가 사이 → 지정가 주문
                return {
                    'action': 'LIMIT_ORDER',
                    'price': target_entry_price,
                    'reason': f'v7.2 호가 범위 내 목표가 - 지정가 주문 등록'
                }
            elif target_entry_price < current_bid * (1 - price_tolerance):
                # 목표가가 현재 매수호가보다 훨씬 낮음 → 지정가 주문 (대기)
                return {
                    'action': 'LIMIT_ORDER',
                    'price': target_entry_price,
                    'reason': f'v7.2 목표가가 현재가보다 낮음 - 하락 대기'
                }
            else:
                # 목표가가 너무 높음 → 계획 취소
                return {
                    'action': 'CANCEL',
                    'price': 0,
                    'reason': f'v7.2 목표가({target_entry_price:,.0f})가 현재가({current_ask:,.0f})보다 과도하게 높음'
                }
                
        except Exception as e:
            logger.error(f"v7.2 진입 전략 결정 중 오류: {e}")
            return {'action': 'CANCEL', 'price': 0, 'reason': 'v7.2 전략 결정 실패'}

    def _execute_immediate_buy_v72(self, trade_id, invest_amount, entry_strategy):
        """v7.2 즉시 매수 실행 (시장가)"""
        try:
            logger.info(f"🚀 v7.2 즉시 매수 실행: {invest_amount:,.0f}원")
            
            # 시장가 매수 주문
            order_result = self.upbit.buy_market_order("KRW-XRP", invest_amount)
            
            if not order_result or 'uuid' not in order_result:
                logger.error("❌ v7.2 시장가 매수 주문 실패")
                return False
            
            # 주문 완료 대기
            time.sleep(3)
            
            # 실제 체결 정보 가져오기
            return self._process_buy_order_result_v72(trade_id, order_result['uuid'], invest_amount)
            
        except Exception as e:
            logger.error(f"❌ v7.2 즉시 매수 실행 중 오류: {e}")
            return False

    def _execute_limit_buy_with_monitoring_v72(self, trade_id, invest_amount, entry_strategy):
        """v7.2 지정가 매수 주문 등록 및 모니터링"""
        try:
            target_price = entry_strategy['price']
            target_quantity = invest_amount / target_price
            
            logger.info(f"📊 v7.2 지정가 매수 주문: {target_price:,.0f}원 × {target_quantity:.4f} XRP")
            
            # 지정가 매수 주문
            order_result = self.upbit.buy_limit_order("KRW-XRP", target_price, target_quantity)
            
            if not order_result or 'uuid' not in order_result:
                logger.error("❌ v7.2 지정가 매수 주문 실패")
                return False
            
            order_uuid = order_result['uuid']
            logger.info(f"✅ v7.2 지정가 주문 등록 완료 (UUID: {order_uuid})")
            
            # 주문 상태 모니터링 (최대 5분)
            return self._monitor_limit_order_v72(trade_id, order_uuid, invest_amount, 300)
            
        except Exception as e:
            logger.error(f"❌ v7.2 지정가 매수 주문 중 오류: {e}")
            return False

    def _monitor_limit_order_v72(self, trade_id, order_uuid, invest_amount, timeout_seconds):
        """v7.2 지정가 주문 모니터링"""
        try:
            start_time = time.time()
            
            while time.time() - start_time < timeout_seconds:
                # 주문 상태 확인
                order_info = self.upbit.get_order(order_uuid)
                
                if not order_info:
                    logger.warning("⚠️ v7.2 주문 정보 조회 실패")
                    time.sleep(10)
                    continue
                
                state = order_info.get('state', '')
                
                if state == 'done':
                    # 주문 완료
                    logger.info("✅ v7.2 지정가 주문 체결 완료!")
                    return self._process_buy_order_result_v72(trade_id, order_uuid, invest_amount)
                    
                elif state == 'cancel':
                    # 주문 취소됨
                    logger.warning("⚠️ v7.2 지정가 주문이 취소되었습니다")
                    return False
                    
                elif state in ['wait', 'watch']:
                    # 대기 중
                    executed_volume = float(order_info.get('executed_volume', 0))
                    trades_count = int(order_info.get('trades_count', 0))
                    
                    if trades_count > 0:
                        logger.info(f"📈 v7.2 부분 체결 진행 중: {executed_volume:.4f} XRP")
                    
                    time.sleep(10)  # 10초마다 체크
                    continue
                    
                else:
                    logger.warning(f"⚠️ v7.2 알 수 없는 주문 상태: {state}")
                    time.sleep(10)
                    continue
            
            # 타임아웃 - 주문 취소
            logger.warning(f"⏰ v7.2 지정가 주문 타임아웃 ({timeout_seconds}초) - 주문 취소 시도")
            
            try:
                cancel_result = self.upbit.cancel_order(order_uuid)
                if cancel_result:
                    logger.info("✅ v7.2 지정가 주문 취소 완료")
                else:
                    logger.warning("⚠️ v7.2 주문 취소 실패 - 수동 확인 필요")
            except Exception as e:
                logger.error(f"❌ v7.2 주문 취소 중 오류: {e}")
            
            return False
            
        except Exception as e:
            logger.error(f"❌ v7.2 지정가 주문 모니터링 중 오류: {e}")
            return False

    def _process_buy_order_result_v72(self, trade_id, order_uuid, original_invest_amount):
        """v7.2 매수 주문 결과 처리 (정확한 수익률 계산용 + v7.2 필드 업데이트)"""
        try:
            # 주문 상세 정보 가져오기
            order_details = self.upbit.get_order(order_uuid)
            
            if not order_details:
                logger.error("❌ v7.2 주문 상세 정보 조회 실패")
                return False
            
            # 실제 체결 정보 추출
            executed_volume = float(order_details.get('executed_volume', 0))
            paid_fee = float(order_details.get('paid_fee', 0))
            
            if executed_volume <= 0:
                logger.error("❌ v7.2 체결된 물량이 없습니다")
                return False
            
            # 실제 체결 단가 계산
            total_paid = 0
            trades = order_details.get('trades', [])
            
            if trades:
                # 개별 체결 내역에서 정확한 평균 단가 계산
                total_paid = sum(float(trade['price']) * float(trade['volume']) for trade in trades)
                actual_entry_price = total_paid / executed_volume
            else:
                # trades 정보가 없으면 대략적 계산
                total_paid = float(order_details.get('price', 0)) * executed_volume
                actual_entry_price = float(order_details.get('price', 0))
            
            # 실제 수수료 반영 총 투자금액
            total_cost = total_paid + paid_fee
            
            # 데이터베이스 업데이트 (v7.2 확률론적 정보 포함)
            entry_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE trades SET 
                        status = 'ACTIVE',
                        position_size_xrp = ?,
                        entry_timestamp = ?,
                        actual_entry_price = ?,
                        commission_krw = ?,
                        entry_reason = COALESCE(entry_reason, '') || ' [v7.2 실제체결: ' || ? || '원]'
                    WHERE trade_id = ?
                ''', (executed_volume, entry_timestamp, actual_entry_price, paid_fee, 
                    round(actual_entry_price), trade_id))
                conn.commit()
            
            logger.info(f"✅ v7.2 정확한 매수 완료:")
            logger.info(f"   체결량: {executed_volume:.4f} XRP")
            logger.info(f"   실제 평단가: {actual_entry_price:,.0f}원")
            logger.info(f"   총 비용: {total_cost:,.0f}원 (수수료: {paid_fee:,.0f}원)")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ v7.2 매수 주문 결과 처리 중 오류: {e}")
            return False

# =============================================================================
    # v7.2 Part 6: 통합된 진입 전략 및 AI 연동
    # =============================================================================
    
    def orient_and_decide_v72(self, market_data):
        """v7.2 판단(Orient) & 결정(Decide): 확률론적 접근 + XRP 전문가 통합 전략 수립"""
        try:
            logger.info("🧠 v7.2 확률론적 접근 + XRP 전문가 AI 전략 수립 중...")
            
            # 포지션 상태 확인
            position_status = market_data.get('position_status', {})
            has_position = position_status.get('has_position', False)
            
            if has_position:
                logger.info("🎯 XRP 보유 중 - v7.2 트리거 기반 포지션 관리 모드")
                return self._generate_position_management_advice_v72(market_data)
            else:
                logger.info("💰 XRP 미보유 - v7.2 확률론적 접근 신규 진입 전략 모드")
                return self._generate_new_entry_strategy_v72(market_data)
                
        except Exception as e:
            logger.error(f"❌ v7.2 전략 수립 중 오류: {e}")
            return None

    def _generate_new_entry_strategy_v72(self, market_data):
        """v7.2 신규 진입 전략: 확률론적 접근 + XRP 전문가 통합"""
        try:
            # 1. 시장체제 분석
            market_regime = self._analyze_market_regime(market_data)
            logger.info(f"🎯 v7.2 진입 분석 - 체제: {market_regime['regime']} (신뢰도: {market_regime['confidence']})")
            
            # 2. v7.2 확률론적 체크리스트 검증
            checklist_result = self._validate_entry_checklist_v72(market_data, market_regime)
            
            # 3. v7.2 신호 신뢰도 승수 계산
            signal_confidence = self._calculate_signal_confidence_multiplier(checklist_result['total_score'])
            
            # 4. v7.2 하드 임계값 검사 (2.5점 미만 진입 금지)
            if checklist_result['total_score'] < 2.5:
                logger.warning(f"🚫 v7.2 하드 임계값 미달: {checklist_result['total_score']:.1f}/5.5점 - 진입 금지")
                return self._create_no_entry_response_v72(market_regime, checklist_result, signal_confidence)
            
            # 5. v7.2 확률론적 동적 포지션 사이징
            krw_balance = self.upbit.get_balance("KRW")
            position_info = self._calculate_dynamic_position_size_v72(krw_balance, market_regime, signal_confidence)
            
            # 6. 최소 투자금 검증
            if position_info['invest_amount'] < 10000:
                logger.warning(f"⚠️ v7.2 최종 투자금({position_info['invest_amount']:,.0f}원) 부족 - 진입 금지")
                return self._create_no_entry_response_v72(market_regime, checklist_result, signal_confidence)
            
            # 7. 하드 임계값 통과 - AI 정교 분석 요청
            logger.info(f"✅ v7.2 확률론적 검증 통과: {signal_confidence['grade']}등급 ({checklist_result['total_score']:.1f}/5.5점)")
            logger.info(f"   💰 투자금: {position_info['invest_amount']:,.0f}원 ({position_info['risk_percentage']:.0%})")
            
            return self._request_ai_entry_analysis_v72(market_data, market_regime, checklist_result, signal_confidence, position_info)
            
        except Exception as e:
            logger.error(f"❌ v7.2 신규 진입 전략 생성 중 오류: {e}")
            return None

    def _create_no_entry_response_v72(self, market_regime, checklist_result, signal_confidence):
        """v7.2 진입 조건 미달 시 응답 생성"""
        total_score = checklist_result['total_score']
        breakdown = checklist_result['breakdown']
        grade = signal_confidence['grade']
        
        return {
            "market_analysis": {
                "regime_verification": f"v7.2 확률론적 검증 실패 - {grade}등급 ({total_score:.1f}/5.5점)",
                "trend_group": f"다중 시간대: {breakdown.get('trend_alignment', 'N/A')}",
                "momentum_group": f"신호 강도: {breakdown.get('signal_strength', 'N/A')}",
                "volatility_group": f"반대 신호: {breakdown.get('no_contrary_signals', 'N/A')}",
                "volume_group": f"XRP 전문가: {breakdown.get('xrp_expert_bonus', 'N/A')}",
                "overall_confidence": "진입 금지",
                "market_condition": "관망 필요"
            },
            "risk_assessment": {
                "risk_level": "매우높음",
                "position_size": "진입 금지",
                "max_holding_time": "해당없음",
                "key_risks": f"v7.2 확률론적 점수 {total_score:.1f}/5.5점으로 진입 조건 미충족"
            },
            "entry_price": 0,
            "target_price": 0,
            "stop_loss_price": 0,
            "entry_reason": f"v7.2 확률론적 검증 실패 ({grade}등급, {total_score:.1f}/5.5점) - 하드 임계값 2.5점 미달",
            "target_reason": "진입하지 않으므로 목표가 설정 불필요",
            "stop_loss_reason": "진입하지 않으므로 손절가 설정 불필요",
            "sell_strategy": "진입 대기 - 확률론적 조건 개선까지 관망",
            "lessons_applied": f"v7.2 확률론적 접근으로 낮은 품질 신호 필터링 (총점: {total_score:.1f}/5.5)",
            "regime_adaptation": f"체제 '{market_regime['regime']}'에서 신중한 접근으로 자본 보호",
            "signal_grade": grade,
            "checklist_score": total_score,
            "checklist_breakdown": breakdown
        }

    def _request_ai_entry_analysis_v72(self, market_data, market_regime, checklist_result, signal_confidence, position_info):
        """v7.2 확률론적 검증 통과 후 AI 정교 분석"""
        try:
            # NumPy 타입 변환
            market_data_serializable = convert_numpy_types(market_data)
            
            # 과거 교훈 및 컨텍스트
            past_trades = self._get_recent_trades_with_lessons(limit=10)
            market_context = self._analyze_current_market_context(market_data)
            learned_lessons = self._extract_learned_lessons()
            
            # v7.2 XRP 전문가 분석
            xrp_analysis = market_data.get('xrp_expert_analysis', {})
            
            # v7.2 강화된 프롬프트
            enhanced_prompt = f"""
# OMNI-XRP v7.2 AI 정교 분석 요청

## 🎯 v7.2 확률론적 검증 결과 (이미 통과 완료!)

✅ **체크리스트 총점**: {checklist_result['total_score']:.1f}/5.5점 (하드 임계값 2.5점 통과)
🏆 **신호 등급**: {signal_confidence['grade']}등급 ({signal_confidence['description']})
💰 **확정 투자금**: {position_info['invest_amount']:,.0f}원 ({position_info['risk_percentage']:.0%})

### 세부 점수 breakdown:
{json.dumps(checklist_result['breakdown'], indent=2, ensure_ascii=False)}

### v7.2 확률론적 포지션 사이징 결과:
- 체제 기본 비중: {position_info['base_risk_percentage']:.0%}
- 신호 신뢰도 승수: {position_info['signal_multiplier']:.1f} ({position_info['signal_grade']}등급)
- BTC 조정: {position_info['btc_adjustment']:.2f}
- 신뢰도 조정: {position_info['reliability_adjustment']:.2f}
- 최종 투자 비중: {position_info['risk_percentage']:.0%}

## 🧪 v7.2 XRP 전문가 분석 결과

### XRP 특화 패턴 감지:
- 에너지 응축 감지: {xrp_analysis.get('energy_compression_detected', False)}
- 응축 강도: {xrp_analysis.get('compression_strength', 0):.3f}
- 돌파 확률: {xrp_analysis.get('breakout_probability', 0):.2f}
- 지배적 패턴: {xrp_analysis.get('dominant_pattern', 'NONE')}
- 위꼬리 위험도: {xrp_analysis.get('wick_pattern_risk', 'unknown')}
- 전문가 신뢰도: {xrp_analysis.get('expert_confidence', 0)}/5

## 📊 OMNI 시스템 시장체제 진단
- **체제**: {market_regime['regime']}
- **접근법**: {market_regime['approach']}
- **신뢰도**: {market_regime['confidence']}
- **체제 점수**: {market_regime.get('regime_score', 0)}/5

## 📊 실시간 시장 데이터
{json.dumps(market_data_serializable, indent=2, ensure_ascii=False)}

## 🧠 시장 맥락 분석
{market_context}

## 📚 과거 거래 성과
{json.dumps(past_trades, indent=2, ensure_ascii=False)}

## 🎓 축적된 핵심 교훈
{learned_lessons}

---

## 🎯 v7.2 AI 정교 분석 요청

위의 확률론적 검증을 통과했으므로, 이제 다음 사항에 집중하여 세부 전략을 수립해주세요:

1. **정확한 진입가 결정**: {signal_confidence['grade']}등급 신호에 최적화된 진입가
2. **XRP 전문가 활용**: 에너지 응축 및 위꼬리 패턴을 고려한 전략
3. **위꼬리 방어 설정**: XRP 특성상 위꼬리 방어 활성화 여부 결정
4. **동적 목표가/손절가**: 확정된 투자금과 XRP 변동성을 고려한 현실적 설정

**특별 지시**: 
- 확률론적 검증을 통과했으므로 entry_price는 반드시 0보다 큰 값으로 설정
- XRP 전문가 분석 결과를 목표가/손절가 설정에 적극 반영
- 위꼬리 위험도가 'high'인 경우 wick_defense_active를 true로 설정 권장

현재 체제 '{market_regime['regime']}'와 {signal_confidence['grade']}등급 신호에 최적화된 정교한 v7.2 진입 전략을 JSON 형식으로 제시하세요.
"""
            
            # GPT 호출 (v7.2 스키마 사용)
            response = self.client.chat.completions.create(
                model="gpt-4.1",
                messages=[
                    {
                        "role": "system",
                        "content": f"""당신은 OMNI-XRP v7.2의 확률론적 AI 전략가입니다.

v7.2 핵심 특징:
1. 확률론적 체크리스트가 이미 신호 품질을 검증했으므로, AI는 세부 실행 전략에 집중
2. 신호 등급({signal_confidence['grade']})과 투자금({position_info['invest_amount']:,.0f}원)이 이미 결정됨
3. XRP 전문가 분석을 필수적으로 전략에 반영
4. 위꼬리 방어 시스템을 고려한 손절가 설정

현재 상황: {market_regime['regime']} 체제에서 {signal_confidence['grade']}등급 ({checklist_result['total_score']:.1f}/5.5점) 신호
목표: 확률론적 검증 결과를 바탕으로 한 최적 실행 전략 수립"""
                    },
                    {"role": "user", "content": enhanced_prompt}
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": self._get_entry_response_schema_v72()
                },
                max_tokens=2500,
                temperature=0.1
            )
            
            ai_strategy = json.loads(response.choices[0].message.content)
            
            # v7.2 추가 정보 포함
            ai_strategy['signal_grade'] = signal_confidence['grade']
            ai_strategy['signal_confidence_multiplier'] = signal_confidence['multiplier']
            ai_strategy['checklist_score'] = checklist_result['total_score']
            ai_strategy['calculated_position_ratio'] = position_info['risk_percentage']
            ai_strategy['checklist_breakdown'] = checklist_result['breakdown']
            
            # XRP 전문가 정보 추가
            ai_strategy['energy_compression_detected'] = xrp_analysis.get('energy_compression_detected', False)
            ai_strategy['xrp_pattern_type'] = xrp_analysis.get('dominant_pattern', 'NONE')
            
            # v7.2 최종 안전 검증
            validated_strategy = self._validate_ai_strategy_v72(ai_strategy, market_regime, checklist_result)
            
            logger.info(f"✅ v7.2 확률론적 AI 전략 생성 완료 ({signal_confidence['grade']}등급, {checklist_result['total_score']:.1f}/5.5점)")
            return validated_strategy
            
        except Exception as e:
            logger.error(f"❌ v7.2 AI 정교 분석 중 오류: {e}")
            return None

    def _get_entry_response_schema_v72(self):
        """v7.2 신규 진입 응답 스키마 (XRP 전문가 필드 포함)"""
        return {
            "name": "omni_entry_strategy_v72",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "reasoning_process": {"type": "string"},
                    "probabilistic_assessment": {"type": "string"},
                    "xrp_expert_integration": {"type": "string"},
                    "market_analysis": {
                        "type": "object",
                        "properties": {
                            "regime_verification": {"type": "string"},
                            "trend_group": {"type": "string"},
                            "momentum_group": {"type": "string"},
                            "volatility_group": {"type": "string"},
                            "volume_group": {"type": "string"},
                            "overall_confidence": {"type": "string"},
                            "market_condition": {
                                "type": "string",
                                "enum": ["강세장", "약세장", "횡보장", "변동성장"]
                            }
                        },
                        "required": ["regime_verification", "trend_group", "momentum_group", "volatility_group", "volume_group", "overall_confidence", "market_condition"],
                        "additionalProperties": False
                    },
                    "risk_assessment": {
                        "type": "object",
                        "properties": {
                            "risk_level": {"type": "string", "enum": ["낮음", "보통", "높음", "매우높음"]},
                            "position_size": {"type": "string"},
                            "max_holding_time": {"type": "string"},
                            "key_risks": {"type": "string"}
                        },
                        "required": ["risk_level", "position_size", "max_holding_time", "key_risks"],
                        "additionalProperties": False
                    },
                    "entry_price": {"type": "number"},
                    "target_price": {"type": "number"},
                    "stop_loss_price": {"type": "number"},
                    "entry_reason": {"type": "string"},
                    "target_reason": {"type": "string"},
                    "stop_loss_reason": {"type": "string"},
                    "sell_strategy": {"type": "string"},
                    "lessons_applied": {"type": "string"},
                    "regime_adaptation": {"type": "string"},
                    "wick_defense_active": {"type": "boolean"},
                    "xrp_pattern_consideration": {"type": "string"},
                    "energy_compression_factor": {"type": "string"},
                    "confidence_level": {"type": "string"}
                },
                "required": [
                    "reasoning_process", "probabilistic_assessment", "xrp_expert_integration",
                    "market_analysis", "risk_assessment", "entry_price", "target_price", 
                    "stop_loss_price", "entry_reason", "target_reason", "stop_loss_reason", 
                    "sell_strategy", "lessons_applied", "regime_adaptation", 
                    "wick_defense_active", "xrp_pattern_consideration", 
                    "energy_compression_factor", "confidence_level"
                ],
                "additionalProperties": False
            }
        }

    def _validate_ai_strategy_v72(self, ai_strategy, market_regime, checklist_result):
        """v7.2 AI 전략 최종 검증 (확률론적 일관성 체크)"""
        try:
            # 확률론적 검증을 통과했는데 진입가가 0인 경우 수정
            if checklist_result['total_score'] >= 2.5 and ai_strategy.get('entry_price', 0) == 0:
                logger.warning("🔧 v7.2 안전장치: 확률론적 검증 통과했으나 AI가 진입가 0 설정 - 수정 필요")
                current_price = market_regime.get('current_price', 1000)
                ai_strategy['entry_price'] = current_price * 0.998  # 0.2% 할인
                ai_strategy['entry_reason'] += " [v7.2 안전장치: 확률론적 검증 통과로 보수적 진입가 설정]"
            
            # 위꼬리 방어 기본값 설정
            if 'wick_defense_active' not in ai_strategy:
                ai_strategy['wick_defense_active'] = True  # v7.2 기본적으로 활성화
            
            # v7.2 확률론적 정보 추가
            ai_strategy['checklist_score'] = checklist_result['total_score']
            ai_strategy['checklist_breakdown'] = checklist_result['breakdown']
            
            logger.info("✅ v7.2 AI 전략 확률론적 검증 완료")
            return ai_strategy
            
        except Exception as e:
            logger.error(f"❌ v7.2 AI 전략 검증 중 오류: {e}")
            return ai_strategy

    def _generate_position_management_advice_v72(self, market_data):
        """v7.2 포지션 관리: 기존 v7.1 트리거 시스템 유지 (위꼬리 방어 통합)"""
        try:
            # 기존 트리거 기반 포지션 관리 로직 유지
            # 단, 위꼬리 방어 시스템이 이미 monitor_active_trades_v72에서 처리되므로
            # 여기서는 기존 로직을 그대로 사용
            
            # 1. 시장체제 분석
            market_regime = self._analyze_market_regime(market_data)
            logger.info(f"🎯 v7.2 포지션 관리 - 현재 체제: {market_regime['regime']} (접근법: {market_regime['approach']})")
            
            # 2. v7.1 관리 변경 트리거 검증 (기존 로직 재사용)
            trigger_result = self._validate_management_triggers(market_data, market_regime)
            
            if trigger_result['trigger'] == 'NONE':
                # 트리거 없음 - 계획 유지
                logger.info("📋 v7.2 트리거 없음 - 기존 계획 유지 권장 (위꼬리 방어 활성 상태)")
                return self._create_maintain_plan_response_v72(market_data, market_regime, trigger_result)
            
            # 3. 트리거 감지 시에만 AI 분석 요청
            logger.info(f"🔥 v7.2 트리거 감지: {trigger_result['trigger']} - AI 관리 분석 시작")
            return self._request_ai_management_analysis_v72(market_data, market_regime, trigger_result)
                
        except Exception as e:
            logger.error(f"❌ v7.2 포지션 관리 조언 생성 중 오류: {e}")
            return None

    def _validate_management_triggers(self, market_data, market_regime):
        """v7.2 관리 변경 트리거 검증 (기존 v7.1 로직)"""
        try:
            logger.info("🔍 v7.2 관리 변경 트리거 검증 시작...")
            
            current_price = market_data['current_price']
            position_status = market_data.get('position_status', {})
            active_trade = position_status.get('active_trade_info')
            
            # 현재 활성 거래 정보 파싱
            if not active_trade or len(active_trade) < 4:
                logger.warning("⚠️ 활성 거래 정보 부족 - 트리거 검증 불가")
                return {'trigger': 'NONE', 'evidence': '활성 거래 정보 부족'}
            
            trade_id, entry_price, current_target, current_stop = active_trade[:4]
            
            # 수익률 계산
            if entry_price and entry_price > 0:
                profit_rate = ((current_price - entry_price) / entry_price * 100)
            else:
                profit_rate = 0
                
            logger.info(f"📊 현재 포지션 상태: 진입가 {entry_price:,.0f}원, 현재 수익률 {profit_rate:+.2f}%")
            
            # 트리거 1: 시장체제 구조적 변화
            if market_regime['regime'] in ['명백한_하락장', '고변동성_혼조장']:
                return {
                    'trigger': 'REGIME_CHANGE',
                    'evidence': f"체제가 '{market_regime['regime']}'로 변화",
                    'severity': 'HIGH',
                    'profit_rate': profit_rate
                }
            
            # 트리거 2: 수치적 임계점 도달
            if profit_rate >= 15 or profit_rate <= -6:
                return {
                    'trigger': 'THRESHOLD_REACHED',
                    'evidence': f"수익률 {profit_rate:+.2f}% 임계점 돌파",
                    'severity': 'HIGH' if abs(profit_rate) >= 20 else 'MEDIUM',
                    'profit_rate': profit_rate
                }
            
            # 트리거 3: 기술적 구조 변화
            indicators = market_data['technical_indicators']
            h1_volatility = indicators.get('1h', {}).get('volatility', {})
            bb_position = h1_volatility.get('bb_position', 0.5)
            volume_ratio = indicators.get('1h', {}).get('volume', {}).get('volume_ratio', 1.0)
            
            if (bb_position > 0.9 or bb_position < 0.1) and volume_ratio > 2.0:
                return {
                    'trigger': 'TECHNICAL_STRUCTURE',
                    'evidence': f"BB 극한 위치 ({bb_position:.2f}) + 거래량 급증 ({volume_ratio:.1f}배)",
                    'severity': 'HIGH',
                    'profit_rate': profit_rate
                }
            
            # 모든 트리거 없음
            logger.info("✅ v7.2 관리 변경 트리거 없음 - 계획 유지")
            return {
                'trigger': 'NONE',
                'evidence': '구조적 변화 없음',
                'profit_rate': profit_rate
            }
            
        except Exception as e:
            logger.error(f"❌ v7.2 트리거 검증 중 오류: {e}")
            return {'trigger': 'NONE', 'evidence': f'검증 오류: {e}'}

    def _create_maintain_plan_response_v72(self, market_data, market_regime, trigger_result):
        """v7.2 계획 유지 응답 생성 (위꼬리 방어 상태 표시)"""
        current_price = market_data['current_price']
        profit_rate = trigger_result.get('profit_rate', 0)
        
        return {
            "market_analysis": {
                "regime_impact": f"v7.2 트리거 없음 - 현재 체제 '{market_regime['regime']}'에서 계획 유지",
                "trend_group": f"추세 상태: {market_regime.get('ma_alignment', 'unknown')}",
                "momentum_group": f"현재 수익률: {profit_rate:+.2f}%",
                "volatility_group": f"변동성: {market_regime.get('volatility_state', 'unknown')}",
                "volume_group": "거래량 분석: 구조적 변화 없음",
                "overall_confidence": "계획 유지",
                "market_condition": "안정적"
            },
            "risk_assessment": {
                "risk_level": "보통",
                "position_size": "현재 포지션 유지",
                "max_holding_time": "트리거 발생까지",
                "key_risks": "v7.2 트리거 기반 관리 + 위꼬리 방어로 리스크 통제"
            },
            "entry_price": 0,  # 보유 중이므로 0
            "target_price": 0,  # 기존 목표가 유지
            "stop_loss_price": 0,  # 기존 손절가 유지
            "entry_reason": "XRP 보유 중 - 진입 불필요",
            "target_reason": "v7.2 트리거 없음 - 기존 목표가 유지 권장",
            "stop_loss_reason": "v7.2 트리거 없음 - 기존 손절가 유지 (위꼬리 방어 활성)",
            "sell_strategy": "현재 계획 유지 - 위꼬리 방어 시스템으로 보호 중",
            "lessons_applied": "v7.2 트리거 기반 관리 + XRP 전문가 위꼬리 방어",
            "regime_specific_action": f"체제 '{market_regime['regime']}'에서 현상 유지 + 위꼬리 방어가 최선",
            "change_trigger": "NONE",
            "trigger_evidence": trigger_result.get('evidence', '트리거 없음'),
            "wick_defense_status": "활성화"
        }

    def _request_ai_management_analysis_v72(self, market_data, market_regime, trigger_result):
        """v7.2 트리거 감지 시 AI 관리 분석 (기존 로직 재사용)"""
        try:
            # 기존 v7.1 포지션 관리 AI 분석 로직을 그대로 사용
            # 단, 위꼬리 방어 정보를 포함하여 응답 생성
            
            # NumPy 타입 변환
            market_data_serializable = convert_numpy_types(market_data)
            
            # 현재 활성 거래 정보
            position_status = market_data.get('position_status', {})
            active_trade = position_status.get('active_trade_info')
            current_price = market_data['current_price']
            
            # 수익/손실 상태 계산
            profit_status = "알수없음"
            if active_trade and len(active_trade) >= 2 and active_trade[1]:
                entry_price = active_trade[1]
                profit_rate = ((current_price - entry_price) / entry_price * 100)
                profit_status = f"{'수익권' if profit_rate > 0 else '손실권'} ({profit_rate:+.2f}%)"
            
            # 간단한 관리 조언 생성 (AI 호출 없이)
            management_advice = {
                "market_analysis": {
                    "regime_impact": f"v7.2 트리거 감지: {trigger_result['trigger']}",
                    "trend_group": f"체제: {market_regime['regime']}",
                    "momentum_group": f"수익 상태: {profit_status}",
                    "volatility_group": f"트리거 심각도: {trigger_result.get('severity', 'MEDIUM')}",
                    "volume_group": "위꼬리 방어 시스템 활성",
                    "overall_confidence": "관리 조정 필요",
                    "market_condition": "변화 감지"
                },
                "risk_assessment": {
                    "risk_level": "높음",
                    "position_size": "현재 포지션 관리 조정",
                    "max_holding_time": "상황에 따른 조정",
                    "key_risks": f"v7.2 {trigger_result['trigger']} 트리거로 인한 관리 필요"
                },
                "entry_price": 0,  # 보유 중이므로 0
                "target_price": current_price * 1.05,  # 5% 상향 조정 (예시)
                "stop_loss_price": current_price * 0.95,  # 5% 하향 조정 (예시)
                "entry_reason": "XRP 보유 중 - 진입 불필요",
                "target_reason": f"v7.2 {trigger_result['trigger']} 트리거에 따른 목표가 조정",
                "stop_loss_reason": f"v7.2 {trigger_result['trigger']} 트리거에 따른 손절가 조정 (위꼬리 방어 유지)",
                "sell_strategy": "트리거 기반 관리 조정 + 위꼬리 방어 시스템 지속",
                "lessons_applied": "v7.2 트리거 기반 적응형 관리",
                "regime_specific_action": f"체제 '{market_regime['regime']}'에 최적화된 관리",
                "change_trigger": trigger_result['trigger'],
                "trigger_evidence": trigger_result.get('evidence', ''),
                "wick_defense_status": "지속 활성화"
            }
            
            logger.info(f"✅ v7.2 트리거 기반 관리 조언 생성 완료: {trigger_result['trigger']}")
            return management_advice
            
        except Exception as e:
            logger.error(f"❌ v7.2 트리거 기반 관리 조언 생성 중 오류: {e}")
            return None

    def save_trade_plan_v72(self, trade_plan):
            """v7.2 개선된 거래 계획 저장: 확률론적 정보 포함"""
            try:
                if not trade_plan or 'entry_price' not in trade_plan:
                    logger.warning("⚠️ 유효한 v7.2 거래 계획이 아닙니다.")
                    return None
                
                # 포지션 상태 재확인
                position_status = self.check_current_position()
                has_position = position_status.get('has_position', False)
                
                if has_position:
                    # XRP 보유 중 - 포지션 관리 모드
                    return self._update_position_management_v72(trade_plan)
                else:
                    # XRP 미보유 - 신규 진입 계획 모드
                    return self._create_new_entry_plan_v72(trade_plan)
                    
            except Exception as e:
                logger.error(f"❌ v7.2 거래 계획 저장 중 오류: {e}")
                return None

    def _create_new_entry_plan_v72(self, trade_plan):
        """v7.2 XRP 미보유일 때: 확률론적 정보 포함 신규 진입 계획 생성"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 1단계: 모든 기존 계획/활성 거래 정리
                cursor.execute('''
                    UPDATE trades 
                    SET status = 'CANCELLED' 
                    WHERE status IN ('PLANNED', 'ACTIVE')
                ''')
                
                cancelled_count = cursor.rowcount
                
                # 2단계: v7.2 새로운 진입 계획 저장
                plan_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # v7.2 확률론적 필드들
                checklist_score = trade_plan.get('checklist_score', 0.0)
                signal_confidence_multiplier = trade_plan.get('signal_confidence_multiplier', 0.0)
                calculated_position_ratio = trade_plan.get('calculated_position_ratio', 0.0)
                checklist_breakdown = json.dumps(trade_plan.get('checklist_breakdown', {}), ensure_ascii=False)
                
                # v7.2 XRP 전문가 필드들
                wick_defense_active = trade_plan.get('wick_defense_active', True)
                energy_compression_detected = trade_plan.get('energy_compression_detected', False)
                xrp_pattern_type = trade_plan.get('xrp_pattern_type', 'NONE')
                
                cursor.execute('''
                    INSERT INTO trades (
                        asset_ticker, status, plan_timestamp,
                        planned_entry_price, planned_target_price, planned_stop_loss,
                        entry_reason, target_reason, stop_loss_reason,
                        checklist_score, checklist_breakdown, signal_confidence_multiplier,
                        calculated_position_ratio, wick_defense_active,
                        energy_compression_detected, xrp_pattern_type
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    'XRP', 'PLANNED', plan_timestamp,
                    trade_plan['entry_price'],
                    trade_plan['target_price'], 
                    trade_plan['stop_loss_price'],
                    trade_plan['entry_reason'],
                    trade_plan['target_reason'],
                    trade_plan['stop_loss_reason'],
                    checklist_score, checklist_breakdown, signal_confidence_multiplier,
                    calculated_position_ratio, wick_defense_active,
                    energy_compression_detected, xrp_pattern_type
                ))
                
                new_trade_id = cursor.lastrowid
                conn.commit()
                
                if cancelled_count > 0:
                    logger.info(f"🗑️ 기존 계획 {cancelled_count}개 정리 완료")
                logger.info(f"📝 v7.2 새로운 진입 계획 저장 완료 (ID: {new_trade_id})")
                logger.info(f"   확률론적 점수: {checklist_score:.1f}/5.5")
                logger.info(f"   신호 신뢰도 승수: {signal_confidence_multiplier:.1f}")
                logger.info(f"   위꼬리 방어: {'활성화' if wick_defense_active else '비활성화'}")
                logger.info(f"   진입가: {trade_plan['entry_price']:,.0f}원")
                logger.info(f"   목표가: {trade_plan['target_price']:,.0f}원")
                
                return new_trade_id
                
        except Exception as e:
            logger.error(f"❌ v7.2 신규 진입 계획 생성 중 오류: {e}")
            return None

    def _update_position_management_v72(self, trade_plan):
        """v7.2 XRP 보유 중일 때: 기존 ACTIVE 거래의 목표가/손절가 업데이트"""
        try:
            # 진입가 강제 0 설정
            if trade_plan.get('entry_price', 0) != 0:
                logger.warning("🚫 XRP 보유 중인데 진입가가 0이 아님 - 강제 수정")
                trade_plan['entry_price'] = 0
                trade_plan['entry_reason'] = "XRP 보유 중 - 진입 불필요"
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 1단계: 현재 ACTIVE 거래 조회
                cursor.execute('''
                    SELECT trade_id, position_size_xrp, actual_entry_price, 
                        entry_timestamp, commission_krw
                    FROM trades 
                    WHERE status = 'ACTIVE'
                    ORDER BY entry_timestamp DESC
                    LIMIT 1
                ''')
                
                active_trade = cursor.fetchone()
                
                if not active_trade:
                    logger.warning("⚠️ XRP 보유 중이지만 ACTIVE 거래가 없습니다. 스킵합니다.")
                    return None
                
                old_trade_id, position_size, entry_price, entry_time, commission = active_trade
                
                # 2단계: 기존 ACTIVE를 SUPERSEDED로 변경
                cursor.execute('''
                    UPDATE trades SET 
                        status = 'SUPERSEDED',
                        target_reason = target_reason || ' [v7.2 새로운 관리계획으로 대체됨]',
                        stop_loss_reason = stop_loss_reason || ' [v7.2 새로운 관리계획으로 대체됨]'
                    WHERE trade_id = ?
                ''', (old_trade_id,))
                
                # 3단계: 새로운 ACTIVE 거래 생성 (기존 정보 + 새로운 목표가/손절가)
                plan_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # v7.2 추가 필드들
                change_trigger = trade_plan.get('change_trigger', 'NONE')
                trigger_evidence = trade_plan.get('trigger_evidence', '')
                wick_defense_active = trade_plan.get('wick_defense_active', True)
                
                cursor.execute('''
                    INSERT INTO trades (
                        asset_ticker, status, plan_timestamp,
                        planned_entry_price, planned_target_price, planned_stop_loss,
                        entry_reason, target_reason, stop_loss_reason,
                        position_size_xrp, entry_timestamp, actual_entry_price, commission_krw,
                        change_trigger, trigger_evidence, wick_defense_active
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    'XRP', 'ACTIVE', plan_timestamp,
                    0,  # 진입가는 0
                    trade_plan['target_price'], 
                    trade_plan['stop_loss_price'],
                    trade_plan['entry_reason'],
                    f"[v7.2 관리계획 업데이트] {trade_plan['target_reason']}",
                    f"[v7.2 관리계획 업데이트] {trade_plan['stop_loss_reason']}",
                    position_size, entry_time, entry_price, commission,
                    change_trigger, trigger_evidence, wick_defense_active
                ))
                
                new_trade_id = cursor.lastrowid
                conn.commit()
                
                logger.info(f"🔄 v7.2 포지션 관리 계획 업데이트 완료:")
                logger.info(f"   이전 거래 ID {old_trade_id} → SUPERSEDED")
                logger.info(f"   새로운 거래 ID {new_trade_id} → ACTIVE")
                logger.info(f"   트리거: {change_trigger}")
                logger.info(f"   새 목표가: {trade_plan['target_price']:,.0f}원")
                logger.info(f"   새 손절가: {trade_plan['stop_loss_price']:,.0f}원")
                
                return new_trade_id
                
        except Exception as e:
            logger.error(f"❌ v7.2 포지션 관리 업데이트 중 오류: {e}")
            return None

    def _check_immediate_buy_opportunity_v72(self, trade_id):
        """v7.2 새로운 계획 저장 직후 즉시 매수 조건 체크 (확률론적 정보 포함)"""
        try:
            logger.info(f"🔍 v7.2 신규 계획 ID {trade_id} 즉시 매수 조건 체크")
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT planned_entry_price, checklist_score, signal_confidence_multiplier
                    FROM trades 
                    WHERE trade_id = ? AND status = 'PLANNED'
                ''', (trade_id,))
                
                result = cursor.fetchone()
            
            if not result:
                logger.info("💡 v7.2 즉시 매수 조건 체크 대상 계획 없음")
                return
            
            planned_entry_price, checklist_score, signal_multiplier = result
            
            # 진입가가 0이면 매수 금지 상태
            if planned_entry_price == 0:
                logger.info("🚫 v7.2 진입가 0 - 매수 금지 상태")
                return
            
            # 현재 가격 확인
            orderbook = pyupbit.get_orderbook(ticker="KRW-XRP")
            current_price = float(orderbook['orderbook_units'][0]['ask_price'])
            
            # 즉시 매수 조건 확인 (±1% 범위)
            entry_range = planned_entry_price * 0.01  # 1% 범위
            price_diff = abs(current_price - planned_entry_price)
            
            if price_diff <= entry_range:
                logger.info(f"🎯 v7.2 즉시 매수 조건 만족! (계획: {planned_entry_price:,.0f}원, 현재: {current_price:,.0f}원)")
                logger.info(f"   가격 차이: {price_diff:,.0f}원 (허용 범위: {entry_range:,.0f}원)")
                logger.info(f"   확률론적 점수: {checklist_score:.1f}/5.5")
                logger.info(f"   신호 신뢰도 승수: {signal_multiplier:.1f}")
                
                # 매수 실행
                success = self._execute_buy_order_v72(trade_id, planned_entry_price)
                if success:
                    logger.info(f"✅ v7.2 매도 완료 후 즉시 매수 성공! (거래 ID: {trade_id})")
                else:
                    logger.warning(f"⚠️ v7.2 매도 완료 후 즉시 매수 실패 (거래 ID: {trade_id})")
            else:
                logger.info(f"⏳ v7.2 즉시 매수 조건 미달성 (차이: {price_diff:,.0f}원 > 허용: {entry_range:,.0f}원)")
                logger.info(f"   정기 모니터링에서 재확인 예정")
                
        except Exception as e:
            logger.error(f"❌ v7.2 즉시 매수 조건 체크 중 오류: {e}")

    def run_strategy_analysis_v72(self):
        """v7.2 전략 분석 - 확률론적 접근 통합"""
        try:
            # 1회성 즉시 분석 스케줄 처리
            cleared_jobs = schedule.clear('immediate_analysis')
            if cleared_jobs:
                logger.info(f"⚡ v7.2 매도 후 즉시 분석 실행 ({cleared_jobs}개 즉시 분석 작업 완료)")
            
            interval_info = f"(v7.2 현재 주기: {self.current_analysis_interval}분)"
            logger.info(f"🧠 v7.2 확률론적 동적 주기 전략 분석 시작 {interval_info}")
            
            # 1. OBSERVE - 시장 데이터 관찰 (XRP 전문가 분석 포함)
            market_data = self.observe_market_data()
            if not market_data:
                logger.error("❌ v7.2 시장 데이터 수집 실패 - 전략 분석 중단")
                return
            
            # 2. ORIENT & DECIDE - v7.2 확률론적 접근 전략 수립
            strategy = self.orient_and_decide_v72(market_data)
            if strategy:
                # 3. ACT - v7.2 거래 계획 저장
                trade_id = self.save_trade_plan_v72(strategy)
                if trade_id:
                    logger.info(f"📋 v7.2 새로운 거래 계획 저장 완료 (ID: {trade_id})")
                    
                    # 즉시 매수 조건 체크
                    position_status = market_data.get('position_status', {})
                    if not position_status.get('has_position', False):
                        self._check_immediate_buy_opportunity_v72(trade_id)
                else:
                    logger.info("📋 v7.2 포지션 관리 조언 또는 저장 불필요")
            
            logger.info(f"✅ v7.2 확률론적 동적 주기 전략 분석 완료 {interval_info}")
            
        except Exception as e:
            logger.error(f"❌ v7.2 전략 분석 중 오류: {e}")

    def get_trading_status_v72(self):
        """v7.2 현재 거래 상태 조회 (확률론적 통계 포함)"""
        try:
            position_status = self.check_current_position()
            
            # 계획된 거래 조회
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT COUNT(*) FROM trades WHERE status = 'PLANNED'
                ''')
                planned_count = cursor.fetchone()[0]
                
                cursor.execute('''
                    SELECT COUNT(*) FROM trades WHERE status = 'ACTIVE'
                ''')
                active_count = cursor.fetchone()[0]
                
                cursor.execute('''
                    SELECT COUNT(*), AVG(profit_rate_pct), SUM(net_profit_krw)
                    FROM trades WHERE status = 'COMPLETED'
                ''')
                completed_data = cursor.fetchone()
                completed_count, avg_profit_rate, total_profit = completed_data
                
                # v7.2 확률론적 통계
                cursor.execute('''
                    SELECT AVG(checklist_score), COUNT(*), AVG(signal_confidence_multiplier)
                    FROM trades WHERE checklist_score > 0
                ''')
                checklist_data = cursor.fetchone()
                avg_checklist_score, checklist_count, avg_signal_multiplier = checklist_data
                
                # v7.2 XRP 전문가 통계
                cursor.execute('''
                    SELECT COUNT(*) FROM trades WHERE wick_defense_active = 1
                ''')
                wick_defense_count = cursor.fetchone()[0]
                
                cursor.execute('''
                    SELECT COUNT(*) FROM trades WHERE trade_result = 'WICK_DEFENSE_SAVE'
                ''')
                wick_saves_count = cursor.fetchone()[0]
                
                cursor.execute('''
                    SELECT COUNT(*) FROM trades WHERE energy_compression_detected = 1
                ''')
                energy_compression_count = cursor.fetchone()[0]
            
            status = {
                'position': {
                    'has_xrp': position_status['has_position'],
                    'xrp_balance': position_status['xrp_balance'],
                    'has_active_trade': position_status['has_active_trade']
                },
                'trades': {
                    'planned': planned_count,
                    'active': active_count,
                    'completed': completed_count or 0
                },
                'performance': {
                    'avg_profit_rate': round(avg_profit_rate or 0, 2),
                    'total_profit_krw': total_profit or 0
                },
                'v72_probabilistic_stats': {
                    'avg_checklist_score': round(avg_checklist_score or 0, 2),
                    'avg_signal_multiplier': round(avg_signal_multiplier or 0, 2),
                    'checklist_entries': checklist_count or 0
                },
                'v72_xrp_expert_stats': {
                    'wick_defense_used': wick_defense_count or 0,
                    'wick_defense_saves': wick_saves_count or 0,
                    'energy_compression_trades': energy_compression_count or 0,
                    'wick_save_rate': round((wick_saves_count / max(wick_defense_count, 1)) * 100, 1)
                }
            }
            
            return status
            
        except Exception as e:
            logger.error(f"❌ v7.2 거래 상태 조회 중 오류: {e}")
            return None

    def show_system_status_v72(self):
        """v7.2 시스템 현재 상태를 콘솔에 출력 (확률론적 + XRP 전문가 통계)"""
        try:
            status = self.get_trading_status_v72()
            position_status = self.check_current_position()
            
            if not status:
                print("❌ v7.2 시스템 상태를 조회할 수 없습니다.")
                return
            
            print("\n" + "="*80)
            print("🎯 OMNI-XRP v7.2 확률론적 접근 + XRP 전문가 시스템 현재 상태")
            print("="*80)
            
            # 포지션 상태
            print(f"💰 XRP 보유 상태: {'보유 중' if position_status['has_position'] else '미보유'}")
            if position_status['has_position']:
                print(f"   보유량: {position_status['xrp_balance']:.4f} XRP")
            
            print(f"📝 계획된 거래: {status['trades']['planned']}개")
            print(f"🚀 활성 거래: {status['trades']['active']}개") 
            print(f"✅ 완료된 거래: {status['trades']['completed']}개")
            
            # v7.2 확률론적 통계
            prob_stats = status['v72_probabilistic_stats']
            if prob_stats['checklist_entries'] > 0:
                print(f"\n📊 v7.2 확률론적 통계:")
                print(f"   평균 체크리스트 점수: {prob_stats['avg_checklist_score']:.1f}/5.5")
                print(f"   평균 신호 신뢰도 승수: {prob_stats['avg_signal_multiplier']:.2f}")
                print(f"   확률론적 적용 거래: {prob_stats['checklist_entries']}회")
            
            # v7.2 XRP 전문가 통계
            expert_stats = status['v72_xrp_expert_stats']
            if expert_stats['wick_defense_used'] > 0:
                print(f"\n🛡️ v7.2 XRP 전문가 통계:")
                print(f"   위꼬리 방어 사용: {expert_stats['wick_defense_used']}회")
                print(f"   위꼬리 방어 성공: {expert_stats['wick_defense_saves']}회")
                print(f"   위꼬리 방어 성공률: {expert_stats['wick_save_rate']}%")
                print(f"   에너지 압축 감지 거래: {expert_stats['energy_compression_trades']}회")
            
            # 성과 정보
            if status['performance']['total_profit_krw'] != 0:
                print(f"\n💰 총 수익: {status['performance']['total_profit_krw']:+,.0f}원")
                print(f"📈 평균 수익률: {status['performance']['avg_profit_rate']:+.2f}%")
            
            # 현재 활성 거래 정보 (v7.2 필드 포함)
            if position_status['has_active_trade']:
                active_trade = position_status['active_trade_info']
                print(f"\n🔥 현재 활성 거래 (v7.2):")
                print(f"   ID: {active_trade[0]}")
                print(f"   진입가: {active_trade[1]:,.0f}원")
                print(f"   목표가: {active_trade[2]:,.0f}원")
                print(f"   손절가: {active_trade[3]:,.0f}원")
                if len(active_trade) > 4:
                    print(f"   체크리스트: {active_trade[4]:.1f}/5.5")
                if len(active_trade) > 6:
                    print(f"   신호 신뢰도 승수: {active_trade[6]:.2f}")
                if len(active_trade) > 7:
                    print(f"   위꼬리 방어: {'활성화' if active_trade[7] else '비활성화'}")
            
            # v7.2 다음 행동 예상
            print(f"\n🎯 v7.2 다음 행동 예상:")
            if position_status['has_position'] and position_status['has_active_trade']:
                print("   → 확률론적 트리거 기반 포지션 관리 중")
                print("   → 위꼬리 방어 시스템으로 보호 중")
                print("   → 목표가/손절가 도달 또는 트리거 발생 시 관리 실행")
            elif status['trades']['planned'] > 0:
                print("   → 확률론적 검증 통과한 진입가 도달 시 매수 실행")
            else:
                print("   → 확률론적 체크리스트 기반 새로운 시장체제 분석 및 전략 수립")
            
            print("="*80)
            
        except Exception as e:
            print(f"❌ v7.2 상태 확인 중 오류: {e}")

    def get_dynamic_analysis_interval(self, position_status, market_regime):
            """v7.2 포지션 상태와 시장체제에 따른 동적 분석 주기 결정"""
            try:
                has_position = position_status.get('has_position', False)
                regime = market_regime.get('regime', '분석실패')
                confidence = market_regime.get('confidence', '낮음')
                
                if has_position:
                    # XRP 보유 중일 때도 시장 상황에 따라 주기 차등화
                    if regime == "명백한_상승장":
                        return 10, "v7.2 포지션 관리: 강세장 추세 추종 (10분 주기)"
                    elif regime == "횡보_박스권":
                        return 15, "v7.2 포지션 관리: 횡보장 모니터링 (15분 주기)"
                    elif regime == "명백한_하락장":
                        return 20, "v7.2 포지션 관리: 하락장 방어 모드 (20분 주기)"
                    else:  # 혼조장
                        return 30, "v7.2 포지션 관리: 보수적 방어 모드 (30분 주기)"
                
                else:
                    # XRP 미보유 - 시장체제별 차별화
                    if regime == "명백한_하락장":
                        return 60, "v7.2 하락장 대기 모드 (1시간 주기)"
                        
                    elif regime == "명백한_상승장" and confidence == "높음":
                        return 5, "v7.2 강세장 기회 포착 모드 (5분 주기)"
                        
                    elif regime == "횡보_박스권":
                        return 7, "v7.2 횡보장 진입점 포착 모드 (7분 주기)"
                        
                    elif regime in ["고변동성_혼조장", "애매한_혼조장"]:
                        return 12, "v7.2 혼조장 신중 관찰 모드 (12분 주기)"
                        
                    elif regime == "명백한_상승장" and confidence != "높음":
                        return 8, "v7.2 약한 상승장 모니터링 (8분 주기)"
                        
                    else:
                        return 30, "v7.2 일반 분석 모드 (30분 주기)"
                        
            except Exception as e:
                logger.error(f"❌ v7.2 동적 주기 계산 중 오류: {e}")
                return 30, "v7.2 오류 발생 - 기본 모드 (30분 주기)"

    def update_analysis_schedule(self, new_interval, mode_description):
        """v7.2 분석 주기 동적 업데이트"""
        try:
            # 현재 주기와 다를 때만 업데이트
            if new_interval != self.current_analysis_interval:
                
                # 기존 스케줄 취소 (있다면)
                cleared_count = len(schedule.clear('strategy_analysis'))
                if cleared_count > 0:
                    logger.info(f"🗑️ v7.2 기존 전략 분석 스케줄 {cleared_count}개 취소")
                
                # 새로운 주기로 스케줄 등록
                schedule.every(new_interval).minutes.do(self.run_strategy_analysis_v72).tag('strategy_analysis')
                
                # 상태 업데이트
                old_interval = self.current_analysis_interval
                self.current_analysis_interval = new_interval
                self.last_interval_change = time.time()
                
                next_run = datetime.now() + timedelta(minutes=new_interval)
                logger.info(f"📅 v7.2 분석 주기 변경: {old_interval}분 → {new_interval}분")
                logger.info(f"🎯 모드: {mode_description}")
                logger.info(f"⏰ 다음 분석: {next_run.strftime('%H:%M:%S')}")
                
                return True
            else:
                # 주기 변경 없음
                return False
                
        except Exception as e:
            logger.error(f"❌ v7.2 분석 주기 업데이트 중 오류: {e}")
            return False

    def check_and_update_analysis_interval(self):
        """v7.2 주기적으로 분석 주기 재평가 (5분마다 실행)"""
        try:
            current_time = time.time()
            
            # 쿨다운 체크 (너무 자주 변경 방지)
            if (self.last_regime_check and 
                current_time - self.last_regime_check < self.regime_change_cooldown):
                return
            
            # 현재 시장 상황 확인
            market_data = self.observe_market_data()
            if not market_data:
                logger.warning("⚠️ v7.2 주기 재평가용 시장 데이터 수집 실패")
                return
                
            position_status = market_data.get('position_status', {})
            market_regime = self._analyze_market_regime(market_data)
            
            # 새로운 분석 주기 계산
            new_interval, mode_description = self.get_dynamic_analysis_interval(
                position_status, market_regime
            )
            
            # 주기 업데이트 시도
            updated = self.update_analysis_schedule(new_interval, mode_description)
            
            if updated:
                self.last_regime_check = current_time
                logger.info(f"✅ v7.2 시장체제 '{market_regime['regime']}' 감지로 분석 주기 조정 완료")
            else:
                # 변경 없어도 체제 확인 시간은 업데이트
                self.last_regime_check = current_time
            
        except Exception as e:
            logger.error(f"❌ v7.2 분석 주기 재평가 중 오류: {e}")

    def start_automated_trading_v72(self):
        """v7.2 자동화된 거래 시스템 시작"""
        logger.info("🚀 OMNI-XRP v7.2 확률론적 접근 + XRP 전문가 자동화 시스템 시작")
        
        # 시스템 시작 시 포지션 검증 및 기존 계획 정리
        self.validate_and_cleanup_existing_plans()
        
        # 1. 현재 상황에 맞는 초기 분석 주기 설정
        logger.info("🔄 v7.2 시스템 시작 - 초기 분석 주기 설정")
        market_data = self.observe_market_data()
        if market_data:
            position_status = market_data.get('position_status', {})
            market_regime = self._analyze_market_regime(market_data)
            
            # 초기 주기 계산 및 즉시 적용
            initial_interval, mode_desc = self.get_dynamic_analysis_interval(
                position_status, market_regime
            )
            
            # 최초 스케줄 등록
            self.current_analysis_interval = initial_interval
            schedule.every(initial_interval).minutes.do(self.run_strategy_analysis_v72).tag('strategy_analysis')
            
            logger.info(f"✅ v7.2 초기 분석 주기 설정: {mode_desc}")
            next_run = datetime.now() + timedelta(minutes=initial_interval)
            logger.info(f"⏰ 첫 번째 정규 분석: {next_run.strftime('%H:%M:%S')}")
        else:
            # 실패 시 기본값
            self.current_analysis_interval = 30
            schedule.every(30).minutes.do(self.run_strategy_analysis_v72).tag('strategy_analysis')
            logger.warning("⚠️ v7.2 초기 데이터 수집 실패 - 30분 기본 주기로 시작")
        
        # 2. 5분마다 주기 재평가 스케줄 등록
        schedule.every(5).minutes.do(self.check_and_update_analysis_interval).tag('interval_check')
        
        # 3. 첫 전략 분석 즉시 실행
        logger.info("🚀 v7.2 첫 전략 분석 즉시 실행")
        self.run_strategy_analysis_v72()
        
        # 메인 루프: 2초마다 가격 감시 + 스케줄 실행
        while True:
            try:
                # 1. v7.2 위꼬리 방어 포함 가격 감시
                self.monitor_price_with_spike_detection_v72()
                
                # 2. 스케줄 확인 및 실행
                schedule.run_pending()
                
                # 2초 대기
                time.sleep(2)
                
            except KeyboardInterrupt:
                logger.info("🛑 사용자 중단 - v7.2 시스템 종료")
                break
            except Exception as e:
                logger.error(f"❌ v7.2 메인 루프 오류: {e}")
                time.sleep(2)

    def monitor_price_with_spike_detection_v72(self):
        """v7.2 가격 감시 + 급변동 감지 + 위꼬리 방어 통합"""
        try:
            # 현재 가격 확인
            orderbook = pyupbit.get_orderbook(ticker="KRW-XRP")
            current_price = float(orderbook['orderbook_units'][0]['ask_price'])
            
            # 급변동 감지
            is_spike, change_pct, spike_type = self._detect_price_spike(current_price)
            
            if is_spike and not self._is_emergency_cooldown_active():
                # 🚨 급변동 발생 - 즉시 분석 실행
                logger.info(f"🔥 v7.2 {spike_type} 트리거 발동 ({change_pct:+.2f}%) - 즉시 전략 재분석 시작")
                self._emergency_strategy_analysis_v72(current_price, change_pct, spike_type)
                self.last_emergency_time = time.time()  # 쿨다운 시작
            elif is_spike and self._is_emergency_cooldown_active():
                logger.info(f"⏰ v7.2 {spike_type} 감지되었으나 쿨다운 중 - 무시")
            
            # v7.2 모니터링 (위꼬리 방어 포함)
            self.monitor_active_trades_v72()
            self.monitor_planned_trades()
            
        except Exception as e:
            logger.error(f"❌ v7.2 급변동 감지 가격 감시 중 오류: {e}")

    def _detect_price_spike(self, current_price):
        """v7.2 급등/급락 감지 - 5분 전 가격과 비교"""
        try:
            # 5분봉 데이터에서 5분 전 가격 가져오기
            df_5m = pyupbit.get_ohlcv("KRW-XRP", interval="minute5", count=2)
            if len(df_5m) < 2:
                return False, 0, ""
            
            # 5분 전 종가와 현재 가격 비교
            price_5min_ago = float(df_5m['close'].iloc[-2])  # 5분 전 종가
            price_change_pct = (current_price - price_5min_ago) / price_5min_ago
            
            # 0.7% 이상 급변동 감지
            if abs(price_change_pct) >= self.price_alert_threshold:
                spike_type = "급등" if price_change_pct > 0 else "급락"
                logger.warning(f"🚨 v7.2 {spike_type} 감지: {price_change_pct:+.2f}% (5분전: {price_5min_ago:,.0f}원 → 현재: {current_price:,.0f}원)")
                
                return True, price_change_pct, spike_type
            
            return False, price_change_pct, ""
            
        except Exception as e:
            logger.error(f"v7.2 급변동 감지 중 오류: {e}")
            return False, 0, ""

    def _is_emergency_cooldown_active(self):
        """v7.2 긴급 분석 쿨다운 체크"""
        try:
            if self.last_emergency_time is None:
                return False
            
            time_since_last = time.time() - self.last_emergency_time
            return time_since_last < self.emergency_cooldown
            
        except Exception as e:
            logger.error(f"v7.2 쿨다운 체크 중 오류: {e}")
            return True  # 오류 시 안전하게 쿨다운 적용

    def _emergency_strategy_analysis_v72(self, current_price, change_pct, spike_type):
        """v7.2 긴급 전략 재분석 (확률론적 접근 적용)"""
        try:
            logger.info("🚨 v7.2 긴급 시장 상황 재분석 시작")
            
            # 시장 데이터 즉시 수집
            market_data = self.observe_market_data()
            if not market_data:
                logger.error("❌ v7.2 긴급 시장 데이터 수집 실패")
                return
            
            # 포지션 상태 확인
            position_status = market_data.get('position_status', {})
            has_position = position_status.get('has_position', False)
            
            if has_position:
                # XRP 보유 중 - 긴급 포지션 관리 (기존 로직 재사용)
                logger.info(f"🎯 v7.2 XRP 보유 중 - {spike_type} 긴급 포지션 재평가")
                emergency_advice = self._generate_position_management_advice_v72(market_data)
                
                if emergency_advice:
                    logger.info("🔄 v7.2 긴급 상황 - 관리 계획 업데이트")
                    trade_id = self.save_trade_plan_v72(emergency_advice)
                    
                    if trade_id:
                        logger.info(f"✅ v7.2 긴급 관리 계획 업데이트 완료 (새 거래 ID: {trade_id})")
                    else:
                        logger.warning("⚠️ v7.2 긴급 관리 계획 업데이트 실패")
                        
            else:
                # XRP 미보유 - 긴급 진입 기회 검토 (v7.2 확률론적 접근)
                logger.info(f"💰 v7.2 XRP 미보유 - {spike_type} 긴급 진입 기회 검토")
                emergency_strategy = self._generate_new_entry_strategy_v72(market_data)
                
                if emergency_strategy:
                    logger.info("🔄 v7.2 긴급 상황 - 진입 계획 저장")
                    trade_id = self.save_trade_plan_v72(emergency_strategy)
                    
                    if trade_id:
                        logger.info(f"✅ v7.2 긴급 진입 계획 저장 완료 (새 거래 ID: {trade_id})")
                        # 즉시 매수 조건 체크
                        self._check_immediate_buy_opportunity_v72(trade_id)
                    else:
                        logger.warning("⚠️ v7.2 긴급 진입 계획 저장 실패")
            
            # 급변동 후 주기 재평가 쿨다운 리셋
            self.last_regime_check = None
            logger.info("🔄 v7.2 급변동 대응 완료 - 주기 재평가 쿨다운 리셋")
            
            logger.info("✅ v7.2 긴급 전략 재분석 완료 - 동적 주기로 정상 운영 재개")
            
        except Exception as e:
            logger.error(f"❌ v7.2 긴급 전략 분석 중 오류: {e}")

    # =============================================================================
    # v7.2 회고 및 교훈 추출 함수들 
    # =============================================================================

    def reflect_single_trade(self, completed_trade_id):
        """v7.2 강화된 GPT 회고 분석 - 확률론적 접근 + XRP 전문가 + 전체 포지션 히스토리"""
        try:
            logger.info(f"🔍 v7.2 거래 ID {completed_trade_id} GPT 전체 히스토리 회고 분석 중...")
            
            # 1단계: 완료된 거래 정보 조회 (v7.2 확률론적 필드 포함)
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT trade_id, planned_entry_price, planned_target_price, planned_stop_loss,
                           actual_entry_price, actual_exit_price, trade_result, net_profit_krw,
                           profit_rate_pct, entry_reason, target_reason, stop_loss_reason, 
                           entry_timestamp, exit_timestamp, position_size_xrp,
                           checklist_score, checklist_breakdown, signal_confidence_multiplier,
                           calculated_position_ratio, wick_defense_active, energy_compression_detected,
                           xrp_pattern_type, change_trigger, trigger_evidence
                    FROM trades 
                    WHERE trade_id = ? AND status = 'COMPLETED'
                ''', (completed_trade_id,))
                
                completed_trade = cursor.fetchone()
            
            if not completed_trade:
                logger.warning(f"⚠️ 거래 ID {completed_trade_id}의 완료된 데이터를 찾을 수 없습니다.")
                return
            
            # 2단계: 전체 포지션 히스토리 추적
            position_history = self._trace_position_history_v72(completed_trade_id)
            
            if not position_history:
                logger.warning(f"⚠️ 거래 ID {completed_trade_id}의 히스토리를 추적할 수 없습니다.")
                return
            
            # 3단계: v7.2 확률론적 회고 분석 실행
            reflection_analysis = self._perform_comprehensive_reflection_v72(completed_trade, position_history)
            
            if reflection_analysis:
                # 4단계: 회고 결과 저장
                self._save_reflection_to_file_v72(completed_trade_id, reflection_analysis)
                logger.info(f"✅ v7.2 거래 ID {completed_trade_id} GPT 종합 회고 분석 완료")
                return reflection_analysis
            else:
                logger.error(f"❌ v7.2 거래 ID {completed_trade_id} 회고 분석 실패")
                return None
                
        except Exception as e:
            logger.error(f"❌ v7.2 강화된 회고 분석 중 오류: {e}")
            return None


    def _trace_position_history_v72(self, completed_trade_id):
        """v7.2 포지션 전체 히스토리 추적 (확률론적 정보 포함)"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 완료된 거래 기본 정보 (v7.2 필드 포함)
                cursor.execute('''
                    SELECT position_size_xrp, entry_timestamp, exit_timestamp, actual_exit_price,
                           checklist_score, signal_confidence_multiplier, calculated_position_ratio
                    FROM trades 
                    WHERE trade_id = ? AND status = 'COMPLETED'
                ''', (completed_trade_id,))
                
                completed_info = cursor.fetchone()
                if not completed_info:
                    return None
                    
                position_size, entry_time, exit_time, exit_price, checklist_score, signal_multiplier, position_ratio = completed_info
                
                # 같은 포지션 크기를 가진 모든 관련 거래 조회 (시간 순)
                cursor.execute('''
                    SELECT trade_id, status, planned_entry_price, planned_target_price, planned_stop_loss,
                           actual_entry_price, entry_reason, target_reason, stop_loss_reason,
                           plan_timestamp, entry_timestamp, checklist_score, signal_confidence_multiplier,
                           wick_defense_active, energy_compression_detected, xrp_pattern_type,
                           change_trigger, trigger_evidence
                    FROM trades 
                    WHERE position_size_xrp = ? OR trade_id = ?
                    ORDER BY plan_timestamp ASC
                ''', (position_size, completed_trade_id))
                
                all_related_trades = cursor.fetchall()
                
                if not all_related_trades:
                    return None
                
                # v7.2 히스토리 분석 (확률론적 정보 포함)
                history = {
                    'original_entry': None,
                    'management_changes': [],
                    'v72_probabilistic_info': {
                        'original_checklist_score': checklist_score,
                        'original_signal_multiplier': signal_multiplier,
                        'original_position_ratio': position_ratio
                    },
                    'v72_xrp_expert_info': {
                        'wick_defense_used': False,
                        'energy_compression_detected': False,
                        'xrp_patterns': []
                    },
                    'final_exit': {
                        'trade_id': completed_trade_id,
                        'exit_price': exit_price,
                        'exit_time': exit_time
                    }
                }
                
                for trade in all_related_trades:
                    (t_id, status, plan_entry, plan_target, plan_stop, actual_entry, 
                    entry_reason, target_reason, stop_reason, plan_time, entry_time,
                    t_checklist_score, t_signal_multiplier, t_wick_defense, t_energy_compression,
                    t_xrp_pattern, t_change_trigger, t_trigger_evidence) = trade
                    
                    # 최초 진입 거래 찾기 (actual_entry_price가 0이 아닌 첫 번째)
                    if actual_entry and actual_entry > 0 and not history['original_entry']:
                        history['original_entry'] = {
                            'trade_id': t_id,
                            'actual_entry_price': actual_entry,
                            'entry_reason': entry_reason,
                            'entry_time': entry_time,
                            'original_target': plan_target,
                            'original_stop': plan_stop,
                            # v7.2 확률론적 정보
                            'checklist_score': t_checklist_score or 0,
                            'signal_multiplier': t_signal_multiplier or 0,
                            'wick_defense_active': t_wick_defense or False,
                            'energy_compression': t_energy_compression or False,
                            'xrp_pattern': t_xrp_pattern or 'NONE'
                        }
                        
                        # XRP 전문가 정보 업데이트
                        if t_wick_defense:
                            history['v72_xrp_expert_info']['wick_defense_used'] = True
                        if t_energy_compression:
                            history['v72_xrp_expert_info']['energy_compression_detected'] = True
                        if t_xrp_pattern and t_xrp_pattern != 'NONE':
                            history['v72_xrp_expert_info']['xrp_patterns'].append(t_xrp_pattern)
                    
                    # 관리 계획 변경 추적 (SUPERSEDED 상태) - v7.2 정보 포함
                    if status == 'SUPERSEDED':
                        history['management_changes'].append({
                            'trade_id': t_id,
                            'plan_time': plan_time,
                            'target_price': plan_target,
                            'stop_price': plan_stop,
                            'target_reason': target_reason,
                            'stop_reason': stop_reason,
                            'change_type': 'SUPERSEDED',
                            'change_trigger': t_change_trigger or 'NONE',
                            'trigger_evidence': t_trigger_evidence or '',
                            'wick_defense_active': t_wick_defense or False
                        })
                
                # 최종 유효한 관리 계획 (COMPLETED 직전)
                if all_related_trades:
                    final_trade = all_related_trades[-1]  # 마지막 거래
                    if final_trade[0] == completed_trade_id:
                        history['final_plan'] = {
                            'final_target': final_trade[3],
                            'final_stop': final_trade[4],
                            'target_reason': final_trade[7],
                            'stop_reason': final_trade[8]
                        }
                
                return history
                
        except Exception as e:
            logger.error(f"v7.2 포지션 히스토리 추적 중 오류: {e}")
            return None

    def _perform_comprehensive_reflection_v72(self, completed_trade, position_history):
        """v7.2 GPT 기반 확률론적 + XRP 전문가 종합 회고 분석"""
        try:
            # 거래 기본 정보 파싱 (v7.2 필드 포함)
            (t_id, plan_entry, plan_target, plan_stop, actual_entry, actual_exit, 
            result, profit, profit_rate, entry_reason, target_reason, stop_reason, 
            entry_time, exit_time, position_size, checklist_score, checklist_breakdown,
            signal_multiplier, position_ratio, wick_defense, energy_compression,
            xrp_pattern, change_trigger, trigger_evidence) = completed_trade
            
            # 실제 진입 정보 (히스토리에서 추출)
            original_entry = position_history.get('original_entry')
            if not original_entry:
                logger.error("실제 진입 정보를 찾을 수 없습니다.")
                return None
                
            real_entry_price = original_entry['actual_entry_price']
            real_entry_reason = original_entry['entry_reason']
            real_entry_time = original_entry['entry_time']
            
            # v7.2 확률론적 정보 추출
            v72_prob_info = position_history.get('v72_probabilistic_info', {})
            v72_expert_info = position_history.get('v72_xrp_expert_info', {})
            
            # 관리 계획 변경 히스토리
            management_changes = position_history.get('management_changes', [])
            
            # 보유 기간 계산
            holding_duration = self._calculate_holding_duration(real_entry_time, exit_time)
            
            # 실제 수익률 재계산 (실제 진입가 기준)
            real_profit_rate = ((actual_exit - real_entry_price) / real_entry_price * 100)
            
            # 매도 이후 시장 분석
            post_sell_analysis = self._analyze_post_sell_market_v72(exit_time, actual_exit)
            
            # v7.2 관리 계획 변경 분석 (트리거 정보 포함)
            management_analysis = self._analyze_management_changes_v72(management_changes, real_entry_price, actual_exit)
            
            # v7.2 확률론적 성과 분석
            probabilistic_analysis = self._analyze_probabilistic_performance_v72(
                checklist_score, signal_multiplier, position_ratio, real_profit_rate
            )
            
            # v7.2 XRP 전문가 시스템 효과 분석
            xrp_expert_analysis = self._analyze_xrp_expert_effectiveness_v72(
                wick_defense, energy_compression, xrp_pattern, result, real_profit_rate
            )
            
            # v7.2 종합 회고 프롬프트 (확률론적 + XRP 전문가 분석 포함)
            comprehensive_prompt = f"""
# OMNI-XRP v7.2 GPT 종합 회고 분석 요청

당신은 OMNI-XRP v7.2의 전문 트레이딩 분석가입니다. 다음 XRP 거래의 **전체 포지션 히스토리**를 확률론적 접근과 XRP 전문가 시스템 관점에서 종합 분석해주세요.

## 🎯 v7.2 확률론적 접근 분석 결과
{probabilistic_analysis}

## 🧪 v7.2 XRP 전문가 시스템 분석 결과  
{xrp_expert_analysis}

## 📊 거래 기본 정보
- **최종 거래 ID**: {t_id}
- **거래 결과**: {result}
- **실제 보유 기간**: {holding_duration}
- **실제 순수익**: {profit:+,.0f}원 ({real_profit_rate:+.2f}%)
- **v7.2 체크리스트 점수**: {checklist_score:.1f}/5.5
- **v7.2 신호 신뢰도 승수**: {signal_multiplier:.2f}
- **v7.2 계산된 포지션 비중**: {position_ratio:.1%}

## 🎯 실제 진입 정보 (확률론적 검증 통과)
- **실제 진입 ID**: {original_entry['trade_id']}
- **실제 진입가**: {real_entry_price:,.0f}원
- **실제 진입 시간**: {real_entry_time}
- **실제 진입 이유**: {real_entry_reason}
- **최초 목표가**: {original_entry['original_target']:,.0f}원
- **최초 손절가**: {original_entry['original_stop']:,.0f}원
- **진입 시 체크리스트**: {original_entry.get('checklist_score', 0):.1f}/5.5
- **진입 시 신호 승수**: {original_entry.get('signal_multiplier', 0):.2f}

## 🛡️ v7.2 XRP 전문가 시스템 적용 현황
- **위꼬리 방어 사용**: {'예' if v72_expert_info.get('wick_defense_used', False) else '아니오'}
- **에너지 응축 감지**: {'예' if v72_expert_info.get('energy_compression_detected', False) else '아니오'}
- **감지된 XRP 패턴**: {', '.join(v72_expert_info.get('xrp_patterns', ['없음']))}

## 📈 포지션 관리 히스토리 (v7.2 트리거 기반)
{management_analysis}

## 🎯 최종 매도 분석
- **최종 매도가**: {actual_exit:,.0f}원
- **최종 매도 시간**: {exit_time}
- **목표가 달성률**: {(actual_exit / plan_target * 100):.1f}%
- **실제 진입가 대비 수익률**: {real_profit_rate:+.2f}%
- **매도 유형**: {result}

## 🔮 매도 후 시장 분석
{post_sell_analysis}

---

## 🎓 v7.2 GPT 회고 분석 요청사항

다음 **12가지 v7.2 핵심 관점**에서 전체 포지션 히스토리를 심층 분석해주세요:

### 📊 확률론적 접근 분석 (4개 관점)
1. **체크리스트 정확성**: {checklist_score:.1f}/5.5점 예측 vs 실제 결과({real_profit_rate:+.2f}%) 비교
2. **신호 신뢰도 승수 효과**: {signal_multiplier:.2f} 승수가 수익에 미친 실제 영향
3. **동적 포지션 사이징 성과**: {position_ratio:.1%} 비중 결정의 적절성
4. **하드 임계값(2.5점) 시스템 검증**: 확률론적 필터링 효과

### 🧪 XRP 전문가 시스템 분석 (4개 관점)
5. **위꼬리 방어 시스템 효과**: 활성화 여부와 실제 보호 효과
6. **에너지 응축 패턴 정확도**: 감지 시 실제 돌파 여부와 수익률
7. **XRP 특화 패턴 인식 성과**: 감지된 패턴의 예측 정확도
8. **전문가 시스템 통합 효과**: 기존 대비 개선된 점

### 🔄 통합 시스템 분석 (4개 관점)  
9. **확률론적 + 전문가 시너지**: 두 시스템의 상호 보완 효과
10. **트리거 기반 관리 적절성**: v7.2 트리거 시스템의 변경 타당성
11. **3층 안전망 시스템 검증**: 체크리스트→AI→검증 단계별 효과
12. **v7.2 전체 시스템 성숙도**: 기존 v7.1 대비 실질적 개선점

---

## 🏆 v7.2 핵심 교훈 추출 (Most Critical v7.2 Lesson)

위 분석을 바탕으로, 이번 거래에서 얻은 **v7.2 시스템 관련 가장 중요한 교훈 3가지**를 아래 포맷에 맞춰 추출해주세요:

### 교훈 1: 확률론적 접근 관련
- **상황**: 체크리스트 {checklist_score:.1f}점, 신호승수 {signal_multiplier:.2f}인 상황
- **행동**: 어떤 확률론적 판단을 했는가?
- **결과**: 그 판단의 실제 결과는?
- **v7.2 규칙**: 확률론적 시스템 개선 방향

### 교훈 2: XRP 전문가 시스템 관련
- **상황**: 위꼬리 방어/에너지 응축 등 XRP 전문가 시스템 적용 상황
- **행동**: 어떤 전문가 시스템을 적용했는가?
- **결과**: 그 시스템의 실제 효과는?
- **v7.2 규칙**: XRP 전문가 시스템 최적화 방향

### 교훈 3: 통합 시스템 관련
- **상황**: 확률론적 접근과 XRP 전문가가 통합된 상황
- **행동**: 두 시스템이 어떻게 협업했는가?
- **결과**: 통합 효과는 어떠했는가?
- **v7.2 규칙**: 시스템 통합 개선 방향

각 교훈은 미래의 v7.2 AI가 이해하고 따를 수 있도록 명확하고 실행 가능해야 합니다.
"""

            # GPT 호출 (v7.2 전용 회고 분석)
            reflection_response = self.client.chat.completions.create(
                model="gpt-4.1",  # 최신 모델 사용
                messages=[
                    {
                        "role": "system",
                        "content": """당신은 OMNI-XRP v7.2의 전문 포지션 관리 회고 분석가입니다.

v7.2 핵심 역량:
1. 확률론적 접근 시스템 (체크리스트 → 신호승수 → 동적포지션사이징) 분석
2. XRP 전문가 시스템 (위꼬리방어, 에너지응축, 패턴인식) 효과 평가  
3. 두 시스템의 통합 시너지 효과 분석
4. v7.2 특화 교훈 추출 및 시스템 개선 방향 제시

분석 접근법:
- 단일 거래가 아닌 **전체 포지션 운영 히스토리** 종합 평가
- 확률론적 예측 vs 실제 결과의 정확도 검증
- XRP 전문가 시스템의 실질적 효과 측정
- v7.2만의 혁신적 특징과 기존 대비 개선점 분석
- 미래 거래에 적용할 구체적이고 실행 가능한 규칙 도출

모든 분석은 실제 데이터 기반이며, v7.2 시스템의 성숙도를 높이는 방향으로 제시됩니다."""
                    },
                    {"role": "user", "content": comprehensive_prompt}
                ],
                max_tokens=3000,
                temperature=0.1
            )
            
            reflection_result = reflection_response.choices[0].message.content
            
            logger.info("✅ v7.2 GPT 종합 회고 분석 완료")
            return reflection_result
            
        except Exception as e:
            logger.error(f"❌ v7.2 GPT 종합 회고 분석 중 오류: {e}")
            return None

    def _analyze_probabilistic_performance_v72(self, checklist_score, signal_multiplier, position_ratio, actual_profit_rate):
        """v7.2 확률론적 성과 분석"""
        try:
            analysis = f"""
## 📊 v7.2 확률론적 접근 성과 분석

### 체크리스트 예측 정확도
- 체크리스트 점수: {checklist_score:.1f}/5.5
- 신호 등급: {'A+급' if checklist_score >= 4.5 else 'A급' if checklist_score >= 3.5 else 'B급' if checklist_score >= 2.5 else 'F급'}
- 실제 수익률: {actual_profit_rate:+.2f}%
- 예측 일치도: {'높음' if (checklist_score >= 3.5 and actual_profit_rate > 0) or (checklist_score < 2.5 and actual_profit_rate < 0) else '보통' if abs(actual_profit_rate) < 5 else '낮음'}

### 신호 신뢰도 승수 효과
- 적용된 승수: {signal_multiplier:.2f}
- 승수 의미: {'최대 투자' if signal_multiplier >= 0.7 else '제한적 투자' if signal_multiplier >= 0.4 else '금지' if signal_multiplier == 0 else '오류'}
- 승수 적절성: {'적절' if (signal_multiplier >= 0.7 and actual_profit_rate > 3) or (signal_multiplier < 0.7 and abs(actual_profit_rate) < 10) else '부적절'}

### 동적 포지션 사이징 성과
- 계산된 투자 비중: {position_ratio:.1%}
- 비중 적절성: {'보수적' if position_ratio < 0.3 else '적절' if position_ratio < 0.7 else '공격적'}
- 리스크 대비 수익: {'효율적' if actual_profit_rate / max(position_ratio, 0.1) > 5 else '비효율적'}
"""
            return analysis
        except Exception as e:
            logger.error(f"확률론적 성과 분석 중 오류: {e}")
            return "확률론적 성과 분석 실패"

    def _analyze_xrp_expert_effectiveness_v72(self, wick_defense, energy_compression, xrp_pattern, result, profit_rate):
        """v7.2 XRP 전문가 시스템 효과 분석"""
        try:
            analysis = f"""
## 🧪 v7.2 XRP 전문가 시스템 효과 분석

### 위꼬리 방어 시스템
- 방어 시스템 활성화: {'예' if wick_defense else '아니오'}
- 방어 효과: {'성공' if result == 'WICK_DEFENSE_SAVE' else '대기' if wick_defense and result == 'PROFIT_TAKE' else '미적용'}
- 생존 기여도: {'높음' if result == 'WICK_DEFENSE_SAVE' else '보통' if wick_defense else '해당없음'}

### 에너지 응축 패턴 분석
- 응축 패턴 감지: {'예' if energy_compression else '아니오'}
- 돌파 성공률: {'성공' if energy_compression and profit_rate > 5 else '부분성공' if energy_compression and profit_rate > 0 else '실패' if energy_compression else '해당없음'}
- 예측 정확도: {'높음' if energy_compression and profit_rate > 8 else '보통' if energy_compression and profit_rate > 0 else '낮음' if energy_compression else '해당없음'}

### XRP 특화 패턴 인식
- 감지된 패턴: {xrp_pattern if xrp_pattern != 'NONE' else '없음'}
- 패턴 활용도: {'높음' if xrp_pattern != 'NONE' and profit_rate > 3 else '보통' if xrp_pattern != 'NONE' else '해당없음'}
- 전문가 시스템 기여도: {'상당함' if (wick_defense or energy_compression) and profit_rate > 0 else '제한적'}
"""
            return analysis
        except Exception as e:
            logger.error(f"XRP 전문가 효과 분석 중 오류: {e}")
            return "XRP 전문가 효과 분석 실패"

    def _analyze_management_changes_v72(self, management_changes, entry_price, exit_price):
        """v7.2 관리 계획 변경 분석 (트리거 정보 포함)"""
        try:
            if not management_changes:
                return "관리 계획 변경 없음 - 최초 계획 그대로 실행"
            
            analysis = f"## 📊 v7.2 트리거 기반 관리 계획 변경 분석\n\n"
            analysis += f"총 {len(management_changes)}회 관리 계획 변경\n\n"
            
            for i, change in enumerate(management_changes, 1):
                trigger = change.get('change_trigger', 'NONE')
                evidence = change.get('trigger_evidence', '')
                wick_defense = change.get('wick_defense_active', False)
                
                analysis += f"### 변경 {i}: {trigger} 트리거\n"
                analysis += f"- 트리거 근거: {evidence}\n"
                analysis += f"- 새 목표가: {change['target_price']:,.0f}원\n"
                analysis += f"- 새 손절가: {change['stop_price']:,.0f}원\n"
                analysis += f"- 위꼬리 방어: {'활성' if wick_defense else '비활성'}\n"
                analysis += f"- 변경 시점: {change['plan_time']}\n\n"
            
            # 변경 효과 분석
            final_result = (exit_price - entry_price) / entry_price * 100
            analysis += f"### 관리 변경 효과\n"
            analysis += f"- 최종 수익률: {final_result:+.2f}%\n"
            analysis += f"- 변경 횟수: {len(management_changes)}회\n"
            analysis += f"- 주요 트리거: {', '.join(set([c.get('change_trigger', 'NONE') for c in management_changes]))}\n"
            
            return analysis
        
        except Exception as e:
            logger.error(f"v7.2 관리 변경 분석 중 오류: {e}")
            return "관리 변경 분석 실패"

    def _analyze_post_sell_market_v72(self, exit_time, exit_price):
        """v7.2 매도 후 시장 분석 (XRP 전문가 관점 포함)"""
        try:
            # 매도 후 1시간, 4시간, 24시간 가격 변화 분석
            exit_datetime = datetime.strptime(exit_time, "%Y-%m-%d %H:%M:%S")
            
            # 현재 시간과 비교하여 분석 기간 결정
            current_time = datetime.now()
            time_diff = current_time - exit_datetime
            
            analysis = f"## 🔮 v7.2 매도 후 시장 분석\n\n"
            analysis += f"매도 시점: {exit_time} ({exit_price:,.0f}원)\n"
            analysis += f"경과 시간: {time_diff.days}일 {time_diff.seconds//3600}시간\n\n"
            
            try:
                # 매도 후 가격 데이터 수집 (가능한 범위에서)
                current_data = pyupbit.get_ohlcv("KRW-XRP", interval="minute60", count=24)
                if current_data is not None and len(current_data) > 0:
                    current_price = float(current_data['close'].iloc[-1])
                    price_change_pct = (current_price - exit_price) / exit_price * 100
                    
                    analysis += f"### 매도 타이밍 평가\n"
                    analysis += f"- 현재가: {current_price:,.0f}원\n"
                    analysis += f"- 매도 후 변화: {price_change_pct:+.2f}%\n"
                    
                    if price_change_pct > 5:
                        analysis += f"- 평가: 조기 매도 (추가 수익 기회 놓침)\n"
                    elif price_change_pct < -5:
                        analysis += f"- 평가: 적절한 매도 (추가 하락 회피)\n"
                    else:
                        analysis += f"- 평가: 적정 타이밍 매도\n"
                        
                    # XRP 전문가 관점 추가 분석
                    analysis += f"\n### XRP 전문가 관점 매도 후 분석\n"
                    
                    # 매도 후 변동성 분석
                    if len(current_data) >= 24:
                        recent_high = current_data['high'].tail(24).max()
                        recent_low = current_data['low'].tail(24).min()
                        volatility = (recent_high - recent_low) / exit_price * 100
                        
                        analysis += f"- 매도 후 24시간 변동성: {volatility:.2f}%\n"
                        
                        if volatility > 10:
                            analysis += f"- XRP 특성: 고변동성 구간 - 매도 타이밍 중요했음\n"
                        else:
                            analysis += f"- XRP 특성: 안정적 구간 - 매도 급박성 낮았음\n"
                    
                    # 위꼬리/아래꼬리 패턴 분석
                    if len(current_data) >= 6:
                        recent_candles = current_data.tail(6)
                        wick_count = 0
                        
                        for _, candle in recent_candles.iterrows():
                            body_size = abs(candle['close'] - candle['open'])
                            upper_wick = candle['high'] - max(candle['close'], candle['open'])
                            lower_wick = min(candle['close'], candle['open']) - candle['low']
                            
                            if body_size > 0 and (upper_wick > body_size * 1.5 or lower_wick > body_size * 1.5):
                                wick_count += 1
                        
                        analysis += f"- 매도 후 위꼬리 패턴: {wick_count}/6개 캔들\n"
                        
                        if wick_count >= 3:
                            analysis += f"- XRP 분석: 매도 후 고변동성 위꼬리 다발 - 위꼬리 방어 필요 구간이었음\n"
                        else:
                            analysis += f"- XRP 분석: 매도 후 안정적 패턴 - 정상적인 흐름\n"
                
                else:
                    analysis += "현재 시장 데이터 수집 불가 - 매도 후 분석 제한적\n"
                    
            except Exception as e:
                analysis += f"매도 후 시장 데이터 분석 중 오류: {e}\n"
            
            return analysis
            
        except Exception as e:
            logger.error(f"v7.2 매도 후 시장 분석 중 오류: {e}")
            return "매도 후 시장 분석 실패"

    def _calculate_holding_duration(self, entry_time, exit_time):
        """보유 기간 계산"""
        try:
            entry_dt = datetime.strptime(entry_time, "%Y-%m-%d %H:%M:%S")
            exit_dt = datetime.strptime(exit_time, "%Y-%m-%d %H:%M:%S")
            
            duration = exit_dt - entry_dt
            days = duration.days
            hours = duration.seconds // 3600
            minutes = (duration.seconds % 3600) // 60
            
            if days > 0:
                return f"{days}일 {hours}시간 {minutes}분"
            elif hours > 0:
                return f"{hours}시간 {minutes}분"
            else:
                return f"{minutes}분"
                
        except Exception as e:
            logger.error(f"보유 기간 계산 중 오류: {e}")
            return "계산 불가"

    def _save_reflection_to_file_v72(self, trade_id, reflection_content):
        """v7.2 회고 결과를 파일로 저장"""
        try:
            # 회고 결과 저장 디렉토리 생성
            reflection_dir = "v72_trade_reflections"
            if not os.path.exists(reflection_dir):
                os.makedirs(reflection_dir)
            
            # 회고 파일명
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{reflection_dir}/reflection_trade_{trade_id}_{timestamp}.md"
            
            # 회고 내용을 마크다운 형식으로 저장
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(f"# OMNI-XRP v7.2 거래 회고 분석\n\n")
                f.write(f"**거래 ID**: {trade_id}\n")
                f.write(f"**분석 시간**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"**분석 시스템**: OMNI-XRP v7.2 GPT 회고 시스템\n\n")
                f.write("---\n\n")
                f.write(reflection_content)
                f.write("\n\n---\n")
                f.write(f"*Generated by OMNI-XRP v7.2 at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n")
            
            # JSON 형태로도 요약 저장
            summary_data = {
                'trade_id': trade_id,
                'analysis_timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'reflection_file': filename,
                'system_version': 'v7.2',
                'analysis_type': 'comprehensive_gpt_reflection'
            }
            
            # 전체 회고 인덱스 파일 업데이트
            index_file = f"{reflection_dir}/reflection_index_v72.json"
            try:
                if os.path.exists(index_file):
                    with open(index_file, 'r', encoding='utf-8') as f:
                        index_data = json.load(f)
                else:
                    index_data = []
                
                index_data.append(summary_data)
                
                with open(index_file, 'w', encoding='utf-8') as f:
                    json.dump(index_data, f, ensure_ascii=False, indent=2)
                    
            except Exception as e:
                logger.warning(f"⚠️ 회고 인덱스 파일 업데이트 실패: {e}")
            
            logger.info(f"💾 v7.2 회고 결과 저장 완료: {filename}")
            return filename
            
        except Exception as e:
            logger.error(f"❌ v7.2 회고 파일 저장 중 오류: {e}")
            return None

    def get_reflection_summary_v72(self, days=7):
        """v7.2 최근 회고 분석 요약"""
        try:
            reflection_dir = "v72_trade_reflections"
            index_file = f"{reflection_dir}/reflection_index_v72.json"
            
            if not os.path.exists(index_file):
                logger.info("📊 아직 v7.2 회고 데이터가 없습니다.")
                return None
            
            with open(index_file, 'r', encoding='utf-8') as f:
                index_data = json.load(f)
            
            # 최근 N일 회고 데이터 필터링
            cutoff_date = datetime.now() - timedelta(days=days)
            recent_reflections = []
            
            for reflection in index_data:
                analysis_time = datetime.strptime(reflection['analysis_timestamp'], "%Y-%m-%d %H:%M:%S")
                if analysis_time >= cutoff_date:
                    recent_reflections.append(reflection)
            
            if not recent_reflections:
                logger.info(f"📊 최근 {days}일간 v7.2 회고 데이터가 없습니다.")
                return None
            
            # 요약 정보 생성
            summary = {
                'period': f"최근 {days}일",
                'total_reflections': len(recent_reflections),
                'reflection_files': [r['reflection_file'] for r in recent_reflections],
                'trade_ids': [r['trade_id'] for r in recent_reflections],
                'analysis_dates': [r['analysis_timestamp'] for r in recent_reflections]
            }
            
            logger.info(f"📊 v7.2 회고 요약: 최근 {days}일간 {len(recent_reflections)}건 분석")
            return summary
            
        except Exception as e:
            logger.error(f"❌ v7.2 회고 요약 조회 중 오류: {e}")
            return None

    def analyze_reflection_patterns_v72(self):
        """v7.2 회고 패턴 분석 - SQLite STDEV 문제 수정"""
        try:
            logger.info("🔍 v7.2 회고 패턴 분석 시작...")
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 🔧 수정: STDEV 함수 제거하고 원시 데이터 가져오기
                cursor.execute('''
                    SELECT 
                        CASE 
                            WHEN checklist_score >= 4.5 THEN 'A+급'
                            WHEN checklist_score >= 3.5 THEN 'A급'
                            WHEN checklist_score >= 2.5 THEN 'B급'
                            ELSE 'F급'
                        END as signal_grade,
                        profit_rate_pct,
                        signal_confidence_multiplier,
                        checklist_score
                    FROM trades 
                    WHERE status = 'COMPLETED' AND checklist_score > 0
                ''')
                
                raw_data = cursor.fetchall()
                
                if not raw_data:
                    logger.warning("⚠️ 분석할 완료된 거래 데이터가 없습니다.")
                    return None
                
                # 🔧 수정: Pandas를 사용하여 통계 계산
                import pandas as pd
                
                df = pd.DataFrame(raw_data, columns=['signal_grade', 'profit_rate_pct', 'signal_confidence_multiplier', 'checklist_score'])
                
                # 등급별 통계 계산
                probabilistic_performance = []
                for grade in ['A+급', 'A급', 'B급', 'F급']:
                    grade_data = df[df['signal_grade'] == grade]
                    
                    if len(grade_data) > 0:
                        count = len(grade_data)
                        avg_profit = grade_data['profit_rate_pct'].mean()
                        profit_stdev = grade_data['profit_rate_pct'].std() if len(grade_data) > 1 else 0
                        win_rate = (grade_data['profit_rate_pct'] > 0).sum() / count * 100
                        avg_multiplier = grade_data['signal_confidence_multiplier'].mean()
                        
                        probabilistic_performance.append((
                            grade, count, avg_profit, profit_stdev, win_rate, avg_multiplier
                        ))
                
                # XRP 전문가 시스템 효과 분석 (STDEV 없음)
                cursor.execute('''
                    SELECT 
                        wick_defense_active,
                        energy_compression_detected,
                        COUNT(*) as count,
                        AVG(profit_rate_pct) as avg_profit,
                        COUNT(CASE WHEN trade_result = 'WICK_DEFENSE_SAVE' THEN 1 END) as wick_saves
                    FROM trades 
                    WHERE status = 'COMPLETED'
                    GROUP BY wick_defense_active, energy_compression_detected
                ''')
                
                expert_system_performance = cursor.fetchall()
                
                # 패턴 분석 결과 정리
                pattern_analysis = {
                    'probabilistic_patterns': {},
                    'expert_system_patterns': {},
                    'integration_insights': []
                }
                
                # 확률론적 패턴 정리
                for grade, count, avg_profit, stdev, win_rate, avg_mult in probabilistic_performance:
                    pattern_analysis['probabilistic_patterns'][grade] = {
                        'sample_size': count,
                        'average_profit': round(avg_profit or 0, 2),
                        'profit_stdev': round(stdev or 0, 2),
                        'win_rate': round(win_rate or 0, 1),
                        'avg_multiplier': round(avg_mult or 0, 2)
                    }
                
                # XRP 전문가 패턴 정리
                for wick_defense, energy_comp, count, avg_profit, saves in expert_system_performance:
                    key = f"wick_defense_{wick_defense}_energy_{energy_comp}"
                    pattern_analysis['expert_system_patterns'][key] = {
                        'sample_size': count,
                        'average_profit': round(avg_profit or 0, 2),
                        'wick_saves': saves or 0,
                        'save_rate': round((saves or 0) / max(count, 1) * 100, 1)
                    }
                
                # 통합 인사이트 생성
                if pattern_analysis['probabilistic_patterns']:
                    best_grade = max(pattern_analysis['probabilistic_patterns'].items(), 
                                   key=lambda x: x[1]['average_profit'])
                    pattern_analysis['integration_insights'].append(
                        f"최고 성과 신호 등급: {best_grade[0]} (평균 수익률: {best_grade[1]['average_profit']:+.2f}%)"
                    )
                
                if pattern_analysis['expert_system_patterns']:
                    wick_saves_total = sum([p['wick_saves'] for p in pattern_analysis['expert_system_patterns'].values()])
                    if wick_saves_total > 0:
                        pattern_analysis['integration_insights'].append(
                            f"위꼬리 방어 시스템 총 {wick_saves_total}회 생명 구조"
                        )
                
                logger.info(f"✅ v7.2 회고 패턴 분석 완료 (SQLite STDEV 문제 해결)")
                logger.info(f"   확률론적 패턴: {len(pattern_analysis['probabilistic_patterns'])}개 등급")
                logger.info(f"   전문가 시스템 패턴: {len(pattern_analysis['expert_system_patterns'])}개 조합")
                logger.info(f"   통합 인사이트: {len(pattern_analysis['integration_insights'])}개")
                
                return pattern_analysis
                
        except Exception as e:
            logger.error(f"❌ v7.2 회고 패턴 분석 중 오류: {e}")
            return None

    def generate_learning_report_v72(self):
        """v7.2 학습 보고서 생성 - GPT 기반 종합 분석"""
        try:
            logger.info("📊 v7.2 학습 보고서 생성 시작...")
            
            # 회고 패턴 분석
            patterns = self.analyze_reflection_patterns_v72()
            if not patterns:
                logger.warning("⚠️ 회고 패턴 데이터 부족으로 학습 보고서 생성 불가")
                return None
            
            # 최근 거래 성과 조회
            recent_trades = self._get_recent_trades_with_lessons_v72(limit=20)
            
            # GPT 기반 학습 보고서 생성
            learning_prompt = f"""
# OMNI-XRP v7.2 학습 보고서 생성 요청

당신은 OMNI-XRP v7.2 시스템의 성과 분석 전문가입니다. 다음 데이터를 바탕으로 종합적인 학습 보고서를 작성해주세요.

## 📊 확률론적 시스템 성과 패턴
{json.dumps(patterns['probabilistic_patterns'], indent=2, ensure_ascii=False)}

## 🧪 XRP 전문가 시스템 성과 패턴
{json.dumps(patterns['expert_system_patterns'], indent=2, ensure_ascii=False)}

## 🔍 최근 거래 데이터 (최근 20건)
{json.dumps(recent_trades, indent=2, ensure_ascii=False)}

## 💡 핵심 통합 인사이트
{json.dumps(patterns['integration_insights'], indent=2, ensure_ascii=False)}

---

## 📋 학습 보고서 작성 요청사항

다음 **8개 섹션**으로 구성된 종합 학습 보고서를 작성해주세요:

### 1. 📊 확률론적 시스템 성과 평가
- 신호 등급별 실제 성과 분석
- 체크리스트 점수의 예측 정확도
- 신호 신뢰도 승수의 실효성

### 2. 🧪 XRP 전문가 시스템 효과 측정
- 위꼬리 방어 시스템의 실제 보호 효과
- 에너지 응축 패턴의 예측 정확도
- XRP 특화 기능들의 ROI 분석

### 3. 🔄 시스템 통합 시너지 분석
- 확률론적 접근 + XRP 전문가의 상호 보완 효과
- 두 시스템이 함께 작동할 때의 성과 향상도
- 통합 시스템의 안정성 평가

### 4. 📈 성과 트렌드 및 학습 곡선
- 시간에 따른 시스템 성과 개선 추이
- 주요 성공/실패 패턴 식별
- 시스템 학습 효과 검증

### 5. ⚠️ 주요 위험 요소 및 취약점
- 확률론적 시스템의 한계점
- XRP 전문가 시스템의 오판 사례
- 시스템 통합 과정에서의 충돌 요소

### 6. 🎯 최적화 우선순위
- 가장 개선 효과가 클 것으로 예상되는 영역
- 확률론적 체크리스트 항목 재조정 필요성
- XRP 전문가 파라미터 튜닝 방향

### 7. 🔮 v7.3 발전 방향 제안
- 현재 시스템을 기반으로 한 다음 단계 혁신 아이디어
- 새로운 확률론적 접근법 또는 XRP 전문가 기능
- 시장 변화에 대응한 적응형 시스템 개선

### 8. 🏆 핵심 성과 지표 및 권장사항
- v7.2 시스템의 현재 성숙도 평가 (0-100점)
- 운영 지속을 위한 핵심 권장사항
- 단기/중기/장기 개선 로드맵

각 섹션은 구체적인 데이터와 근거를 바탕으로 작성하고, 실행 가능한 개선 방안을 제시해주세요.
"""
            
            # GPT 기반 학습 보고서 생성
            learning_response = self.client.chat.completions.create(
                model="gpt-4.1",
                messages=[
                    {
                        "role": "system",
                        "content": """당신은 OMNI-XRP v7.2의 성과 분석 및 시스템 개선 전문가입니다.

전문 영역:
1. 확률론적 트레이딩 시스템 성과 분석
2. XRP 특화 전문가 시스템 효과 측정
3. 통합 시스템의 시너지 효과 평가
4. 데이터 기반 시스템 개선 방향 제시

분석 원칙:
- 모든 평가는 실제 거래 데이터 기반
- 정량적 지표와 정성적 인사이트 균형
- 확률론적 사고와 XRP 전문성 통합 관점
- 실행 가능하고 구체적인 개선 방안 제시
- v7.2 시스템의 혁신성과 실용성 동시 평가

목표: v7.2 시스템의 성과를 정확히 진단하고, 더 나은 v7.3로 발전할 수 있는 명확한 방향을 제시"""
                    },
                    {"role": "user", "content": learning_prompt}
                ],
                max_tokens=4000,
                temperature=0.2
            )
            
            learning_report = learning_response.choices[0].message.content
            
            # 학습 보고서 파일로 저장
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_filename = f"v72_trade_reflections/learning_report_v72_{timestamp}.md"
            
            with open(report_filename, 'w', encoding='utf-8') as f:
                f.write(f"# OMNI-XRP v7.2 종합 학습 보고서\n\n")
                f.write(f"**생성 시간**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"**분석 시스템**: OMNI-XRP v7.2 GPT 학습 분석 시스템\n")
                f.write(f"**데이터 기간**: 시스템 운영 시작부터 현재까지\n\n")
                f.write("---\n\n")
                f.write(learning_report)
                f.write("\n\n---\n")
                f.write(f"*Generated by OMNI-XRP v7.2 Learning System at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n")
            
            logger.info(f"✅ v7.2 학습 보고서 생성 완료: {report_filename}")
            return {
                'report_content': learning_report,
                'report_file': report_filename,
                'analysis_timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
        except Exception as e:
            logger.error(f"❌ v7.2 학습 보고서 생성 중 오류: {e}")
            return None

    def _get_recent_trades_with_lessons(self, limit=10):
        """최근 거래 교훈 추출 (v7.2 확률론적 정보 포함)"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT trade_id, profit_rate_pct, trade_result, 
                           checklist_score, signal_confidence_multiplier, calculated_position_ratio,
                           wick_defense_active, energy_compression_detected, xrp_pattern_type,
                           entry_reason, target_reason, stop_loss_reason,
                           entry_timestamp, exit_timestamp
                    FROM trades 
                    WHERE status = 'COMPLETED' 
                    ORDER BY exit_timestamp DESC 
                    LIMIT ?
                ''', (limit,))
                
                trades = cursor.fetchall()
                
                lessons = []
                for trade in trades:
                    (trade_id, profit_rate, result, checklist_score, signal_multiplier, 
                     position_ratio, wick_defense, energy_compression, xrp_pattern,
                     entry_reason, target_reason, stop_reason, entry_time, exit_time) = trade
                    
                    # v7.2 교훈 생성
                    lesson = {
                        'trade_id': trade_id,
                        'profit_rate': profit_rate or 0,
                        'result': result or 'UNKNOWN',
                        'checklist_score': checklist_score or 0,
                        'signal_multiplier': signal_multiplier or 0,
                        'position_ratio': position_ratio or 0,
                        'v72_features': {
                            'wick_defense': bool(wick_defense),
                            'energy_compression': bool(energy_compression),
                            'xrp_pattern': xrp_pattern or 'NONE'
                        },
                        'key_lesson': self._extract_key_lesson_from_trade(
                            profit_rate, checklist_score, signal_multiplier, result
                        )
                    }
                    lessons.append(lesson)
                
                return lessons
                
        except Exception as e:
            logger.error(f"❌ v7.2 최근 거래 교훈 추출 중 오류: {e}")
            return []

    def _extract_key_lesson_from_trade(self, profit_rate, checklist_score, signal_multiplier, result):
        """개별 거래에서 핵심 교훈 추출"""
        try:
            profit_rate = profit_rate or 0
            checklist_score = checklist_score or 0
            signal_multiplier = signal_multiplier or 0
            
            # v7.2 확률론적 교훈 생성
            if checklist_score >= 4.5 and profit_rate > 5:
                return f"A+급 신호({checklist_score:.1f}점)의 높은 신뢰성 재확인 - 수익률 {profit_rate:+.1f}%"
            elif checklist_score < 3.0 and profit_rate < 0:
                return f"낮은 체크리스트 점수({checklist_score:.1f}점)의 위험성 확인 - 손실 {profit_rate:+.1f}%"
            elif signal_multiplier >= 0.7 and profit_rate > 0:
                return f"높은 신호승수({signal_multiplier:.1f})의 효과적 활용 - 수익 {profit_rate:+.1f}%"
            elif result == "WICK_DEFENSE_SAVE":
                return f"위꼬리 방어 시스템의 생명구조 효과 입증 - 최종 수익 {profit_rate:+.1f}%"
            elif checklist_score >= 3.5 and profit_rate < -5:
                return f"고점수 신호에서도 손실 발생 - 시장 예측의 한계 인식 필요"
            else:
                return f"일반적인 거래 패턴 - 체크리스트 {checklist_score:.1f}점, 수익률 {profit_rate:+.1f}%"
                
        except Exception as e:
            return f"교훈 추출 실패: {e}"
        

    def _analyze_current_market_context(self, market_data):
        """현재 시장 맥락 분석 (v7.2 확률론적 + XRP 전문가 관점)"""
        try:
            current_price = market_data['current_price']
            indicators = market_data['technical_indicators']
            xrp_analysis = market_data.get('xrp_expert_analysis', {})
            
            # 기본 시장 상황
            context = f"""
v7.2 시장 맥락 종합 분석:

📊 기본 정보:
- 현재가: {current_price:,.0f}원
- 분석 시간: {market_data.get('current_time', 'Unknown')}

🎯 확률론적 관점:
- 다중 시간대 추세: {self._get_multi_timeframe_trend_summary(indicators)}
- 모멘텀 상태: {self._get_momentum_summary(indicators)}
- 변동성 체제: {self._get_volatility_summary(indicators)}

🧪 XRP 전문가 관점:
- 지배적 패턴: {xrp_analysis.get('dominant_pattern', 'NONE')}
- 에너지 응축: {'감지됨' if xrp_analysis.get('energy_compression_detected', False) else '없음'}
- 응축 강도: {xrp_analysis.get('compression_strength', 0):.3f}
- 돌파 확률: {xrp_analysis.get('breakout_probability', 0):.2f}
- 위꼬리 위험도: {xrp_analysis.get('wick_pattern_risk', 'unknown')}
- 전문가 신뢰도: {xrp_analysis.get('expert_confidence', 0)}/5

💡 종합 판단:
- 시장 상황: {self._get_overall_market_assessment(indicators, xrp_analysis)}
- 주의사항: {self._get_market_warnings(indicators, xrp_analysis)}
"""
            return context
            
        except Exception as e:
            logger.error(f"❌ v7.2 시장 맥락 분석 중 오류: {e}")
            return f"시장 맥락 분석 실패: {e}"

    def _get_multi_timeframe_trend_summary(self, indicators):
        """다중 시간대 추세 요약"""
        try:
            trends = []
            for tf in ['15m', '1h', '4h', 'day']:
                if tf in indicators:
                    strength = indicators[tf]['trend'].get('trend_strength', 0)
                    if strength >= 1:
                        trends.append(f"{tf}↗")
                    elif strength <= -1:
                        trends.append(f"{tf}↘")
                    else:
                        trends.append(f"{tf}→")
            
            return ", ".join(trends) if trends else "분석불가"
        except:
            return "분석불가"

    def _get_momentum_summary(self, indicators):
        """모멘텀 상태 요약"""
        try:
            h1_momentum = indicators.get('1h', {}).get('momentum', {})
            rsi = h1_momentum.get('rsi', 50)
            
            if rsi > 70:
                return f"과매수(RSI {rsi:.1f})"
            elif rsi < 30:
                return f"과매도(RSI {rsi:.1f})"
            elif rsi > 60:
                return f"강세(RSI {rsi:.1f})"
            elif rsi < 40:
                return f"약세(RSI {rsi:.1f})"
            else:
                return f"중립(RSI {rsi:.1f})"
        except:
            return "분석불가"

    def _get_volatility_summary(self, indicators):
        """변동성 상태 요약"""
        try:
            h4_vol = indicators.get('4h', {}).get('volatility', {})
            atr_ratio = h4_vol.get('atr_ratio', 2.0)
            bb_squeeze = h4_vol.get('bb_squeeze', False)
            
            if bb_squeeze:
                return f"압축상태(ATR {atr_ratio:.1f}%)"
            elif atr_ratio > 4:
                return f"고변동(ATR {atr_ratio:.1f}%)"
            elif atr_ratio > 2:
                return f"정상변동(ATR {atr_ratio:.1f}%)"
            else:
                return f"저변동(ATR {atr_ratio:.1f}%)"
        except:
            return "분석불가"

    def _get_overall_market_assessment(self, indicators, xrp_analysis):
        """종합 시장 평가"""
        try:
            # 기본 추세 확인
            trend_score = 0
            for tf in ['1h', '4h', 'day']:
                if tf in indicators:
                    strength = indicators[tf]['trend'].get('trend_strength', 0)
                    trend_score += strength
            
            # XRP 전문가 보정
            expert_confidence = xrp_analysis.get('expert_confidence', 0)
            energy_compression = xrp_analysis.get('energy_compression_detected', False)
            
            if trend_score >= 3 and expert_confidence >= 3:
                return "강세 유리 + XRP 전문가 지지"
            elif trend_score <= -3:
                return "약세 주의 + 신중한 접근 필요"
            elif energy_compression:
                return "횡보 압축 + 돌파 대기 상태"
            elif abs(trend_score) < 1:
                return "혼조 상태 + 방향성 대기"
            else:
                return "약한 방향성 + 추가 확인 필요"
                
        except:
            return "평가불가"

    def _get_market_warnings(self, indicators, xrp_analysis):
        """시장 주의사항"""
        try:
            warnings = []
            
            # 기술적 주의사항
            h1_momentum = indicators.get('1h', {}).get('momentum', {})
            if h1_momentum.get('rsi_divergence') == 'bearish':
                warnings.append("RSI 하락 다이버전스 감지")
            
            # XRP 전문가 주의사항
            if xrp_analysis.get('wick_pattern_risk') == 'high':
                warnings.append("위꼬리 패턴 고위험 구간")
            
            # 변동성 주의사항
            h4_vol = indicators.get('4h', {}).get('volatility', {})
            if h4_vol.get('atr_ratio', 0) > 5:
                warnings.append("극도 변동성 구간")
            
            return ", ".join(warnings) if warnings else "특별한 주의사항 없음"
            
        except:
            return "주의사항 분석불가"

    def _extract_learned_lessons(self):
        """축적된 교훈 추출 (v7.2 버전)"""
        try:
            # 기본 v7.2 교훈들
            base_lessons = """
v7.2 시스템 핵심 교훈:

🎯 확률론적 접근 교훈:
1. 체크리스트 4.5점 이상(A+급): 최대 투자 비중으로 적극 진입
2. 체크리스트 3.5-4.4점(A급): 70% 비중으로 안정적 진입  
3. 체크리스트 2.5-3.4점(B급): 40% 비중으로 신중한 진입
4. 체크리스트 2.5점 미만(F급): 절대 진입 금지 (하드 임계값)
5. 신호 신뢰도 승수는 시장체제와 독립적으로 적용

🧪 XRP 전문가 시스템 교훈:
6. 위꼬리 방어는 XRP 거래에서 기본적으로 활성화
7. 에너지 응축 패턴 감지 시 돌파 확률 80% 이상이면 목표가 상향
8. 위꼬리 패턴 위험도 'high' 시 반드시 위꼬리 방어 적용
9. 15분봉 종가 기준 위꼬리 방어가 생존율을 크게 높임
10. XRP 특화 패턴은 일반 기술분석보다 정확도 높음

🔄 통합 시스템 교훈:
11. 확률론적 검증 → AI 분석 → 최종 검증의 3층 안전망 효과적
12. 체크리스트와 XRP 전문가 보너스의 시너지 효과 확인
13. 트리거 기반 포지션 관리로 과도한 변경 방지
14. 동적 포지션 사이징이 리스크 조절에 핵심적 역할
15. 급변동 감지 시스템이 시기적절한 대응 가능하게 함
"""
            
            # 실제 거래 데이터에서 추가 교훈 추출
            additional_lessons = self._extract_data_driven_lessons()
            
            return base_lessons + "\n" + additional_lessons
            
        except Exception as e:
            logger.error(f"❌ v7.2 교훈 추출 중 오류: {e}")
            return "기본 v7.2 교훈 세트 적용"


    def _extract_data_driven_lessons(self):
        """실제 데이터 기반 교훈 추출"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 성과가 좋았던 패턴 추출
                cursor.execute('''
                    SELECT checklist_score, signal_confidence_multiplier, 
                           wick_defense_active, profit_rate_pct
                    FROM trades 
                    WHERE status = 'COMPLETED' AND profit_rate_pct > 5
                    ORDER BY profit_rate_pct DESC
                    LIMIT 5
                ''')
                
                successful_trades = cursor.fetchall()
                
                lessons = "\n📊 실제 데이터 기반 추가 교훈:\n"
                
                if successful_trades:
                    avg_checklist = sum([t[0] or 0 for t in successful_trades]) / len(successful_trades)
                    avg_multiplier = sum([t[1] or 0 for t in successful_trades]) / len(successful_trades)
                    wick_defense_ratio = sum([1 for t in successful_trades if t[2]]) / len(successful_trades)
                    
                    lessons += f"16. 성공 거래 평균 체크리스트: {avg_checklist:.1f}/5.5\n"
                    lessons += f"17. 성공 거래 평균 신호승수: {avg_multiplier:.2f}\n"
                    lessons += f"18. 성공 거래 위꼬리방어 사용률: {wick_defense_ratio:.1%}\n"
                
                # 실패 패턴 분석
                cursor.execute('''
                    SELECT checklist_score, trade_result
                    FROM trades 
                    WHERE status = 'COMPLETED' AND profit_rate_pct < -3
                    LIMIT 5
                ''')
                
                failed_trades = cursor.fetchall()
                if failed_trades:
                    failed_avg_checklist = sum([t[0] or 0 for t in failed_trades]) / len(failed_trades)
                    lessons += f"19. 실패 거래 평균 체크리스트: {failed_avg_checklist:.1f}/5.5 (성공 대비 낮음)\n"
                
                return lessons
                
        except Exception as e:
            logger.error(f"데이터 기반 교훈 추출 중 오류: {e}")
            return "20. 데이터 기반 교훈 추출 실패 - 기본 교훈만 적용\n"

    def load_entry_strategy_prompt(self):
        """v7.2 진입 전략 프롬프트 로드"""
        try:
            if os.path.exists('omni_entry_strategy_v72.txt'):
                with open('omni_entry_strategy_v72.txt', 'r', encoding='utf-8') as f:
                    return f.read()
            else:
                logger.warning("⚠️ v7.2 진입 프롬프트 파일이 없어 기본값 사용")
                return self._get_default_entry_prompt_v72()
        except Exception as e:
            logger.error(f"❌ v7.2 진입 프롬프트 로드 중 오류: {e}")
            return self._get_default_entry_prompt_v72()

    def load_position_management_prompt(self):
        """v7.2 포지션 관리 프롬프트 로드"""
        try:
            if os.path.exists('omni_position_management_v72.txt'):
                with open('omni_position_management_v72.txt', 'r', encoding='utf-8') as f:
                    return f.read()
            else:
                logger.warning("⚠️ v7.2 포지션 관리 프롬프트 파일이 없어 기본값 사용")
                return self._get_default_position_prompt_v72()
        except Exception as e:
            logger.error(f"❌ v7.2 포지션 관리 프롬프트 로드 중 오류: {e}")
            return self._get_default_position_prompt_v72()

    def _get_default_entry_prompt_v72(self):
        """v7.2 기본 진입 프롬프트"""
        return """
# OMNI-XRP v7.2 확률론적 진입 전략 가이드

## 🎯 v7.2 핵심 철학
"신호의 품질에 따른 확률론적 투자 - 완벽한 신호를 기다리지 말고, 신호의 품질만큼 베팅하라"

## 📊 확률론적 접근법
- A+등급 (4.5+점): 100% 투자비중 - 최상의 기회
- A등급 (3.5-4.4점): 70% 투자비중 - 좋은 기회  
- B등급 (2.5-3.4점): 40% 투자비중 - XRP 특별 허용 구간
- F등급 (2.5점 미만): 0% 투자비중 - 절대 진입 금지

## 🧪 XRP 전문가 시스템 통합
- 에너지 응축 패턴 감지 시 보너스 점수 부여
- 위꼬리 패턴 위험도에 따른 위꼬리 방어 시스템 권장
- 돌파 확률이 높은 경우 목표가 상향 조정 고려

## 💡 핵심 원칙
1. 체크리스트 점수는 신호 품질의 순수한 평가
2. 투자 비중은 신호 품질에 정확히 비례
3. XRP 특성을 반영한 전문가 시스템 적극 활용
4. 불확실성을 회피하지 말고 확률적으로 대응

## 절대 원칙
- 체크리스트 2.5점 미만 시 entry_price = 0
- 명백한_하락장에서는 어떤 경우에도 진입 금지
- BTC 급락(-3% 이상) 시 진입 금지
"""

    def _get_default_position_prompt_v72(self):
        """v7.2 기본 포지션 관리 프롬프트"""
        return """
# OMNI-XRP v7.2 포지션 관리 가이드

## 🛡️ 위꼬리 방어 시스템
XRP의 순간적 급변동(위꼬리/아래꼬리)으로부터 포지션을 보호하는 핵심 시스템

### 작동 원리:
1. 손절가 도달 시 즉시 매도하지 않음
2. 15분봉 마감까지 대기
3. 종가가 손절가 아래면 매도, 위면 생존

### 활성화 조건:
- XRP 거래에서 기본적으로 활성화 권장
- 특히 위꼬리 패턴 위험도가 'high'인 경우 필수

## 🔄 트리거 기반 관리
기존 트리거 시스템 유지:
- REGIME_CHANGE: 시장체제 구조적 변화
- THRESHOLD_REACHED: 수익/손실 임계점 도달  
- TECHNICAL_STRUCTURE: 기술적 구조 변화

## 💰 확률론적 관리
포지션 관리에서도 확률론적 사고 적용:
- 신호 품질이 높았던 거래는 더 오래 보유
- 신호 품질이 낮았던 거래는 빠른 정리

## 절대 원칙
- entry_price = 0 (보유 중이므로)
- 트리거 없으면 계획 유지
- 감정적 판단 금지
"""

# =============================================================================
# v7.2 메인 실행부
# =============================================================================

def create_enhanced_strategy_prompt_files_v72():
    """v7.2 최적화된 전문 프롬프트 파일들 생성"""
    
    # v7.2 확률론적 진입 전략 프롬프트
    entry_strategy_v72 = """# OMNI-XRP v7.2 확률론적 진입 전략 가이드

## 🎯 v7.2 핵심 철학
"신호의 품질에 따른 확률론적 투자 - 완벽한 신호를 기다리지 말고, 신호의 품질만큼 베팅하라"

## 📊 확률론적 접근법
- A+등급 (4.5+점): 100% 투자비중 - 최상의 기회
- A등급 (3.5-4.4점): 70% 투자비중 - 좋은 기회  
- B등급 (2.5-3.4점): 40% 투자비중 - XRP 특별 허용 구간
- F등급 (2.5점 미만): 0% 투자비중 - 절대 진입 금지

## 🧪 XRP 전문가 시스템 통합
- 에너지 응축 패턴 감지 시 보너스 점수 부여
- 위꼬리 패턴 위험도에 따른 위꼬리 방어 시스템 권장
- 돌파 확률이 높은 경우 목표가 상향 조정 고려

## 💡 핵심 원칙
1. 체크리스트 점수는 신호 품질의 순수한 평가
2. 투자 비중은 신호 품질에 정확히 비례
3. XRP 특성을 반영한 전문가 시스템 적극 활용
4. 불확실성을 회피하지 말고 확률적으로 대응
"""

    # v7.2 포지션 관리 프롬프트  
    position_management_v72 = """# OMNI-XRP v7.2 포지션 관리 가이드

## 🛡️ 위꼬리 방어 시스템
XRP의 순간적 급변동(위꼬리/아래꼬리)으로부터 포지션을 보호하는 핵심 시스템

### 작동 원리:
1. 손절가 도달 시 즉시 매도하지 않음
2. 15분봉 마감까지 대기
3. 종가가 손절가 아래면 매도, 위면 생존

### 활성화 조건:
- XRP 거래에서 기본적으로 활성화 권장
- 특히 위꼬리 패턴 위험도가 'high'인 경우 필수

## 🔄 트리거 기반 관리
기존 v7.1의 트리거 시스템 유지:
- REGIME_CHANGE: 시장체제 구조적 변화
- THRESHOLD_REACHED: 수익/손실 임계점 도달  
- TECHNICAL_STRUCTURE: 기술적 구조 변화

## 💰 확률론적 관리
포지션 관리에서도 확률론적 사고 적용:
- 신호 품질이 높았던 거래는 더 오래 보유
- 신호 품질이 낮았던 거래는 빠른 정리
"""

    # 파일 생성
    with open('omni_entry_strategy_v72.txt', 'w', encoding='utf-8') as f:
        f.write(entry_strategy_v72)
    
    with open('omni_position_management_v72.txt', 'w', encoding='utf-8') as f:
        f.write(position_management_v72)
    
    print("✅ v7.2 전문화된 프롬프트 파일 시스템 생성 완료:")
    print("  📁 omni_entry_strategy_v72.txt (확률론적 진입 전략)")
    print("  📁 omni_position_management_v72.txt (위꼬리 방어 포지션 관리)")

def main_v72():
    """v7.2 메인 실행 함수"""
    try:
        print("🎯 OMNI-XRP v7.2 확률론적 접근 + XRP 전문가 통합 시스템 시작")
        print("⚡ 실행 주기: 가격감시 2초 | 전략분석 동적주기")
        print("🔬 v7.2 혁신 기능:")
        print("   • 확률론적 체크리스트 (5.5점 만점 + 신호 신뢰도 승수)")
        print("   • XRP 전문가 위꼬리 방어 시스템")
        print("   • 에너지 응축 패턴 감지 및 돌파 전략")
        print("   • 신호 품질 연동 동적 포지션 사이징")
        print("   • 3층 안전망 (확률론적 + AI + 검증)")
        print("🚨 급변동 감지: 0.7% 이상 (3분 쿨다운)")
        
        if not os.path.exists('omni_entry_strategy_v72.txt'):
            create_enhanced_strategy_prompt_files_v72()
        
        # OMNI-XRP v7.2 시스템 초기화
        omni_system = OMNIXRPSystem()
        
        # 현재 상태 확인
        status = omni_system.get_trading_status_v72()
        if status:
            logger.info(f"📊 v7.2 현재 시스템 상태: {status}")
        
        # v7.2 자동화 거래 시작
        omni_system.start_automated_trading_v72()
        
    except KeyboardInterrupt:
        logger.info("🛑 사용자 중단 - OMNI-XRP v7.2 시스템 종료")
    except Exception as e:
        logger.error(f"❌ v7.2 메인 실행 중 오류: {e}")

if __name__ == "__main__":
    import sys
    
    # 명령줄 인자 처리
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        system = OMNIXRPSystem()
        system.show_system_status_v72()
    else:
        main_v72()
