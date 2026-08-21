# OMNI — 암호화폐 자동매매 시스템 3세대 (아카이브)

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white) ![OpenAI](https://img.shields.io/badge/OpenAI-412991?style=for-the-badge&logo=openai&logoColor=white) ![Google Gemini](https://img.shields.io/badge/Google_Gemini-8E75B2?style=for-the-badge&logo=googlegemini&logoColor=white) ![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)

> VALKYR → ARGOS → **OMNI** → METIS → HERMES → KAIROS → ATHENA
> 전체 계보: [github.com/deltaomega02](https://github.com/deltaomega02)

**OODA 루프(Observe–Orient–Decide–Act)로 매매 주기를 구조화**한 세대.
매매가 끝날 때마다 결과를 회고해 교훈(lessons)으로 축적하고, 다음 판단의 프롬프트에
주입하는 학습 루프를 붙였다.

> 회고 루프 자체는 OMNI 가 처음이 아니다. 1세대 VALKYR 에 이미 회고를 DB 에 쌓고
> 패턴을 뽑는 코드가 있었다(`valkyr/Ver_3.0.0/vk_3_0_0.py:101,107`).
> OMNI 의 기여는 그것을 **OODA 라는 명시적 주기 안에 넣어 매 사이클 강제한 것**이다.

## 기술 스택

Python · OpenAI / Gemini API · Upbit API · Streamlit

## 동작 방식

```
Observe   시세·지표·뉴스 수집
Orient    AI가 시장 상황 해석 (+ 누적된 lessons를 컨텍스트로 주입)
Decide    진입/청산/관망 결정
Act       주문 실행
  ↓ 매매 종료 후
Reflect   거래 결과 회고 → 교훈 추출 → lessons에 누적 → 다음 Orient에 반영
```

5단계 파이프라인으로 "분석 → 실행 → 학습"이 한 사이클을 이루는 구조.

## 폴더 가이드

| 폴더 | 내용 |
|---|---|
| `OMNI/` | 메인 시스템 (OODA 파이프라인, 모듈 구조: core / dashboard) |
| `OMNI-XRP/` | XRP 단일 코인 특화 버전 (버전별 메인·대시보드 변천 포함) |
| `OMNI-fractal/` | 프랙탈(다중 시간대) 분석 실험 분기 |

## 이 세대가 다음 세대에 넘긴 것

- 회고→학습 루프: 7세대 ATHENA의 학습 시스템으로 부활
- 학습의 부작용도 발견 — 적은 표본의 교훈이 과적합을 만들 수 있다는 것. 이후 세대가 "교훈 자동 반영"에 신중해진 이유.

## 면책

연구·학습 목적의 개인 프로젝트 아카이브입니다.
