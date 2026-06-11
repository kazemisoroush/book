"""Audio package: TTS, ambient, sound effects, and music generation.

Sub-packages
------------
tts/          – text-to-speech providers, voice management, beat synthesis
ambient/      – ambient audio generation and providers
sound_effect/ – sound effect generation and providers
music/        – background music generation and providers

Top-level modules
-----------------
audio_trimmer                       – ABC for beat-MP3 transforms
start_and_end_beat_silence_trimmer  – strips vendor-baked leading/trailing silence
audio_duration                      – ffprobe-backed duration helper
"""
