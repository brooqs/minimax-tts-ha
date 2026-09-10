# MiniMax TTS for Home Assistant

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz)
[![HA](https://img.shields.io/badge/Home%20Assistant-2026.8+-blue.svg)](https://www.home-assistant.io/)

Cloud-based Text-to-Speech integration for Home Assistant using the MiniMax T2A v2 API.

Features **28+ system voices** including native **Turkish** (`Turkish_Trustworthyman`, `Turkish_CalmWoman`), plus English, Chinese, Japanese, Arabic, German, French, and 15+ other languages. Voice cloning and emotion control (happy/sad/angry/calm/whisper/etc.) supported.

---

## Features

- Config flow UI - set up in Settings -> Devices & Services
- 28+ system voices across 20+ languages
- Voice cloning support (bring your own MiniMax voice_id)
- Emotion control - happy, sad, angry, calm, whisper, etc. (model-dependent)
- Speed/pitch/volume tuning per call or globally
- Audio caching - generated MP3s served via `/local/minimax_tts/`
- HACS compatible - installable from a custom repository
- Async - built on `aiohttp`, no event loop blocking
- 8 models - `speech-2.8-hd/turbo`, `speech-2.6-hd/turbo`, `speech-02-hd/turbo`, `speech-01-hd/turbo`

---

## Installation

### Option A - HACS (recommended)

1. Open HACS -> Integrations -> menu -> **Custom repositories**
2. Add `https://github.com/brooqs/minimax-tts-ha` (category: **Integration**)
3. Click **Download** on "MiniMax TTS"
4. Restart Home Assistant
5. Settings -> Devices & Services -> **+ Add Integration** -> search "MiniMax TTS"

### Option B - Manual

```bash
cd /config/custom_components
git clone https://github.com/brooqs/minimax-tts-ha.git
mv minimax-tts-ha/custom_components/minimax_tts ./minimax_tts
rm -rf minimax-tts-ha
```

Restart Home Assistant, then add the integration from the UI.

---

## Setup

1. **Get an API key** from [MiniMax platform](https://platform.minimax.io/user-center/basic-information/interface-key)
2. In HA: Settings -> Devices & Services -> **+ Add Integration** -> "MiniMax TTS"
3. Paste your API key and choose your region (Global / China)
4. Click **Options** on the integration card to configure default voice/model

---

## Configuration

All configuration is done via the HA UI. No `configuration.yaml` editing required.

### Initial setup (config flow)

| Field       | Required | Description                                                                                            |
| ----------- | -------- | ------------------------------------------------------------------------------------------------------ |
| `api_key`   | Yes      | Bearer JWT from platform.minimax.io |
| `base_url`  | No       | `https://api.minimax.io/v1/t2a_v2` (default Global) or `https://api.minimaxi.com/v1/t2a_v2` (China) |

### Options (post-setup)

| Field            | Default                  | Range / Options                                                                                   |
| ---------------- | ------------------------ | ------------------------------------------------------------------------------------------------- |
| `model`          | `speech-2.8-hd`          | `speech-2.8-{hd,turbo}`, `speech-2.6-{hd,turbo}`, `speech-02-{hd,turbo}`, `speech-01-{hd,turbo}` |
| `voice_id`       | `English_Graceful_Lady`  | Any MiniMax voice ID                                                                              |
| `speed`          | `1.0`                    | `0.5` to `2.0`                                                                                    |
| `pitch`          | `0`                      | `-12` to `12` (semitones)                                                                         |
| `emotion`        | (none)                   | `happy`, `sad`, `angry`, `fearful`, `disgusted`, `surprised`, `calm`, `fluent`, `whisper`         |
| `language_boost` | `auto`                   | `auto`, `Turkish`, `English`, `Chinese`, `Japanese`, 20+ languages                                |
| `sample_rate`    | `32000`                  | `8000`, `16000`, `22050`, `24000`, `32000`, `44100`                                               |
| `bitrate`        | `128000`                 | `32000`, `64000`, `128000`, `256000`                                                              |

---

## Usage

### Basic - call from Developer Tools

```yaml
service: tts.minimax_say
target:
  entity_id: tts.minimax_tts
data:
  message: "Merhaba dunya, bu bir testtir."
```

### With voice override

```yaml
service: tts.minimax_say
target:
  entity_id: tts.minimax_tts
data:
  message: "Good morning, Dave."
  language: en
options:
  voice_id: English_Graceful_Lady
  speed: 1.1
  emotion: happy
```

### Play on a specific media_player

```yaml
service: tts.minimax_say
target:
  entity_id: tts.minimax_tts
data:
  message: "Yatak odasi isiklari acildi"
  media_player_entity_id: media_player.bedroom_speaker
```

See [`examples/automations.yaml`](examples/automations.yaml) for complete automation examples.

---

## Available Turkish voices

| Voice ID                      | Gender | Style                      |
| ----------------------------- | ------ | -------------------------- |
| `Turkish_Trustworthyman`      | Male   | Trustworthy, deep          |
| `Turkish_CalmWoman`           | Female | Calm, soothing             |

Other popular voices:

| Language   | Voice IDs                                                                              |
| ---------- | -------------------------------------------------------------------------------------- |
| English    | `English_Graceful_Lady`, `English_Insightful_Speaker`, `English_radiant_girl`, `English_Persuasive_Man`, `English_Aussie_Bloke`, `English_Lucky_Robot` |
| Chinese    | `Chinese_(Mandarin)_Lyrical_Voice`, `Chinese_(Mandarin)_HK_Flight_Attendant`            |
| Japanese   | `Japanese_Whisper_Belle`                                                                |
| Cantonese  | `Cantonese_GentleLady`, `Cantonese_podacast_host_1`                                    |

Full list: https://platform.minimax.io/docs/faq/system-voice-id

---

## Troubleshooting

### "invalid_auth" error during setup

Your API key is wrong or revoked. Regenerate it at https://platform.minimax.io/user-center/basic-information/interface-key

### Audio not playing

- Verify the entity exists: `Developer Tools -> States -> search "tts.minimax"`
- Check `media_player` is on and volume > 0
- Check `/config/www/minimax_tts/` exists and is writable
- Check `home-assistant.log` for `[homeassistant.components.minimax_tts]` errors

### Quota exceeded

MiniMax will return status 1002. Buy more credits at https://platform.minimax.io and reload the integration.

### Long text cut off

Sync API limit is 10,000 characters per call. For longer text, split into chunks of 10K or less.

### Voice sounds robotic

Try `speech-2.8-hd` instead of `speech-2.8-turbo` (slower but more natural). Adjust `speed` to 0.9-1.0.

---

## API reference

This integration wraps the [MiniMax T2A v2 endpoint](https://platform.minimax.io/docs/api-reference/speech-t2a-http). MiniMax returns hex-encoded MP3 in a JSON response, which we decode and cache under `/config/www/minimax_tts/`.

---

## License

Apache 2.0 - see [LICENSE](LICENSE).

## Credits

Built by [@brooqs](https://github.com/brooqs) for the Home Assistant community.
