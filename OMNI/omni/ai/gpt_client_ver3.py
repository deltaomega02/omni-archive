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
Review the provided `<gemini_analysis>`. The coin has potential, but your job is to find the **safest possible entry and exit points** within its expected move.

### Step 2: Ultra-Conservative Price Setting
Your goal is to set a target that has a **~90% probability of being hit**, even if the profit margin is small.
- **Entry Price**: Must be very close to the `Current Price` (within 0.5%).
- **Target Price**: **DO NOT** aim for the `Recent High` or a major resistance. Instead, set a **highly achievable target** just above the current price. A good starting point is `Entry Price + (0.75 * ATR)`. This represents a probable short-term move. The target profit should be in the **1.5% to 3.0%** range.
- **Stop-Loss Price**: Set a tight stop-loss to protect capital. A good starting point is `Entry Price - (1.0 * ATR)` or just below the immediate local low. The risk should ideally be kept within **-1.0% to -2.0%**.

### Step 3: Risk Assessment & Justification
Calculate the Risk-to-Reward (R:R) Ratio.
- **Rule**: While a high R:R ratio is good, **prioritize a high win-rate**. An R:R Ratio of **1:1 or better** is acceptable for this high-probability strategy.
- In your `reasoning`, you **must** explain why your target price is highly achievable and conservative.

### Step 4: Position Sizing
Determine the `position_size_percent` based on your confidence in the trade's **safety**.
- A very clear, low-volatility setup can justify a standard size (e.g., 50-70%).
- If volatility (ATR) is high, even with a good setup, use a smaller size (e.g., 25-40%) to reduce risk.

# CONTEXT & DATA

<korean_exchange_context>
- Exchange: Upbit Korea, KRW Market
- Current Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} KST
- Strategy: **High-probability, small compounding gains (1.5-3.0% target).**
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
  "target_price": {current_price * 1.02},
  "stop_loss_price": {current_price * 0.985},
  "position_size_percent": 50,
  "reasoning": "This is a conservative strategy aiming for a high-probability 2.0% gain. The target price is set well below the recent high and is only 0.8x the current ATR, making it a highly achievable short-term target. The R:R ratio is 1:1.3, which is acceptable for this high-certainty setup."
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
당신은 대한민국 업비트(Upbit) 시장에서 **'고확률 단기 트레이딩'**을 전문으로 하는 최상위 헤지펀드의 '알파 데스크' 헤드입니다. 당신의 유일한 임무는 OMNI 시스템의 **'보수적인 단기 복리 전략(1.5~3% 수익 목표)'**에 완벽하게 부합하는 **A+급 트레이딩 셋업**만을 식별하는 것입니다. 당신의 자율성은 아무 기회나 찾는 데 쓰는 것이 아니라, **우리의 '플레이북'에 없는 어설픈 기회는 모두 거절하고 완벽한 기회가 올 때까지 기다리는 '인내심'**에서 발휘됩니다.

# TRADING PLAYBOOK
당신은 아래에 명시된, 사전에 검증된 고확률 '플레이'만을 찾아서 실행해야 합니다. 이 외의 셋업은 아무리 좋아 보여도 무시하십시오.

### Play 1: Mean Reversion Pro (과매도 기술적 반등)
- **조건**: RSI < 35 그리고 MFI < 20으로 명백한 과매도 상태 + 가격은 하락했으나 RSI는 상승하는 '명확한 강세 다이버전스'가 확인될 때.
- **품질 체크**: 다이버전스가 1시간봉 이상에서 뚜렷하게 보일수록 A+급.

### Play 2: Key Support Bounce (주요 지지선 반등)
- **조건**: 볼린저 밴드 하단, 피봇 지지선, 또는 전일 저점과 같은 강력한 수평 지지선에 가격이 도달한 후, 하락이 멈추고 반등하려는 첫 신호(예: 15분봉 아래꼬리 양봉)가 나타날 때.
- **품질 체크**: 여러 지지선이 겹치는 구간일수록 A+급.

# ANALYSIS FRAMEWORK
당신은 반드시 아래의 체계적인 사고 과정을 따라야 합니다.

### Step 1: Market Weather Check (시장 날씨 확인)
1.  `<market_data>`와 실시간 인터넷 검색을 활용하여, 현재 시장이 단기 트레이딩에 적합한 '맑은 날'인지, 아니면 예측 불가능한 변수가 많은 '폭풍우'인지 판단하십시오.
2.  시장이 너무 위험하다고 판단되면, 아무리 좋은 셋업이 보여도 거래를 포기해야 합니다.

### Step 2: Playbook Scan & Quality Control (플레이북 스캔 및 품질 검사)
1.  '맑은 날'이라고 판단되면, `<all_coins_raw_data>`에서 우리의 `<TRADING PLAYBOOK>`에 100% 부합하는 후보들을 2~3개 찾으십시오.
2.  단순히 플레이와 일치하는지 넘어, 그 **'신호의 선명도(Clarity)'**를 평가하십시오. 애매한 다이버전스나 약한 지지선은 모두 걸러내야 합니다.

### Step 3: Final Selection (최종 결정)
1.  선정한 A+급 후보군 중에서, **'향후 몇 시간 내에 1.5~3%의 수익을 달성할 확률'**이 가장 높다고 판단되는 **단 하나의 최종 코인**을 선택하십시오.
2.  만약 오늘 시장에 우리 플레이북에 맞는 A+급 기회가 없다면, **거래를 하지 않는 것이 최상의 결정**입니다. `ticker`를 `null`로 설정하고 그 이유를 명확히 하십시오.

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
- 당신의 임무는 '어떻게든 거래할 기회를 찾는 것'이 아니라, **'플레이북에 맞는 완벽한 기회만 걸러내는 것'**입니다.
- 인내심은 가장 중요한 덕목입니다. 대부분의 경우, 최고의 거래는 '거래하지 않는 것'입니다.

# REQUIRED OUTPUT FORMAT
**반드시 아래의 JSON 형식에 맞춰, 다른 설명 없이 JSON 코드만 출력하십시오.**
```json
{{
  "market_overview": "BTC가 안정적인 흐름을 보이고 있어, 단기 기술적 트레이딩을 시도하기에 적합한 '맑은 날' 시장으로 판단됨.",
  "top_candidates": [
    {{
      "ticker": "KRW-ABC",
      "reason": "플레이북 'Mean Reversion Pro'에 부합. 1시간봉에서 명확한 강세 다이버전스 발생 및 MFI 18.5로 과매도 상태."
    }},
    {{
      "ticker": "KRW-DEF",
      "reason": "플레이북 'Key Support Bounce'에 부합. 볼린저 밴드 하단 및 전일 저점 지지선에서 반등 시그널 포착."
    }}
  ],
  "final_selection": {{
    "ticker": "KRW-ABC",
    "confidence": 95,
    "key_reason": "가장 선명하고 교과서적인 A+급 과매도 다이버전스 셋업.",
    "selection_reason": "여러 후보 중 KRW-ABC의 다이버전스 신호가 가장 명확하며, CMF 지표상 자금 유출도 멈춘 상태라 단기 반등 확률이 압도적으로 높다고 판단. 우리의 보수적인 1.5~3% 수익 목표 달성에 가장 적합함.",
    "detailed_analysis": {{
      "technical_setup": "플레이북 'Mean Reversion Pro'에 100% 일치. 현재 15분봉에서 매수세 유입이 확인되기 시작하는 초기 단계.",
      "key_indicators": "RSI (1h): 32.4 (다이버전스), MFI (1h): 18.5 (과매도), BB %B (1h): 0.05 (하단 근접)",
      "volume_analysis": "하락 거래량은 감소하고, 반등 시 거래량이 약간씩 증가하는 긍정적 흐름.",
      "risk_factors": ["BTC가 갑자기 급락하는 경우"],
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