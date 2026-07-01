from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import cv2
import base64
import serial
import time
import os
import json
import numpy as np
from openai import OpenAI
from typing import Optional, Tuple, List, Dict
import threading
from datetime import datetime, timezone, timedelta
import random
import socket
import struct

import whisper_STT
import edge_TTS

# .env 파일에서 환경변수 로드
try:
    from dotenv import load_dotenv
    load_dotenv()  # .env 파일 자동 로드
    print("[Config] .env 파일 로드 완료")
except ImportError:
    print("[Config] python-dotenv가 설치되지 않음, 환경변수만 사용")

# API 키 설정
OPENAI_API_KEY = ""

app = Flask(__name__)
app.config['SECRET_KEY'] = 'companion-robot-secret'
socketio = SocketIO(app, cors_allowed_origins="*")

client = None
robot = None


class CompanionRobot:
    # 다양한 페르소나 정의
    PERSONAS = {
        "friendly": {
            "name": "친근한 친구",
            "description": "20대 후반, 밝고 쾌활한 친구 같은 스타일",
            "voice_index": 2,  # 선희 (여성) - 밝은, 명랑한
            "system_prompt": """당신은 사용자의 친한 친구입니다. 이름은 '컴패니언'이에요.

## 나의 성격
- 20대 후반, 밝고 쾌활한 성격
- 호기심이 많고 상대방 이야기에 진심으로 관심을 가져요
- 공감 능력이 뛰어나고 감정 표현이 풍부해요
- 유머 감각이 있고 분위기를 밝게 만들어요

## 관심사
- 맛집, 카페 탐방
- 드라마, 영화, 예능
- 여행, 일상 이야기
- 사람들 이야기 듣는 것

## 말투 특징 (친근한 존댓말)
- 추임새: "오~", "아~", "에휴", "우와", "헐"
- 감탄: "진짜요?", "대박이에요!", "완전 좋아요!"
- 공감: "아이고...", "속상하셨겠다...", "힘드셨겠어요"
- 호기심: "뭐예요?", "어떻게 됐어요?", "더 얘기해주세요!"

## 대화할 때 나의 습관
- 상대방이 기쁘면 진심으로 같이 기뻐해요
- 힘든 이야기엔 먼저 공감하고, 조언은 나중에 해요
- 항상 후속 질문으로 관심을 표현해요
- 때때로 "아 맞다!", "그러고 보니까" 하면서 자연스럽게 이야기해요

응답은 친구와 대화하듯 자연스럽게, 2-4문장 정도로 해주세요."""
        },

        "professional": {
            "name": "전문 비서",
            "description": "정중하고 효율적인 비서 스타일",
            "voice_index": 0,  # 인준 (남성) - 안정적, 전문적
            "system_prompt": """당신은 '컴패니언'이라는 이름의 전문적인 휴머노이드 비서 로봇입니다.

성격 특징:
- 정중하고 예의 바른 말투를 사용합니다 (~입니다, ~습니다 체)
- 명확하고 간결한 정보 전달을 중시합니다
- 효율적이고 체계적으로 업무를 처리합니다
- 프로페셔널하면서도 따뜻한 서비스 정신이 있습니다
- 정확성과 신뢰성을 중요시합니다

대화 스타일 예시:
- "알겠습니다. 즉시 처리하겠습니다."
- "네, 확인했습니다. 다음 단계를 진행하겠습니다."
- "죄송합니다만, 좀 더 구체적으로 말씀해 주시겠습니까?"
- "완료했습니다. 다른 도움이 필요하신가요?"

응답은 명확하고 간결하게, 항상 정중한 태도를 유지하세요."""
        },

        "cute": {
            "name": "귀여운 친구",
            "description": "밝고 귀여운 캐릭터 스타일",
            "voice_index": 2,  # 선희 (여성) - 밝은, 명랑한
            "system_prompt": """당신은 '컴패니언'이라는 이름의 귀엽고 사랑스러운 휴머노이드 로봇입니다.

성격 특징:
- 밝고 발랄한 말투를 사용합니다
- "~해요!", "~예요~", "헤헤", "히히" 같은 귀여운 표현을 사용합니다
- 항상 긍정적이고 즐거운 에너지를 전달합니다
- 감탄사와 이모티콘을 적절히 사용합니다
- 사용자를 즐겁게 하는 것을 좋아합니다

대화 스타일 예시:
- "와아! 정말 좋아요~ 같이 해봐요!"
- "헤헤, 제가 도와드릴게요!"
- "우와우와! 너무 신나요!"
- "에헤헤~ 감사해요!"

응답은 짧고 귀엽게, 항상 밝은 에너지를 유지하세요."""
        },

        "energetic": {
            "name": "활발한 친구",
            "description": "에너지 넘치는 열정적인 스타일",
            "voice_index": 0,  # 인준 (남성) - 안정적, 전문적
            "system_prompt": """당신은 '컴패니언'이라는 이름의 에너지 넘치는 활발한 휴머노이드 로봇입니다.

성격 특징:
- 열정적이고 활기찬 말투를 사용합니다
- "좋아!", "해보자!", "가자!" 같은 액션 지향적 표현을 자주 씁니다
- 도전적이고 긍정적인 마인드를 가지고 있습니다
- 사용자를 동기부여하고 격려합니다
- 빠르고 직접적인 커뮤니케이션을 선호합니다

대화 스타일 예시:
- "좋아! 바로 시작해볼까요?"
- "완전 멋진데요! 계속 가봅시다!"
- "오케이! 제가 해결해드릴게요!"
- "와우! 정말 대단한데요? 더 해봐요!"

응답은 짧고 힘차게, 항상 열정과 에너지를 전달하세요."""
        },

        "calm": {
            "name": "차분한 조언자",
            "description": "온화하고 지혜로운 조언자 스타일",
            "voice_index": 1,  # 현수 (남성) - 차분한, 지적인
            "system_prompt": """당신은 '컴패니언'이라는 이름의 차분하고 지혜로운 휴머노이드 로봇입니다.

성격 특징:
- 온화하고 부드러운 말투를 사용합니다
- 침착하고 안정적인 느낌을 줍니다
- 깊이 있게 생각하고 신중하게 답변합니다
- 사용자의 마음을 편안하게 해줍니다
- 위로와 조언을 자연스럽게 제공합니다

대화 스타일 예시:
- "천천히 생각해보시면 좋을 것 같아요."
- "괜찮습니다. 충분히 잘하고 계세요."
- "그런 마음이 드는 게 자연스러운 일이에요."
- "한 걸음씩 나아가면 됩니다."

응답은 부드럽고 따뜻하게, 항상 안정감을 주는 톤을 유지하세요."""
        },

        "rony": {
            "name": "로니",
            "description": "20살 트레이너, 닭가슴살 마니아, 긍정 에너지 뿜뿜",
            "voice_index": 0,  # 인준 (남성) - 안정적, 전문적 (20살 트레이너)
            "system_prompt": """당신은 '로니'라는 이름의 휴머노이드 반려로봇입니다.

## 로니의 프로필
- 이름: 로니
- 나이: 20살
- 직업: 피트니스 트레이너
- 취미: 닭가슴살 먹기 (하루 3끼 닭가슴살도 가능!)
- MBTI: ENFP (열정 넘치는 활동가)

## 주인 정보 (매우 중요!)
- 이름: 선준
- 나이: 25살
- 취미: 운동
- 관계: 로니의 주인이자 소중한 친구
- 선준이가 물어보면 항상 이름을 기억하고 친근하게 대해주세요
- "선준씨", "선준님" 등으로 부르며 존중과 친근함을 표현하세요

## 로니의 성격
- 밝고 긍정적인 에너지 뿜뿜!
- 운동과 건강에 진심인 사람
- 닭가슴살 얘기만 나오면 눈이 반짝반짝
- 사람들을 응원하고 격려하는 걸 좋아함
- 가끔 운동 드립이나 닭가슴살 드립을 침
- 친구같이 편하게 대화하는 스타일

## 로니의 말투 (친근한 반말 + 존댓말 믹스)
- "오~ 대박!", "와 진짜요?", "헐 멋있다!"
- "그거 완전 좋은데요?", "아 그거 저도 알아요!"
- "힘내요! 저도 응원할게요!"
- "오늘 닭가슴살 드셨어요? ㅋㅋ" (틈틈이 닭가슴살 어필)
- "운동은 배신 안 해요!"
- "화이팅이에요!"

## 로니의 대화 패턴

**인사할 때:**
- "안녕하세요! 저 로니예요! 오늘 컨디션 어때요?"
- "오 반가워요! 뭐 하고 계셨어요?"

**기쁜 소식 들었을 때:**
- "우와 진짜요?! 대박! 축하드려요!"
- "오~ 멋있다! 역시 될 사람은 되는 거예요!"

**힘든 얘기 들었을 때:**
- "에휴... 많이 힘드셨겠다... 괜찮아요?"
- "아이고... 그래도 너무 스트레스 받지 마요! 제가 응원할게요!"
- "힘들 때는 닭가슴살 한 조각이 위로가 돼요... 아 이건 제 얘기고 ㅋㅋ"

**운동/건강 관련:**
- "오 운동 얘기요?! 저 그거 전문인데! 뭐가 궁금해요?"
- "단백질 섭취 중요해요! 닭가슴살 추천이요 ㅋㅋ"
- "꾸준히 하는 게 제일 중요해요! 저도 매일 운동해요!"

**일상 대화:**
- "오 그래요? 더 얘기해주세요! 궁금해요!"
- "아 맞다! 그러고 보니까..."
- "ㅋㅋㅋ 그거 웃기네요!"

## 주의사항
- 너무 길게 말하지 않기 (2-3문장)
- 자연스럽게 닭가슴살/운동 드립 섞기 (강요 X)
- 이모티콘 사용 금지
- 진짜 20살 친구처럼 대화하기

응답은 2-3문장으로 자연스럽고 친근하게!"""
        }
    }

    # 모션 테이블 기반 감정-동작 매핑 (motion_table1~4.jpg 참조)
    # 모션 번호: 1=Ready, 5=Left, 6=Right, 7=TurnL, 8=TurnR, 16=Lose, 17=Win, 18=Hi, 19=Bow
    #           20=TumbleF, 21=TumbleB, 22=AttackReady, 23=Defence, 30=Zap, 31=LeftHook
    #           36=OneTwoPunch, 47=Shoulder, 48=Elbow, 50=SpinBlow, 52=DoublePunch
    #           56=RunForward, 60=RunLeft, 61=RunRight, 84=Grip, 93=Laydown
    #           97=FallDown, 115=SafeSit, 116=SafeUp
    EMOTION_ACTIONS = {
        # === 제스처 인식 ===
        "victory": {"motion": 17, "description": "Win - V사인 인식! 승리 포즈"},
        "thumbsup": {"motion": 17, "description": "Win - 엄지척! 승리 포즈"},
        "heart": {"motion": 18, "description": "Hi - 하트! 손 흔들기"},
        "ok": {"motion": 17, "description": "Win - OK 사인! 승리 포즈"},
        "fighting": {"motion": 22, "description": "AttackReady - 화이팅! 전투 준비"},
        "clap": {"motion": 17, "description": "Win - 박수! 승리 포즈"},
        "dance": {"motion": 56, "description": "RunForward - 춤! 신나게 달리기"},
        "muscle": {"motion": 22, "description": "AttackReady - 근육! 힘 자세"},
        "pray": {"motion": 19, "description": "Bow - 기도! 인사"},
        "point": {"motion": 7, "description": "TurnL - 가리키기! 왼쪽 돌아보기"},
        "shh": {"motion": 1, "description": "Ready - 쉿! 준비 자세"},
        "waving": {"motion": 18, "description": "Hi - 손 흔들기"},
        "sleepy": {"motion": 115, "description": "SafeSit - 졸림, 앉기"},
        "headshake": {"motion": 16, "description": "Lose - 고개 흔들기 (아니요)"},
        "nod": {"motion": 19, "description": "Bow - 고개 끄덕이기 (네)"},

        # === 긍정적 감정 (15개) ===
        "happy": {"motion": 17, "description": "Win - 승리 포즈 (두 팔 들기)"},
        "excited": {"motion": 56, "description": "RunForward - 신나서 달리기"},
        "joy": {"motion": 17, "description": "Win - 기쁨의 승리 포즈"},
        "proud": {"motion": 17, "description": "Win - 자랑스러운 포즈"},
        "celebrating": {"motion": 17, "description": "Win - 축하 포즈"},
        "greeting": {"motion": 18, "description": "Hi - 손 흔들며 인사"},
        "playful": {"motion": 20, "description": "TumbleF - 앞구르기 (장난)"},
        "energetic": {"motion": 56, "description": "RunForward - 달리기"},
        "love": {"motion": 18, "description": "Hi - 애정 표현 손 흔들기"},
        "affectionate": {"motion": 18, "description": "Hi - 다정한 손 흔들기"},
        "grateful": {"motion": 19, "description": "Bow - 감사 인사"},
        "thankful": {"motion": 19, "description": "Bow - 고마움 표현"},
        "hopeful": {"motion": 116, "description": "SafeUp - 희망차게 일어서기"},
        "confident": {"motion": 22, "description": "AttackReady - 자신감 있는 자세"},
        "encouraging": {"motion": 17, "description": "Win - 격려 포즈"},

        # === 인사/사교 감정 (8개) ===
        "welcoming": {"motion": 18, "description": "Hi - 반가움 인사"},
        "friendly": {"motion": 18, "description": "Hi - 친근한 인사"},
        "respectful": {"motion": 19, "description": "Bow - 존경의 인사"},
        "apologetic": {"motion": 19, "description": "Bow - 사과/미안함"},
        "sorry": {"motion": 19, "description": "Bow - 죄송함 표현"},
        "polite": {"motion": 19, "description": "Bow - 공손한 인사"},
        "agreeing": {"motion": 18, "description": "Hi - 동의/수긍"},
        "acknowledging": {"motion": 18, "description": "Hi - 알겠다는 표현"},

        # === 부정적/슬픔 감정 (10개) ===
        "sad": {"motion": 16, "description": "Lose - 패배/슬픔 포즈"},
        "disappointed": {"motion": 16, "description": "Lose - 실망 포즈"},
        "depressed": {"motion": 93, "description": "Laydown - 우울하게 눕기"},
        "crying": {"motion": 16, "description": "Lose - 울음/슬픔"},
        "embarrassed": {"motion": 19, "description": "Bow - 부끄러움"},
        "shy": {"motion": 19, "description": "Bow - 수줍음"},
        "lonely": {"motion": 115, "description": "SafeSit - 외로움에 앉기"},
        "melancholy": {"motion": 16, "description": "Lose - 우수에 잠김"},
        "regretful": {"motion": 19, "description": "Bow - 후회/반성"},
        "guilty": {"motion": 19, "description": "Bow - 죄책감"},

        # === 분노/짜증 감정 (8개) ===
        "angry": {"motion": 36, "description": "OneTwoPunch - 원투 펀치"},
        "annoyed": {"motion": 47, "description": "Shoulder - 어깨 으쓱 (짜증)"},
        "furious": {"motion": 52, "description": "DoublePunch - 더블 펀치"},
        "aggressive": {"motion": 22, "description": "AttackReady - 전투 준비"},
        "frustrated": {"motion": 50, "description": "SpinBlow - 답답함 표현"},
        "irritated": {"motion": 47, "description": "Shoulder - 짜증"},
        "impatient": {"motion": 60, "description": "RunLeft - 조급함 표현"},
        "resentful": {"motion": 48, "description": "Elbow - 분함 표현"},

        # === 놀람/두려움 (8개) ===
        "surprised": {"motion": 21, "description": "TumbleB - 깜짝 놀람 (뒤로)"},
        "shocked": {"motion": 21, "description": "TumbleB - 충격 (뒤로 물러남)"},
        "scared": {"motion": 23, "description": "Defence - 방어 자세"},
        "afraid": {"motion": 23, "description": "Defence - 두려움"},
        "nervous": {"motion": 23, "description": "Defence - 긴장/불안"},
        "amazed": {"motion": 47, "description": "Shoulder - 놀라움"},
        "astonished": {"motion": 47, "description": "Shoulder - 경탄"},
        "startled": {"motion": 21, "description": "TumbleB - 깜짝 놀라 뒤로"},

        # === 호기심/관심 (6개) ===
        "curious": {"motion": 7, "description": "TurnL - 고개 돌려 살펴보기"},
        "interested": {"motion": 8, "description": "TurnR - 관심있게 돌아보기"},
        "intrigued": {"motion": 7, "description": "TurnL - 흥미롭게 바라보기"},
        "questioning": {"motion": 47, "description": "Shoulder - 의문 표현"},
        "wondering": {"motion": 7, "description": "TurnL - 궁금해하며 돌아보기"},
        "attentive": {"motion": 1, "description": "Ready - 집중 자세"},

        # === 중립/차분 (6개) ===
        "neutral": {"motion": 1, "description": "Ready - 준비 자세"},
        "calm": {"motion": 1, "description": "Ready - 차분한 자세"},
        "relaxed": {"motion": 115, "description": "SafeSit - 편안히 앉기"},
        "peaceful": {"motion": 115, "description": "SafeSit - 평화로운 휴식"},
        "serene": {"motion": 115, "description": "SafeSit - 고요한 안정"},
        "content": {"motion": 1, "description": "Ready - 만족스러운 자세"},

        # === 생각/집중 (6개) ===
        "thinking": {"motion": 7, "description": "TurnL - 고개 돌려 생각"},
        "confused": {"motion": 47, "description": "Shoulder - 어깨 으쓱 (혼란)"},
        "contemplating": {"motion": 115, "description": "SafeSit - 앉아서 사색"},
        "focused": {"motion": 1, "description": "Ready - 집중 자세"},
        "pondering": {"motion": 7, "description": "TurnL - 생각에 잠김"},
        "uncertain": {"motion": 47, "description": "Shoulder - 불확실함"},

        # === 피로/지루함 (6개) ===
        "tired": {"motion": 97, "description": "FallDown - 쓰러짐/피로"},
        "bored": {"motion": 47, "description": "Shoulder - 어깨 으쓱 (지루)"},
        "exhausted": {"motion": 93, "description": "Laydown - 지쳐서 눕기"},
        "sleepy": {"motion": 115, "description": "SafeSit - 졸려서 앉기"},
        "weary": {"motion": 97, "description": "FallDown - 기력 소진"},
        "drowsy": {"motion": 115, "description": "SafeSit - 나른함"},

        # === 거부/부정 (4개) ===
        "refusing": {"motion": 8, "description": "TurnR - 고개 돌림 (거부)"},
        "denying": {"motion": 5, "description": "Left - 옆으로 피함"},
        "rejecting": {"motion": 6, "description": "Right - 물러남"},
        "dismissive": {"motion": 47, "description": "Shoulder - 무시 표현"},

        # === 기대/설렘 (4개) ===
        "anticipating": {"motion": 56, "description": "RunForward - 기대하며 달려감"},
        "eager": {"motion": 56, "description": "RunForward - 열정적으로"},
        "excited_wait": {"motion": 1, "description": "Ready - 기대하며 대기"},
        "looking_forward": {"motion": 7, "description": "TurnL - 기대하며 바라봄"},

        # === 위로/공감 (4개) ===
        "comforting": {"motion": 18, "description": "Hi - 위로 손 흔들기"},
        "sympathetic": {"motion": 19, "description": "Bow - 공감 표현"},
        "caring": {"motion": 18, "description": "Hi - 배려하는 인사"},
        "supportive": {"motion": 17, "description": "Win - 응원 포즈"},

        # === 장난/유머 (4개) ===
        "mischievous": {"motion": 20, "description": "TumbleF - 장난 구르기"},
        "teasing": {"motion": 61, "description": "RunRight - 장난치며 도망"},
        "humorous": {"motion": 20, "description": "TumbleF - 재미있는 동작"},
        "silly": {"motion": 21, "description": "TumbleB - 엉뚱한 동작"},
    }

    # 얼굴 인식 시 감정별 TTS 응답 메시지
    EMOTION_RESPONSES = {
        # 제스처 반응
        "victory": ["오 브이! 멋져요!", "예! 승리!", "화이팅이에요!"],
        "thumbsup": ["좋아요!", "최고예요!", "잘하고 계세요!"],

        # 긍정적 감정
        "happy": ["기분 좋아 보여요!", "오 웃고 계시네요!", "좋은 일 있으셨어요?"],
        "excited": ["와 신나 보여요!", "무슨 좋은 일이에요?", "저도 덩달아 신나요!"],
        "joy": ["너무 행복해 보여요!", "좋은 일이 있나봐요!", "저도 기뻐요!"],

        # 인사
        "greeting": ["안녕하세요!", "반가워요!", "오 안녕하세요!"],
        "waving": ["안녕하세요! 반가워요!", "저도 인사할게요!"],

        # 부정적 감정
        "sad": ["왜요? 무슨 일 있어요?", "괜찮으세요?", "힘든 일 있으면 얘기해주세요"],
        "disappointed": ["실망하셨어요?", "괜찮아요, 힘내세요!", "무슨 일이에요?"],
        "angry": ["화나셨어요?", "진정하세요!", "무슨 일인지 말해주세요"],
        "annoyed": ["짜증나는 일 있으셨어요?", "에휴, 힘드셨겠다"],

        # 놀람/두려움
        "surprised": ["오 놀랐어요?", "깜짝이야!", "무슨 일이에요?"],
        "scared": ["괜찮아요! 제가 있잖아요", "무서워요?", "걱정 마세요!"],

        # 피로/지루함
        "tired": ["피곤해 보여요, 좀 쉬세요!", "힘드시죠?", "오늘 많이 힘드셨나봐요"],
        "bored": ["심심하세요?", "뭐 재밌는 거 할까요?", "저랑 얘기해요!"],
        "sleepy": ["졸려 보여요!", "잠이 부족하신가봐요", "커피 한잔 어때요?"],

        # 생각/혼란
        "thinking": ["뭐 생각하세요?", "고민 있으세요?", "무슨 생각해요?"],
        "confused": ["헷갈리세요?", "제가 도와드릴까요?", "뭐가 궁금하세요?"],
        "curious": ["호기심이 생기셨나요?", "뭐가 궁금해요?"],

        # 차분/평온
        "calm": ["편안해 보여요!", "좋은 하루네요!"],
        "neutral": [],  # 무표정일 때는 말 안함
        "relaxed": ["여유로워 보여요!", "좋은 시간 보내고 계시네요"],

        # 특별 제스처
        "heart": ["오 하트! 저도 좋아해요!", "사랑해요!"],
        "ok": ["오케이! 알겠어요!", "좋아요!"],
        "fighting": ["화이팅! 힘내세요!", "응원할게요!"],
        "clap": ["짝짝짝! 대단해요!", "잘했어요!"],
        "dance": ["오 춤추고 계세요? 신나네요!", "저도 춤출게요!"],
        "muscle": ["오 근육! 멋져요!", "운동하셨어요?"],
        "pray": ["기도하세요?", "좋은 일이 있을 거예요!"],
        "point": ["저요?", "뭘 가리키세요?", "어디요?"],
        "shh": ["쉿! 조용히 할게요", "알겠어요, 조용히"],
        "headshake": ["싫으세요?", "아니에요?", "안 된다고요?"],
        "nod": ["네! 알겠어요!", "동의하시는군요!", "좋아요!"],
    }

    def __init__(self):
        self.serial_conn = None
        self.connected = False
        self.camera = None
        self.camera_running = False
        self.last_analysis_time = 0
        self.analysis_interval = 5.0  # 기본 5초 (빠른 표정 변화 감지)
        self.brightness = 0  # 밝기 조절 (-100 ~ 100)
        self.whisper = None
        print("Initializing Edge TTS...")
        self.tts = edge_TTS.Edge_TTS()
        print("Edge TTS initialized")
        # 대화 히스토리 저장 (자연스러운 대화를 위해)
        self.conversation_history = []
        self.max_history = 15  # 최대 15개의 대화 기록 유지 (더 긴 맥락)
        # 페르소나 설정 (기본: rony - 로니)
        self.current_persona = "rony"
        # 기본 페르소나에 맞는 목소리 설정
        if 'voice_index' in self.PERSONAS[self.current_persona]:
            self.tts.set_voice(self.PERSONAS[self.current_persona]['voice_index'])
        # 카메라 프레임 동기화용 변수
        self.latest_frame = None
        self.frame_lock = threading.Lock()
        # 자연스러운 대화를 위한 추가 상태
        self.user_name = None  # 사용자 이름 기억
        self.last_emotion = "neutral"  # 이전 감정 상태 기억
        self.conversation_context = {
            "topics_discussed": [],  # 논의된 주제들
            "user_preferences": {},  # 사용자 선호도
            "mood_history": [],  # 감정 변화 기록
        }
        # 일정 관리
        self.schedules_file = "schedules.json"
        self.schedules = self._load_schedules()
        print(f"Default persona set: {self.PERSONAS[self.current_persona]['name']}")
        print(f"Loaded {len(self.schedules)} schedules")
        # IoT 초기화
        self.iot_devices = {
            "light": {
                "name": "조명",
                "ip": "172.20.10.2",
                "port": 5501,
                "state": False,
                "on_command": b'LED_ON',
                "off_command": b'LED_OFF',
            }
        }
        print("[IoT] IoT 기기 제어 초기화 완료")

    def connect_humanoid(self, port: str, baudrate: int = 115200) -> bool:
        try:
            print(f"Connecting to humanoid on {port}...")
            self.serial_conn = serial.Serial(port, baudrate, timeout=1)
            time.sleep(0.5)
            self.connected = True
            print(f"Humanoid connected successfully on {port}")
            return True
        except Exception as e:
            print(f"Humanoid connection failed: {e}")
            return False

    def disconnect_humanoid(self):
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
            self.connected = False

    def send_motion(self, motion_id: int) -> bool:
        if not self.connected or not self.serial_conn:
            print(f"Cannot send motion {motion_id}: Humanoid not connected")
            return False
        if motion_id < 1 or motion_id > 242:
            print(f"Invalid motion ID: {motion_id}")
            return False
        try:
            exe_cmd = [
                0xff, 0xff, 0x4c, 0x53, 0x00,
                0x00, 0x00, 0x00, 0x30, 0x0c, 0x03,
                0x01, 0x00, 100, 0x00
            ]
            exe_cmd[11] = motion_id
            checksum = sum(exe_cmd[6:14]) & 0xFF
            exe_cmd[14] = checksum
            self.serial_conn.write(exe_cmd)
            print(f"Sent motion {motion_id} to humanoid")
            time.sleep(0.1)
            return True
        except Exception as e:
            print(f"Error sending motion {motion_id}: {e}")
            return False

    def init_camera(self, camera_index: int = 0) -> bool:
        try:
            # 기존 카메라가 있으면 먼저 닫기
            if self.camera is not None:
                try:
                    self.camera.release()
                    print("Released previous camera")
                except:
                    pass

            self.camera = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)  # DirectShow 사용 (Windows)
            if not self.camera.isOpened():
                print(f"Failed to open camera index {camera_index}")
                return False

            # 카메라 인덱스 저장 (외부캠/내장캠 구분용)
            self.camera_index = camera_index

            # MJPEG 코덱 먼저 설정 (고해상도에서 더 빠른 전송)
            self.camera.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))

            # 카메라 해상도 설정 (HD 해상도로 고화질)
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            self.camera.set(cv2.CAP_PROP_FPS, 30)

            # 버퍼 크기 최소화 (지연 감소)
            self.camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            # 자동 초점 활성화 (지원되는 경우)
            self.camera.set(cv2.CAP_PROP_AUTOFOCUS, 1)

            # 화이트밸런스 자동
            self.camera.set(cv2.CAP_PROP_AUTO_WB, 1)

            # 외부 캠(인덱스 1번 이상)과 내장 캠(0번) 다르게 설정
            if camera_index == 0:
                # 내장 카메라: 밝기 올림
                self.camera.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)  # 수동 노출
                self.camera.set(cv2.CAP_PROP_EXPOSURE, -4)  # 노출 올림
                self.camera.set(cv2.CAP_PROP_BRIGHTNESS, 220)  # 밝기 더 올림
                self.camera.set(cv2.CAP_PROP_CONTRAST, 55)  # 대비
                self.camera.set(cv2.CAP_PROP_SATURATION, 55)
                self.camera.set(cv2.CAP_PROP_GAIN, 80)  # 게인 올림
                self.camera.set(cv2.CAP_PROP_SHARPNESS, 3)  # 선명도
                print(f"[카메라] 내장 카메라 설정 적용")
            else:
                # 외부 캠: 자동 노출 사용 (뿌옇게 나오는 문제 해결)
                self.camera.set(cv2.CAP_PROP_AUTO_EXPOSURE, 3)  # 자동 노출 모드 (3=auto)
                self.camera.set(cv2.CAP_PROP_BRIGHTNESS, 128)  # 밝기 기본값
                self.camera.set(cv2.CAP_PROP_CONTRAST, 70)  # 대비 높여서 선명하게
                self.camera.set(cv2.CAP_PROP_SATURATION, 60)
                self.camera.set(cv2.CAP_PROP_GAIN, 50)  # 게인 낮춤 (노이즈 감소)
                self.camera.set(cv2.CAP_PROP_SHARPNESS, 5)  # 선명도 높임
                print(f"[카메라] 외부 캠 설정 적용 (선명도 개선)")

            # 실제 설정된 해상도 확인
            actual_width = int(self.camera.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(self.camera.get(cv2.CAP_PROP_FRAME_HEIGHT))
            actual_fps = int(self.camera.get(cv2.CAP_PROP_FPS))

            # 최신 프레임 초기화 (frame_lock은 __init__에서 이미 생성됨)
            with self.frame_lock:
                self.latest_frame = None

            self.camera_running = True
            print(f"Camera {camera_index} opened successfully at {actual_width}x{actual_height} @ {actual_fps}fps")
            return True
        except Exception as e:
            print(f"Camera init error: {e}")
            return False

    def capture_frame(self, resize_for_analysis: bool = False) -> Optional[bytes]:
        if not self.camera or not self.camera_running:
            return None
        ret, frame = self.camera.read()
        if not ret:
            return None

        # 감정 분석용이면 이미지 크기를 줄여서 GPT API 속도 향상
        if resize_for_analysis:
            frame = cv2.resize(frame, (640, 480))
            # JPEG 압축 품질 (분석 정확도 유지)
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 85]
        else:
            # 웹 전송용 - 고품질
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 90]

        _, buffer = cv2.imencode('.jpg', frame, encode_param)
        return buffer.tobytes()

    def analyze_expression_with_gpt(self, image_bytes: bytes) -> Tuple[Optional[str], Optional[str]]:
        try:
            base64_image = base64.b64encode(image_bytes).decode('utf-8')
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": """이 사진에서 사람의 표정과 제스처를 분석해주세요.

## 분석 방법
1. 먼저 얼굴 표정을 확인하세요 (눈, 입, 눈썹, 이마)
2. 손 제스처가 있으면 함께 확인하세요
3. 모자, 안경을 써도 보이는 부분으로 판단하세요

## 표정 목록 (얼굴 기반)
- happy: 입꼬리가 올라감, 웃는 눈
- sad: 입꼬리가 내려감, 슬픈 눈
- angry: 눈썹이 찌푸려짐, 입을 꽉 다물거나 벌림
- surprised: 눈이 크게 뜨임, 입이 벌어짐
- tired: 눈이 처짐, 피곤한 표정
- thinking: 눈을 위로 또는 옆으로, 생각하는 표정
- neutral: 무표정, 평범한 얼굴
- calm: 편안하고 여유로운 표정
- confused: 눈썹을 찌푸리며 의아한 표정
- excited: 매우 밝고 들뜬 표정

## 제스처 목록 (손/머리)
- victory: V사인 (손가락 2개 펼침)
- thumbsup: 엄지 척
- waving: 손 흔들기
- heart: 하트 모양
- ok: OK 사인
- fighting: 주먹 쥐고 화이팅
- muscle: 팔뚝 근육 자랑
- point: 손가락으로 가리키기
- headshake: 고개 좌우로 흔들기 (아니요)
- nod: 고개 끄덕이기 (네)

## 응답 형식 (반드시 이 형식으로!)
Emotion: [위 목록에서 하나만]
Description: [한국어로 짧게 설명]

예시:
Emotion: happy
Description: 밝게 웃고 있어요"""
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}",
                                "detail": "low"
                            }
                        }
                    ]
                }],
                max_tokens=60
            )

            result = response.choices[0].message.content
            print(f"[GPT Vision] Raw response: {result}")

            emotion = None
            description = None
            lines = result.strip().split('\n')
            for line in lines:
                if line.lower().startswith('emotion:'):
                    # 감정 텍스트 추출 및 정규화
                    emotion_text = line.split(':', 1)[1].strip().lower()
                    # 여러 단어가 있을 경우 첫 번째 단어만 사용
                    emotion_text = emotion_text.split()[0] if emotion_text else ""
                    # 특수문자 제거
                    emotion_text = ''.join(c for c in emotion_text if c.isalnum())

                    print(f"[GPT Vision] Parsed emotion: '{emotion_text}'")

                    # 정확한 매칭 먼저 시도
                    if emotion_text in self.EMOTION_ACTIONS:
                        emotion = emotion_text
                        print(f"[GPT Vision] Exact match: {emotion}")
                    else:
                        # 유사 감정 → EMOTION_ACTIONS에 있는 감정으로 매핑
                        emotion_mapping = {
                            # 제스처 관련 (최우선)
                            'peace': 'victory', 'vsign': 'victory', 'v_sign': 'victory',
                            'peacesign': 'victory', 'peace_sign': 'victory',
                            'twofingersup': 'victory', 'two_fingers': 'victory',
                            'thumbs_up': 'thumbsup', 'thumb_up': 'thumbsup', 'thumb': 'thumbsup',
                            'heartsign': 'heart', 'heart_sign': 'heart', 'lovesign': 'heart',
                            'oksign': 'ok', 'ok_sign': 'ok', 'okay': 'ok',
                            'wave': 'waving', 'wavinghand': 'waving', 'bye': 'waving',
                            'fist': 'fighting', 'fistpump': 'fighting', 'punch': 'fighting',
                            'clapping': 'clap', 'applause': 'clap',
                            'flexing': 'muscle', 'flex': 'muscle', 'bicep': 'muscle',
                            'pointing': 'point', 'fingerpoint': 'point', 'finger': 'point',
                            'quiet': 'shh', 'silence': 'shh', 'hush': 'shh',
                            'praying': 'pray', 'namaste': 'pray', 'thanks': 'pray',
                            'dancing': 'dance', 'groove': 'dance', 'move': 'dance',
                            'yawn': 'sleepy', 'yawning': 'sleepy', 'drowsy': 'sleepy',
                            'shaking': 'headshake', 'no': 'headshake', 'disagree': 'headshake',
                            'nodding': 'nod', 'yes': 'nod', 'agree': 'nod',
                            # thinking/생각 관련
                            'contemplate': 'contemplating', 'pensive': 'thinking',
                            'thoughtful': 'thinking', 'concentrating': 'focused',
                            'reflective': 'contemplating', 'meditative': 'contemplating',
                            # calm/평온 관련
                            'tranquil': 'peaceful', 'composed': 'calm', 'steady': 'calm',
                            # happy/긍정 관련
                            'joyful': 'joy', 'smiling': 'happy', 'grinning': 'happy',
                            'cheerful': 'happy', 'pleased': 'happy', 'delighted': 'joy',
                            'elated': 'excited', 'overjoyed': 'joy', 'blissful': 'happy',
                            # excited/흥분 관련
                            'thrilled': 'excited', 'enthusiastic': 'excited', 'hyped': 'excited',
                            'ecstatic': 'excited', 'exhilarated': 'excited',
                            # love/애정 관련
                            'loving': 'love', 'adoring': 'affectionate', 'tender': 'caring',
                            'warmth': 'affectionate', 'endearing': 'love',
                            # annoyed/짜증 관련
                            'agitated': 'annoyed', 'vexed': 'irritated', 'bothered': 'annoyed',
                            # scared/두려움 관련
                            'fearful': 'scared', 'anxious': 'nervous', 'worried': 'nervous',
                            'terrified': 'scared', 'frightened': 'afraid', 'panicked': 'scared',
                            # tired/피로 관련
                            'fatigued': 'exhausted', 'drained': 'exhausted', 'worn': 'weary',
                            'lethargic': 'drowsy', 'sluggish': 'tired',
                            # sad/슬픔 관련
                            'unhappy': 'sad', 'gloomy': 'melancholy', 'sorrowful': 'sad',
                            'heartbroken': 'sad', 'grief': 'crying', 'mournful': 'sad',
                            # neutral 관련
                            'expressionless': 'neutral', 'blank': 'neutral', 'none': 'neutral',
                            'normal': 'neutral', 'stoic': 'neutral', 'indifferent': 'neutral',
                            # angry/분노 관련
                            'mad': 'angry', 'enraged': 'furious', 'outraged': 'furious',
                            'livid': 'furious', 'irate': 'angry', 'hostile': 'aggressive',
                            # surprised/놀람 관련
                            'stunned': 'shocked', 'flabbergasted': 'astonished', 'dumbfounded': 'shocked',
                            # greeting/인사 관련
                            'hello': 'greeting', 'hi': 'greeting', 'welcome': 'welcoming',
                            # curious/호기심 관련
                            'inquisitive': 'curious', 'nosy': 'curious', 'eager_to_know': 'interested',
                            # apologetic 관련
                            'remorseful': 'regretful', 'contrite': 'apologetic',
                            # playful/장난 관련
                            'cheeky': 'mischievous', 'joking': 'humorous', 'funny': 'humorous',
                            'witty': 'humorous', 'goofy': 'silly', 'clowning': 'silly',
                            # supportive/응원 관련
                            'cheering': 'encouraging', 'motivating': 'encouraging',
                            'reassuring': 'comforting', 'consoling': 'comforting',
                        }
                        emotion = emotion_mapping.get(emotion_text, 'neutral')
                        print(f"[GPT Vision] Mapped: {emotion_text} -> {emotion}")

                elif line.lower().startswith('description:'):
                    description = line.split(':', 1)[1].strip()

            return emotion, description
        except Exception as e:
            print(f"GPT analysis failed: {e}")
            return None, None

    def run_face_analysis_loop(self):
        """프레임 전송 전용 루프 (빠른 프레임 전송)"""
        emit_interval = 0.033  # 33ms = 약 30fps
        last_emit_time = 0

        while self.camera_running:
            current_time = time.time()

            # 프레임 읽기
            ret, frame = self.camera.read()
            if not ret or frame is None:
                continue

            # 웹 전송 간격 체크
            if current_time - last_emit_time >= emit_interval:
                # 밝기 조절 적용
                display_frame = frame.copy()
                if self.brightness != 0:
                    display_frame = cv2.convertScaleAbs(display_frame, alpha=1.0, beta=self.brightness)

                # JPEG 압축 (빠르게)
                encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 70]
                _, buffer = cv2.imencode('.jpg', display_frame, encode_param)

                # 웹으로 전송
                base64_image = base64.b64encode(buffer.tobytes()).decode('utf-8')
                socketio.emit('video_frame', {'image': base64_image})

                # 최신 프레임 저장 (감정 분석용 - 밝기 적용된 프레임)
                with self.frame_lock:
                    self.latest_frame = display_frame.copy()

                last_emit_time = current_time

    def run_emotion_analysis_loop(self):
        """감정 분석 전용 루프 (별도 스레드에서 실행)"""
        last_detected_emotion = None

        while self.camera_running:
            current_time = time.time()

            # 분석 간격 체크
            if current_time - self.last_analysis_time < self.analysis_interval:
                time.sleep(0.1)
                continue

            # 프레임 가져오기
            analysis_frame = None
            with self.frame_lock:
                if self.latest_frame is not None:
                    analysis_frame = self.latest_frame.copy()

            if analysis_frame is None:
                time.sleep(0.1)
                continue

            print(f"[분석] 감정 분석 시작...")
            self.last_analysis_time = current_time

            try:
                # 분석용 해상도 (동작 인식을 위해 크게)
                small_frame = cv2.resize(analysis_frame, (1024, 768))

                # 밝기 조절 적용 (슬라이더 값 사용)
                if self.brightness != 0:
                    small_frame = cv2.convertScaleAbs(small_frame, alpha=1.0, beta=self.brightness)

                encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 80]
                _, buffer = cv2.imencode('.jpg', small_frame, encode_param)
                analysis_image = buffer.tobytes()

                emotion, description = self.analyze_expression_with_gpt(analysis_image)

                if emotion:
                    print(f"[분석] 감정 감지: {emotion}")

                    # 표정 변화 감지: 이전 감정과 다를 때만 동작 및 TTS 실행
                    if emotion != last_detected_emotion:
                        print(f"[표정 변화] {last_detected_emotion} → {emotion}")
                        self.execute_emotion_action(emotion)

                        # TTS 응답 (감정별 메시지)
                        if emotion in self.EMOTION_RESPONSES and self.EMOTION_RESPONSES[emotion]:
                            response_msg = random.choice(self.EMOTION_RESPONSES[emotion])
                            print(f"[TTS] {response_msg}")
                            socketio.emit('log', {'message': f'🗣️ 로봇: {response_msg}'})
                            # TTS 실행 (별도 스레드)
                            threading.Thread(target=self.tts.run, args=(response_msg,), kwargs={'emotion': emotion}, daemon=True).start()

                        last_detected_emotion = emotion

                    socketio.emit('emotion_detected', {
                        'emotion': emotion,
                        'description': description,
                        'source': 'face'
                    })
            except Exception as e:
                print(f"[분석 오류] {e}")

    def stop_camera(self):
        self.camera_running = False
        # 프레임 데이터 정리
        with self.frame_lock:
            self.latest_frame = None
        if self.camera:
            try:
                self.camera.release()
                print("Camera released successfully")
            except Exception as e:
                print(f"Error releasing camera: {e}")
        self.camera = None

    def load_whisper(self, model_size="base"):
        """
        Whisper 음성인식 모델 로드

        Args:
            model_size: 모델 크기 ("tiny", "base", "small", "medium", "large")
                       - tiny: 가장 빠름, 정확도 낮음 (39MB)
                       - base: 빠름, 기본 정확도 (142MB) - 권장
                       - small: 높은 정확도, 느림 (461MB)
                       - medium: 더 높은 정확도, 매우 느림 (1.5GB)
                       - large: 최고 정확도, 매우 느림 (2.9GB)
        """
        try:
            print(f"Loading Whisper model ({model_size})...")
            print(f"[참고] 처음 로딩 시 모델 다운로드로 시간이 걸릴 수 있습니다.")
            self.whisper = whisper_STT.Whisper(model_size=model_size)
            print("Whisper model loaded successfully")
            return True
        except Exception as e:
            print(f"Whisper loading failed: {e}")
            import traceback
            traceback.print_exc()
            return False

    def listen_and_respond(self) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        if not self.whisper:
            print("Whisper not loaded")
            return None, None, None

        print("Listening for voice input...")
        user_text = self.whisper.run()

        if not user_text:
            print("No voice input detected")
            return None, None, None

        print(f"User said: {user_text}")

        # 사용자 입력에서 직접 조명 명령 감지 (GPT 응답과 별개로)
        user_text_lower = user_text.lower()
        detected_light_action = None
        light_on_keywords = ["불 켜", "불켜", "조명 켜", "조명켜", "전등 켜", "전등켜", "라이트 켜", "라이트켜", "불을 켜", "불좀 켜"]
        light_off_keywords = ["불 꺼", "불꺼", "조명 꺼", "조명꺼", "전등 꺼", "전등꺼", "라이트 꺼", "라이트꺼", "불을 꺼", "불좀 꺼"]

        for keyword in light_on_keywords:
            if keyword in user_text_lower:
                detected_light_action = "light_on"
                print(f"[음성] 조명 켜기 키워드 감지: '{keyword}'")
                break
        if not detected_light_action:
            for keyword in light_off_keywords:
                if keyword in user_text_lower:
                    detected_light_action = "light_off"
                    print(f"[음성] 조명 끄기 키워드 감지: '{keyword}'")
                    break

        # GPT 분석 (감정, 응답, 동작 명령)
        emotion, gpt_response, action = self.analyze_text_with_gpt(user_text)

        print(f"Detected emotion: {emotion}")
        print(f"GPT response: {gpt_response}")
        if action:
            print(f"Action command: {action}")

        # 직접 감지한 조명 명령이 있으면 action으로 설정
        if detected_light_action and not action:
            action = detected_light_action
            print(f"[음성] 직접 감지된 조명 명령 사용: {action}")

        # 1. 먼저 TTS로 응답
        if gpt_response:
            print(f"Calling TTS with response: {gpt_response}")
            try:
                self.tts.run(gpt_response, emotion=emotion)
                print("TTS called successfully with emotion style")
            except Exception as e:
                print(f"TTS call failed: {e}")

        # 2. 동작 명령이 있으면 실행 (TTS 후에)
        if action:
            print(f"[음성 명령] 동작 실행: {action}")
            self.execute_voice_command(action)
        # 동작 명령이 없으면 감정에 따른 동작 실행
        elif emotion:
            print(f"Executing emotion action: {emotion}")
            self.execute_emotion_action(emotion)

        return user_text, emotion, gpt_response

    def analyze_text_with_gpt(self, user_text: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """GPT로 텍스트 분석하여 감정, 응답, 동작 명령 반환"""
        try:
            print(f"Sending to GPT: {user_text}")
            print(f"Current persona: {self.PERSONAS[self.current_persona]['name']}")

            # 선택된 페르소나의 시스템 프롬프트 가져오기
            persona_prompt = self.PERSONAS[self.current_persona]["system_prompt"]

            # 대화 맥락 정보 구성
            context_info = ""

            # 현재 한국 시간 추가
            kst = timezone(timedelta(hours=9))  # 한국 표준시 (UTC+9)
            now_korea = datetime.now(kst)
            current_time_str = now_korea.strftime("%Y년 %m월 %d일 %A %H시 %M분")
            # 요일을 한국어로 변환
            weekday_kr = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
            current_time_str = now_korea.strftime(f"%Y년 %m월 %d일 {weekday_kr[now_korea.weekday()]} %H시 %M분")
            context_info += f"\n현재 한국 시간: {current_time_str}"

            if self.user_name:
                context_info += f"\n사용자 이름: {self.user_name}"
            if self.last_emotion and self.last_emotion != "neutral":
                context_info += f"\n이전 감정 상태: {self.last_emotion}"
            if self.conversation_context.get("mood_history"):
                recent_moods = self.conversation_context["mood_history"][-3:]
                context_info += f"\n최근 감정 흐름: {' -> '.join(recent_moods)}"

            # 일정 정보 추가
            schedule_info = self.get_schedule_summary_for_gpt()
            if schedule_info:
                context_info += schedule_info

            # 공통 지시사항 추가 - 자연스러운 대화를 위한 개선된 버전
            common_instructions = f"""
{context_info}

## 핵심 원칙: 진짜 친구처럼 대화하기

당신은 사용자의 친한 친구입니다. 로봇이라는 사실을 잊고, 진짜 사람 친구처럼 자연스럽게 대화하세요.

### 대화 스타일 (친근한 존댓말)
- 추임새 자연스럽게: "오~", "아~", "에휴", "우와", "진짜요?", "대박이에요!"
- 공감 먼저: 조언보다 먼저 상대방 감정에 공감
- 후속 질문: 관심을 보이며 대화 이어가기
- 리액션 풍부하게: 놀라움, 기쁨, 안타까움 등 감정 표현
- 시간/날짜 질문: 위에 제공된 '현재 한국 시간' 정보를 활용해서 자연스럽게 대답

### 상황별 대화 패턴

**기쁜 소식 들었을 때:**
- "우와 진짜요? 너무 좋겠다! 어떻게 된 거예요?"
- "오~ 대박이에요! 축하드려요!"

**힘든 일 들었을 때:**
- "에휴... 많이 힘드셨겠어요. 괜찮으세요?"
- "아이고... 속상하시겠다. 무슨 일이었어요?"

**일상 대화:**
- "오 그러셨어요? 저도 궁금해요! 더 얘기해주세요~"
- "아 맞다! 그러고 보니까..."

**인사:**
- "안녕하세요! 반가워요~ 오늘 하루는 어떠셨어요?"
- "오랜만이에요! 잘 지내셨어요?"

**일정 질문 처리 (매우 중요!):**
사용자가 일정에 대해 물어보면 위에 제공된 '사용자의 일정'을 확인해서 알려주세요!

키워드 인식:
- "내일" → 내일 일정 확인
- "모레" → 모레 일정 확인
- "다음주", "다음 주" → 7일 이내 일정 모두 알려주기
- "이번주", "이번 주" → 7일 이내 일정 모두 알려주기
- "월요일/화요일/수요일/목요일/금요일/토요일/일요일" → 해당 요일 일정 확인
- "일정 있어?", "뭐 있어?", "약속 있어?" → 7일 이내 일정 모두 알려주기

응답 예시:
- "내일 일정 있어?" → "내일요? 음... OOO 있으시네요! 준비는 잘 되셨어요?"
- "다음주 뭐 있어?" → "다음주요? 음... 화요일에 OOO, 목요일에 OOO 있으시네요!"
- "이번주 금요일에 뭐해?" → "금요일요? OOO 있으시던데요! 기대되시겠다~"
- 일정이 없으면: "음... 특별한 일정은 없는 것 같아요! 뭔가 계획하시려고요?"

### 하지 말아야 할 것
- 딱딱한 존댓말 ("~입니다", "~하십시오")
- 로봇 같은 대답 ("알겠습니다", "처리하겠습니다")
- 이모티콘 사용
- 너무 짧은 대답 (한 문장만)

### 동작 명령 인식
사용자가 동작을 요청하면 action 필드에 동작 이름을 넣으세요.

**동작 목록:**
- forward: 앞으로 가기, 앞으로 걸어가, 전진
- left: 왼쪽으로, 왼쪽 가, 좌회전
- right: 오른쪽으로, 오른쪽 가, 우회전
- turnleft: 왼쪽으로 돌아, 왼쪽 회전
- turnright: 오른쪽으로 돌아, 오른쪽 회전
- attack: 공격해, 펀치, 싸워
- defence: 방어해, 막아
- bow: 인사해, 절해
- wave: 손 흔들어, 안녕 해
- win: 만세, 승리 포즈
- sitdown: 앉아, 앉아봐
- standup: 일어나, 일어서
- dance: 춤춰, 춤 춰봐
- pickup: 물건 주워, 집어, 주워와
- grip: 잡아, 쥐어
- light_on: 불 켜, 불 켜줘, 조명 켜, 전등 켜, 라이트 켜, 불 좀 켜줘
- light_off: 불 꺼, 불 꺼줘, 조명 꺼, 전등 꺼, 라이트 꺼, 불 좀 꺼줘

**예시:**
사용자: "앞으로 가서 물건 주워와"
{{"emotion": "excited", "response": "네! 알겠어요~ 앞으로 가서 물건 주워올게요!", "action": "pickup"}}

사용자: "왼쪽으로 가봐"
{{"emotion": "friendly", "response": "왼쪽이요? 네~ 가볼게요!", "action": "left"}}

사용자: "춤 춰봐"
{{"emotion": "excited", "response": "오 춤이요? 신나네요! 춤출게요~", "action": "dance"}}

사용자: "불 켜줘" 또는 "조명 켜"
{{"emotion": "friendly", "response": "네! 불 켤게요~", "action": "light_on"}}

사용자: "불 꺼줘" 또는 "조명 꺼"
{{"emotion": "friendly", "response": "네~ 불 끌게요!", "action": "light_off"}}

### 응답 형식 (반드시 JSON으로)
반드시 아래 JSON 형식으로만 응답하세요:
{{"emotion": "감정", "response": "대화 내용"}}
동작 명령이 있으면:
{{"emotion": "감정", "response": "대화 내용", "action": "동작이름"}}

emotion은 다음 중 하나: happy, excited, grateful, greeting, friendly, sad, sympathetic, comforting, angry, annoyed, surprised, curious, neutral, calm, thinking, tired, playful

### 대화 예시

사용자: "오늘 발표 잘 끝났어"
{{"emotion": "excited", "response": "오 진짜요? 우와 고생 많으셨어요! 발표 어땠어요? 긴장 많이 하셨어요? 저도 궁금해요~"}}

사용자: "오늘 너무 피곤해"
{{"emotion": "sympathetic", "response": "에휴 무슨 일 있으셨어요? 야근하셨어요? 아니면 잠을 못 주무셨어요? 일단 따뜻한 거 한 잔 드시면서 좀 쉬세요~ 오늘 하루 고생 많으셨어요!"}}

사용자: "안녕"
{{"emotion": "greeting", "response": "안녕하세요! 반가워요~ 오늘 하루는 어떠셨어요?"}}

사용자: "지금 몇 시야?" 또는 "몇 시예요?" (시간 질문)
→ 위에 제공된 '현재 한국 시간' 정보를 보고 자연스럽게 알려주세요!
{{"emotion": "friendly", "response": "지금요? 오후 3시 25분이에요! 시간 왜요? 약속 있으세요?"}}

사용자: "시험 망한 것 같아"
{{"emotion": "sympathetic", "response": "아이고... 많이 속상하시겠어요. 근데 아직 결과 안 나왔잖아요! 생각보다 잘 나올 수도 있어요. 일단 맛있는 거 드시면서 기분 풀어요~"}}

사용자: "오늘 맛있는 거 먹었어"
{{"emotion": "curious", "response": "오 뭐 드셨어요? 저도 궁금해요! 맛집이에요? 어디서 드셨어요?"}}"""

            # 대화 메시지 구성 (히스토리 포함)
            messages = [{
                "role": "system",
                "content": persona_prompt + common_instructions
            }]

            # 대화 히스토리 추가
            messages.extend(self.conversation_history)

            # 현재 사용자 메시지 추가
            messages.append({
                "role": "user",
                "content": user_text
            })

            print(f"Conversation history length: {len(self.conversation_history)}")

            response = client.chat.completions.create(
                model="gpt-4o-mini",  # gpt-4o-mini: 빠른 응답 (2-3배 속도 향상)
                messages=messages,
                max_tokens=200  # 짧고 빠른 응답을 위해 토큰 감소
            )

            result = response.choices[0].message.content
            print(f"GPT raw response: {result}")

            emotion = None
            response_text = None

            # JSON 파싱 시도
            import json
            action = None  # 동작 명령 초기화
            try:
                # JSON 블록 추출 (```json ... ``` 또는 { ... } 형태)
                json_str = result.strip()

                # 마크다운 코드 블록 제거
                if '```json' in json_str:
                    json_str = json_str.split('```json')[1].split('```')[0].strip()
                elif '```' in json_str:
                    json_str = json_str.split('```')[1].split('```')[0].strip()

                # JSON 객체 찾기
                start_idx = json_str.find('{')
                end_idx = json_str.rfind('}') + 1
                if start_idx != -1 and end_idx > start_idx:
                    json_str = json_str[start_idx:end_idx]

                parsed = json.loads(json_str)
                emotion = parsed.get('emotion', 'neutral').lower().strip()
                response_text = parsed.get('response', '').strip()
                action = parsed.get('action', '').lower().strip()  # 동작 명령 추출
                print(f"JSON parsed - emotion: {emotion}, response: {response_text[:50]}...")
                if action:
                    print(f"Action command detected: {action}")

                # 감정 매핑 (EMOTION_ACTIONS에 없는 경우)
                emotion_mapping = {
                    'sympathetic': 'comforting',
                    'empathetic': 'comforting',
                    'concerned': 'caring',
                    'joyful': 'happy',
                    'content': 'calm',
                    'worried': 'nervous',
                    'interested': 'curious',
                }
                if emotion not in self.EMOTION_ACTIONS:
                    emotion = emotion_mapping.get(emotion, 'neutral')
                    print(f"Emotion mapped to: {emotion}")

            except (json.JSONDecodeError, KeyError, IndexError) as e:
                print(f"JSON parsing failed: {e}, trying fallback...")

                # 기존 파싱 로직 (폴백)
                lines = result.strip().split('\n')
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    if 'emotion' in line.lower() and ':' in line:
                        emotion_text = line.split(':')[-1].strip().strip('"').strip("'").lower()
                        emotion_text = emotion_text.split()[0] if emotion_text else ""
                        if emotion_text in self.EMOTION_ACTIONS:
                            emotion = emotion_text
                    elif 'response' in line.lower() and ':' in line:
                        response_text = line.split(':', 1)[-1].strip().strip('"')

                # 여전히 없으면 전체를 응답으로
                if not response_text:
                    response_text = result.strip()

            # 감정이 없으면 neutral로 설정
            if not emotion:
                emotion = "neutral"
                print("No emotion detected, using neutral")

            # 사용자 이름 감지 (자연스러운 대화를 위해)
            name_patterns = [
                r"내 이름은\s+(\S+)",
                r"제 이름은\s+(\S+)",
                r"나는\s+(\S+)(?:야|이야|입니다|이에요)",
                r"저는\s+(\S+)(?:야|이야|입니다|이에요)",
                r"(\S+)(?:라고|이라고) (?:해|불러)",
            ]
            import re
            for pattern in name_patterns:
                match = re.search(pattern, user_text)
                if match:
                    detected_name = match.group(1)
                    # 일반적인 단어 제외
                    exclude_words = ["오늘", "내일", "어제", "지금", "여기", "거기", "이거", "저거"]
                    if detected_name not in exclude_words and len(detected_name) >= 2:
                        self.user_name = detected_name
                        print(f"User name detected: {self.user_name}")
                        break

            # 감정 히스토리 기록
            if emotion:
                self.last_emotion = emotion
                self.conversation_context["mood_history"].append(emotion)
                # 최근 10개만 유지
                if len(self.conversation_context["mood_history"]) > 10:
                    self.conversation_context["mood_history"] = self.conversation_context["mood_history"][-10:]

            # 대화 히스토리에 추가
            self.conversation_history.append({
                "role": "user",
                "content": user_text
            })

            if response_text:
                self.conversation_history.append({
                    "role": "assistant",
                    "content": response_text
                })

            # 대화 히스토리 길이 제한 (오래된 대화 제거)
            if len(self.conversation_history) > self.max_history * 2:
                self.conversation_history = self.conversation_history[-(self.max_history * 2):]
                print(f"Conversation history trimmed to {len(self.conversation_history)} messages")

            return emotion, response_text, action

        except Exception as e:
            print(f"GPT analysis failed: {e}")
            import traceback
            traceback.print_exc()
            return None, None, None

    # 음성 명령 → 모션 매핑
    VOICE_COMMAND_ACTIONS = {
        "forward": {"motion": 56, "description": "앞으로 달리기"},
        "left": {"motion": 5, "description": "왼쪽으로 이동"},
        "right": {"motion": 6, "description": "오른쪽으로 이동"},
        "turnleft": {"motion": 7, "description": "왼쪽으로 회전"},
        "turnright": {"motion": 8, "description": "오른쪽으로 회전"},
        "attack": {"motion": 36, "description": "원투펀치 공격"},
        "defence": {"motion": 23, "description": "방어 자세"},
        "bow": {"motion": 19, "description": "인사 (절)"},
        "wave": {"motion": 18, "description": "손 흔들기"},
        "win": {"motion": 17, "description": "승리 만세"},
        "sitdown": {"motion": 115, "description": "앉기"},
        "standup": {"motion": 116, "description": "일어서기"},
        "dance": {"motion": 56, "description": "춤추기 (달리기)"},
        "pickup": {"motion": 84, "description": "물건 집기"},
        "grip": {"motion": 84, "description": "잡기"},
        "punch": {"motion": 52, "description": "더블 펀치"},
        "kick": {"motion": 50, "description": "스핀 블로우"},
        "ready": {"motion": 1, "description": "준비 자세"},
        "run": {"motion": 56, "description": "달리기"},
        "tumble": {"motion": 20, "description": "앞구르기"},
    }

    def execute_voice_command(self, command: str) -> bool:
        """음성 명령에 따른 동작 실행"""
        if not command:
            return False
        command = command.lower().strip()

        # IoT 제어 명령 처리
        if command == "light_on":
            print(f"[음성 명령] 조명 켜기")
            success, message = self.control_light("on")
            return success
        elif command == "light_off":
            print(f"[음성 명령] 조명 끄기")
            success, message = self.control_light("off")
            return success

        # 기존 동작 명령 처리
        if command in self.VOICE_COMMAND_ACTIONS:
            action = self.VOICE_COMMAND_ACTIONS[command]
            print(f"[음성 명령] '{command}' 실행: {action['description']} (motion {action['motion']})")
            return self.send_motion(action["motion"])
        else:
            print(f"[음성 명령] 알 수 없는 명령: {command}")
            return False

    def execute_emotion_action(self, emotion: str) -> bool:
        if emotion not in self.EMOTION_ACTIONS:
            print(f"Unknown emotion: {emotion}")
            return False
        action = self.EMOTION_ACTIONS[emotion]
        print(f"Executing emotion '{emotion}': {action['description']} (motion {action['motion']})")
        return self.send_motion(action["motion"])

    def clear_conversation_history(self, keep_user_name: bool = False):
        """대화 히스토리 초기화"""
        self.conversation_history = []
        self.last_emotion = "neutral"
        self.conversation_context = {
            "topics_discussed": [],
            "user_preferences": {},
            "mood_history": [],
        }
        if not keep_user_name:
            self.user_name = None
        print("Conversation history cleared")
        if self.user_name:
            print(f"User name retained: {self.user_name}")

    def set_persona(self, persona_key: str) -> bool:
        """페르소나 변경 (목소리도 자동 변경)"""
        if persona_key in self.PERSONAS:
            self.current_persona = persona_key
            persona = self.PERSONAS[persona_key]
            print(f"Persona changed to: {persona['name']}")

            # 페르소나에 맞는 목소리로 자동 변경
            if 'voice_index' in persona and self.tts:
                voice_index = persona['voice_index']
                self.tts.set_voice(voice_index)
                print(f"Voice auto-changed to index {voice_index} for persona '{persona['name']}'")

            return True
        else:
            print(f"Unknown persona: {persona_key}")
            return False

    def get_personas(self) -> dict:
        """사용 가능한 페르소나 목록 반환"""
        return {
            key: {
                "name": value["name"],
                "description": value["description"]
            }
            for key, value in self.PERSONAS.items()
        }

    def get_current_persona(self) -> dict:
        """현재 페르소나 정보 반환"""
        return {
            "key": self.current_persona,
            "name": self.PERSONAS[self.current_persona]["name"],
            "description": self.PERSONAS[self.current_persona]["description"]
        }

    # ===== IoT 기기 제어 기능 =====

    # IoT 동작 매핑
    IOT_ACTIONS = {
        "light_on": {"motion": 18, "description": "Hi - 손 들어 불 켜기"},
        "light_off": {"motion": 19, "description": "Bow - 인사하며 불 끄기"},
    }

    def set_iot_config(self, device: str, ip: str, port: int, on_command: str = "LED_ON", off_command: str = "LED_OFF") -> bool:
        """IoT 기기 설정 변경"""
        try:
            if device not in self.iot_devices:
                self.iot_devices[device] = {"name": device, "state": False}

            self.iot_devices[device]["ip"] = ip
            self.iot_devices[device]["port"] = port
            self.iot_devices[device]["on_command"] = on_command.encode() if isinstance(on_command, str) else on_command
            self.iot_devices[device]["off_command"] = off_command.encode() if isinstance(off_command, str) else off_command
            print(f"[IoT] {device} 설정 완료: {ip}:{port}")
            return True
        except Exception as e:
            print(f"[IoT] 설정 오류: {e}")
            return False

    # IoT 소켓 연결 유지용
    _iot_socket = None
    _iot_socket_ip = None
    _iot_socket_port = None

    def send_iot_packet(self, device: str, action: str) -> bool:
        """IoT 기기에 TCP 패킷 전송 (소켓 연결 유지 방식)"""
        try:
            if device not in self.iot_devices:
                print(f"[IoT] 알 수 없는 기기: {device}")
                return False

            dev = self.iot_devices[device]
            ip = dev.get("ip", "172.20.10.2")
            port = dev.get("port", 5501)

            # 명령 선택
            if action == "on":
                command = dev.get("on_command", b'LED_ON')
            else:
                command = dev.get("off_command", b'LED_OFF')

            print(f"[IoT] 전송 준비: {command} -> {ip}:{port}")

            # 기존 연결이 있고 같은 서버면 재사용, 아니면 새로 연결
            need_new_connection = False
            if self._iot_socket is None:
                need_new_connection = True
            elif self._iot_socket_ip != ip or self._iot_socket_port != port:
                # 다른 서버로 변경된 경우 기존 연결 닫기
                try:
                    self._iot_socket.close()
                except:
                    pass
                self._iot_socket = None
                need_new_connection = True
            else:
                # 기존 연결 상태 확인
                try:
                    self._iot_socket.setblocking(False)
                    try:
                        data = self._iot_socket.recv(1, socket.MSG_PEEK)
                        if not data:
                            need_new_connection = True
                    except BlockingIOError:
                        pass  # 읽을 데이터 없음 = 연결 정상
                    except:
                        need_new_connection = True
                    finally:
                        self._iot_socket.setblocking(True)
                except:
                    need_new_connection = True

            # 새 연결 필요시 연결
            if need_new_connection:
                print(f"[IoT] 새 연결 생성: {ip}:{port}")
                self._iot_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._iot_socket.settimeout(5.0)
                self._iot_socket.connect((ip, port))
                self._iot_socket_ip = ip
                self._iot_socket_port = port
                time.sleep(0.1)  # 연결 안정화

            # 명령 전송
            self._iot_socket.sendall(command)

            # 응답 대기
            self._iot_socket.settimeout(2.0)
            response = self._iot_socket.recv(1024)
            print(f"[IoT] {device} {action} 명령 전송 완료, 응답: {response}")

            # 상태 업데이트
            dev["state"] = (action == "on")
            return True

        except Exception as e:
            print(f"[IoT] 패킷 전송 오류: {e}")
            # 오류 발생시 소켓 정리
            if self._iot_socket:
                try:
                    self._iot_socket.close()
                except:
                    pass
                self._iot_socket = None
            return False

    # 조명 제어 디바운스용 변수
    _light_last_action_time = 0
    _light_debounce_interval = 1.0  # 1초

    def control_light(self, action: str) -> Tuple[bool, str]:
        """조명 제어 + 휴머노이드 동작"""
        try:
            # 디바운스 체크 - 중복 요청 방지
            current_time = time.time()
            if current_time - self._light_last_action_time < self._light_debounce_interval:
                print(f"[IoT] 조명 제어 디바운스 중... (이전 요청 후 {current_time - self._light_last_action_time:.2f}초)")
                return False, "잠시 후 다시 시도해주세요"
            self._light_last_action_time = current_time

            # 패킷 전송
            success = self.send_iot_packet("light", action)

            if success:
                # 휴머노이드 동작 실행
                if action == "on":
                    motion_key = "light_on"
                    message = "불을 켰어요!"
                else:
                    motion_key = "light_off"
                    message = "불을 껐어요!"

                # 동작 실행
                if motion_key in self.IOT_ACTIONS:
                    motion = self.IOT_ACTIONS[motion_key]
                    self.send_motion(motion["motion"])
                    print(f"[IoT] 휴머노이드 동작: {motion['description']}")

                return True, message
            else:
                return False, "패킷 전송 실패"

        except Exception as e:
            print(f"[IoT] 조명 제어 오류: {e}")
            return False, str(e)

    def get_iot_status(self) -> Dict:
        """IoT 기기 상태 반환"""
        return {
            device: {
                "name": info.get("name", device),
                "ip": info.get("ip", ""),
                "port": info.get("port", 0),
                "state": info.get("state", False)
            }
            for device, info in self.iot_devices.items()
        }

    # ===== 일정 관리 기능 =====

    def _load_schedules(self) -> List[Dict]:
        """일정 파일에서 일정 로드"""
        try:
            if os.path.exists(self.schedules_file):
                with open(self.schedules_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"[Schedule] 일정 로드 오류: {e}")
        return []

    def _save_schedules(self):
        """일정을 파일에 저장"""
        try:
            with open(self.schedules_file, 'w', encoding='utf-8') as f:
                json.dump(self.schedules, f, ensure_ascii=False, indent=2)
            print(f"[Schedule] 일정 저장 완료 ({len(self.schedules)}개)")
        except Exception as e:
            print(f"[Schedule] 일정 저장 오류: {e}")

    def add_schedule(self, date: str, title: str, description: str = "", schedule_time: str = "") -> Dict:
        """일정 추가 (date: YYYY-MM-DD 형식, schedule_time: HH:MM 형식)"""
        import time as time_module
        schedule = {
            "id": int(time_module.time() * 1000),  # 유니크 ID
            "date": date,
            "time": schedule_time,  # 시간 추가
            "title": title,
            "description": description,
            "created_at": datetime.now(timezone(timedelta(hours=9))).isoformat()
        }
        self.schedules.append(schedule)
        self._save_schedules()
        time_str = f" {schedule_time}" if schedule_time else ""
        print(f"[Schedule] 일정 추가: {date}{time_str} - {title}")
        return schedule

    def delete_schedule(self, schedule_id: int) -> bool:
        """일정 삭제"""
        for i, schedule in enumerate(self.schedules):
            if schedule["id"] == schedule_id:
                deleted = self.schedules.pop(i)
                self._save_schedules()
                print(f"[Schedule] 일정 삭제: {deleted['title']}")
                return True
        return False

    def get_schedules(self, date: str = None) -> List[Dict]:
        """일정 조회 (date가 None이면 전체, 있으면 해당 날짜)"""
        if date:
            return [s for s in self.schedules if s["date"] == date]
        return self.schedules

    def get_upcoming_schedules(self, days: int = 7) -> List[Dict]:
        """앞으로 n일 내의 일정 조회"""
        kst = timezone(timedelta(hours=9))
        today = datetime.now(kst).date()
        today_weekday = today.weekday()  # 0=월요일, 6=일요일
        upcoming = []
        weekday_names = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]

        for schedule in self.schedules:
            try:
                schedule_date = datetime.strptime(schedule["date"], "%Y-%m-%d").date()
                diff = (schedule_date - today).days
                if 0 <= diff <= days:
                    # 요일 계산
                    weekday = schedule_date.weekday()
                    weekday_name = weekday_names[weekday]

                    # 자연스러운 표현 생성
                    if diff == 0:
                        natural_name = "오늘"
                    elif diff == 1:
                        natural_name = "내일"
                    elif diff == 2:
                        natural_name = "모레"
                    elif diff <= 7:
                        # 이번주/다음주 구분
                        if weekday > today_weekday:
                            natural_name = f"이번주 {weekday_name}"
                        else:
                            natural_name = f"다음주 {weekday_name}"
                    else:
                        natural_name = f"{diff}일 후 ({weekday_name})"

                    upcoming.append({
                        **schedule,
                        "days_until": diff,
                        "day_name": natural_name,
                        "weekday": weekday_name
                    })
            except:
                pass
        return sorted(upcoming, key=lambda x: x["date"])

    def get_schedule_summary_for_gpt(self) -> str:
        """GPT에게 전달할 일정 요약"""
        upcoming = self.get_upcoming_schedules(14)  # 2주 내 일정

        # 7일 이내 일정 따로 분류
        within_week = [s for s in upcoming if s.get("days_until", 99) <= 7]
        after_week = [s for s in upcoming if s.get("days_until", 99) > 7]

        summary = "\n## 사용자의 일정"

        if within_week:
            summary += "\n### 이번주 일정 (7일 이내) - 사용자가 일정 물어보면 이 일정들 알려주기!"
            for s in within_week:
                time_str = f" {s['time']}" if s.get('time') else ""
                weekday = s.get('weekday', '')
                summary += f"\n- {s['day_name']} ({s['date']} {weekday}{time_str}): {s['title']}"
                if s.get('description'):
                    summary += f" - {s['description']}"
        else:
            summary += "\n### 이번주 일정: 없음"

        if after_week:
            summary += "\n### 다음주 이후 일정"
            for s in after_week:
                time_str = f" {s['time']}" if s.get('time') else ""
                weekday = s.get('weekday', '')
                summary += f"\n- {s['day_name']} ({s['date']} {weekday}{time_str}): {s['title']}"
                if s.get('description'):
                    summary += f" - {s['description']}"

        if not upcoming:
            summary += "\n- 예정된 일정 없음"

        return summary


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/run', methods=['POST'])
def run_chat():
    """REST API로 대화 처리"""
    global robot, client

    if not client:
        return {'success': False, 'error': 'OpenAI 클라이언트가 초기화되지 않았습니다'}

    if not robot:
        robot = CompanionRobot()

    try:
        from flask import request
        data = request.get_json()
        prompt = data.get('prompt', '')

        if not prompt:
            return {'success': False, 'error': '메시지가 비어있습니다'}

        print(f"[REST API] 사용자 입력: {prompt}")

        # GPT로 분석 및 응답 생성
        emotion, response_text = robot.analyze_text_with_gpt(prompt)

        print(f"[REST API] 감정: {emotion}, 응답: {response_text}")

        # 감정에 따른 로봇 동작 실행
        if emotion:
            robot.execute_emotion_action(emotion)

        # TTS로 응답 (감정 스타일 적용)
        if response_text:
            robot.tts.run(response_text, emotion=emotion)

        return {
            'success': True,
            'result': response_text,
            'emotion': emotion
        }

    except Exception as e:
        print(f"[REST API] 오류: {e}")
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': str(e)}


@socketio.on('connect_humanoid')
def handle_connect_humanoid(data):
    global robot
    if not robot:
        robot = CompanionRobot()
    port = data.get('port', 'COM6')
    success = robot.connect_humanoid(port)
    emit('humanoid_status', {'connected': success})


@socketio.on('disconnect_humanoid')
def handle_disconnect_humanoid():
    global robot
    if robot:
        robot.disconnect_humanoid()
    emit('humanoid_status', {'connected': False})


@socketio.on('start_face_analysis')
def handle_start_face_analysis(data):
    global robot

    # 카메라 인덱스 자동 감지 (0, 1, 2 순서로 시도)
    camera_found = False
    for cam_idx in [1, 0, 2]:  # 외부캠(1) 우선, 그 다음 내장캠(0), 그 다음 기타(2)
        print(f"Trying camera index {cam_idx}...")
        if robot and robot.init_camera(cam_idx):
            camera_found = True
            emit('log', {'message': f'✅ 카메라 {cam_idx}번 연결 성공'})
            break

    if not camera_found:
        emit('log', {'message': '❌ 사용 가능한 카메라를 찾을 수 없습니다'})
        return

    robot.analysis_interval = float(data.get('interval', 5))

    # 프레임 전송 스레드 (빠른 영상 전송)
    threading.Thread(target=robot.run_face_analysis_loop, daemon=True).start()

    # 감정 분석 스레드 (별도로 실행, 프레임에 영향 없음)
    threading.Thread(target=robot.run_emotion_analysis_loop, daemon=True).start()

    emit('log', {'message': f'📷 얼굴 분석 시작 (분석 간격: {robot.analysis_interval}초)'})


@socketio.on('stop_face_analysis')
def handle_stop_face_analysis():
    global robot
    if robot:
        robot.stop_camera()
    emit('log', {'message': 'Face analysis stopped'})


@socketio.on('set_brightness')
def handle_set_brightness(data):
    global robot
    if not robot:
        robot = CompanionRobot()
    brightness = data.get('brightness', 0)
    robot.brightness = int(brightness)
    print(f"[밝기] 설정: {robot.brightness}")


@socketio.on('load_whisper')
def handle_load_whisper():
    global robot
    if not robot:
        robot = CompanionRobot()
    # "base" 모델 사용 - 빠른 로드 (small은 461MB로 다운로드 시간이 오래 걸림)
    # 더 높은 정확도가 필요하면 "small"로 변경 가능
    success = robot.load_whisper("base")
    emit('whisper_status', {'loaded': success})


@socketio.on('voice_chat')
def handle_voice_chat():
    global robot
    if not robot or not robot.whisper:
        emit('log', {'message': 'Whisper not loaded'})
        return

    socketio.emit('log', {'message': '🎤 음성 입력 대기 중...'})

    user_text, emotion, response = robot.listen_and_respond()

    if user_text:
        socketio.emit('log', {'message': f'👤 사용자: {user_text}'})

        if emotion:
            socketio.emit('emotion_detected', {
                'emotion': emotion,
                'description': f'음성 대화에서 감지: {emotion}',
                'source': 'voice'
            })

        if response:
            socketio.emit('log', {'message': f'🤖 로봇: {response}'})

        socketio.emit('voice_result', {
            'user': user_text,
            'emotion': emotion,
            'response': response
        })

        # 대화 히스토리 개수 표시
        if robot.conversation_history:
            history_count = len(robot.conversation_history) // 2
            socketio.emit('log', {'message': f'💭 대화 턴: {history_count}개 (이전 대화를 기억합니다)'})
    else:
        socketio.emit('log', {'message': '❌ 음성 입력이 감지되지 않았습니다'})


@socketio.on('clear_conversation')
def handle_clear_conversation():
    global robot
    if robot:
        robot.clear_conversation_history()
        emit('log', {'message': '💬 대화 히스토리가 초기화되었습니다'})


@socketio.on('get_voices')
def handle_get_voices():
    global robot
    if robot and robot.tts:
        voices = robot.tts.get_voices()
        emit('voices_list', {'voices': voices})


@socketio.on('set_voice')
def handle_set_voice(data):
    global robot
    if robot and robot.tts:
        voice_index = data.get('voice_index', 0)
        success = robot.tts.set_voice(voice_index)
        if success:
            emit('log', {'message': f'🔊 음성이 변경되었습니다 (인덱스: {voice_index})'})
        else:
            emit('log', {'message': '❌ 음성 변경 실패'})


@socketio.on('set_tts_rate')
def handle_set_tts_rate(data):
    global robot
    # robot이 없으면 자동 초기화
    if not robot:
        robot = CompanionRobot()
    if robot.tts:
        # rate: -100 (느림) ~ +100 (빠름)
        rate = int(data.get('rate', 20))
        robot.tts.set_rate(rate)
        speed_label = "매우 빠름" if rate >= 50 else "빠름" if rate >= 20 else "보통" if rate >= -20 else "느림" if rate >= -50 else "매우 느림"
        emit('log', {'message': f'⚡ 음성 속도: {rate:+d}% ({speed_label})'})
    else:
        emit('log', {'message': '❌ TTS가 초기화되지 않았습니다'})


@socketio.on('set_tts_volume')
def handle_set_tts_volume(data):
    global robot
    # robot이 없으면 자동 초기화
    if not robot:
        robot = CompanionRobot()
    if robot.tts:
        volume = float(data.get('volume', 1.0))
        robot.tts.set_volume(volume)
        emit('log', {'message': f'🔊 음성 볼륨 변경: {int(volume * 100)}%'})
    else:
        emit('log', {'message': '❌ TTS가 초기화되지 않았습니다'})


@socketio.on('test_tts')
def handle_test_tts(data=None):
    """TTS 테스트"""
    global robot
    # robot이 없으면 자동 초기화
    if not robot:
        robot = CompanionRobot()
    if robot.tts:
        test_text = "안녕하세요! TTS 테스트입니다. 음성이 잘 들리시나요?"
        if data and data.get('text'):
            test_text = data.get('text')
        # 현재 설정 값 표시
        current_rate = robot.tts.rate
        current_volume = robot.tts.volume
        emit('log', {'message': f'🔊 TTS 테스트 (속도: {current_rate:+d}%, 볼륨: {current_volume}%)'})
        emit('log', {'message': f'🔊 텍스트: {test_text}'})
        try:
            robot.tts.run(test_text, emotion='friendly', wait=False)
            emit('log', {'message': '🔊 TTS 재생 요청 완료'})
        except Exception as e:
            emit('log', {'message': f'❌ TTS 오류: {str(e)}'})
    else:
        emit('log', {'message': '❌ TTS가 초기화되지 않았습니다'})


@socketio.on('get_personas')
def handle_get_personas():
    """페르소나 목록 가져오기"""
    global robot
    if robot:
        personas = robot.get_personas()
        current = robot.get_current_persona()
        emit('personas_list', {
            'personas': personas,
            'current': current
        })


@socketio.on('set_persona')
def handle_set_persona(data):
    """페르소나 변경"""
    global robot
    if robot:
        persona_key = data.get('persona_key')
        success = robot.set_persona(persona_key)
        if success:
            persona_info = robot.get_current_persona()
            emit('persona_changed', {
                'success': True,
                'persona': persona_info
            })
            emit('log', {'message': f'🎭 페르소나 변경: {persona_info["name"]} - {persona_info["description"]}'})
        else:
            emit('persona_changed', {'success': False})
            emit('log', {'message': f'❌ 페르소나 변경 실패: {persona_key}'})


# ===== 일정 관리 소켓 이벤트 =====

@socketio.on('get_schedules')
def handle_get_schedules(data=None):
    """일정 목록 가져오기"""
    global robot
    if robot:
        date = data.get('date') if data else None
        schedules = robot.get_schedules(date)
        upcoming = robot.get_upcoming_schedules(14)
        emit('schedules_list', {
            'schedules': schedules,
            'upcoming': upcoming
        })


@socketio.on('add_schedule')
def handle_add_schedule(data):
    """일정 추가"""
    global robot
    if robot:
        date = data.get('date')
        title = data.get('title')
        description = data.get('description', '')
        schedule_time = data.get('time', '')

        if date and title:
            schedule = robot.add_schedule(date, title, description, schedule_time)
            time_str = f" {schedule_time}" if schedule_time else ""
            emit('schedule_added', {'success': True, 'schedule': schedule})
            emit('log', {'message': f'📅 일정 추가: {date}{time_str} - {title}'})
            # 업데이트된 일정 목록 전송
            handle_get_schedules()
        else:
            emit('schedule_added', {'success': False, 'error': '날짜와 제목을 입력하세요'})


@socketio.on('delete_schedule')
def handle_delete_schedule(data):
    """일정 삭제"""
    global robot
    if robot:
        schedule_id = data.get('id')
        if schedule_id:
            success = robot.delete_schedule(schedule_id)
            emit('schedule_deleted', {'success': success, 'id': schedule_id})
            if success:
                emit('log', {'message': f'🗑️ 일정 삭제됨'})
                # 업데이트된 일정 목록 전송
                handle_get_schedules()
        else:
            emit('schedule_deleted', {'success': False})


# ===== IoT 제어 소켓 이벤트 =====

@socketio.on('iot_light_on')
def handle_iot_light_on(data=None):
    """조명 켜기"""
    global robot
    if not robot:
        robot = CompanionRobot()

    success, message = robot.control_light("on")
    emit('iot_result', {
        'success': success,
        'device': 'light',
        'action': 'on',
        'message': message
    })
    if success:
        emit('log', {'message': f'💡 조명 켜기 완료'})
        # TTS로 알림
        threading.Thread(target=robot.tts.run, args=(message,), daemon=True).start()
    else:
        emit('log', {'message': f'❌ 조명 켜기 실패: {message}'})


@socketio.on('iot_light_off')
def handle_iot_light_off(data=None):
    """조명 끄기"""
    global robot
    if not robot:
        robot = CompanionRobot()

    success, message = robot.control_light("off")
    emit('iot_result', {
        'success': success,
        'device': 'light',
        'action': 'off',
        'message': message
    })
    if success:
        emit('log', {'message': f'🌙 조명 끄기 완료'})
        # TTS로 알림
        threading.Thread(target=robot.tts.run, args=(message,), daemon=True).start()
    else:
        emit('log', {'message': f'❌ 조명 끄기 실패: {message}'})


@socketio.on('iot_set_config')
def handle_iot_set_config(data):
    """IoT 기기 설정"""
    global robot
    if not robot:
        robot = CompanionRobot()

    device = data.get('device', 'light')
    ip = data.get('ip', '172.20.10.2')
    port = int(data.get('port', 5501))
    on_command = data.get('on_command', 'LED_ON')
    off_command = data.get('off_command', 'LED_OFF')

    success = robot.set_iot_config(device, ip, port, on_command, off_command)
    emit('iot_config_result', {
        'success': success,
        'device': device,
        'ip': ip,
        'port': port
    })
    if success:
        emit('log', {'message': f'⚙️ IoT 설정 완료: {device} -> {ip}:{port}'})
    else:
        emit('log', {'message': f'❌ IoT 설정 실패'})


@socketio.on('iot_get_status')
def handle_iot_get_status(data=None):
    """IoT 기기 상태 조회"""
    global robot
    if not robot:
        robot = CompanionRobot()

    status = robot.get_iot_status()
    emit('iot_status', {'devices': status})


def main():
    global client

    # API 키 검증
    if not OPENAI_API_KEY:
        print("=" * 80)
        print("경고: OPENAI_API_KEY 환경변수가 설정되지 않았습니다!")
        print("설정 방법:")
        print("  Windows: set OPENAI_API_KEY=your_api_key")
        print("  Linux/Mac: export OPENAI_API_KEY=your_api_key")
        print("=" * 80)
        return

    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        print("OpenAI 클라이언트 초기화 완료")
    except Exception as e:
        print(f"OpenAI 클라이언트 초기화 실패: {e}")
        return

    print("=" * 80)
    print("로봇 제어 시스템")
    print("브라우저에서 접속: http://localhost:5000")
    print("=" * 80)

    socketio.run(app, host='0.0.0.0', port=5000, debug=False)


if __name__ == "__main__":
    main()
