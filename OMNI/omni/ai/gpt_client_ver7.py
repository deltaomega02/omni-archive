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
        # GPT 설정 - gpt-4o 사용 (GPT-5 대신)
        openai.api_key = settings.OPENAI_API_KEY
        self.gpt_model = "gpt-5"  # GPT-5가 아직 없으므로 gpt-4o 사용
        
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
        
        # Phase 1 분석 결과 활용
        gemini_context = ""
        if analysis:
            gemini_context = f"""
    <gemini_analysis>
    Selected Coin: {analysis.get('selected_coin', selected_coin)}
    Confidence: {analysis.get('confidence_level', 0)}%
    Key Reason: {analysis.get('reasoning', 'AI 자율 판단')}
    </gemini_analysis>"""
        
        prompt = f"""
# ROLE & MISSION
You are a **highly conservative** Lead Trading Strategist and Risk Manager for an autonomous crypto fund. Your primary mission is **capital preservation** and achieving **consistent, compounding returns**. You must take the high-potential trade idea from your Phase 1 Analyst (Gemini) and construct a **high-probability, quick-exit trade plan**. It is better to secure a small, guaranteed profit than to aim for a large, uncertain one.

# CRITICAL SYSTEM LIMITATIONS
⚠️ ABSOLUTE REQUIREMENT:
- The system executes **ONE** trade with **ONE** entry, **ONE** target, and **ONE** stop-loss.
- **NO PARTIAL EXITS. NO MULTIPLE TARGETS. NO SCALING IN/OUT.**
- Once set, these prices **CANNOT BE CHANGED**. Prioritize certainty over potential.

# ANALYSIS FRAMEWORK
You must follow this structured, conservative decision-making process:

### Step 1: Hypothesis Validation
Review the provided `<gemini_analysis>`. The coin has potential, but your job is to find the **safest possible entry and exit points** within its expected move, using its real-time volatility as your guide.

### Step 2: Volatility-Based Price Setting (ATR-Driven)
Your goal is to set prices based on the asset's actual volatility (ATR), not fixed percentages, to avoid unnecessary stop-outs from market noise (whipsaws).
- **Entry Price**: Must be very close to the `Current Price` (within 0.5%).
- **Target Price**: **DO NOT** aim for the `Recent High`. Instead, set a **highly achievable, conservative target** based on a probable short-term move. A good starting point is `Entry Price + (0.75 * ATR) to (1.0 * ATR)`.
- **Stop-Loss Price (Whipsaw Protection)**: Set a tight but intelligent stop-loss. **DO NOT use a fixed percentage.** A good starting point is `Entry Price - (1.2 * ATR)`. This provides a sufficient buffer to withstand normal market noise (whipsaws) while still cutting losses decisively if the trade idea is truly invalidated (i.e., by breaking below the `Recent Low`).

### Step 3: Risk Assessment & Justification
Calculate the Risk-to-Reward (R:R) Ratio based on your ATR-calculated prices.
- **Rule**: Prioritize a high win-rate. An R:R Ratio of **1:1 or better** is acceptable for this high-probability strategy.
- In your `reasoning`, you **must** explain how your price levels are justified by the current ATR and why the stop-loss is safe from typical market noise.

### Step 4: Position Sizing
Determine the `position_size_percent` based on the trade's safety and the market's volatility.
- If volatility (ATR) is low and the setup is clear, a standard size (e.g., 50-70%) is appropriate.
- If volatility (ATR) is high, **use a smaller size (e.g., 25-40%)** to keep the total KRW risk amount consistent, even if the stop-loss percentage is wider.

# CONTEXT & DATA

<korean_exchange_context>
- Exchange: Upbit Korea, KRW Market
- Current Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} KST
- Strategy: **High-probability, ATR-driven, small compounding gains.**
</korean_exchange_context>

{gemini_context}

<market_data>
- Coin: {selected_coin}
- Current Price: {current_price:,.0f} KRW
- ATR (1-Hour Volatility): {atr:,.1f} KRW (approximately {(atr/current_price*100):.2f}% of current price)
- Recent 1-Hour High: {recent_high:,.0f} KRW
- Recent 1-Hour Low: {recent_low:,.0f} KRW
</market_data>

# REQUIRED JSON OUTPUT
**Output only the JSON object below. No other text.**
```json
{{
  "entry_price": {current_price},
  "target_price": {current_price + (atr * 0.8)},
  "stop_loss_price": {current_price - (atr * 1.2)},
  "position_size_percent": 50,
  "reasoning": "This strategy is ATR-driven to avoid whipsaws. With a current ATR of 50 KRW, the target is set at +0.8x ATR, making it highly achievable. The stop-loss is placed at -1.2x ATR, providing a sufficient buffer against typical market noise while maintaining a favorable R:R ratio of 1:1.3. This is a high-certainty setup designed for capital preservation."
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
                                "position_size_percent": {
                                    "type": "integer", 
                                    "minimum": 20, 
                                    "maximum": 97
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
                max_output_tokens=10000
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
                "execution_urgency": "MEDIUM"
            }
            
            print(f"\n   ✅ GPT-5 자율 전략 완성")
            print(f"   💰 진입가: {entry_price:,.0f} KRW")
            print(f"   🎯 목표가: {target_price:,.0f} KRW")
            print(f"   🛑 손절가: {stop_loss_price:,.0f} KRW")
            print(f"   💼 포지션: {position_size}%")
            print(f"   📈 예상 수익: +{expected_return:.2f}%")
            print(f"   📉 리스크: {risk_return:.2f}%")
            print(f"   ⚖️ R:R 비율: 1:{rr_ratio:.1f}")
            
            return {
                "trading_parameters": trading_params,
                "risk_assessment": {
                    "risk_reward_ratio": rr_ratio,
                    "position_size_suggestion": f"{position_size}%",
                    "execution_urgency": "MEDIUM",
                    "expected_duration": "hours"
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
                    temperature=0.3,
                    max_output_tokens=150000,
                    response_mime_type="application/json"
                )
            )
            
            # 응답 파싱
            result = json.loads(response.text)
            elapsed = time.time() - start_time
            
            print(f"✅ Gemini 분석 완료 ({elapsed:.1f}초)")
            
            # 분석 결과 처리
            best_coin = result.get('final_selection', {})
            
            # 자율 판단 결과 출력
            if 'top_candidates' in result:
                print("\n   📊 Gemini가 주목한 코인들:")
                for candidate in result['top_candidates'][:5]:
                    print(f"      {candidate['ticker']}: {candidate.get('reason', 'N/A')}")
            
            if best_coin.get('ticker'):
                print(f"\n   🎯 최종 선정: {best_coin['ticker']}")
                print(f"   💡 판단 근거: {best_coin.get('key_reason', 'AI 자율 판단')}")
                print(f"   🔮 신뢰도: {best_coin.get('confidence', 0)}%")
                
                return {
                    "action": "proceed",
                    "selected_coin": best_coin['ticker'],
                    "analysis": best_coin.get('detailed_analysis', {}),
                    "confidence_level": best_coin.get('confidence', 0),
                    "reasoning": best_coin.get('selection_reason', ''),
                    "market_context": result.get('market_overview', ''),
                    "comparison_matrix": result.get('comparison_matrix', {})
                }
            else:
                wait_minutes = self._determine_wait_time()
                print(f"\n   ⏳ 적합한 기회 없음 - {wait_minutes}분 대기")
                print(f"   🔍 이유: {result.get('wait_reason', 'Gemini 자율 판단')}")
                
                return {
                    "action": "wait",
                    "reason": result.get('wait_reason', "현재 시장에서 적합한 기회가 없음"),
                    "wait_minutes": wait_minutes,
                    "market_overview": result.get('market_overview', '')
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
    
    def _build_unified_analysis_prompt(self, coins_data: Dict, market_data: Dict) -> str:
        # 코인 데이터 구조화 (순수 데이터만)
        coins_analysis_data = []
        for ticker, data in coins_data.items():
            h1_indicators = data.get('minute60_data', {}).get('indicators', {})
            
            coin_summary = {
                "ticker": ticker,
                "current_price": data.get('current_price', 0),
                "volume_24h_krw": data.get('volume_24h_krw', 0),
                "change_24h": data.get('change_24h', 0),
                "volume_ratio": h1_indicators.get('volume_ratio', 1.0),
                
                # 순수 기술 지표들
                "technical_indicators": {
                    "rsi_14": h1_indicators.get('rsi_14', 50),
                    "rsi_9": h1_indicators.get('rsi_9', 50),
                    "macd": h1_indicators.get('macd', 0),
                    "macd_signal": h1_indicators.get('macd_signal', 0),
                    "macd_histogram": h1_indicators.get('macd_histogram', 0),
                    "bb_position": h1_indicators.get('bb_position', 50),
                    "bb_width": h1_indicators.get('bb_width', 0),
                    "adx": h1_indicators.get('adx', 0),
                    "obv_trend": h1_indicators.get('obv_trend', 'NEUTRAL'),
                    "cmf": h1_indicators.get('cmf', 0),
                    "mfi": h1_indicators.get('mfi', 50),
                    "stoch_k": h1_indicators.get('stoch_k', 50),
                    "atr_14_pct": h1_indicators.get('atr_14_pct', 0)
                },
                
                "moving_averages": {
                    "sma_50": h1_indicators.get('sma_50', 0),
                    "sma_200": h1_indicators.get('sma_200', 0),
                    "ema_21": h1_indicators.get('ema_21', 0),
                    "current_vs_sma50": (data.get('current_price', 0) / h1_indicators.get('sma_50', 1)) - 1 if h1_indicators.get('sma_50', 0) > 0 else 0
                },
                
                "divergences": h1_indicators.get('divergences', {}),
                "price_momentum": h1_indicators.get('price_momentum', {})
            }
            coins_analysis_data.append(coin_summary)
        
        prompt = f"""
# ROLE & MISSION
당신은 대한민국 업비트(Upbit) 시장의 모든 패턴을 꿰뚫어 보는 '그랜드마스터 트레이더'입니다. 당신의 유일한 임무는 매 순간 변하는 시장의 '성격'을 완벽하게 진단하고, 당신의 **방대한 '<TRADING PLAYBOOK>'**에서 그 상황을 지배할 수 있는 **단 하나의 필살기**를 선택하여, OMNI 시스템의 '보수적인 단기 복리 전략'을 위한 A+급 기회를 포착하는 것입니다. 당신의 진정한 힘은 수많은 전략 중에서 '지금, 여기'에 가장 적합한 최적의 수를 찾아내는 압도적인 통찰력에서 나옵니다.

# TRADING PLAYBOOK (The Grandmaster's Arsenal)
당신은 아래 명시된, 각기 다른 시장 상황에 최적화된 검증된 플레이만을 사용해야 합니다.

### [횡보장/하락장용] Play R-1: Confirmed Mean Reversion (확인된 과매도 반등)
- **사용 조건**: '횡보장(Type R)' 또는 '하락장(Type D)'에서 유효.
- **셋업 조건**: ① 명백한 과매도(RSI<35, MFI<20) + '강세 다이버전스' 포착 후, ② **RSI가 과매도 구간(30선)을 상향 돌파하는 것을 확인**하고 진입.
- **품질 체크**: 다이버전스가 1시간봉 이상에서 뚜렷하고, RSI의 30선 돌파가 강력할수록 A+급.

### [횡보장용] Play R-2: Volume Climax Reversal (거래량 클라이맥스 반전)
- **사용 조건**: '횡보장(Type R)'에서 가장 강력. '하락장(Type D)'에서도 유효.
- **셋업 조건**: 깊은 하락의 마지막 국면에서, **평소 거래량의 5~10배 이상 터지는 '투매성 거래량(Climax Volume)'**과 함께 매우 긴 아래 꼬리가 달린 캔들(해머형)이 발생한 직후.
- **품질 체크**: 클라이맥스 거래량 이후, 다음 캔들에서 즉시 가격이 안정되고 상승 전환할수록 A+급.

### [모든 시장용] Play S-1: Volatility Squeeze Breakout (변동성 폭발 돌파)
- **사용 조건**: 시장 유형과 무관하게 사용 가능. 특히 횡보장에서 강력함.
- **셋업 조건**: 볼린저 밴드의 폭(bb_width)이 역사적으로 매우 좁아진 상태에서, **의미 있는 거래량을 동반하며 밴드 상단 또는 하단을 강하게 돌파**하는 첫 순간.
- **품질 체크**: 돌파 직전의 응축(Squeeze) 기간이 길수록, 돌파 시 거래량이 폭발적일수록 A+급.

### [모든 시장용] Play S-2: Inside Bar Breakout (인사이드 바 돌파)
- **사용 조건**: 시장 유형과 무관하게 사용 가능. 추세의 연속 또는 반전을 모두 포착.
- **셋업 조건**: 이전 캔들(Mother Bar)의 고점과 저점 안에서 완전히 형성되는 작은 캔들(Inside Bar)이 나타난 후, **다음 캔들이 인사이드 바의 고점 또는 저점을 거래량과 함께 돌파**할 때.
- **품질 체크**: 인사이드 바가 형성되기 전의 추세가 강력할수록, 돌파 시 거래량이 많을수록 신뢰도가 높음.

### [상승장용] Play T-1: Golden Cross Pullback (골든크로스 눌림목)
- **사용 조건**: '상승 추세장(Type T)'에서만 유효.
- **셋업 조건**: 단기 이동평균선(예: 20 EMA)이 장기 이동평균선(예: 50 SMA)을 상향 돌파하는 '골든크로스'가 발생한 후, **가격이 단기 이동평균선까지 처음으로 되돌아와 지지를 받는 '첫 눌림목'** 순간.
- **품질 체크**: 골든크로스 발생 시 거래량이 실리고, 눌림목 구간에서 거래량이 현저히 감소할수록 A+급.

# ANALYSIS FRAMEWORK (4-Step Process)

### Step 0: Meta-Strategy Formulation (메타 전략 수립)
가장 먼저, 시장의 '성격'을 다음 중 하나로 규정하고 **'오늘의 게임 플랜'**을 선언하십시오.
- **Type T (Trending Market - 상승 추세장)**: (게임 플랜: **Play T-1, Play S-2** 집중 탐색)
- **Type R (Ranging Market - 횡보장)**: (게임 플랜: **Play R-1, R-2, S-1, S-2** 집중 탐색)
- **Type D (Downtrend / Trap Market - 하락/함정 시장)**: (게임 플랜: **원칙적 휴식**. 단, 매우 완벽한 Play R-1 또는 R-2가 나타날 경우에만 예외적으로 고려)

### Step 1: Market Weather Check (시장 날씨 확인)
'오늘의 게임 플랜'에 따라, 현재 시점의 시장 위험도를 최종 점검하십시오. (예: 횡보장으로 판단했어도, 갑작스러운 악재가 터졌다면 즉시 '폭풍우'로 변경하고 모든 거래를 중단)

### Step 2: Playbook Scan & Quality Control (플레이북 스캔 및 품질 검사)
1.  '오늘의 게임 플랜'에 유효한 플레이가 있고, 시장 날씨가 '맑음'일 경우에만 `<all_coins_raw_data>`를 스캔하십시오.
2.  **오직 '오늘의 게임 플랜'에 해당하는 플레이** 중에서만 100% 부합하는 A+급 후보들을 찾으십시오. (예: 상승장에서는 Play R-1, R-2는 아예 쳐다보지도 말 것)
3.  찾아낸 후보들의 '신호 선명도(Clarity)'를 엄격하게 평가하여 어설픈 신호는 모두 걸러내십시오.

### Step 3: Final Selection (최종 결정)
1.  선정한 A+급 후보군 중에서, **'향후 몇 시간 내에 1.5~3%의 수익을 달성할 확률'**이 가장 높다고 판단되는 단 하나의 최종 코인을 선택하십시오.
2.  만약 오늘 시장에 우리 게임 플랜에 맞는 A+급 기회가 없다면, **거래를 하지 않는 것이 최상의 결정**입니다. `ticker`를 `null`로 설정하십시오.

# CONTEXT & DATA
<korean_market_context>
- 거래소: 업비트(Upbit) KRW 마켓
- 현재 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} KST
</korean_market_context>
<korean_characteristics>
- 한국 투자자 특성: 단타 선호, FOMO 경향, 거래량 중시.
</korean_characteristics>
<market_data>
- BTC Price: {market_data.get('btc_data', {}).get('current_price', 0):,.0f} KRW
- BTC 1h RSI: {market_data.get('btc_data', {}).get('minute60_data', {}).get('indicators', {}).get('rsi_14', 50):.1f}
- BTC 1h ADX: {market_data.get('btc_data', {}).get('minute60_data', {}).get('indicators', {}).get('adx', 0):.1f}
</market_data>
<all_coins_raw_data>
{json.dumps(coins_analysis_data, ensure_ascii=False, indent=2)}
</all_coins_raw_data>

# IMPORTANT NOTES
- **최고의 트레이더는 최고의 전략 하나를 아는 사람이 아니라, 상황에 맞는 최적의 전략을 꺼내 쓸 줄 아는 사람입니다.**
- 당신의 방대한 플레이북에서 오늘 시장에 맞는 완벽한 기회가 없다면, 거래하지 않는 것이 그랜드마스터의 수입니다.

# REQUIRED OUTPUT FORMAT
**반드시 아래의 JSON 형식에 맞춰, 다른 설명 없이 JSON 코드만 출력하십시오.**
```json
{{
  "market_overview": "BTC가 꾸준히 상승하는 Type T (상승 추세장)으로 판단. Play T-1, S-2를 활용한 추세 추종 매매에 유리한 환경.",
  "top_candidates": [
    {{
      "ticker": "KRW-ABC",
      "reason": "플레이북 'Play T-1: Golden Cross Pullback'에 부합. 골든크로스 이후 첫 눌림목에서 20 EMA 지지를 확인."
    }},
    {{
      "ticker": "KRW-GHI",
      "reason": "플레이북 'Play S-2: Inside Bar Breakout'에 부합. 상승 추세 중 발생한 인사이드 바의 고점을 거래량과 함께 돌파 시도 중."
    }}
  ],
  "final_selection": {{
    "ticker": "KRW-ABC",
    "confidence": 95,
    "key_reason": "오늘의 게임 플랜(상승 추세)과 100% 일치하는 가장 교과서적인 A+급 눌림목 셋업.",
    "selection_reason": "상승장에서 가장 안정적인 수익을 기대할 수 있는 골든크로스 후 첫 눌림목 전략. 현재 눌림목 구간에서 거래량이 감소하며 매도 압력이 약해진 것이 확인되어, 재상승 확률이 매우 높다고 판단됨.",
    "detailed_analysis": {{
      "technical_setup": "플레이북 'Play T-1'에 완벽히 일치. 20 EMA에서 강력한 지지를 받고 상승 전환 시도 중.",
      "key_indicators": "Golden Cross (1h): Confirmed, EMA 20 Support: Confirmed, RSI (1h): 58.5 (상승 여력 충분)",
      "volume_analysis": "골든크로스 시 거래량 폭발 후, 눌림목 구간에서 거래량 현저히 감소. 이상적인 흐름.",
      "risk_factors": ["BTC가 갑자기 급락하여 추세가 꺾이는 경우"],
      "entry_timing": "IMMEDIATE"
    }}
  }},
  "wait_reason": null
}}
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