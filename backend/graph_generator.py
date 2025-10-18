import openai
import os
import json
try:
    from config import (
        OPENAI_MODEL, OPENAI_MAX_TOKENS, OPENAI_TEMPERATURE,
        MIN_SPEAKERS, MAX_SPEAKERS, MIN_TOPICS, MAX_TOPICS,
        MIN_OPINIONS, MAX_OPINIONS, MAX_TRANSCRIPT_LENGTH
    )
except ImportError:
    OPENAI_MODEL = "gpt-3.5-turbo"
    OPENAI_MAX_TOKENS = 2000
    OPENAI_TEMPERATURE = 0.7
    MIN_SPEAKERS = 2
    MAX_SPEAKERS = 8
    MIN_TOPICS = 5
    MAX_TOPICS = 10
    MIN_OPINIONS = 8
    MAX_OPINIONS = 15
    MAX_TRANSCRIPT_LENGTH = 4000

# Set your OpenAI API key
openai.api_key = os.getenv('OPENAI_API_KEY', '')

def generate_graph(transcript, speaker_info=None):
    """
    Generate a D3-compatible graph from a political TV program transcript.
    
    This function uses OpenAI API to analyze the transcript and extract:
    - Speakers and their names
    - Main topics/nouns discussed
    - Opinions expressed (positive, neutral, negative)
    - Relationships between speakers, topics, and opinions
    
    Args:
        transcript (str): The full transcript text
        speaker_info (dict): Optional speaker diarization info with num_speakers and speakers list
        
    Returns:
        dict: Graph data in D3.js format with nodes and links
    """

    prompt = f"""
You are analyzing a transcript from a political TV program.
The transcript is structured in a way that speakers are identified by a speaker id.
Go through the transcript and identify the following:

1. Identify main TOPICS/NOUNS (political issues, entities, concepts discussed)
2. Identify OPINIONS expressed by each speaker about topics (classify as positive, neutral, or negative)
3. Create relationships between speakers, topics, and opinions

Return ONLY a valid JSON object in this exact format:

{{
  "nodes": [
    {{"id": "speaker1", "label": "Speaker Name", "type": "speaker"}},
    {{"id": "topic1", "label": "Topic Name", "type": "topic"}},
    {{"id": "opinion1", "label": "Opinion Text", "type": "opinion", "sentiment": "positive|neutral|negative", "context": "Detailed explanation and context of the opinion and the stance"}},
  ],
  "links": [
    {{"source": "speaker1", "target": "opinion1", "label": "expresses"}},
    {{"source": "opinion1", "target": "topic1", "label": "about"}},
  ]
}}

Rules:
- Each speaker should be a node with type "speaker"
- Each topic should be a node with type "topic"
- Each opinion should be a node with type "opinion" and have a sentiment field
- Links connect speakers to opinions and opinions to topics
- Keep labels concise (max 5 words)
- Sentiment can be: "positive", "neutral", or "negative"
- Extract {MIN_SPEAKERS}-{MAX_SPEAKERS} speakers, {MIN_TOPICS}-{MAX_TOPICS} topics, and {MIN_OPINIONS}-{MAX_OPINIONS} opinions

Transcript to analyze:
{transcript[:MAX_TRANSCRIPT_LENGTH]}

Return only the JSON object, no other text.
"""
    
    try:
        # Call OpenAI API
        response = openai.ChatCompletion.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "You are an expert at analyzing political discourse and extracting structured data. Always respond with valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=OPENAI_TEMPERATURE,
            max_tokens=OPENAI_MAX_TOKENS
        )
        
        # Extract the response
        result = response.choices[0].message.content.strip()
        
        # Parse JSON
        graph_data = json.loads(result)
        
        # Validate structure
        if 'nodes' not in graph_data or 'links' not in graph_data:
            raise ValueError("Invalid graph structure returned by API")
        
        return graph_data
        
    except json.JSONDecodeError as e:
        print(f"JSON parsing error: {str(e)}")
        # Return error message instead of default graph
        return {
            "error": True,
            "message": f"Failed to generate graph: JSON parsing error - {str(e)}"
        }
        
    except Exception as e:
        print(f"Error generating graph: {str(e)}")
        # Return error message instead of default graph
        return {
            "error": True,
            "message": f"Failed to generate graph: {str(e)}"
        }


if __name__ == "__main__":
    # Test the function
    test_transcript = "Host: Welcome to our political debate. Today we discuss healthcare reform. Senator Smith believes the new healthcare plan will benefit millions. Senator Jones argues it's too expensive and inefficient. Let's hear from both sides."
    graph = generate_graph(test_transcript)
    print(json.dumps(graph, indent=2))
