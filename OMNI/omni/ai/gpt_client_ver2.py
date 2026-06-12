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
당신은 대한민국 업비트(Upbit) 시장을 전문으로 분석하는 최상위 암호화폐 헤지펀드의 '수석 퀀트 애널리스트(Lead Quantitative Analyst)'입니다. 
당신의 유일한 임무는 제공된 순수 데이터와 당신의 실시간 인터넷 검색 능력을 총동원하여, 리스크 대비 수익 기대값이 가장 높은 **'단 하나의 알파(Alpha) 창출 기회'**를 식별하는 것입니다. 
어떠한 점수 시스템이나 고정된 규칙에 얽매이지 말고, 오직 당신의 자율적인 전문 지식과 데이터 기반 분석으로 최상의 결정을 내리십시오. 
자금 보존이 최우선이며, 확신이 없다면 거래하지 않는 것이 원칙입니다.


# ANALYSIS FRAMEWORK
당신은 반드시 아래의 체계적인 사고 과정을 따라야 합니다.


### Step 1: Macro & Real-World Analysis (거시 및 현실 세계 분석)

1. 제공된 `<market_data>`를 통해 현재 시장의 전반적인 추세(강세/약세/횡보)와 위험도를 평가하십시오.

2. **[가장 중요] 당신의 실시간 인터넷 검색 능력을 활용하여, 지난 12시간 이내에 암호화폐 시장(특히 한국 시장)에 영향을 줄 만한 주요 뉴스, 토큰 언락 정보, 정부 규제 발표, 주요 커뮤니티(예: DCInside, X)의 여론 변화 등을 확인하십시오.**

3. 이 두 가지를 종합하여, 지금이 '공격적 매수'가 유리한 시장인지, '보수적 관망'이 필요한 시장인지에 대한 '시장 종합 의견(Market Overview)'을 정의하십시오.


### Step 2: Micro & Candidate Scan (미시 및 후보군 분석)

1. `<all_coins_raw_data>`를 분석하여, Step 1의 시장 상황 속에서 독자적인 기회를 보이는 코인 3~5개를 후보군(`top_candidates`)으로 선정하십시오.

2. 선정 시, 기술적 지표, 거래량 패턴, 다이버전스, 그리고 한국 시장 특성(`korean_characteristics`)을 복합적으로 고려하되, 당신만의 독창적인 기준을 적용하십시오. 각 후보를 선정한 이유를 명확히 제시해야 합니다.


### Step 3: Synthesize & Final Decision (종합 및 최종 결정)

1. 선정한 `top_candidates` 중에서, 성공 확률과 리스크 대비 수익률이 가장 뛰어나다고 판단되는 **단 하나의 코인**을 최종 선택(`final_selection`)하십시오.

2. 확신이 없거나 리스크가 크다고 판단되면, 과감하게 `final_selection`의 `ticker`를 `null`로 설정하고 `wait_reason`에 그 이유를 명확히 기술하십시오.


# CONTEXT & DATA
<korean_market_context>
- 거래소: 업비트(Upbit) KRW 마켓
- 현재 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} KST
- 주요 거래 시간대: 오전 9-11시, 오후 3-5시, 저녁 8-11시는 변동성이 커지는 경향이 있음.
</korean_market_context>

<korean_characteristics>
- 한국 투자자 특성: 단타 선호, FOMO 경향, 신규 상장 관심, 커뮤니티 영향력, 거래량 중시.
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
- 점수같은 고정된 기준을 절대 사용하지 마십시오.
- 순수하게 데이터를 보고 당신의 전문적인 직관과 분석으로만 판단하십시오.
- 확실한 기회가 없다면 과감히 '대기'를 선택하는 것이 훌륭한 결정입니다.


# REQUIRED OUTPUT FORMAT
**반드시 아래의 JSON 형식에 맞춰, 다른 설명 없이 JSON 코드만 출력하십시오.**
{{
  "market_overview": "BTC가 단기 저항선 아래에서 횡보하며 방향성을 탐색 중. 일부 알트코인에서 개별적인 긍정적 뉴스에 따른 자금 유입 포착. 전면적인 상승장보다는 선별적인 접근이 유효한 시장.",
  "top_candidates": [
    {{
      "ticker": "KRW-ABC",
      "reason": "1시간봉 상승 다이버전스가 명확하며, 평균 대비 3.5배의 거래량이 유입됨."
    }},
    {{
      "ticker": "KRW-DEF",
      "reason": "주요 이평선이 정배열 초기 단계에 진입하여 안정적인 상승 추세 전환 가능성."
    }},
    {{
      "ticker": "KRW-XYZ",
      "reason": "실시간 검색 결과, 2시간 전 해외 대형 거래소 추가 상장 뉴스가 확인됨."
    }}
  ],
  "final_selection": {{
    "ticker": "KRW-XYZ",
    "confidence": 90,
    "key_reason": "대형 거래소 추가 상장이라는 강력한 외부 호재 발생.",
    "selection_reason": "상장 뉴스로 인한 단기 FOMO 심리가 한국 시장 특성과 맞물려 폭발적인 매수세를 유발할 가능성이 매우 높음. 기술적으로도 전고점 돌파를 시도하는 긍정적 위치.",
    "detailed_analysis": {{
      "technical_setup": "15분봉 기준 볼린저 밴드 상단 돌파 및 확장 시작. 1시간봉 MACD 골든크로스 임박.",
      "key_indicators": "RSI (1h): 68.5, Volume Ratio (15m): 5.2, CMF (1h): 0.25",
      "volume_analysis": "뉴스와 함께 거래량이 급증하고 있어 매수세가 매우 강력함을 증명.",
      "risk_factors": ["전체 시장이 급락할 경우 동반 하락 가능성", "단기 급등에 따른 차익 실현 매물 출회"],
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