"""
Configuration file for the Political TV Program Analyzer
"""

# OpenAI Whisper API Configuration
WHISPER_API_MODEL = "whisper-1"  # OpenAI's Whisper API model
WHISPER_LANGUAGE = "en"  # Language code for Whisper transcription

# OpenAI Configuration
OPENAI_MODEL = "gpt-4-turbo"  # Options: gpt-3.5-turbo, gpt-4, gpt-4-turbo
OPENAI_MAX_TOKENS = 2000
OPENAI_TEMPERATURE = 0.7

# YouTube Download Configuration
DOWNLOAD_AUDIO_ONLY = True  # Set to True to download only audio (recommended)
DOWNLOAD_LOWEST_QUALITY = True  # Set to True to download lowest quality (recommended)

# Graph Generation Configuration
MIN_SPEAKERS = 2
MAX_SPEAKERS = 8
MIN_TOPICS = 5
MAX_TOPICS = 10
MIN_OPINIONS = 8
MAX_OPINIONS = 15

# Flask Configuration
FLASK_DEBUG = True
FLASK_HOST = '0.0.0.0'
FLASK_PORT = 5000

# Transcript Configuration
MAX_TRANSCRIPT_LENGTH = 4000  # Characters to send to OpenAI for analysis
