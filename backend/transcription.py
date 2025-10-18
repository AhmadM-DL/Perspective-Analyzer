import re
import argparse
import os
from pytubefix import YouTube
import tempfile
import requests
import json
from pydub import AudioSegment
from datetime import datetime

def extract_video_id(url):
    """
    Extract YouTube video ID from various URL formats
    """
    patterns = [
        r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/watch\?v=([a-zA-Z0-9_-]+)',
        r'(?:https?:\/\/)?(?:www\.)?youtu\.be\/([a-zA-Z0-9_-]+)',
        r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/embed\/([a-zA-Z0-9_-]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None

def merge_transcript_with_speakers(transcript, speaker_segments):
    """
    Merge Whisper transcript with speaker diarization data.
    Creates a formatted transcript with speaker labels.
    
    Args:
        transcript (str): Raw transcript from Whisper
        speaker_segments (list): List of speaker segments with timestamps
        
    Returns:
        str: Formatted transcript with speaker labels
    """
    if not speaker_segments or len(speaker_segments) == 0:
        return transcript
    
    # For now, we'll split the transcript by sentences and assign speakers based on time proportions
    # This is a simplified approach - ideally we'd use word-level timestamps
    
    sentences = transcript.replace('!', '.').replace('?', '.').split('.')
    sentences = [s.strip() for s in sentences if s.strip()]
    
    if not sentences:
        return transcript
    
    # Calculate total duration
    total_duration = max([seg['end'] for seg in speaker_segments])
    
    # Assign approximate time to each sentence
    time_per_sentence = total_duration / len(sentences)
    
    formatted_transcript = []
    current_speaker = None
    speaker_text = []
    
    for i, sentence in enumerate(sentences):
        sentence_time = i * time_per_sentence
        
        # Find which speaker is talking at this time
        speaker = None
        for seg in speaker_segments:
            if seg['start'] <= sentence_time <= seg['end']:
                speaker = seg['speaker']
                break
        
        if speaker is None:
            # Find closest speaker
            closest_seg = min(speaker_segments, key=lambda x: min(abs(x['start'] - sentence_time), abs(x['end'] - sentence_time)))
            speaker = closest_seg['speaker']
        
        # If speaker changed, output previous speaker's text
        if speaker != current_speaker:
            if current_speaker is not None and speaker_text:
                formatted_transcript.append(f"{current_speaker}: {' '.join(speaker_text)}")
            current_speaker = speaker
            speaker_text = [sentence]
        else:
            speaker_text.append(sentence)
    
    # Add last speaker's text
    if current_speaker is not None and speaker_text:
        formatted_transcript.append(f"{current_speaker}: {' '.join(speaker_text)}")
    
    return '\n\n'.join(formatted_transcript)

def get_youtube_transcript(youtube_url, progress_callback=None):
    """
    Download video, perform speaker diarization, split audio by speaker, and transcribe each chunk.
    Returns a speaker-labeled transcript with better accuracy.
    
    Args:
        youtube_url (str): YouTube video URL
        progress_callback (callable): Optional callback function for progress updates
        
    Returns:
        dict: Contains formatted transcript with speaker labels and speaker information
    """
    temp_dir = None
    audio_file = None
    wav_file = None
    
    try:
        if progress_callback:
            progress_callback("Initializing YouTube download...")
        
        # Create temporary directory
        temp_dir = tempfile.mkdtemp()
        
        # Download audio from YouTube
        if progress_callback:
            progress_callback("Downloading audio from YouTube...")
        
        yt = YouTube(youtube_url)
        
        # Get audio stream with lowest quality for faster processing
        audio_stream = yt.streams.filter(only_audio=True).order_by('abr').first()
        
        if not audio_stream:
            raise Exception("No audio stream available")
        
        # Download audio
        audio_file = audio_stream.download(output_path=temp_dir, filename="audio.mp4")
        
        if progress_callback:
            progress_callback(f"Audio downloaded: {os.path.basename(audio_file)}")
        
        # Convert audio to WAV format for diarization service
        if progress_callback:
            progress_callback("Converting audio to WAV format...")
        
        wav_file = os.path.join(temp_dir, "audio.wav")
        audio = AudioSegment.from_file(audio_file)
        audio.export(wav_file, format="wav")
        
        if progress_callback:
            progress_callback("Audio converted to WAV format")
        
        # Step 1: Diarize and split audio by speaker
        if progress_callback:
            progress_callback("Identifying speakers and splitting audio...")
        
        diarization_url = os.getenv('DIARIZATION_SERVICE_URL', 'http://diarization-service:5002')
        
        with open(wav_file, 'rb') as f:
            files = {'audio': f}
            response = requests.post(f"{diarization_url}/diarize-and-split", files=files, timeout=600)
        
        if response.status_code != 200:
            raise Exception(f"Diarization service error: {response.text}")
        
        diarization_result = response.json()
        speaker_segments = diarization_result.get('speakers', [])
        num_speakers = diarization_result.get('num_speakers', 0)
        unique_speakers = diarization_result.get('unique_speakers', [])
        audio_chunks = diarization_result.get('audio_chunks', {})
        
        if progress_callback:
            progress_callback(f"Diarization completed: {num_speakers} speakers identified, audio split into {len(audio_chunks)} chunks")
        
        # Step 2: Transcribe each speaker's audio chunk with Whisper
        if progress_callback:
            progress_callback("Transcribing speaker audio chunks with Whisper AI...")
        
        whisper_url = os.getenv('WHISPER_SERVICE_URL', 'http://whisper-service:5001')
        
        # Send all chunks to Whisper service
        response = requests.post(
            f"{whisper_url}/transcribe-chunks", 
            json={'chunks': audio_chunks, 'language': 'en'},
            timeout=600
        )
        
        if response.status_code != 200:
            raise Exception(f"Whisper service error: {response.text}")
        
        whisper_result = response.json()
        speaker_transcripts = whisper_result.get('transcripts', {})
        
        if progress_callback:
            progress_callback(f"Transcription completed for {len(speaker_transcripts)} speakers")
        
        # Step 3: Merge transcripts with speaker timeline
        if progress_callback:
            progress_callback("Merging transcripts with speaker timeline...")
        
        formatted_lines = []
        total_chars = 0
        
        # Group segments by speaker in chronological order
        for segment in speaker_segments:
            speaker = segment['speaker']
            if speaker in speaker_transcripts and speaker_transcripts[speaker].strip():
                # Only add if we haven't seen this speaker's text yet in this position
                # This creates a more natural conversation flow
                pass
        
        # Create a better formatted transcript by ordering segments chronologically
        # and assigning the transcribed text proportionally
        speaker_texts = {}
        for speaker, text in speaker_transcripts.items():
            # Split text into sentences
            sentences = [s.strip() for s in text.replace('!', '.').replace('?', '.').split('.') if s.strip()]
            speaker_texts[speaker] = sentences
        
        speaker_indices = {sp: 0 for sp in unique_speakers}
        
        for segment in speaker_segments:
            speaker = segment['speaker']
            if speaker in speaker_texts and speaker_indices[speaker] < len(speaker_texts[speaker]):
                sentence = speaker_texts[speaker][speaker_indices[speaker]]
                formatted_lines.append(f"{speaker}: {sentence}")
                total_chars += len(sentence)
                speaker_indices[speaker] += 1
        
        formatted_transcript = '\n\n'.join(formatted_lines)
        
        # Create raw transcript (all speakers combined)
        raw_transcript = ' '.join([text for text in speaker_transcripts.values()])
        
        # Save final labeled transcript to file with timestamp
        output_dir = "/app/outputs"
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(output_dir, f"final_transcript_{timestamp}.txt")
        
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"Final Speaker-Labeled Transcript - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"{'='*80}\n\n")
                f.write(f"YouTube URL: {youtube_url}\n")
                f.write(f"Number of speakers: {num_speakers}\n")
                f.write(f"Speakers: {', '.join(unique_speakers)}\n")
                f.write(f"Total characters: {total_chars}\n\n")
                f.write(f"{'='*80}\n\n")
                f.write("Speaker-Labeled Transcript:\n\n")
                f.write(formatted_transcript)
                f.write(f"\n\n{'='*80}\n\n")
                f.write("Raw Transcript (All Speakers):\n\n")
                f.write(raw_transcript)
            
            print(f"Final transcript saved to: {output_file}")
            if progress_callback:
                progress_callback(f"Transcript saved to file: {os.path.basename(output_file)}")
        except Exception as e:
            print(f"Warning: Could not save transcript to file: {str(e)}")
        
        if progress_callback:
            progress_callback("Audio processing completed successfully!")
        
        return {
            'transcript': formatted_transcript,
            'raw_transcript': raw_transcript,
            'speakers': speaker_segments,
            'num_speakers': num_speakers,
            'unique_speakers': unique_speakers
        }
        
    except Exception as e:
        error_msg = f"Error with transcription/diarization: {str(e)}"
        print(error_msg)
        if progress_callback:
            progress_callback(error_msg)
        return None
        
    finally:
        # Clean up temporary files
        try:
            if wav_file and os.path.exists(wav_file):
                os.remove(wav_file)
            if audio_file and os.path.exists(audio_file):
                os.remove(audio_file)
            if temp_dir and os.path.exists(temp_dir):
                os.rmdir(temp_dir)
        except Exception as e:
            print(f"Error cleaning up temp files: {str(e)}")



if __name__ == "__main__":
    # Set up argument parser
    parser = argparse.ArgumentParser(
        description='Transcribe YouTube video with speaker diarization using Whisper AI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python transcription.py --url "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
  python transcription.py -u "https://youtu.be/dQw4w9WgXcQ" -v
        """
    )
    
    parser.add_argument(
        '-u', '--url',
        type=str,
        required=True,
        help='YouTube video URL to transcribe'
    )
    
    parser.add_argument(
        '-o', '--output',
        type=str,
        required=False,
        help='Output file path to save transcript (optional)'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose output'
    )
    
    # Parse arguments
    args = parser.parse_args()
    
    # Fetch transcript
    if args.verbose:
        print(f"Transcribing video: {args.url}")
    
    def print_progress(message):
        if args.verbose:
            print(f"[PROGRESS] {message}")
    
    result = get_youtube_transcript(args.url, progress_callback=print_progress)
    
    print("\n" + "="*80)
    if result:
        # Whisper + Diarization result
        print("SUCCESS! (Whisper + Speaker Diarization)")
        print(f"Transcript length: {len(result['transcript'])} characters")
        print(f"Number of speakers: {result['num_speakers']}")
        print(f"Speakers: {', '.join(result['unique_speakers'])}")
        print("\nFirst 500 characters:")
        print("-"*80)
        print(result['transcript'][:500])
        print("-"*80)
        
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(f"Transcript ({result['num_speakers']} speakers):\n\n")
                f.write(result['transcript'])
                f.write(f"\n\nSpeakers: {', '.join(result['unique_speakers'])}")
            print(f"✓ Transcript saved to: {args.output}")
    else:
        print("✗ Failed to transcribe video")
    print("="*80)

