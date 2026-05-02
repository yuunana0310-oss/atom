import queue
import threading
import numpy as np

# 音声入力用の依存関係
# pip install sounddevice numpy faster-whisper
try:
    import sounddevice as sd
    from faster_whisper import WhisperModel
    HAS_AUDIO_DEPS = True
except ImportError:
    HAS_AUDIO_DEPS = False

class AudioRecognizer:
    _instance = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self, model_size="small", device="cpu"):
        self.model_size = model_size
        self.device = device
        self.is_recording = False
        self.model = None
        self.stream = None
        self.audio_data = []
        self._load_model()

    def _load_model(self):
        """非同期または初期化時にモデルをロードする"""
        if HAS_AUDIO_DEPS and self.model is None:
            # compute_typeをint8にすることでCPUでも高速・省メモリになる
            try:
                self.model = WhisperModel(self.model_size, device=self.device, compute_type="int8")
                print("Whisper model loaded successfully.")
            except Exception as e:
                print(f"Error loading whisper model: {e}")
                
    def is_available(self):
        return HAS_AUDIO_DEPS and self.model is not None

    def start_recording(self):
        if not self.is_available():
            raise RuntimeError("音声認識モジュール(sounddevice, faster-whisper)が利用できません")
        
        self.is_recording = True
        self.audio_data = []
        
        def callback(indata, frames, time, status):
            if status:
                print(status)
            if self.is_recording:
                self.audio_data.append(indata.copy())

        # Whisperは 16kHz モノラル入力を期待する
        self.stream = sd.InputStream(samplerate=16000, channels=1, dtype='float32', callback=callback)
        self.stream.start()

    def stop_recording_and_transcribe(self) -> str:
        """
        録音を終了し、ローカル推論を行ってテキストを返す
        """
        if not self.is_recording or self.stream is None:
            return ""
        
        self.is_recording = False
        self.stream.stop()
        self.stream.close()
        self.stream = None
        
        if not self.audio_data:
            return ""
            
        # 録音データを結合して1次元配列にする
        audio_np = np.concatenate(self.audio_data, axis=0).flatten()
        
        # Whisperでの推論
        segments, info = self.model.transcribe(audio_np, language="ja", beam_size=5)
        text = "".join([segment.text for segment in segments])
        
        return text.strip()
