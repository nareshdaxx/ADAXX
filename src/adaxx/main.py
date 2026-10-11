from google import genai
from google.genai import types
import sounddevice as sd
from gtts import gTTS
from gtts.lang import tts_langs
from playsound3 import playsound
import io
import json
import os
import tempfile
import wave
from pathlib import Path


def get_api_key():
    """Read the key from Windows/the shell, then from this project's .env file."""
    key = os.environ.get("GEMINI_API_KEY")
    if key:
        return key.strip()

    env_file = Path(__file__).with_name(".env")
    try:
        for line in env_file.read_text(encoding="utf-8").splitlines():
            name, separator, value = line.partition("=")
            if separator and name.strip() == "GEMINI_API_KEY" and value.strip():
                return value.strip().strip('"').strip("'")
    except OSError:
        pass

    return None


api_key = get_api_key()
if not api_key:
    raise RuntimeError(
        "GEMINI_API_KEY is not set. Start ADAXX with OPEN_ADAXX.bat or set the environment variable."
    )

# ADAXX Setup
client = genai.Client(api_key=api_key)

def speak(text, language="en"):
    print(f"ADAXX: {text}")
    audio_file = None
    language = language.lower().split("-")[0]

    if language not in tts_langs():
        language = "en"

    try:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
            audio_file = temp_file.name

        tts_options = {"text": text, "lang": language}
        if language == "en":
            tts_options["tld"] = "co.in"

        gTTS(**tts_options).save(audio_file)
        playsound(audio_file)
    except Exception as error:
        print(f"Speech error: {error}")
    finally:
        if audio_file and os.path.exists(audio_file):
            try:
                os.remove(audio_file)
            except OSError:
                pass


def listen(silent=True):
    sample_rate = 16000
    block_size = 1600  # 0.1 seconds of audio
    silence_blocks_needed = 12  # Stop after roughly 1.2 seconds of silence.
    max_blocks = 600  # Safety limit: listen for at most 60 seconds.

    try:
        if not silent:
            print("Listening...")
        audio_parts = []
        heard_speech = False
        silent_blocks = 0

        with sd.InputStream(
            samplerate=sample_rate,
            channels=1,
            dtype="int16",
            blocksize=block_size,
        ) as stream:
            for _ in range(max_blocks):
                recording, _ = stream.read(block_size)
                volume = abs(recording).max()

                if volume >= 500:
                    heard_speech = True
                    silent_blocks = 0
                elif heard_speech:
                    silent_blocks += 1

                if heard_speech:
                    audio_parts.append(recording.tobytes())

                if heard_speech and silent_blocks >= silence_blocks_needed:
                    break

        # In sleep mode, do nothing when there is only silence or faint noise.
        if not heard_speech:
            return ""

        return b"".join(audio_parts)
    except sd.PortAudioError:
        speak("I could not access the microphone.")

    return ""


def make_wav(audio_bytes, sample_rate=16000):
    wav_buffer = io.BytesIO()

    with wave.open(wav_buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio_bytes)

    return wav_buffer.getvalue()


def chat(audio_bytes):
    try:  
        prompt = """
You are ADAXX, a helpful AI assistant like Jarvis from Iron Man.
Listen to the user's audio and detect the language they spoke.
Reply in the exact same language, using one short, helpful sentence.
Return only valid JSON with these keys:
{
  "transcript": "the user's words in their original language",
  "reply": "your reply in that same language",
  "language": "the ISO 639-1 two-letter language code, for example en, te, hi, ta, kn, ml, mr, bn, gu, pa, or ur"
}
"""
        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=[
                prompt,
                types.Part.from_bytes(
                    data=make_wav(audio_bytes),
                    mime_type="audio/wav",
                ),
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )
        result = json.loads(response.text)
        transcript = result.get("transcript", "")
        reply = result.get("reply", "Sorry, I could not generate a response.")
        language = result.get("language", "en")
        return transcript, reply, language
    except Exception as error:
        print(f"Gemini error: {error}")
        return "", "Sorry sir, I cannot reach", "en"

# Start ADAXX
speak("HAi SIR!. I'm adaxx")
print("Speak whenever you are ready.")

try:
    while True:
        audio = listen(silent=True)

        if not audio:
            continue

        transcript, reply, language = chat(audio)

        if transcript:
            print(f"You: {transcript}")

        speak(reply, language)

except KeyboardInterrupt:
    print("\nADAXX: Goodbye, sir!")