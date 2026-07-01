# -*- coding: utf-8 -*-
import edge_tts
import asyncio
import threading
import tempfile
import os
import re
import winsound
from pathlib import Path

class Edge_TTS:
    """
    Edge TTS - Microsoft Edge의 고품질 Neural TTS 엔진
    100개 이상 언어/방언 지원, 자연스러운 음성 합성
    한국어 Neural TTS로 감정 표현이 풍부한 대화 가능
    """

    # 한국어 음성 목록 (Microsoft Edge Neural TTS - 실제 사용 가능한 음성)
    KOREAN_VOICES = [
        # === 남성 음성 ===
        {
            'id': 'ko-KR-InJoonNeural',
            'name': '인준 (남성) - 안정적, 전문적',
            'gender': 'Male',
            'description': '깊고 안정적인 남성 목소리, 전문적인 느낌',
            'style': 'professional'
        },
        {
            'id': 'ko-KR-HyunsuMultilingualNeural',
            'name': '현수 (남성) - 차분한, 지적인',
            'gender': 'Male',
            'description': '차분하고 지적인 남성 목소리, 다국어 지원',
            'style': 'calm'
        },
        # === 여성 음성 ===
        {
            'id': 'ko-KR-SunHiNeural',
            'name': '선희 (여성) - 밝은, 명랑한',
            'gender': 'Female',
            'description': '밝고 명랑한 여성 목소리',
            'style': 'bright'
        },
    ]

    # 감정에 따른 음성 스타일 조절 (rate, pitch, volume)
    EMOTION_VOICE_STYLES = {
        # 긍정적 감정 - 밝고 빠르게
        'happy': {'rate': '+15%', 'pitch': '+5Hz', 'volume': '+10%'},
        'excited': {'rate': '+25%', 'pitch': '+10Hz', 'volume': '+15%'},
        'joy': {'rate': '+20%', 'pitch': '+8Hz', 'volume': '+10%'},
        'love': {'rate': '-5%', 'pitch': '+3Hz', 'volume': '-5%'},
        'grateful': {'rate': '-10%', 'pitch': '+2Hz', 'volume': '+5%'},
        'hopeful': {'rate': '+5%', 'pitch': '+5Hz', 'volume': '+5%'},
        'encouraging': {'rate': '+10%', 'pitch': '+5Hz', 'volume': '+15%'},

        # 인사/사교 - 친근하게
        'greeting': {'rate': '+10%', 'pitch': '+5Hz', 'volume': '+10%'},
        'welcoming': {'rate': '+5%', 'pitch': '+3Hz', 'volume': '+10%'},
        'friendly': {'rate': '+8%', 'pitch': '+3Hz', 'volume': '+5%'},

        # 슬픔 - 느리고 낮게
        'sad': {'rate': '-20%', 'pitch': '-5Hz', 'volume': '-10%'},
        'disappointed': {'rate': '-15%', 'pitch': '-3Hz', 'volume': '-5%'},
        'depressed': {'rate': '-25%', 'pitch': '-8Hz', 'volume': '-15%'},
        'lonely': {'rate': '-20%', 'pitch': '-5Hz', 'volume': '-10%'},

        # 분노 - 빠르고 강하게
        'angry': {'rate': '+15%', 'pitch': '-3Hz', 'volume': '+20%'},
        'annoyed': {'rate': '+10%', 'pitch': '+0Hz', 'volume': '+10%'},
        'furious': {'rate': '+20%', 'pitch': '-5Hz', 'volume': '+25%'},
        'frustrated': {'rate': '+5%', 'pitch': '-2Hz', 'volume': '+10%'},

        # 놀람 - 빠르고 높게
        'surprised': {'rate': '+20%', 'pitch': '+10Hz', 'volume': '+15%'},
        'shocked': {'rate': '+25%', 'pitch': '+15Hz', 'volume': '+20%'},
        'amazed': {'rate': '+15%', 'pitch': '+8Hz', 'volume': '+10%'},

        # 두려움 - 떨리듯이
        'scared': {'rate': '+10%', 'pitch': '+5Hz', 'volume': '-10%'},
        'nervous': {'rate': '+5%', 'pitch': '+3Hz', 'volume': '-5%'},
        'afraid': {'rate': '+8%', 'pitch': '+5Hz', 'volume': '-10%'},

        # 호기심 - 흥미롭게
        'curious': {'rate': '+5%', 'pitch': '+5Hz', 'volume': '+5%'},
        'interested': {'rate': '+5%', 'pitch': '+3Hz', 'volume': '+5%'},
        'wondering': {'rate': '+0%', 'pitch': '+5Hz', 'volume': '+0%'},

        # 중립/차분 - 기본
        'neutral': {'rate': '+0%', 'pitch': '+0Hz', 'volume': '+0%'},
        'calm': {'rate': '-10%', 'pitch': '-2Hz', 'volume': '-5%'},
        'relaxed': {'rate': '-15%', 'pitch': '-3Hz', 'volume': '-10%'},
        'peaceful': {'rate': '-15%', 'pitch': '-3Hz', 'volume': '-10%'},

        # 생각 - 천천히
        'thinking': {'rate': '-15%', 'pitch': '+0Hz', 'volume': '-5%'},
        'confused': {'rate': '-10%', 'pitch': '+3Hz', 'volume': '+0%'},
        'pondering': {'rate': '-20%', 'pitch': '-2Hz', 'volume': '-5%'},

        # 피로 - 느리고 낮게
        'tired': {'rate': '-25%', 'pitch': '-5Hz', 'volume': '-15%'},
        'exhausted': {'rate': '-30%', 'pitch': '-8Hz', 'volume': '-20%'},
        'sleepy': {'rate': '-25%', 'pitch': '-5Hz', 'volume': '-15%'},
        'bored': {'rate': '-15%', 'pitch': '-3Hz', 'volume': '-10%'},

        # 공감/위로 - 부드럽게
        'comforting': {'rate': '-10%', 'pitch': '+2Hz', 'volume': '-5%'},
        'sympathetic': {'rate': '-10%', 'pitch': '+0Hz', 'volume': '-5%'},
        'caring': {'rate': '-5%', 'pitch': '+3Hz', 'volume': '+0%'},

        # 장난 - 밝고 활기차게
        'playful': {'rate': '+15%', 'pitch': '+8Hz', 'volume': '+10%'},
        'mischievous': {'rate': '+20%', 'pitch': '+10Hz', 'volume': '+10%'},
        'humorous': {'rate': '+10%', 'pitch': '+5Hz', 'volume': '+5%'},
        'silly': {'rate': '+20%', 'pitch': '+12Hz', 'volume': '+10%'},
    }

    def __init__(self):
        # 기본 음성: 한국어 남성 (InJoon) - 로니에게 적합
        self.current_voice = self.KOREAN_VOICES[0]['id']

        # 음성 설정
        self.rate = 20  # 속도 (-100% ~ +100%, 기본값 +20%로 약간 빠르게)
        self.volume = 100  # 볼륨 (0 ~ 100)
        self.current_emotion = 'neutral'  # 현재 감정 상태

        print(f"[Edge TTS] Neural TTS 초기화 완료")
        print(f"[Edge TTS] 음성: {self.KOREAN_VOICES[0]['name']}")
        print(f"[Edge TTS] 지원 감정 스타일: {len(self.EMOTION_VOICE_STYLES)}개")

    def set_emotion(self, emotion: str):
        """감정 상태 설정 - 다음 음성 출력에 적용"""
        if emotion in self.EMOTION_VOICE_STYLES:
            self.current_emotion = emotion
            print(f"[Edge TTS] 감정 설정: {emotion}")
        else:
            self.current_emotion = 'neutral'
            print(f"[Edge TTS] 알 수 없는 감정 '{emotion}', neutral로 설정")

    def get_emotion_style(self, emotion: str = None) -> dict:
        """감정에 따른 음성 스타일 반환"""
        emotion = emotion or self.current_emotion
        return self.EMOTION_VOICE_STYLES.get(emotion, self.EMOTION_VOICE_STYLES['neutral'])

    def get_voices(self):
        """사용 가능한 음성 목록 반환"""
        voices_list = []
        for idx, voice in enumerate(self.KOREAN_VOICES):
            voices_list.append({
                'index': idx,
                'id': voice['id'],
                'name': voice['name']
            })
        return voices_list

    def set_voice(self, voice_index):
        """음성 변경"""
        try:
            if 0 <= voice_index < len(self.KOREAN_VOICES):
                self.current_voice = self.KOREAN_VOICES[voice_index]['id']
                print(f"[Edge TTS] 음성 변경: {self.KOREAN_VOICES[voice_index]['name']}")
                return True
            return False
        except Exception as e:
            print(f"[Edge TTS] 음성 변경 오류: {e}")
            return False

    def set_rate(self, rate):
        """
        음성 속도 변경
        rate: -100 (매우 느림) ~ +100 (매우 빠름), 0 = 기본 속도
        """
        # 범위 제한
        if rate < -100:
            rate = -100
        if rate > 100:
            rate = 100

        self.rate = int(rate)
        print(f"[Edge TTS] 속도 변경: {self.rate:+d}%")

    def set_volume(self, volume):
        """음성 볼륨 변경 (0.0 ~ 1.0)"""
        # 0.0 ~ 1.0 -> 0 ~ 100
        self.volume = int(volume * 100)
        print(f"[Edge TTS] 볼륨 변경: {self.volume}%")

    def remove_emojis(self, text):
        """텍스트에서 이모티콘만 제거 (한글, 영문, 숫자, 기본 문장부호는 유지)"""
        # 이모지만 정확히 제거 (한글 범위 제외)
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # 이모티콘 (스마일리)
            "\U0001F300-\U0001F5FF"  # 기호 및 픽토그램
            "\U0001F680-\U0001F6FF"  # 교통 및 지도 기호
            "\U0001F1E0-\U0001F1FF"  # 국기
            "\U0001F900-\U0001F9FF"  # 보충 이모지
            "\U0001FA00-\U0001FA6F"  # 체스 기호
            "\U0001FA70-\U0001FAFF"  # 기호 확장
            "\U00002702-\U000027B0"  # 딩뱃 (한글 범위 전)
            "\U0001F926-\U0001F937"  # 제스처
            "\U00010000-\U0001FFFF"  # 보충 다국어 평면 (SMP) - 이모지 대부분
            "]+",
            flags=re.UNICODE
        )
        text = emoji_pattern.sub('', text)
        # 연속 공백 정리
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    async def _synthesize(self, text, emotion: str = None):
        """비동기 음성 합성 - 감정에 따른 스타일 적용"""
        try:
            # 텍스트 정리 및 인코딩 확인
            if not text or not text.strip():
                print("[Edge TTS] 빈 텍스트, 건너뜀")
                return None

            text = text.strip()
            print(f"[Edge TTS] 합성 시작 - 텍스트 길이: {len(text)}")
            print(f"[Edge TTS] 음성: {self.current_voice}")

            # 감정 스타일 가져오기
            emotion = emotion or self.current_emotion
            style = self.get_emotion_style(emotion)
            print(f"[Edge TTS] 감정: {emotion}")

            # 기본 rate에 감정 스타일 적용
            try:
                base_rate = self.rate
                rate_str_raw = style.get('rate', '+0%')
                emotion_rate = int(rate_str_raw.replace('%', '').replace('+', ''))
                combined_rate = base_rate + emotion_rate
                # 범위 제한 (-50% ~ +50%)
                combined_rate = max(-50, min(50, combined_rate))
                rate_str = f"{combined_rate:+d}%"
            except:
                rate_str = "+0%"

            # 볼륨 설정
            try:
                volume_percent = max(0, min(100, self.volume))
                # edge-tts 볼륨: -100% ~ +100%
                volume_str = f"{volume_percent - 100:+d}%" if volume_percent < 100 else "+0%"
            except:
                volume_str = "+0%"

            print(f"[Edge TTS] 최종 속도: {rate_str}, 볼륨: {volume_str}")

            # Edge TTS 통신 객체 생성 (속도 설정 적용!)
            communicate = edge_tts.Communicate(
                text=text,
                voice=self.current_voice,
                rate=rate_str,
                volume=volume_str
            )

            # 임시 MP3 파일로 저장
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp_file:
                output_file = tmp_file.name

            print(f"[Edge TTS] 임시 파일: {output_file}")
            print(f"[Edge TTS] Microsoft 서버에 연결 중...")

            # 음성 합성 및 저장
            await communicate.save(output_file)

            print(f"[Edge TTS] 음성 파일 저장 완료!")

            # 파일 크기 확인
            file_size = os.path.getsize(output_file)
            print(f"[Edge TTS] 파일 크기: {file_size} bytes")

            if file_size == 0:
                print(f"[Edge TTS] 경고: 파일이 비어있습니다!")
                return None

            return output_file

        except Exception as e:
            print(f"[Edge TTS] 합성 오류 발생!")
            print(f"[Edge TTS] 오류 타입: {type(e).__name__}")
            print(f"[Edge TTS] 오류 메시지: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _play_audio(self, audio_file):
        """오디오 파일 재생 (Windows) - 여러 방법 시도"""
        import time as time_module
        import subprocess
        played = False

        try:
            print(f"[Edge TTS] 오디오 재생 시작: {audio_file}")

            # 파일 존재 확인
            if not os.path.exists(audio_file):
                print(f"[Edge TTS] 오류: 파일이 존재하지 않음!")
                return

            file_size = os.path.getsize(audio_file)
            print(f"[Edge TTS] 파일 크기: {file_size} bytes")

            if file_size == 0:
                print(f"[Edge TTS] 오류: 파일이 비어있음!")
                return

            # 파일 경로를 절대 경로로 변환
            abs_path = os.path.abspath(audio_file)
            print(f"[Edge TTS] 절대 경로: {abs_path}")

            # 방법 1: Windows Media Player (wmplayer) - 가장 안정적
            try:
                print(f"[Edge TTS] Windows Media Player로 재생 시도...")
                # wmplayer 실행 후 종료 대기
                proc = subprocess.Popen(
                    ['powershell', '-Command', f'''
                        Add-Type -AssemblyName presentationCore
                        $player = New-Object System.Windows.Media.MediaPlayer
                        $player.Open("{abs_path}")
                        Start-Sleep -Milliseconds 500
                        $player.Play()
                        while ($player.NaturalDuration.HasTimeSpan -eq $false) {{ Start-Sleep -Milliseconds 100 }}
                        $duration = $player.NaturalDuration.TimeSpan.TotalSeconds
                        Start-Sleep -Seconds ($duration + 0.5)
                        $player.Close()
                    '''],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                proc.wait(timeout=30)
                print(f"[Edge TTS] Windows Media Player 재생 완료!")
                played = True
                return
            except Exception as e:
                print(f"[Edge TTS] Windows Media Player 실패: {e}")

            # 방법 2: Windows MCI (Media Control Interface)
            if not played:
                try:
                    import ctypes
                    print(f"[Edge TTS] Windows MCI로 재생 시도...")

                    winmm = ctypes.windll.winmm

                    # 유니크한 alias 생성
                    import random
                    alias = f"tts{random.randint(1000, 9999)}"

                    # 버퍼 준비
                    buf = ctypes.create_unicode_buffer(256)

                    # 이전 alias 정리
                    winmm.mciSendStringW(f'close {alias}', buf, 256, None)

                    # 열기 (mpegvideo 타입 사용)
                    open_cmd = f'open "{abs_path}" type mpegvideo alias {alias}'
                    result = winmm.mciSendStringW(open_cmd, buf, 256, None)
                    if result != 0:
                        winmm.mciGetErrorStringW(result, buf, 256)
                        raise Exception(f"MCI open 실패: {buf.value}")

                    # 재생 (완료까지 대기)
                    play_cmd = f'play {alias} wait'
                    result = winmm.mciSendStringW(play_cmd, buf, 256, None)

                    # 닫기
                    winmm.mciSendStringW(f'close {alias}', buf, 256, None)

                    if result != 0:
                        winmm.mciGetErrorStringW(result, buf, 256)
                        raise Exception(f"MCI play 실패: {buf.value}")

                    print(f"[Edge TTS] MCI 재생 완료!")
                    played = True
                    return

                except Exception as e:
                    print(f"[Edge TTS] MCI 실패: {e}")

            # 방법 3: pygame
            if not played:
                try:
                    import pygame
                    print(f"[Edge TTS] pygame으로 재생 시도...")

                    # pygame 완전 초기화
                    try:
                        pygame.mixer.quit()
                    except:
                        pass
                    try:
                        pygame.quit()
                    except:
                        pass

                    # pygame 초기화
                    pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=4096)
                    pygame.mixer.init()
                    time_module.sleep(0.1)

                    # 음악 로드 및 재생
                    pygame.mixer.music.load(abs_path)
                    pygame.mixer.music.set_volume(1.0)
                    pygame.mixer.music.play()

                    # 재생 완료 대기
                    while pygame.mixer.music.get_busy():
                        time_module.sleep(0.1)

                    time_module.sleep(0.2)
                    pygame.mixer.music.stop()
                    pygame.mixer.quit()
                    print(f"[Edge TTS] pygame 재생 완료!")
                    played = True
                    return

                except ImportError:
                    print(f"[Edge TTS] pygame 미설치")
                except Exception as e:
                    print(f"[Edge TTS] pygame 실패: {e}")
                    try:
                        pygame.mixer.quit()
                    except:
                        pass

            # 방법 4: playsound 라이브러리
            if not played:
                try:
                    from playsound import playsound
                    print(f"[Edge TTS] playsound로 재생 시도...")
                    playsound(abs_path)
                    print(f"[Edge TTS] playsound 재생 완료!")
                    played = True
                    return
                except ImportError:
                    print(f"[Edge TTS] playsound 미설치")
                except Exception as e:
                    print(f"[Edge TTS] playsound 실패: {e}")

            # 방법 5: os.startfile (Windows 기본 연결 프로그램)
            if not played:
                try:
                    print(f"[Edge TTS] os.startfile로 재생 시도...")
                    os.startfile(abs_path)
                    time_module.sleep(5)  # 재생 시간 대기
                    print(f"[Edge TTS] os.startfile 재생 시작됨!")
                    played = True
                    return
                except Exception as e:
                    print(f"[Edge TTS] os.startfile 실패: {e}")

            if not played:
                print(f"[Edge TTS] 모든 재생 방법 실패!")

        except Exception as e:
            print(f"[Edge TTS] 재생 오류 발생!")
            print(f"[Edge TTS] 오류 타입: {type(e).__name__}")
            print(f"[Edge TTS] 오류 메시지: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # 임시 파일 삭제 (약간의 지연 후)
            time_module.sleep(1.0)
            try:
                if os.path.exists(audio_file):
                    os.unlink(audio_file)
                    print(f"[Edge TTS] 임시 파일 삭제됨")
            except Exception as e:
                print(f"[Edge TTS] 임시 파일 삭제 실패 (사용 중일 수 있음): {e}")

    def run(self, txt, emotion: str = None, wait: bool = False):
        """
        텍스트를 음성으로 변환하여 재생

        Args:
            txt: 말할 텍스트
            emotion: 감정 (happy, sad, excited 등) - 음성 스타일에 반영
            wait: True면 재생 완료까지 대기
        """
        # 이모티콘 제거
        txt = self.remove_emojis(txt)
        if not txt:
            print("[Edge TTS] 텍스트가 비어있음 (이모티콘만 있었음)")
            return

        # 감정 설정
        if emotion:
            self.set_emotion(emotion)

        def _speak(text, emotion_style):
            try:
                print(f"[Edge TTS] ========== TTS 시작 ==========")
                print(f"[Edge TTS] 텍스트: {text[:50]}..." if len(text) > 50 else f"[Edge TTS] 텍스트: {text}")
                if emotion_style:
                    print(f"[Edge TTS] 감정 스타일: {emotion_style}")

                # 비동기 함수 실행을 위한 이벤트 루프 (안전하게 생성)
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                except Exception as e:
                    print(f"[Edge TTS] 이벤트 루프 생성 실패: {e}")
                    # 기존 루프 사용 시도
                    try:
                        loop = asyncio.get_event_loop()
                    except:
                        print("[Edge TTS] 이벤트 루프를 가져올 수 없음!")
                        return

                # 음성 합성 (감정 스타일 전달)
                try:
                    audio_file = loop.run_until_complete(self._synthesize(text, emotion_style))
                except Exception as e:
                    print(f"[Edge TTS] 합성 실행 오류: {e}")
                    import traceback
                    traceback.print_exc()
                    audio_file = None
                finally:
                    try:
                        loop.close()
                    except:
                        pass

                if not audio_file:
                    print("[Edge TTS] 음성 합성 실패 - 파일 없음")
                    return

                print(f"[Edge TTS] 음성 합성 완료: {audio_file}")

                # 오디오 재생
                self._play_audio(audio_file)

                print("[Edge TTS] ========== TTS 완료 ==========")

            except Exception as e:
                print(f"[Edge TTS] 오류 발생: {e}")
                import traceback
                traceback.print_exc()

        # 스레드 실행
        print(f"[Edge TTS] 스레드 시작...")
        thread = threading.Thread(target=_speak, args=(txt, emotion or self.current_emotion))
        thread.daemon = True
        thread.start()

        # 대기 옵션
        if wait:
            thread.join()
            print(f"[Edge TTS] 스레드 완료 (wait 모드)")
