# NLP-Humanoid

# 🤖 NLP 기반 반려로봇 시스템

<div align="center">

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o--mini-green.svg)
![Whisper](https://img.shields.io/badge/Whisper-STT-orange.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

**음성 대화, 감정 분석, 실시간 응답이 가능한 지능형 반려로봇**


</div>

---

## 📋 프로젝트 소개

본 프로젝트는 **OpenAI의 GPT-4o-mini, Whisper(STT), Edge-TTS**를 활용하여 
실시간 음성 대화 및 감정 분석이 가능한 반려로봇 시스템입니다.

사용자의 음성을 인식하고, 표정/제스처를 분석하며, 상황에 맞는 감정적인 응답과 
로봇 동작을 생성합니다.

### ✨ 주요 특징
- 🎤 **실시간 음성 인식**: OpenAI Whisper를 통한 정확한 STT
- 🧠 **지능형 대화**: GPT-4o-mini 기반 자연어 이해 및 응답 생성
- 😊 **감정 분석**: Vision API로 표정/제스처 인식 + 텍스트 감정 분석
- 🗣️ **감정 기반 TTS**: Edge-TTS로 상황별 적절한 음성 출력
- 🤖 **로봇 제어**: 대화 내용에 따른 자동 동작 명령 생성

---

## 🛠️ 기술 스택

### Core Technologies
| 분류 | 기술 | 버전 | 설명 |
|------|------|------|------|
| **STT** | OpenAI Whisper | latest | 음성 → 텍스트 (99개 언어) |
| **LLM** | GPT-4o-mini | API | 텍스트/이미지 분석, 응답 생성 |
| **TTS** | Edge-TTS | latest | 텍스트 → 음성 합성 |

### Additional
- **Language**: Python 3.11+
- **Communication**: WebSocket, REST API
- **Vision**: OpenCV (카메라 프레임 처리)
- **Async**: Threading, Asyncio

---

## 🏗️ 시스템 아키텍처

### 전체 흐름
```mermaid
graph TD
    A[사용자 음성] --> B[Whisper STT]
    C[카메라 영상] --> D[GPT Vision]
    B --> E[텍스트]
    D --> F[감정/제스처]
    E --> G[GPT-4o-mini]
    F --> G
    G --> H[응답 텍스트]
    G --> I[감정 정보]
    G --> J[동작 명령]
    H --> K[Edge-TTS]
    K --> L[음성 출력]
    J --> M[로봇 동작]
