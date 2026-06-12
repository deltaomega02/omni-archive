# ai/gpt_client.py
# AI Client for Trading System - Gemini 2.5 Pro (Phase 1) and GPT-5 (Phase 3)
# FIXED: JSON format requirement for GPT-5 API

import openai
import google.generativeai as genai
import json
import asyncio
import time
from typing import Dict, Any, Optional, List
from config.settings import settings
from datetime import datetime

_gpt_client_instance = None

def get_gpt_client():
    global _gpt_client_instance
    if _gpt_client_instance is None:
        _gpt_client_instance = GPTClient()
    return _gpt_client_instance

class GPTClient:
    def __init__(self):
        openai.api_key = settings.OPENAI_API_KEY
        self.gpt_model = "gpt-5"
        
        # Gemini 2.5 Pro 설정
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.gemini_model = genai.GenerativeModel('gemini-2.5-pro')
        
        # 캐시 관리
        self.response_cache = {}
        self.last_analysis_time = None
    
def create_strategy_phase3(self, 
                            coin_data: Dict[str, Any], 
                            selected_coin: str,
                            analysis: Dict[str, Any] = None) -> Dict[str, Any]:
        
        print(f"\n🤖 GPT-5 자율 전략 수립 (V14: 2-Target): {selected_coin}")
        
        current_price = coin_data.get('current_price', 0)
        
        # indicators.py에서 계산된 정확한 레벨 사용
        key_levels = coin_data.get('key_levels', {})
        if not key_levels:
            h1_data = coin_data.get('minute60_analysis', {})
            key_levels = h1_data.get('key_levels', {})
        
        recent_high = key_levels.get('recent_high', current_price)
        recent_low = key_levels.get('recent_low', current_price)
        price_position = key_levels.get('price_position', 50.0)
        atr = coin_data.get('minute60_analysis', {}).get('indicators', {}).get('atr_14', 0)
        
        print(f"   📊 가격 분석:")
        print(f"      현재가: {current_price:,.0f} KRW")
        print(f"      최근 고점: {recent_high:,.0f} KRW")
        print(f"      최근 저점: {recent_low:,.0f} KRW")
        print(f"      위치: {price_position:.1f}%")
        
        # 오더북 데이터 추출 및 분석
        orderbook_analysis = coin_data.get('orderbook_analysis', {})
        orderbook_context = ""
        
        if orderbook_analysis:
            print(f"\n   📊 오더북 상태:")
            print(f"      스프레드: {orderbook_analysis.get('spread', 0):.3f}%")
            print(f"      매수/매도 비율: {orderbook_analysis.get('bid_ask_ratio', 1):.2f}")
            print(f"      주문 불균형: {orderbook_analysis.get('order_imbalance', 0):+.1f}%")
            print(f"      시장 압력: {orderbook_analysis.get('pressure', 'NEUTRAL')}")
            
            bid_walls = orderbook_analysis.get('bid_walls', [])
            ask_walls = orderbook_analysis.get('ask_walls', [])
            
            if bid_walls:
                print(f"      🧱 매수벽 감지: {len(bid_walls)}개")
                for wall in bid_walls[:2]:
                    print(f"         - {wall['price']:,.0f}원 (평균의 {wall['ratio']:.1f}배)")
            
            if ask_walls:
                print(f"      🧱 매도벽 감지: {len(ask_walls)}개")
                for wall in ask_walls[:2]:
                    print(f"         - {wall['price']:,.0f}원 (평균의 {wall['ratio']:.1f}배)")
            
            pressure = orderbook_analysis.get('pressure', 'NEUTRAL')
            spread = orderbook_analysis.get('spread', 0)
            
            if pressure == 'STRONG_BUY':
                execution_urgency = "HIGH"
                urgency_reason = "강한 매수 압력 감지"
            elif pressure == 'STRONG_SELL':
                execution_urgency = "LOW"
                urgency_reason = "강한 매도 압력 - 대기 권장"
            elif spread > 0.3:
                execution_urgency = "LOW"
                urgency_reason = "넓은 스프레드 - 지정가 권장"
            else:
                execution_urgency = "MEDIUM"
                urgency_reason = "정상 시장 상태"
        else:
            execution_urgency = "MEDIUM"
            urgency_reason = "오더북 데이터 없음"
        
        # Phase 1에서 전달받은 시장 체제 및 분석
        market_regime = analysis.get('market_regime', 'SIDEWAYS') if analysis else 'SIDEWAYS'
        expected_move = analysis.get('expected_move', '2-3%') if analysis else '2-3%'
        confidence = analysis.get('confidence_level', 70) if analysis else 70

        pressure = orderbook_analysis.get('pressure', 'NEUTRAL') if orderbook_analysis else 'NEUTRAL'
        spread = orderbook_analysis.get('spread', 0) if orderbook_analysis else 0

        # Phase 1 분석 결과 활용
        gemini_context = ""
        if analysis:
            gemini_context = f"""
        <phase1_analysis>
        Market Regime: {market_regime}
        Selected Coin: {selected_coin}
        Confidence: {confidence}%
        Expected Move: {expected_move}
        Reasoning: {analysis.get('reasoning', 'N/A') if analysis else 'N/A'}
        </phase1_analysis>"""

        # 오더북 컨텍스트 준비
        if orderbook_analysis:
            orderbook_context = f"""
        # ORDERBOOK ANALYSIS (Real-time)
        - Spread: {orderbook_analysis.get('spread', 0):.3f}% ({orderbook_analysis.get('spread_krw', 0):,.0f} KRW)
        - Buy/Sell Volume Ratio: {orderbook_analysis.get('bid_ask_ratio', 1):.2f}
        - Order Imbalance: {orderbook_analysis.get('order_imbalance', 0):+.1f}%
        - Market Pressure: {orderbook_analysis.get('pressure', 'NEUTRAL')}
        - Best Bid: {orderbook_analysis.get('best_bid', 0):,.0f} KRW
        - Best Ask: {orderbook_analysis.get('best_ask', 0):,.0f} KRW
        - Weighted Mid Price: {orderbook_analysis.get('weighted_mid_price', 0):,.0f} KRW"""
            
            bid_walls = orderbook_analysis.get('bid_walls', [])
            ask_walls = orderbook_analysis.get('ask_walls', [])
            
            if bid_walls:
                orderbook_context += f"\n- Bid Walls Detected: {len(bid_walls)} levels"
                for i, wall in enumerate(bid_walls[:2], 1):
                    orderbook_context += f"\n  Wall {i}: {wall['price']:,.0f} KRW ({wall['ratio']:.1f}x average)"
            
            if ask_walls:
                orderbook_context += f"\n- Ask Walls Detected: {len(ask_walls)} levels"
                for i, wall in enumerate(ask_walls[:2], 1):
                    orderbook_context += f"\n  Wall {i}: {wall['price']:,.0f} KRW ({wall['ratio']:.1f}x average)"
 
        prompt = f"""
# V14: 2-TARGET SCALING OUT STRATEGY - LET WINNERS RUN
You are creating a strategy that maximizes profit while protecting capital using a 2-target system.

# CORE PHILOSOPHY (V14 UPDATE)
- OLD: Single target at first resistance → Cut winners short
- NEW: Split exit (70% safe / 30% runner) → Let winners run
- **Target 1 (70% position)**: Secure quick profit at first resistance
- **Target 2 (30% position)**: Chase big gains with ZERO RISK (stop moves to breakeven)

# CRITICAL INSIGHT
- Problem: We were hitting +2% then immediately selling, missing +5-10% moves
- Solution: After T1 reached → Move stop to entry → Let 30% chase T2 risk-free
- Effect: ONE +10% runner pays for MULTIPLE small losses

{gemini_context}

# CURRENT MARKET DATA
- Coin: {selected_coin}
- Current Price: {current_price:,.0f} KRW
- ATR (1H): {atr:,.0f} KRW ({(atr/current_price*100):.2f}% volatility)
- Recent High: {recent_high:,.0f} KRW
- Recent Low: {recent_low:,.0f} KRW
- Price Position: {price_position:.1f}% (0=low, 100=high)

{orderbook_context}

# ENTRY RULES (UNCHANGED - STILL PRECISE)
Same as before: Buy at support, adjust for orderbook pressure.

### Entry Price Calculation:
- STRONG_BUY pressure: Enter at market (current price)
- BUY pressure: Enter at current -0.1%
- NEUTRAL: Enter at current -0.2%
- SELL pressure: Enter at current -0.3%
- STRONG_SELL: Enter at current -0.5%

# V14: 2-TARGET SYSTEM (CRITICAL CHANGE)

## Target 1 (70% Exit - SAFE MONEY)
**Purpose**: Secure realistic profit quickly
**Calculation**:
```
IF first ask wall exists within 3%:
    Target_1 = wall_price × 0.998  (just below wall)
ELSE:
    Target_1 = Entry + (1.0 * ATR) or Entry + 2.0%, whichever is lower
```
**Logic**: Conservative target to bank profit fast (usually +1.5-2.5%)

## Target 2 (30% Exit - JACKPOT RUNNER)
**Purpose**: Capture explosive moves with ZERO additional risk
**Calculation**:
```
Target_2 = Entry + (2.5 * ATR) OR next major resistance
Minimum: Target_1 + 2.0%
Maximum: Target_1 + 10.0%
```
**Logic**: Aggressive target for big wins. Stop moves to entry after T1, so this 30% trades with NO RISK.

## Why This Works:
**Scenario A (Target 1 reached, then reversal)**:
- 70% exits at +2.0% = +1.4% gain
- 30% exits at breakeven = 0%
- **Total: +1.4%** (same as old system, NO LOSS)

**Scenario B (Target 2 reached - THE JACKPOT)**:
- 70% exits at +2.0% = +1.4% gain
- 30% exits at +8.0% = +2.4% gain
- **Total: +3.8%** (one jackpot wipes out 3-4 losses!)

## STOP LOSS (STILL TIGHT)
- Initial Stop: Entry - 0.8% to -1.0% (same as before)
- **After T1 Reached**: Stop moves to Entry (breakeven protection)

## POSITION SIZING (UNCHANGED)
Same formula as before: 35-90% based on confidence × orderbook × market regime

# REQUIRED JSON OUTPUT (V14 UPDATED)

{{
  "entry_price": [Calculated entry with orderbook adjustment],
  "target_price_1": [70% exit - conservative, below first wall],
  "target_price_2": [30% exit - aggressive, 2.5x ATR or next resistance],
  "target_split_ratio": 0.7,
  "stop_loss_price": [Entry - 0.8-1.0%],
  "position_size_percent": [35-90 with multipliers],
  "reasoning": "Entry: [why]. T1 (70%): [safe target logic]. T2 (30%): [runner target logic]. Stop: [protection]. Position: [size rationale]. Strategy: After T1 → stop moves to entry → T2 trades risk-free."
}}

# EXAMPLE REASONING (V14):

"Entry: 1,020 with SELL pressure, waiting -0.3% at 1,017. T1 (70%): +2.2% at 1,039 just below ask wall at 1,042 - realistic 1-2hr target. T2 (30%): +6.5% at 1,083 (next resistance from recent high) - runner for 4-8hr move. Stop: -0.9% at 1,008 below support. Position: 73%. Strategy: Secure +1.54% with T1, then move stop to 1,017 (breakeven) and let 30% chase +6.5% jackpot with ZERO additional risk. R:R = 1.7 (T1) / 7.2 (T2 if hit)."
"""

        try:
            print("   📡 GPT-5 API 호출 (V14: 2-Target 전략)")
            start_time = time.time()
            
            # GPT-5 Responses API 사용
            response = openai.responses.create(
                model=self.gpt_model,  # "gpt-5"
                input=prompt,
                reasoning={
                    "effort": "medium"
                },
                text={
                    "verbosity": "low",
                    "format": {
                        "type": "json_schema",
                        "name": "trading_strategy_v14",
                        "schema": {
                            "type": "object",
                            "properties": {
                                "entry_price": {"type": "number"},
                                "target_price_1": {"type": "number"},  # V14
                                "target_price_2": {"type": "number"},  # V14
                                "target_split_ratio": {"type": "number", "default": 0.7},  # V14
                                "stop_loss_price": {"type": "number"},
                                "position_size_percent": {
                                    "type": "integer", 
                                    "minimum": 35, 
                                    "maximum": 90
                                },
                                "reasoning": {"type": "string"}
                            },
                            "required": [
                                "entry_price", 
                                "target_price_1",   # V14
                                "target_price_2",   # V14
                                "stop_loss_price", 
                                "position_size_percent", 
                                "reasoning"
                            ],
                            "additionalProperties": False
                        }
                    }
                },
                max_output_tokens=70000
            )
            
            elapsed = time.time() - start_time
            print(f"   ✅ GPT-5 응답 완료 ({elapsed:.1f}초)")
            
            # 응답 파싱
            if not hasattr(response, 'output_text') or not response.output_text:
                print("   ❌ GPT-5 응답에 output_text 없음")
                return {"error": "GPT-5 응답 실패 - output_text 없음"}
            
            try:
                strategy = json.loads(response.output_text)
                print("   ✅ JSON 파싱 성공 (V14)")
            except json.JSONDecodeError as e:
                print(f"   ❌ JSON 파싱 실패: {e}")
                return {"error": f"GPT-5 JSON 파싱 실패: {str(e)}"}
            
            # V14: 2개 목표가 추출
            entry_price = float(strategy.get('entry_price', 0))
            target_price_1 = float(strategy.get('target_price_1', 0))  # V14
            target_price_2 = float(strategy.get('target_price_2', 0))  # V14
            target_split_ratio = float(strategy.get('target_split_ratio', 0.7))  # V14
            stop_loss_price = float(strategy.get('stop_loss_price', 0))
            position_size = int(strategy.get('position_size_percent', 0))
            reasoning = strategy.get('reasoning', '')
            
            # 오더북 기반 가격 미세 조정
            if orderbook_analysis and entry_price > 0:
                if pressure == 'STRONG_BUY':
                    entry_price = min(entry_price, current_price * 1.001)
                elif pressure == 'STRONG_SELL':
                    entry_price = min(entry_price, current_price * 0.995)
                
                # 매도벽 회피 (T1만 조정, T2는 유지)
                if ask_walls:
                    nearest_wall = ask_walls[0]['price']
                    if abs(target_price_1 - nearest_wall) / nearest_wall < 0.005:
                        target_price_1 = nearest_wall * 0.998
                        print(f"   🎯 T1 조정: {target_price_1:,.0f}원 (매도벽 회피)")
            
            # V14: 가격 유효성 검사 (2개 목표가)
            if not (entry_price > 10 and 
                    target_price_1 > entry_price and 
                    target_price_2 > target_price_1 and  # V14: T2 > T1
                    stop_loss_price < entry_price and
                    abs(entry_price - current_price) / current_price < 0.1):
                print(f"   ❌ 가격 검증 실패!")
                print(f"      진입: {entry_price}, T1: {target_price_1}, T2: {target_price_2}, 손절: {stop_loss_price}")
                return {"error": "GPT-5 전략 가격 검증 실패 (V14)"}
            
            # 포지션 크기 검증
            position_size = max(20, min(97, position_size))
            
            # 오더북 압력에 따른 포지션 조정
            if orderbook_analysis:
                if pressure == 'STRONG_BUY' and confidence >= 80:
                    position_size = min(position_size * 1.1, 90)
                    print(f"   💼 포지션 상향: {position_size}% (강한 매수압력)")
                elif pressure == 'STRONG_SELL':
                    position_size = max(position_size * 0.9, 20)
                    print(f"   💼 포지션 하향: {position_size}% (강한 매도압력)")
            
            position_size = int(position_size)
            
            # V14: 혼합 수익률 계산
            expected_return_1 = ((target_price_1 - entry_price) / entry_price) * 100
            expected_return_2 = ((target_price_2 - entry_price) / entry_price) * 100
            blended_return = (expected_return_1 * target_split_ratio) + (expected_return_2 * (1 - target_split_ratio))
            risk_return = ((stop_loss_price - entry_price) / entry_price) * 100
            rr_ratio = abs(blended_return / risk_return) if risk_return != 0 else 0
            
            # V14: 전략 파라미터 (2개 목표가)
            trading_params = {
                "coin_ticker": selected_coin,
                "current_price": current_price,
                "entry_price": entry_price,
                "target_price_1": target_price_1,      # V14
                "target_price_2": target_price_2,      # V14
                "target_split_ratio": target_split_ratio,  # V14
                "stop_loss_price": stop_loss_price,
                "entry_reason": reasoning,
                "target_reason": f"T1: {expected_return_1:.1f}% (70%) / T2: {expected_return_2:.1f}% (30%)",  # V14
                "stop_loss_reason": f"손실 제한 {risk_return:.1f}%",
                "position_size_percent": position_size,
                "execution_urgency": execution_urgency,
                "urgency_reason": urgency_reason
            }
            
            print(f"\n   ✅ GPT-5 자율 전략 완성 (V14)")
            print(f"   💰 진입가: {entry_price:,.0f} KRW")
            print(f"   🎯 목표가 1: {target_price_1:,.0f} KRW (+{expected_return_1:.2f}%) [70% 청산]")  # V14
            print(f"   🚀 목표가 2: {target_price_2:,.0f} KRW (+{expected_return_2:.2f}%) [30% 추격]")  # V14
            print(f"   🛑 손절가: {stop_loss_price:,.0f} KRW")
            print(f"   💼 포지션: {position_size}%")
            print(f"   📈 혼합 수익: +{blended_return:.2f}% (가중평균)")  # V14
            print(f"   📉 리스크: {risk_return:.2f}%")
            print(f"   ⚖️ R:R 비율: 1:{rr_ratio:.1f}")
            print(f"   ⚡ 실행 긴급도: {execution_urgency} ({urgency_reason})")
            
            return {
                "trading_parameters": trading_params,
                "risk_assessment": {
                    "risk_reward_ratio": rr_ratio,
                    "position_size_suggestion": f"{position_size}%",
                    "execution_urgency": execution_urgency,
                    "urgency_reason": urgency_reason,
                    "expected_duration": "hours",
                    "orderbook_quality": "GOOD" if spread < 0.2 else "FAIR" if spread < 0.5 else "POOR"
                }
            }
            
        except openai.APIError as e:
            print(f"   ❌ GPT-5 API 오류: {e}")
            return {"error": f"GPT-5 API 오류: {str(e)}"}
            
        except Exception as e:
            print(f"   ❌ GPT-5 전략 수립 실패: {e}")
            import traceback
            traceback.print_exc()
            return {"error": f"GPT-5 전략 수립 실패: {str(e)}"}

    # Phase 1 Gemini 분석 함수는 그대로 유지
    async def analyze_market_phase1_gemini(self, 
                                          market_data: Dict[str, Any], 
                                          coins_data: Dict[str, Any]) -> Dict[str, Any]:
        
        print("🤖 Gemini 2.5 Pro 자율 분석 시작...")
        start_time = time.time()
        
        # 상위 20개 코인 선택
        top_20_coins = self._select_top_20_coins(coins_data)
        print(f"   📊 분석 대상: {len(top_20_coins)}개 코인")
        
        # 모든 코인 데이터를 하나의 구조화된 JSON으로 구성
        batch_prompt = self._build_unified_analysis_prompt(top_20_coins, market_data)
        
        try:
            print("   🚀 Gemini 2.5 Pro 호출 (자율 판단)")
            
            # Gemini 단일 요청 - 모든 코인 동시 분석
            response = self.gemini_model.generate_content(
                batch_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.2,
                    max_output_tokens=150000,
                    response_mime_type="application/json"
                )
            )
            
            # 응답 파싱
            result = json.loads(response.text)
            elapsed = time.time() - start_time
            
            print(f"✅ Gemini 분석 완료 ({elapsed:.1f}초)")
            
            # 시장 체제 출력
            market_regime = result.get('market_regime', 'SIDEWAYS')
            print(f"\n   🌍 시장 체제: {market_regime}")
            print(f"   📝 시장 개요: {result.get('market_overview', '')}")

            # 분석 결과 처리
            best_coin = result.get('final_selection', {})
            
            if best_coin.get('ticker'):
                print(f"\n   🎯 최종 선정: {best_coin['ticker']}")
                print(f"   💡 판단 근거: {best_coin.get('key_reason', 'AI 자율 판단')}")
                print(f"   🔮 신뢰도: {best_coin.get('confidence', 0)}%")
                print(f"   📈 예상 움직임: {best_coin.get('expected_move', 'N/A')}")
                
                return {
                    "action": "proceed",
                    "selected_coin": best_coin['ticker'],
                    "analysis": best_coin.get('detailed_analysis', {}),
                    "confidence_level": best_coin.get('confidence', 0),
                    "reasoning": best_coin.get('selection_reason', ''),
                    "market_context": result.get('market_overview', ''),
                    "market_regime": market_regime,  # Phase 3로 전달
                    "expected_move": best_coin.get('expected_move', '2-3%'),  # Phase 3로 전달
                    "comparison_matrix": result.get('comparison_matrix', {})
                }
            else:
                # 거래하지 않기로 결정
                wait_reason = result.get('wait_reason', 'No suitable opportunities')
                wait_minutes = self._determine_wait_time_by_regime(market_regime)
                
                print(f"\n   ⏳ 거래 대기 결정 - {wait_minutes}분")
                print(f"   🔍 이유: {wait_reason}")
                
                return {
                    "action": "wait",
                    "reason": wait_reason,
                    "wait_minutes": wait_minutes,
                    "market_overview": result.get('market_overview', ''),
                    "market_regime": market_regime
                }
                
        except Exception as e:
            print(f"   ❌ Gemini 분석 오류: {e}")
            import traceback
            traceback.print_exc()
            
            return {
                "action": "wait",
                "reason": f"분석 오류: {str(e)}",
                "wait_minutes": 30
            }
    
    def _determine_wait_time_by_regime(self, market_regime: str) -> int:
        """시장 체제별 대기 시간 결정"""
        wait_times = {
            'BULL_TREND': 30,     # 활발한 시장, 자주 체크
            'SIDEWAYS': 45,       # 중간 빈도
            'BEAR_TRAP': 90,     # 위험한 시장, 긴 대기
            'KOREAN_PUMP': 20    # 빠른 시장, 자주 체크
        }
        return wait_times.get(market_regime, 30)

    def _build_unified_analysis_prompt(self, coins_data: Dict, market_data: Dict) -> str:
        # 코인 데이터 구조화
        coins_analysis_data = []
        for ticker, data in coins_data.items():
            h1_indicators = data.get('minute60_data', {}).get('indicators', {})
            
            coin_summary = {
                "ticker": ticker,
                "current_price": data.get('current_price', 0),
                "volume_24h_krw": data.get('volume_24h_krw', 0),
                "change_24h": data.get('change_24h', 0),
                "volume_ratio": h1_indicators.get('volume_ratio', 1.0),
                
                "technical_indicators": {
                    "rsi_14": h1_indicators.get('rsi_14', 50),
                    "macd": h1_indicators.get('macd', 0),
                    "macd_signal": h1_indicators.get('macd_signal', 0),
                    "macd_histogram": h1_indicators.get('macd_histogram', 0),
                    "bb_position": h1_indicators.get('bb_position', 50),
                    "adx": h1_indicators.get('adx', 0),
                    "obv_trend": h1_indicators.get('obv_trend', 'NEUTRAL'),
                    "mfi": h1_indicators.get('mfi', 50),
                    "atr_14_pct": h1_indicators.get('atr_14_pct', 0)
                },
                
                "moving_averages": {
                    "sma_50": h1_indicators.get('sma_50', 0),
                    "sma_200": h1_indicators.get('sma_200', 0),
                    "ema_21": h1_indicators.get('ema_21', 0),
                },
                
                "divergences": h1_indicators.get('divergences', {}),
            }
            coins_analysis_data.append(coin_summary)
        
        # BTC 데이터 추출
        btc_data = market_data.get('btc_data', {})
        btc_price = btc_data.get('current_price', 0)
        btc_h1 = btc_data.get('minute60_data', {}).get('indicators', {})
        btc_rsi = btc_h1.get('rsi_14', 50)
        btc_adx = btc_h1.get('adx', 0)
        
        # 현재 시간 체크 (한국 시장 특성)
        current_hour = datetime.now().hour
        time_context = "Korean Peak Hours" if (9 <= current_hour <= 11) or (20 <= current_hour <= 23) else "Normal Hours"
         
        prompt = f"""
# ULTRA-PRECISE BOTTOM HUNTER - HIGH WIN RATE SYSTEM
Your ONLY mission: Find coins at the EXACT moment they're about to bounce for a quick 1-2% gain with 85%+ win rate.

Current Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} KST ({time_context})

# CORE PHILOSOPHY: SMALL & CERTAIN > BIG & RISKY
- Target: 1-2% realistic gains (NOT 3-5%)
- Win Rate Goal: 85%+ (quality over quantity)
- Stop Loss: -1% max (tight and disciplined)
- We DON'T compete with real-time traders who can exit at 2%. We compete with PRECISION entry timing.

# CRITICAL FILTERS (ELIMINATE LOSERS FIRST)

## INSTANT REJECTION CRITERIA:
1. **Already Pumped**: If price is up >2% in last 4 hours → REJECT (we missed it)
2. **Death Spiral**: Consecutive red 1H candles (3+) without support hold → REJECT (falling knife)
3. **Volume Desert**: Current volume <0.5x average → REJECT (no momentum)
4. **BTC Collapse**: If BTC RSI <35 and falling → REJECT ALL (market risk too high)
5. **Fake Bottom**: RSI <30 but no bullish divergence → REJECT (can go lower)

## MANDATORY REQUIREMENTS (ALL MUST BE TRUE):
1. ✓ Price touching or below major support (SMA50/SMA200 or previous swing low)
2. ✓ RSI between 25-40 (oversold but not death zone)
3. ✓ Volume spike visible (1.5x+ recent average, buyers stepping in)
4. ✓ NOT down >5% today (avoid panic selling continuation)
5. ✓ Bullish divergence OR support bounce pattern visible

# STEP 1: MARKET CONTEXT ANALYSIS

## Current BTC Status:
- Price: {btc_price:,.0f} KRW
- RSI (1H): {btc_rsi:.1f}
- ADX (1H): {btc_adx:.1f}

## Market Classification:
- **SAFE** (BTC RSI 45-60, ADX <30): Trade normally, look for 1.5-2% targets
- **CAUTION** (BTC RSI 40-45 or 60-70): Only trade PERFECT setups, target 1-1.5%
- **DANGER** (BTC RSI <40 or >70): 90% of time WAIT. Only trade if 95% confident + divergence present

→ Current Market: [Classify based on above]

# STEP 2: HUNT FOR THE PERFECT BOTTOM

<all_coins_data>
{json.dumps(coins_analysis_data, ensure_ascii=False, indent=2)}
</all_coins_data>

## For Each Coin, Ask:
1. **Is this THE bottom?** (Support hold + RSI oversold + volume spike?)
2. **Can it fall MORE?** (Check: bearish momentum, no support below, panic selling?)
3. **Will it bounce in next 1-4 hours?** (Look: divergence, volume change, time pattern)
4. **Can I get 1.5%+ before it reverses?** (Calculate: ATR, recent volatility, typical bounce size)

## Pattern Priority (High to Low Win Rate):

### 🎯 90%+ Win Rate (BEST):
- **Support Bounce + Bullish Divergence**: RSI making higher low while price makes lower low at major support
- **Volume Capitulation**: Panic selling volume peak (5x+) followed by immediate absorption (buyers stepping in)

### 🎯 80%+ Win Rate (GOOD):
- **Support Test #2-3**: Price returns to support that held once/twice before + RSI 30-40
- **Korean Morning Surge Start**: 9:00-9:30 KST, volume 3x+, price just starting move (<3% up)

### 🎯 70%+ Win Rate (ACCEPTABLE):
- **Bollinger Lower Band Touch**: Price hits BB lower + RSI <35 + volume increase
- **MACD Bullish Cross at Oversold**: MACD crossing signal line while RSI <40

### ⚠️ <60% Win Rate (AVOID):
- Price "looks cheap" but no clear support
- RSI oversold but still falling momentum
- Low volume grind down (no capitulation, can continue)

# STEP 3: CALCULATE REALISTIC EXPECTATION

## Expected Bounce Size Estimation:
- If ATR is 3% → Typical bounce = 1.5-2%
- If ATR is 5% → Typical bounce = 2-3%
- If support is strong → Add 0.3-0.5%
- If volume is huge → Add 0.3-0.5%
- If Korean peak hours → Add 0.2-0.4%

## Risk Calculation:
- Distance to next support below = Max potential loss
- If >2% away from next support → High risk, need 90%+ confidence
- If <1% away from next support → Lower risk, 75%+ confidence OK

# STEP 4: FINAL SELECTION LOGIC

## Decision Tree:
```
IF (BTC in DANGER zone)
  → 95% confidence required to trade
  → ELSE wait
  
IF (No coins pass ALL mandatory requirements)
  → wait_reason: "No clear bottom signals"
  
IF (Multiple coins pass)
  → Pick the one with:
    1. Strongest support level
    2. Clearest volume spike
    3. Best divergence signal
    
IF (Top pick has confidence <75%)
  → wait_reason: "Setup not clear enough"
```

## Confidence Scoring Guide:
- 95%: Perfect divergence + strong support + volume spike + SAFE market
- 85%: 2 of 3 (divergence/support/volume) perfect + SAFE market
- 75%: 1 perfect signal + 2 good signals + CAUTION market
- <75%: Don't trade

# OUTPUT REQUIREMENTS
Return this exact JSON structure:
{{
  "market_overview": "Brief market state (1 sentence)",
  "market_regime": "SAFE|CAUTION|DANGER",
  "top_candidates": [
    {{"ticker": "KRW-XXX", "reason": "WHY this is near bottom"}},
    {{"ticker": "KRW-YYY", "reason": "WHY this is near bottom"}}
  ],
  "final_selection": {{
    "ticker": "KRW-XXX",  // or null if no setup
    "confidence": 85,  // 75-95 ONLY
    "key_reason": "Exact bottom signal type",
    "expected_move": "1.5-2%",  // Be realistic
    "selection_reason": "Why THIS coin will bounce in next 1-4 hours",
    "detailed_analysis": {{
      "technical_setup": "Exact pattern (e.g., 'Support bounce at SMA200 with bullish divergence')",
      "key_indicators": "Specific values (e.g., 'RSI 32→35 turning up, Volume 2.3x, Support at 1,020')",
      "volume_analysis": "Exact volume context (e.g., 'Spike from 50M to 115M in last hour')",
      "risk_factors": ["Specific risk (e.g., 'Next support -2% below at 1,000')"],
      "entry_timing": "IMMEDIATE|WAIT_DIP|WAIT_CONFIRMATION"
    }}
  }},
  "wait_reason": null  // or specific reason (e.g., "No coins at clear support", "BTC too weak", "All coins already bounced >2%")
}}

# FINAL REMINDER
- You're looking for THE EXACT BOTTOM, not "cheap looking" coins
- 1-2% gain with 85% win rate BEATS 5% gain with 50% win rate
- If doubt exists, WAIT. There's always another trade.
- Your job is to MAKE MONEY, not to trade frequently.
- Already up 2%+ in last 4 hours? TOO LATE. Find another.
"""
        return prompt
    
    def _select_top_20_coins(self, coins_data: Dict) -> Dict:
        # 거래량 기준으로 상위 20개 선택
        sorted_coins = sorted(
            coins_data.items(),
            key=lambda x: x[1].get('volume_24h_krw', 0),
            reverse=True
        )
        
        selected = dict(sorted_coins[:20])
        
        # 선택된 코인 목록 출력
        print("\n   📋 분석 대상 20개 코인:")
        coin_names = [ticker.replace('KRW-', '') for ticker in selected.keys()]
        for i in range(0, len(coin_names), 5):
            print(f"      {', '.join(coin_names[i:i+5])}")
        
        return selected
    
    def _determine_wait_time(self) -> int:
        current_hour = datetime.now().hour
        
        # 새벽 시간대 (1-9시): 긴 대기
        if 1 <= current_hour < 9:
            return 120  # 2시간
        # 활발한 시간대: 짧은 대기  
        else:
            return 30  # 30분
    
    def analyze_market_phase1(self, 
                            market_data: Dict[str, Any], 
                            coins_data: Dict[str, Any],
                            memory: Dict[str, str] = None) -> Dict[str, Any]:
        # 동기 래퍼
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                self.analyze_market_phase1_gemini(market_data, coins_data)
            )
            return result
        finally:
            loop.close()
    
    def cleanup(self):
        self.response_cache.clear()
        self.last_analysis_time = None
        print("🧹 AI 클라이언트 정리 완료")