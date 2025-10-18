from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from pyannote.audio import Pipeline
from pydub import AudioSegment
import tempfile
import os
import torch
import json
import base64
import io
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Create output directory for saving results
OUTPUT_DIR = "/app/outputs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Global variable to hold the pipeline
diarization_pipeline = None

def load_pipeline():
    """Load diarization pipeline on startup"""
    global diarization_pipeline
    if diarization_pipeline is None:
        print("Loading speaker diarization pipeline...")
        
        # Get HuggingFace token from environment
        hf_token = os.getenv('HUGGINGFACE_TOKEN')
        
        if not hf_token:
            print("WARNING: HUGGINGFACE_TOKEN not set. Diarization may not work.")
            print("Get token from: https://huggingface.co/settings/tokens")
            print("Accept model conditions at: https://huggingface.co/pyannote/speaker-diarization-3.1")
            return None
        
        try:
            # Load pre-trained pipeline
            diarization_pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=hf_token,
                cache_dir="/models/diarization"
            )
            
            # Use GPU if available
            if torch.cuda.is_available():
                diarization_pipeline.to(torch.device("cuda"))
                print("Using GPU for diarization")
            else:
                print("Using CPU for diarization")
            
            print("Speaker diarization pipeline loaded successfully!")
            
        except Exception as e:
            print(f"Error loading diarization pipeline: {str(e)}")
            return None
    
    return diarization_pipeline

@app.route('/health', methods=['GET'])
def health_check():
    pipeline_status = 'loaded' if diarization_pipeline is not None else 'not loaded'
    return jsonify({'status': 'healthy', 'pipeline': pipeline_status}), 200

@app.route('/diarize-and-split', methods=['POST'])
def diarize_and_split():
    """
    Perform speaker diarization and split audio into speaker chunks
    Expected: multipart/form-data with 'audio' file
    Returns: Diarization data + base64 encoded audio chunks for each speaker
    """
    try:
        if 'audio' not in request.files:
            return jsonify({'error': 'No audio file provided'}), 400
        
        audio_file = request.files['audio']
        num_speakers = request.form.get('num_speakers', None)
        
        if num_speakers:
            num_speakers = int(num_speakers)
        
        # Save to temporary file
        temp_dir = tempfile.mkdtemp()
        temp_path = os.path.join(temp_dir, 'audio.mp4')
        audio_file.save(temp_path)
        
        try:
            # Load pipeline if not already loaded
            pipeline = load_pipeline()
            
            if pipeline is None:
                return jsonify({
                    'error': 'Diarization pipeline not available. Check HUGGINGFACE_TOKEN.',
                    'speakers': []
                }), 500
            
            # Perform diarization
            print(f"Performing speaker diarization and audio splitting...")
            
            if num_speakers:
                diarization = pipeline(temp_path, num_speakers=num_speakers)
            else:
                diarization = pipeline(temp_path)
            
            # Load audio file
            audio = AudioSegment.from_file(temp_path)
            
            # Extract speaker segments and split audio
            speakers = []
            speaker_chunks = {}  # Dict to store audio chunks per speaker
            
            for turn, _, speaker in diarization.itertracks(yield_label=True):
                segment_data = {
                    'speaker': speaker,
                    'start': turn.start,
                    'end': turn.end,
                    'duration': turn.end - turn.start
                }
                speakers.append(segment_data)
                
                # Extract audio chunk for this segment
                start_ms = int(turn.start * 1000)
                end_ms = int(turn.end * 1000)
                chunk = audio[start_ms:end_ms]
                
                # Add chunk to speaker's audio
                if speaker not in speaker_chunks:
                    speaker_chunks[speaker] = []
                speaker_chunks[speaker].append(chunk)
            
            # Merge chunks for each speaker
            merged_chunks = {}
            for speaker, chunks in speaker_chunks.items():
                # Concatenate all chunks for this speaker
                merged_audio = sum(chunks)
                
                # Export to bytes
                buffer = io.BytesIO()
                merged_audio.export(buffer, format='mp3')
                buffer.seek(0)
                
                # Encode as base64
                audio_b64 = base64.b64encode(buffer.read()).decode('utf-8')
                merged_chunks[speaker] = audio_b64
            
            # Get unique speakers
            unique_speakers = list(set([s['speaker'] for s in speakers]))
            
            print(f"Diarization and splitting completed: {len(unique_speakers)} speakers, {len(speakers)} segments")
            
            # Save results to file with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = os.path.join(OUTPUT_DIR, f"diarization_split_{timestamp}.txt")
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"Diarization & Audio Split Results - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"{'='*80}\n\n")
                f.write(f"Number of speakers: {len(unique_speakers)}\n")
                f.write(f"Unique speakers: {', '.join(unique_speakers)}\n")
                f.write(f"Total segments: {len(speakers)}\n")
                f.write(f"Audio chunks generated: {len(merged_chunks)}\n\n")
                f.write(f"{'='*80}\n\n")
                f.write("Speaker Timeline:\n\n")
                
                for segment in speakers:
                    f.write(f"{segment['speaker']}: {segment['start']:.2f}s - {segment['end']:.2f}s (duration: {segment['duration']:.2f}s)\n")
                
                f.write(f"\n{'='*80}\n\n")
                f.write("Audio Chunks Info:\n\n")
                for speaker in unique_speakers:
                    chunk_size = len(merged_chunks.get(speaker, ''))
                    f.write(f"{speaker}: {chunk_size} bytes (base64 encoded)\n")
            
            print(f"Diarization results saved to: {output_file}")
            
            return jsonify({
                'speakers': speakers,
                'num_speakers': len(unique_speakers),
                'unique_speakers': unique_speakers,
                'audio_chunks': merged_chunks  # Base64 encoded audio for each speaker
            }), 200
            
        finally:
            # Clean up
            if os.path.exists(temp_path):
                os.remove(temp_path)
            if os.path.exists(temp_dir):
                os.rmdir(temp_dir)
    
    except Exception as e:
        print(f"Error during diarization and splitting: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Pre-load the pipeline on startup
    print("Starting Diarization Service...")
    load_pipeline()
    print("Diarization Service ready!")
    app.run(host='0.0.0.0', port=5002, debug=False)
