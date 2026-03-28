# ElevenLabs API Reference

**Status**: TODO - TTS integration not yet implemented

## Purpose

This document will contain:

- ElevenLabs API usage patterns
- Voice selection strategies
- Rate limiting and quota management
- Error handling patterns
- Audio quality settings
- Cost optimization techniques

## Current State

The `tts/elevenlabs_provider.py` module exists as a stub. TTS integration is deferred to future work.

## Related Files

- `src/tts/tts_provider.py` - TTS provider interface
- `src/tts/elevenlabs_provider.py` - ElevenLabs implementation (stub)
- `src/domain/models.py` - Character model (will map to voices)

## Future Work

When TTS integration begins:

1. Voice assignment algorithm (CharacterRegistry → ElevenLabs voices)
2. Audio synthesis (text + voice ID → audio file)
3. Audio assembly (segments → chapters → complete audiobook)
4. Prosody control (EmphasisSpan → SSML or prosody tags)
5. Cost management (caching, rate limiting, voice reuse)

## External Resources

- [ElevenLabs API Documentation](https://docs.elevenlabs.io/)
- [ElevenLabs Python SDK](https://github.com/elevenlabs/elevenlabs-python)
