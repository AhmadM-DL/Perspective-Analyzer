from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
from transcription import get_youtube_transcript
from graph_generator import generate_graph
import os
import json
import queue
import threading

app = Flask(__name__)
CORS(app)

@app.route('/analyze-stream', methods=['POST'])
def analyze_video_stream():
    """
    Analyze video with Server-Sent Events for progress updates
    """
    def generate():
        try:
            data = request.get_json()
            youtube_url = data.get('youtube_url')
            
            if not youtube_url:
                yield f"data: {json.dumps({'error': 'YouTube URL is required'})}\n\n"
                return
            
            # Create a queue for progress messages
            progress_queue = queue.Queue()
            
            def progress_callback(message):
                progress_queue.put(message)
            
            # Variable to store results
            result = {'transcript': None, 'graph': None, 'error': None}
            
            def fetch_and_analyze():
                try:
                    # Step 1: Get transcript with progress
                    transcript_result = get_youtube_transcript(youtube_url, progress_callback)
                    
                    if not transcript_result:
                        result['error'] = 'Could not fetch transcript for this video'
                        progress_queue.put('ERROR: Could not fetch transcript')
                        return
                    
                    # Handle both simple transcript and enriched result with speaker info
                    if isinstance(transcript_result, dict):
                        result['transcript'] = transcript_result['transcript']
                        result['transcriptLength'] = len(result['transcript'])
                        result['numSpeakers'] = transcript_result.get('num_speakers', 0)
                        result['speakers'] = transcript_result.get('unique_speakers', [])
                        
                        progress_callback(f"Transcript received: {result['transcriptLength']} characters, {result['numSpeakers']} speakers detected")
                    else:
                        result['transcript'] = transcript_result
                        result['transcriptLength'] = len(result['transcript'])
                        result['numSpeakers'] = 0
                        result['speakers'] = []
                        
                        progress_callback(f"Transcript received: {result['transcriptLength']} characters")
                    
                    # Step 2: Generate graph with speaker info
                    progress_callback("Analyzing transcript and generating graph...")
                    
                    if result['numSpeakers'] > 0:
                        result['graph'] = generate_graph(
                            result['transcript'], 
                            speaker_info={'num_speakers': result['numSpeakers'], 'speakers': result['speakers']}
                        )
                    else:
                        result['graph'] = generate_graph(result['transcript'])
                    
                    # Check if graph generation failed
                    if not result['graph'] or result['graph'].get('error'):
                        error_msg = result['graph'].get('message', 'Could not generate graph from transcript') if result['graph'] else 'Could not generate graph from transcript'
                        result['graph'] = None
                        result['graphError'] = error_msg
                        progress_callback(f"Warning: {error_msg}")
                    else:
                        progress_callback("Graph generated successfully")
                    
                    progress_queue.put('COMPLETE')
                    
                except Exception as e:
                    result['error'] = str(e)
                    progress_queue.put(f'ERROR: {str(e)}')
            
            # Start processing in background thread
            thread = threading.Thread(target=fetch_and_analyze)
            thread.daemon = True
            thread.start()
            
            # Stream progress updates
            while True:
                try:
                    message = progress_queue.get(timeout=0.5)
                    
                    if message == 'COMPLETE':
                        # Send final result with transcript length and speaker info
                        yield f"data: {json.dumps({'type': 'complete', 'graph': result['graph'], 'transcriptLength': result.get('transcriptLength', 0), 'numSpeakers': result.get('numSpeakers', 0)})}\n\n"
                        break
                    elif message.startswith('ERROR:'):
                        yield f"data: {json.dumps({'type': 'error', 'message': message[7:]})}\n\n"
                        break
                    else:
                        # Send progress update
                        yield f"data: {json.dumps({'type': 'progress', 'message': message})}\n\n"
                        
                except queue.Empty:
                    # Send keepalive
                    yield f"data: {json.dumps({'type': 'keepalive'})}\n\n"
                    
                    # Check if thread is still alive
                    if not thread.is_alive() and progress_queue.empty():
                        if result['error']:
                            yield f"data: {json.dumps({'type': 'error', 'message': result['error']})}\n\n"
                        break
                        
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy'}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
