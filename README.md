# Rhasspy ASR Pocketsphinx Hermes MQTT Service

Implements `hermes/asr` functionality from [Hermes protocol](https://docs.snips.ai/reference/hermes) using openAi's Whisper HTTP API.
This is a fork that uses rhasspy-asr-pocketsphinx-hermes as a base to implement the hermes/asr functionality for openai Whisper.

## Installation

```bash
$ git clone https://github.com/rhasspy/rhasspy-asr-whisper-hermes
$ cd rhasspy-asr-whisper-hermes
$ ./configure
$ make
$ make install
```

## Running

```bash
$ bin/rhasspy-asr-whisper-hermes <ARGS>
```

## Command-Line Options

```
usage: rhasspy-asr-whisper-hermes [-h] [--openai-api-key OPENAI_API_KEY]
                                       [--voice-skip-seconds VOICE_SKIP_SECONDS]
                                       [--voice-min-seconds VOICE_MIN_SECONDS]
                                       [--voice-speech-seconds VOICE_SPEECH_SECONDS]
                                       [--voice-silence-seconds VOICE_SILENCE_SECONDS]
                                       [--voice-before-seconds VOICE_BEFORE_SECONDS]
                                       [--voice-sensitivity {1,2,3}]
                                       [--host HOST] [--port PORT]
                                       [--username USERNAME]
                                       [--password PASSWORD] [--tls]
                                       [--tls-ca-certs TLS_CA_CERTS]
                                       [--tls-certfile TLS_CERTFILE]
                                       [--tls-keyfile TLS_KEYFILE]
                                       [--tls-cert-reqs {CERT_REQUIRED,CERT_OPTIONAL,CERT_NONE}]
                                       [--tls-version TLS_VERSION]
                                       [--tls-ciphers TLS_CIPHERS]
                                       [--site-id SITE_ID] [--debug]
                                       [--log-format LOG_FORMAT]

optional arguments:
  -h, --help            show this help message and exit
  --openai-api-key OPENAI_API_KEY 
                        the openai api key to send requests to the whisper model
  --voice-skip-seconds VOICE_SKIP_SECONDS
                        Seconds of audio to skip before a voice command
  --voice-min-seconds VOICE_MIN_SECONDS
                        Minimum number of seconds for a voice command
  --voice-speech-seconds VOICE_SPEECH_SECONDS
                        Consecutive seconds of speech before start
  --voice-silence-seconds VOICE_SILENCE_SECONDS
                        Consecutive seconds of silence before stop
  --voice-before-seconds VOICE_BEFORE_SECONDS
                        Seconds to record before start
  --voice-sensitivity {1,2,3}
                        VAD sensitivity (1-3)
  --host HOST           MQTT host (default: localhost)
  --port PORT           MQTT port (default: 1883)
  --username USERNAME   MQTT username
  --password PASSWORD   MQTT password
  --tls                 Enable MQTT TLS
  --tls-ca-certs TLS_CA_CERTS
                        MQTT TLS Certificate Authority certificate files
  --tls-certfile TLS_CERTFILE
                        MQTT TLS certificate file (PEM)
  --tls-keyfile TLS_KEYFILE
                        MQTT TLS key file (PEM)
  --tls-cert-reqs {CERT_REQUIRED,CERT_OPTIONAL,CERT_NONE}
                        MQTT TLS certificate requirements (default:
                        CERT_REQUIRED)
  --tls-version TLS_VERSION
                        MQTT TLS version (default: highest)
  --tls-ciphers TLS_CIPHERS
                        MQTT TLS ciphers to use
  --site-id SITE_ID     Hermes site id(s) to listen for (default: all)
  --debug               Print DEBUG messages to the console
  --log-format LOG_FORMAT
                        Python logger format
```
