# -*- coding: utf-8 -*-
import sys
import io
if sys.platform == 'win32' and not isinstance(sys.stdout, io.TextIOWrapper):
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except:
        pass

import warnings
warnings.filterwarnings("ignore", category=UserWarning)

import pyaudio
import webrtcvad
import numpy as np
import whisper
import time


class Whisper:
    # Whisper model
    model = None
    current_model_size = None

    # PyAudio settings
    RATE = 16000
    CHANNELS = 1
    FORMAT = pyaudio.paInt16
    FRAME_DURATION = 30  # ms
    FRAME_SIZE = int(RATE * FRAME_DURATION / 1000)
    CHUNK = FRAME_SIZE

    # VAD initialization (0~3, higher = more aggressive filtering)
    # 0 = 가장 민감 (모든 소리 캡처), 3 = 매우 공격적 (노이즈 많이 필터링)
    vad = webrtcvad.Vad(2)  # 2로 설정: 적당한 노이즈 필터링 + 음성 잘 캡처

    def __init__(self, model_size="base"):
        """
        Whisper initialization

        Args:
            model_size: Model size ("tiny", "base", "small", "medium", "large")
                       한국어 인식 정확도: large > medium > small > base > tiny
                       권장: "base" (빠른 로드, 적절한 정확도)
        """
        # 모델이 없거나 다른 크기의 모델을 요청한 경우 로드
        if Whisper.model is None or Whisper.current_model_size != model_size:
            print(f"Loading Whisper {model_size} model...")
            print(f"[참고] 처음 로딩 시 모델 다운로드로 시간이 걸릴 수 있습니다.")
            Whisper.model = whisper.load_model(model_size)
            Whisper.current_model_size = model_size
            print(f"Whisper {model_size} model loaded!")

    def process_audio(self, frames):
        audio_data = b''.join(frames)
        audio_np = np.frombuffer(audio_data, np.int16).astype(np.float32) / 32768.0

        # 한국어 인식 최적화 옵션 (속도 우선)
        result = self.model.transcribe(
            audio_np,
            language="ko",  # "korean" 대신 "ko" 사용 (더 정확)
            fp16=False,
            task="transcribe",
            beam_size=1,  # 빔 서치 크기 최소화 (속도 향상)
            best_of=1,    # 단일 후보 (속도 향상)
            temperature=0,  # 결정적 출력 (일관성)
            condition_on_previous_text=False,  # 이전 텍스트 무시 (단일 문장)
            initial_prompt="한국어"  # 짧은 힌트로 속도 향상
        )

        text = result["text"].strip()
        print(f"[Whisper] 인식 결과: {text}")
        return text

    def run(self):
        p = pyaudio.PyAudio()

        # 마이크 입력 장치 정보 출력
        try:
            default_device = p.get_default_input_device_info()
            print(f"[Whisper] 마이크: {default_device['name']}")
        except:
            pass

        stream = p.open(format=self.FORMAT,
                        channels=self.CHANNELS,
                        rate=self.RATE,
                        input=True,
                        frames_per_buffer=self.CHUNK)

        print("[Whisper] 말씀해 주세요... (최대 10초)")

        frames = []
        speech_started = False
        silence_frames = 0
        SILENCE_LIMIT = int(700 / self.FRAME_DURATION)  # 0.7초 침묵 = 말 끝 (빠른 응답)
        MAX_RECORD_TIME = 10  # 최대 녹음 시간 (초) - 10초로 감소
        MIN_SPEECH_FRAMES = 8  # 최소 음성 프레임 수 (너무 짧은 소음 무시)
        start_time = time.time()

        try:
            while True:
                # 최대 녹음 시간 체크
                if time.time() - start_time > MAX_RECORD_TIME:
                    print("[Whisper] 최대 녹음 시간 초과")
                    if frames:
                        text = self.process_audio(frames)
                        stream.stop_stream()
                        stream.close()
                        p.terminate()
                        return text
                    break

                frame = stream.read(self.CHUNK, exception_on_overflow=False)
                is_speech = self.vad.is_speech(frame, self.RATE)
                if is_speech:
                    frames.append(frame)
                    speech_started = True
                    silence_frames = 0
                else:
                    if speech_started:
                        silence_frames += 1
                        frames.append(frame)
                        if silence_frames > SILENCE_LIMIT:
                            # 너무 짧은 소음은 무시
                            if len(frames) < MIN_SPEECH_FRAMES:
                                print(f"[Whisper] 너무 짧은 소리 무시 ({len(frames)} 프레임)")
                                frames = []
                                speech_started = False
                                silence_frames = 0
                                continue

                            print(f"[Whisper] 음성 감지 완료 ({len(frames)} 프레임, 약 {len(frames) * self.FRAME_DURATION / 1000:.1f}초)")
                            text = self.process_audio(frames)
                            stream.stop_stream()
                            stream.close()
                            p.terminate()
                            return text

        except KeyboardInterrupt:
            print("\n[Whisper] 중단됨")

        stream.stop_stream()
        stream.close()
        p.terminate()
        return None


if __name__ == "__main__":
    Whisper().run()
