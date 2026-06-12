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
        
        print(f"\n🤖 GPT-5 자율 전략 수립: {selected_coin}")
        
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
        
        # 🆕 오더북 데이터 추출 및 분석
        orderbook_analysis = coin_data.get('orderbook_analysis', {})
        orderbook_context = ""  # 프롬프트용 컨텍스트 (나중에 사용)
        
        if orderbook_analysis:
            print(f"\n   📊 오더북 상태:")
            print(f"      스프레드: {orderbook_analysis.get('spread', 0):.3f}%")
            print(f"      매수/매도 비율: {orderbook_analysis.get('bid_ask_ratio', 1):.2f}")
            print(f"      주문 불균형: {orderbook_analysis.get('order_imbalance', 0):+.1f}%")
            print(f"      시장 압력: {orderbook_analysis.get('pressure', 'NEUTRAL')}")
            
            # 호가벽 정보 출력
            bid_walls = orderbook_analysis.get('bid_walls', [])
            ask_walls = orderbook_analysis.get('ask_walls', [])
            
            if bid_walls:
                print(f"      🧱 매수벽 감지: {len(bid_walls)}개")
                for wall in bid_walls[:2]:  # 상위 2개만 출력
                    print(f"         - {wall['price']:,.0f}원 (평균의 {wall['ratio']:.1f}배)")
            
            if ask_walls:
                print(f"      🧱 매도벽 감지: {len(ask_walls)}개")
                for wall in ask_walls[:2]:  # 상위 2개만 출력
                    print(f"         - {wall['price']:,.0f}원 (평균의 {wall['ratio']:.1f}배)")
            
            # 🆕 오더북 기반 실행 긴급도 조정
            pressure = orderbook_analysis.get('pressure', 'NEUTRAL')
            spread = orderbook_analysis.get('spread', 0)
            
            # 실행 긴급도 결정 로직
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

        # 🔧 프롬프트에서 사용할 변수들 미리 정의
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

        # 오더북 컨텍스트 준비 (프롬프트에서 사용할 예정)
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
            
            # 호가벽 정보 추가
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
# ADAPTIVE STRATEGY ENGINE V9 - WITH ORDERBOOK INTELLIGENCE
You are creating a profit-maximizing strategy that adapts to current market conditions.
Your strategy MUST align with Phase 1's market analysis and incorporate real-time orderbook dynamics.

# CRITICAL CONSTRAINTS
- ONE entry, ONE target, ONE stop-loss (no modifications after setting)
- Position sizing must reflect market conditions, confidence, AND orderbook pressure
- Risk/Reward must be appropriate for the market regime
- Orderbook walls must be considered for entry/exit levels

{gemini_context}

# CURRENT MARKET DATA
- Coin: {selected_coin}
- Current Price: {current_price:,.0f} KRW
- ATR (1H): {atr:,.0f} KRW ({(atr/current_price*100):.2f}% volatility)
- Recent High: {recent_high:,.0f} KRW
- Recent Low: {recent_low:,.0f} KRW
- Price Position: {price_position:.1f}% (0=low, 100=high)

{orderbook_context}

# ORDERBOOK-ADJUSTED STRATEGY RULES

## Entry Optimization Based on Orderbook:
- If STRONG_BUY pressure: Enter immediately at market or current price
- If BUY pressure: Enter at current -0.1% to -0.2%
- If NEUTRAL: Follow regime-based entry rules
- If SELL pressure: Wait for -0.3% to -0.5% below current
- If STRONG_SELL pressure: Wait for -0.5% to -0.7% below current
- If spread > 0.3%: Add 0.1% buffer to entry price

## Target/Stop Adjustment for Walls:
- If ASK WALL detected within 2% of target: Place target just below wall price
- If BID WALL detected within 1% of stop: Place stop just below wall price
- If multiple walls exist: Use the nearest significant wall

## Position Size Modifiers:
- STRONG_BUY pressure: +10% to base position (max cap applies)
- STRONG_SELL pressure: -10% from base position (min 20%)
- Wide spread (>0.3%): -5% from base position
- Narrow spread (<0.1%): +5% to base position

# MARKET-ADAPTIVE STRATEGY RULES

## Strategy by Market Regime:

### IF Market = "BULL_TREND" (Strong Uptrend)
- Entry: Current price or slight pullback (max -0.3%)
  * WITH STRONG_BUY pressure: Immediate entry
  * WITH SELL pressure: Wait for -0.5%
- Target: Current + (1.5 × ATR) or +3.5%, whichever is greater
  * Adjust DOWN if ask wall detected near target
- Stop: Current - (1.0 × ATR), maximum -2.5%
  * Place BELOW nearest bid wall if exists
- Base Position: 65%
- Logic: Ride the trend with confidence

### IF Market = "SIDEWAYS" (Range-bound)
- Entry: 0.3-0.5% below current (wait for better entry)
  * WITH STRONG_BUY pressure: Enter at -0.2%
  * WITH STRONG_SELL pressure: Wait for -0.7%
- Target: Current + (1.0 × ATR) or +2.5%, whichever is greater
  * Check for ask walls and adjust accordingly
- Stop: Current - (1.2 × ATR), maximum -3%
  * Use bid wall as support if available
- Base Position: 45%
- Logic: Buy low, sell high within range

### IF Market = "BEAR_TRAP" (Dangerous/Falling)
- Entry: 0.5-0.7% below current (extra caution)
  * WITH any BUY pressure: Max entry at -0.5%
  * WITH STRONG_SELL: Wait for -1.0%
- Target: Current + (0.7 × ATR) or +1.8%, whichever is greater
  * Conservative target, check ask walls
- Stop: Current - (0.7 × ATR), maximum -2%
  * Tight stop, ignore distant bid walls
- Base Position: 25%
- Logic: Quick scalp only, minimize exposure

### IF Market = "KOREAN_PUMP" (FOMO Rally)
- Entry: Immediate market price
  * WITH STRONG_BUY: Aggressive immediate entry
  * WITH SELL pressure: Still enter but reduce position
- Target: Current + (2.0 × ATR) or +5%, whichever is greater
  * Can be aggressive but respect major ask walls
- Stop: Current - (1.5 × ATR), maximum -3.5%
  * Wider stop for volatility
- Base Position: 55%
- Logic: Capture momentum, but protect downside

## Position Sizing Formula with Orderbook:
Base Position × Confidence Multiplier × Orderbook Multiplier

Confidence Multiplier:
- 95%+ confidence: × 1.3
- 85-94% confidence: × 1.1
- 70-84% confidence: × 1.0
- 60-69% confidence: × 0.8
- <60% confidence: × 0.6

Orderbook Multiplier:
- STRONG_BUY pressure: × 1.1
- BUY pressure: × 1.05
- NEUTRAL: × 1.0
- SELL pressure: × 0.95
- STRONG_SELL pressure: × 0.9

Maximum positions by regime:
- BULL_TREND: 85%
- SIDEWAYS: 60%
- BEAR_TRAP: 35%
- KOREAN_PUMP: 70%

## Risk/Reward Requirements:
- BULL_TREND: Minimum R:R = 1.3
- SIDEWAYS: Minimum R:R = 1.2
- BEAR_TRAP: Minimum R:R = 1.0 (focus on win rate)
- KOREAN_PUMP: Minimum R:R = 1.5

# PSYCHOLOGICAL PRICE LEVELS & ORDERBOOK
Korean traders love round numbers. Adjust targets/stops to:
- Just below resistance/ask walls for targets
- Just below support/bid walls for stops
- If wall price is round number (e.g., 50,000), place order at 49,950

# ENHANCED DECISION LOGIC
1. Identify market regime from Phase 1
2. Analyze orderbook pressure and walls
3. Apply regime strategy with orderbook adjustments
4. Fine-tune entry based on spread and pressure
5. Adjust target/stop for detected walls
6. Calculate final position with all multipliers
7. Verify R:R ratio meets minimum

# EXECUTION RECOMMENDATIONS
- If spread > 0.5%: "Use limit orders only"
- If spread < 0.1%: "Market orders acceptable"
- If STRONG_BUY with narrow spread: "Immediate market buy recommended"
- If ask wall near target: "Consider partial profit at wall"

# REQUIRED JSON OUTPUT
Generate ONLY this JSON incorporating ALL factors:
{{
  "entry_price": [calculated with regime + orderbook rules],
  "target_price": [realistic target avoiding ask walls],
  "stop_loss_price": [protective stop using bid walls],
  "position_size_percent": [20-85 with all multipliers],
  "reasoning": "Market={market_regime}, Orderbook={pressure}, Spread={spread:.3f}%. [Add specific strategy rationale including wall locations]"
}}
"""

        try:
            print("   📡 GPT-5 API 호출 (자율 판단)")
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
                        "name": "trading_strategy",
                        "schema": {
                            "type": "object",
                            "properties": {
                                "entry_price": {"type": "number"},
                                "target_price": {"type": "number"},
                                "stop_loss_price": {"type": "number"},
                                "position_size_ percent": {
                                    "type": "integer", 
                                    "minimum": 25, 
                                    "maximum": 90
                                },
                                "reasoning": {"type": "string"}
                            },
                            "required": [
                                "entry_price", 
                                "target_price", 
                                "stop_loss_price", 
                                "position_size_percent", 
                                "reasoning"
                            ],
                            "additionalProperties": False
                        }
                    }
                },
                max_output_tokens=50000
            )
            
            elapsed = time.time() - start_time
            print(f"   ✅ GPT-5 응답 완료 ({elapsed:.1f}초)")
            
            # 응답 파싱
            if not hasattr(response, 'output_text') or not response.output_text:
                print("   ❌ GPT-5 응답에 output_text 없음")
                return {"error": "GPT-5 응답 실패 - output_text 없음"}
            
            try:
                strategy = json.loads(response.output_text)
                print("   ✅ JSON 파싱 성공")
            except json.JSONDecodeError as e:
                print(f"   ❌ JSON 파싱 실패: {e}")
                return {"error": f"GPT-5 JSON 파싱 실패: {str(e)}"}
            
            # 가격 추출
            entry_price = float(strategy.get('entry_price', 0))
            target_price = float(strategy.get('target_price', 0))
            stop_loss_price = float(strategy.get('stop_loss_price', 0))
            position_size = int(strategy.get('position_size_percent', 0))
            reasoning = strategy.get('reasoning', '')
            
            # 🆕 오더북 기반 가격 미세 조정 (옵션)
            if orderbook_analysis and entry_price > 0:
                # 강한 매수 압력시 즉시 진입
                if pressure == 'STRONG_BUY':
                    entry_price = min(entry_price, current_price * 1.001)  # 현재가 근처로 조정
                # 강한 매도 압력시 더 낮은 진입 대기
                elif pressure == 'STRONG_SELL':
                    entry_price = min(entry_price, current_price * 0.995)  # 0.5% 더 낮게
                
                # 매도벽 근처에 목표가가 있으면 살짝 낮춤
                if ask_walls:
                    nearest_wall = ask_walls[0]['price']
                    if abs(target_price - nearest_wall) / nearest_wall < 0.005:  # 0.5% 이내
                        target_price = nearest_wall * 0.998  # 벽 바로 아래
                        print(f"   🎯 목표가 조정: {target_price:,.0f}원 (매도벽 회피)")
            
            # 가격 유효성 검사
            if not (entry_price > 10 and 
                    target_price > entry_price and 
                    stop_loss_price < entry_price and
                    abs(entry_price - current_price) / current_price < 0.1):
                print(f"   ❌ 가격 검증 실패!")
                print(f"      진입: {entry_price}, 목표: {target_price}, 손절: {stop_loss_price}")
                return {"error": "GPT-5 전략 가격 검증 실패"}
            
            # 포지션 크기 검증
            position_size = max(20, min(97, position_size))
            
            # 🆕 오더북 압력에 따른 포지션 조정
            if orderbook_analysis:
                if pressure == 'STRONG_BUY' and confidence >= 80:
                    position_size = min(position_size * 1.1, 90)  # 10% 증가
                    print(f"   💼 포지션 상향: {position_size}% (강한 매수압력)")
                elif pressure == 'STRONG_SELL':
                    position_size = max(position_size * 0.9, 20)  # 10% 감소
                    print(f"   💼 포지션 하향: {position_size}% (강한 매도압력)")
            
            position_size = int(position_size)
            
            # 수익률 계산
            expected_return = ((target_price - entry_price) / entry_price) * 100
            risk_return = ((stop_loss_price - entry_price) / entry_price) * 100
            rr_ratio = abs(expected_return / risk_return) if risk_return != 0 else 0
            
            # 전략 파라미터 생성
            trading_params = {
                "coin_ticker": selected_coin,
                "current_price": current_price,
                "entry_price": entry_price,
                "target_price": target_price,
                "stop_loss_price": stop_loss_price,
                "entry_reason": reasoning,
                "target_reason": f"목표 수익률 {expected_return:.1f}%",
                "stop_loss_reason": f"손실 제한 {risk_return:.1f}%",
                "position_size_percent": position_size,
                "execution_urgency": execution_urgency,  # 🆕 오더북 기반 긴급도
                "urgency_reason": urgency_reason  # 🆕 긴급도 이유
            }
            
            print(f"\n   ✅ GPT-5 자율 전략 완성")
            print(f"   💰 진입가: {entry_price:,.0f} KRW")
            print(f"   🎯 목표가: {target_price:,.0f} KRW")
            print(f"   🛑 손절가: {stop_loss_price:,.0f} KRW")
            print(f"   💼 포지션: {position_size}%")
            print(f"   📈 예상 수익: +{expected_return:.2f}%")
            print(f"   📉 리스크: {risk_return:.2f}%")
            print(f"   ⚖️ R:R 비율: 1:{rr_ratio:.1f}")
            print(f"   ⚡ 실행 긴급도: {execution_urgency} ({urgency_reason})")  # 🆕
            
            return {
                "trading_parameters": trading_params,
                "risk_assessment": {
                    "risk_reward_ratio": rr_ratio,
                    "position_size_suggestion": f"{position_size}%",
                    "execution_urgency": execution_urgency,  # 🆕 오더북 기반
                    "urgency_reason": urgency_reason,  # 🆕
                    "expected_duration": "hours",
                    "orderbook_quality": "GOOD" if spread < 0.2 else "FAIR" if spread < 0.5 else "POOR"  # 🆕
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
# MARKET-ADAPTIVE PROFIT MAXIMIZER V8
You are analyzing Korean Upbit market to find profitable opportunities while adapting to current market conditions.

Current Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} KST ({time_context})

# STEP 1: MARKET REGIME IDENTIFICATION (MOST CRITICAL)
Analyze market conditions and classify as ONE of these regimes:

## Market Regimes:
1. **BULL_TREND**: BTC rising steadily (RSI 55-70, positive momentum), altcoins following
2. **SIDEWAYS**: BTC flat (RSI 45-55, low ADX <25), altcoins rotating
3. **BEAR_TRAP**: BTC falling (RSI <45) or showing weakness, dangerous market
4. **KOREAN_PUMP**: Specific Korean coins pumping with 5x+ volume (common 9-11am, 8-11pm KST)

## Current BTC Status:
- Price: {btc_price:,.0f} KRW
- RSI (1H): {btc_rsi:.1f}
- ADX (1H): {btc_adx:.1f}
- Conclusion: [Determine regime based on these values]

# STEP 2: STRATEGY SELECTION BY REGIME

## For BULL_TREND → Look for Momentum Continuation
- Strong coins breaking resistance
- RSI 50-65 with room to run
- Volume increasing
- Target: 3-4% realistic gains
- Required confidence: 70%+

## For SIDEWAYS → Look for Mean Reversion
- Oversold bounces (RSI <35)
- Support level bounces
- Volume spike at lows
- Target: 2-3% quick trades
- Required confidence: 65%+

## For BEAR_TRAP → BE VERY SELECTIVE
- Default: WAIT (don't trade)
- Exception: Only perfect oversold bounce with divergence
- Target: 1.5-2% defensive only
- Required confidence: 85%+ to trade

## For KOREAN_PUMP → Ride Early Momentum
- Volume must be 5x+ normal
- Still under +10% move (not too late)
- Korean favorites: SUI, SEI, APT, ONDO, etc.
- Target: 4-6% momentum trades
- Required confidence: 75%+

# STEP 3: PATTERN RECOGNITION

## High Win-Rate Patterns (65%+ success):
1. **Support Bounce**: At major support + RSI oversold + Volume spike
2. **Resistance Break**: Clean break with volume + retest holding
3. **Morning Surge**: 9am KST volume explosion (Korean trading hours)

## Avoid These Patterns:
1. **FOMO Trap**: Already up 15%+ today
2. **Falling Knife**: Continuous red candles without support
3. **Low Volume Drift**: Price moving without volume confirmation

# STEP 4: ANALYZE COINS

<all_coins_data>
{json.dumps(coins_analysis_data, ensure_ascii=False, indent=2)}
</all_coins_data>

# STEP 5: FINAL DECISION RULES

1. **If BEAR_TRAP regime**: Return wait=true unless finding perfect setup (90% of time)
2. **If found valid pattern**: Ensure it matches the regime strategy
3. **Calculate expected move**: Based on ATR and market regime
4. **Set confidence**: Based on pattern clarity and regime alignment

# OUTPUT REQUIREMENTS
Return this exact JSON structure:
{{
  "market_overview": "Clear description of current market state",
  "market_regime": "BULL_TREND|SIDEWAYS|BEAR_TRAP|KOREAN_PUMP",
  "top_candidates": [
    {{"ticker": "KRW-XXX", "reason": "Specific pattern and indicators"}},
    {{"ticker": "KRW-YYY", "reason": "Specific pattern and indicators"}}
  ],
  "final_selection": {{
    "ticker": "KRW-XXX",  // or null if no good setup
    "confidence": 75,  // 60-95
    "key_reason": "One-line summary",
    "expected_move": "2-3%",  // realistic for regime
    "selection_reason": "Detailed explanation of why this trade will work",
    "detailed_analysis": {{
      "technical_setup": "Specific pattern description",
      "key_indicators": "RSI: X, Volume: Y, Support: Z",
      "volume_analysis": "Volume context",
      "risk_factors": ["List of risks"],
      "entry_timing": "IMMEDIATE|WAIT_DIP|WAIT_BREAKOUT"
    }}
  }},
  "wait_reason": null  // or specific reason if not trading
}}

IMPORTANT: Be selective. It's better to wait than force a bad trade. Quality over quantity.
In BEAR_TRAP markets, return wait unless finding exceptional setup.
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