#!/usr/bin/env bash
# First 10 TTS requests to ElevenLabs API (eleven_multilingual_v2)
# Uses same-character previous_text/next_text and LLM-provided voice settings.
# Set ELEVENLABS_API_KEY before running.

API_KEY="${ELEVENLABS_API_KEY:?Set ELEVENLABS_API_KEY}"

# --- Segment 0: Narrator ---
curl -s -X POST "https://api.elevenlabs.io/v1/text-to-speech/CwhRBWXzGAHq8TQ4Fs17" \
  -H "xi-api-key: $API_KEY" \
  -H "Content-Type: application/json" \
  -o seg_0000.mp3 \
  -d '{
    "text": "It is a truth universally acknowledged, that a single man in possession of a good fortune must be in want of a wife.",
    "model_id": "eleven_multilingual_v2",
    "next_text": "However little known the feelings or views of such a man may be on his first entering a neighbourhood, this truth is so well fixed in the minds of the surrounding families, that he is considered as the rightful property of some one or other of their daughters.",
    "voice_settings": {
      "stability": 0.65,
      "style": 0.05,
      "similarity_boost": 0.75,
      "use_speaker_boost": true
    }
  }'
echo "seg_0000.mp3 done"

# --- Segment 1: Narrator ---
curl -s -X POST "https://api.elevenlabs.io/v1/text-to-speech/CwhRBWXzGAHq8TQ4Fs17" \
  -H "xi-api-key: $API_KEY" \
  -H "Content-Type: application/json" \
  -o seg_0001.mp3 \
  -d '{
    "text": "However little known the feelings or views of such a man may be on his first entering a neighbourhood, this truth is so well fixed in the minds of the surrounding families, that he is considered as the rightful property of some one or other of their daughters.",
    "model_id": "eleven_multilingual_v2",
    "previous_text": "It is a truth universally acknowledged, that a single man in possession of a good fortune must be in want of a wife.",
    "next_text": "said his lady to him one day,",
    "voice_settings": {
      "stability": 0.65,
      "style": 0.05,
      "similarity_boost": 0.75,
      "use_speaker_boost": true
    }
  }'
echo "seg_0001.mp3 done"

# --- Segment 2: Mrs. Bennet ---
curl -s -X POST "https://api.elevenlabs.io/v1/text-to-speech/Xb7hH8MSUJpSbSDYk0k2" \
  -H "xi-api-key: $API_KEY" \
  -H "Content-Type: application/json" \
  -o seg_0002.mp3 \
  -d '{
    "text": "My dear Mr. Bennet,",
    "model_id": "eleven_multilingual_v2",
    "next_text": "have you heard that Netherfield Park is let at last?",
    "voice_settings": {
      "stability": 0.35,
      "style": 0.40,
      "similarity_boost": 0.75,
      "use_speaker_boost": true
    }
  }'
echo "seg_0002.mp3 done"

# --- Segment 3: Narrator ---
curl -s -X POST "https://api.elevenlabs.io/v1/text-to-speech/CwhRBWXzGAHq8TQ4Fs17" \
  -H "xi-api-key: $API_KEY" \
  -H "Content-Type: application/json" \
  -o seg_0003.mp3 \
  -d '{
    "text": "said his lady to him one day,",
    "model_id": "eleven_multilingual_v2",
    "previous_text": "However little known the feelings or views of such a man may be on his first entering a neighbourhood, this truth is so well fixed in the minds of the surrounding families, that he is considered as the rightful property of some one or other of their daughters.",
    "next_text": "Mr. Bennet replied that he had not.",
    "voice_settings": {
      "stability": 0.65,
      "style": 0.05,
      "similarity_boost": 0.75,
      "use_speaker_boost": true
    }
  }'
echo "seg_0003.mp3 done"

# --- Segment 4: Mrs. Bennet ---
curl -s -X POST "https://api.elevenlabs.io/v1/text-to-speech/Xb7hH8MSUJpSbSDYk0k2" \
  -H "xi-api-key: $API_KEY" \
  -H "Content-Type: application/json" \
  -o seg_0004.mp3 \
  -d '{
    "text": "have you heard that Netherfield Park is let at last?",
    "model_id": "eleven_multilingual_v2",
    "previous_text": "My dear Mr. Bennet,",
    "next_text": "But it is,",
    "voice_settings": {
      "stability": 0.35,
      "style": 0.40,
      "similarity_boost": 0.75,
      "use_speaker_boost": true
    }
  }'
echo "seg_0004.mp3 done"

# --- Segment 5: Narrator ---
curl -s -X POST "https://api.elevenlabs.io/v1/text-to-speech/CwhRBWXzGAHq8TQ4Fs17" \
  -H "xi-api-key: $API_KEY" \
  -H "Content-Type: application/json" \
  -o seg_0005.mp3 \
  -d '{
    "text": "Mr. Bennet replied that he had not.",
    "model_id": "eleven_multilingual_v2",
    "previous_text": "said his lady to him one day,",
    "next_text": "returned she;",
    "voice_settings": {
      "stability": 0.65,
      "style": 0.05,
      "similarity_boost": 0.75,
      "use_speaker_boost": true
    }
  }'
echo "seg_0005.mp3 done"

# --- Segment 6: Mrs. Bennet ---
curl -s -X POST "https://api.elevenlabs.io/v1/text-to-speech/Xb7hH8MSUJpSbSDYk0k2" \
  -H "xi-api-key: $API_KEY" \
  -H "Content-Type: application/json" \
  -o seg_0006.mp3 \
  -d '{
    "text": "But it is,",
    "model_id": "eleven_multilingual_v2",
    "previous_text": "have you heard that Netherfield Park is let at last?",
    "next_text": "for Mrs. Long has just been here, and she told me all about it.",
    "voice_settings": {
      "stability": 0.35,
      "style": 0.40,
      "similarity_boost": 0.75,
      "use_speaker_boost": true
    }
  }'
echo "seg_0006.mp3 done"

# --- Segment 7: Narrator ---
curl -s -X POST "https://api.elevenlabs.io/v1/text-to-speech/CwhRBWXzGAHq8TQ4Fs17" \
  -H "xi-api-key: $API_KEY" \
  -H "Content-Type: application/json" \
  -o seg_0007.mp3 \
  -d '{
    "text": "returned she;",
    "model_id": "eleven_multilingual_v2",
    "previous_text": "Mr. Bennet replied that he had not.",
    "next_text": "Mr. Bennet made no answer.",
    "voice_settings": {
      "stability": 0.65,
      "style": 0.05,
      "similarity_boost": 0.75,
      "use_speaker_boost": true
    }
  }'
echo "seg_0007.mp3 done"

# --- Segment 8: Mrs. Bennet ---
curl -s -X POST "https://api.elevenlabs.io/v1/text-to-speech/Xb7hH8MSUJpSbSDYk0k2" \
  -H "xi-api-key: $API_KEY" \
  -H "Content-Type: application/json" \
  -o seg_0008.mp3 \
  -d '{
    "text": "for Mrs. Long has just been here, and she told me all about it.",
    "model_id": "eleven_multilingual_v2",
    "previous_text": "But it is,",
    "next_text": "Do not you want to know who has taken it?",
    "voice_settings": {
      "stability": 0.35,
      "style": 0.40,
      "similarity_boost": 0.75,
      "use_speaker_boost": true
    }
  }'
echo "seg_0008.mp3 done"

# --- Segment 9: Narrator ---
curl -s -X POST "https://api.elevenlabs.io/v1/text-to-speech/CwhRBWXzGAHq8TQ4Fs17" \
  -H "xi-api-key: $API_KEY" \
  -H "Content-Type: application/json" \
  -o seg_0009.mp3 \
  -d '{
    "text": "Mr. Bennet made no answer.",
    "model_id": "eleven_multilingual_v2",
    "previous_text": "returned she;",
    "next_text": "cried his wife, impatiently.",
    "voice_settings": {
      "stability": 0.65,
      "style": 0.05,
      "similarity_boost": 0.75,
      "use_speaker_boost": true
    }
  }'
echo "seg_0009.mp3 done"
