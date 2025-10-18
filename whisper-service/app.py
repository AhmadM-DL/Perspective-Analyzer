from flask import Flask, request, jsonify
from flask_cors import CORS
import whisper
import tempfile
import os
import base64
import io
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Create output directory for saving results
OUTPUT_DIR = "/app/outputs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Global variable to hold the model
whisper_model = None
MODEL_NAME = os.getenv('WHISPER_MODEL', 'base')

def load_model():
    """Load Whisper model on startup"""
    global whisper_model
    if whisper_model is None:
        print(f"Loading Whisper {MODEL_NAME} model...")
        # Models will be cached in /models/whisper volume
        whisper_model = whisper.load_model(MODEL_NAME, download_root="/models/whisper")
        print(f"Whisper {MODEL_NAME} model loaded successfully!")
    return whisper_model

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'model': MODEL_NAME}), 200

@app.route('/transcribe-chunks', methods=['POST'])
def transcribe_chunks():
    """
    Transcribe multiple audio chunks (one per speaker)
    Expected: JSON with { 'chunks': { 'SPEAKER_00': 'base64_audio', ...} }
    Returns: { 'transcripts': { 'SPEAKER_00': 'text', ...} }
    """
    try:
        data = request.get_json()
        
        if not data or 'chunks' not in data:
            return jsonify({'error': 'No audio chunks provided'}), 400
        
        chunks = data['chunks']
        language = data.get('language', 'en')
        
        # Load model if not already loaded
        model = load_model()
        
        transcripts = {}
        temp_dir = tempfile.mkdtemp()
        
        try:
            print(f"Transcribing {len(chunks)} speaker chunks...")
            
            for speaker, audio_b64 in chunks.items():
                # Decode base64 audio
                audio_bytes = base64.b64decode(audio_b64)
                
                # Save to temporary file
                temp_path = os.path.join(temp_dir, f'{speaker}.mp3')
                with open(temp_path, 'wb') as f:
                    f.write(audio_bytes)
                
                # Transcribe
                print(f"Transcribing {speaker}...")
                result = model.transcribe(temp_path, language=language, fp16=False)
                transcripts[speaker] = result["text"]
                
                # Clean up this file
                os.remove(temp_path)
                
                print(f"{speaker}: {len(result['text'])} characters")
            
            print(f"All {len(chunks)} chunks transcribed successfully!")
            
            # Save speaker transcripts to file with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = os.path.join(OUTPUT_DIR, f"whisper_chunks_{timestamp}.txt")
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"Whisper Speaker Chunk Transcription - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"{'='*80}\n\n")
                f.write(f"Model: {MODEL_NAME}\n")
                f.write(f"Language: {language}\n")
                f.write(f"Number of speakers: {len(transcripts)}\n\n")
                f.write(f"{'='*80}\n\n")
                f.write("Speaker Transcripts:\n\n")
                
                for speaker, text in sorted(transcripts.items()):
                    f.write(f"{speaker}:\n")
                    f.write(f"{'-'*80}\n")
                    f.write(f"{text}\n\n")
            
            print(f"Speaker transcripts saved to: {output_file}")
            
            return jsonify({
                'transcripts': transcripts,
                'language': language,
                'num_speakers': len(transcripts)
            }), 200
            
        finally:
            # Clean up temp directory
            if os.path.exists(temp_dir):
                os.rmdir(temp_dir)
    
    except Exception as e:
        print(f"Error transcribing chunks: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Pre-load the model on startup
    print("Starting Whisper Service...")
    load_model()
    print("Whisper Service ready!")
    app.run(host='0.0.0.0', port=5001, debug=False)
