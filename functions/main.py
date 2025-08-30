#
#  IST Chatbot FYP - Semantic Search Cloud Function (Firebase Version)
#  -------------------------------------------------------------------
#  This is the main Python code for the backend "brain" of the chatbot.
#  It's designed to be deployed using the Firebase CLI.
#

# Firebase and Google Cloud imports
from firebase_functions import https_fn
from firebase_functions.options import set_global_options
from firebase_admin import initialize_app, firestore

# AI and Data Processing imports
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import re

# For cost control and performance management.
# This sets a global limit of 10 concurrent instances for all functions.
set_global_options(max_instances=10)

# --- GLOBAL VARIABLES (INITIALIZED ONCE ON COLD START) ---

# Initialize Firebase Admin SDK.
# Credentials are automatically handled by the Firebase/Google Cloud environment.
initialize_app()
db = firestore.client()

# Load the Sentence Transformer model. This is a heavy operation, so we do it
# once when the function instance starts, not for every request.
print("Loading SentenceTransformer model...")
model = SentenceTransformer('all-MiniLM-L6-v2')
print("Model loaded successfully.")

# Pre-fetch the entire knowledge base from Firestore and store it in memory.
# This makes the search much faster as we don't have to query the database on every request.
knowledge_base = []
print("Fetching knowledge base from Firestore...")
try:
    docs = db.collection('qna_semantic').stream()
    for doc in docs:
        doc_data = doc.to_dict()
        # Ensure the document has a valid 'embedding' field
        if 'embedding' in doc_data and doc_data['embedding']:
             knowledge_base.append(doc_data)
    print(f"Knowledge base fetched successfully. {len(knowledge_base)} documents loaded.")
except Exception as e:
    print(f"Error fetching knowledge base: {e}")


# --- MAIN CLOUD FUNCTION ---

@https_fn.on_request()
def find_answer(req: https_fn.Request) -> https_fn.Response:
    """
    HTTP Cloud Function that receives a user's question and returns the best answer.
    """
    # Set CORS headers to allow requests from any origin (your chatbot widget)
    # This is necessary for the browser to allow the frontend to talk to the backend.
    headers = {'Access-Control-Allow-Origin': '*'}

    if req.method == 'OPTIONS':
        # Pre-flight request. Reply successfully.
        cors_headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Max-Age': '3600'
        }
        return ("", 204, cors_headers)

    # Get the user's question from the request body
    try:
        request_json = req.get_json(silent=True)
    except Exception as e:
        print(f"Error parsing JSON: {e}")
        return https_fn.Response(body="Invalid JSON format.", status=400, headers=headers)

    if not request_json or 'question' not in request_json:
        return https_fn.Response(body="Invalid request. 'question' field is missing.", status=400, headers=headers)

    user_query = request_json['question'].strip()

    if not user_query:
        return https_fn.Response(body="Please ask a question.", status=200, headers=headers)

    # --- Layer 1: Conversational Greetings ---
    greetings = {'hi', 'hello', 'hey', 'hy', 'greetings', 'yo'}
    thanks = {'thanks', 'thank you', 'thx'}
    
    # Use regex to check for simple greetings, ignoring punctuation
    if re.fullmatch(r"[\w\s]*\b(" + "|".join(greetings) + r")\b[\w\s]*!?", user_query.lower()):
        return https_fn.Response("Hello! How can I assist you with IST today?", status=200, headers=headers)
    if re.fullmatch(r"[\w\s]*\b(" + "|".join(thanks) + r")\b[\w\s]*!?", user_query.lower()):
        return https_fn.Response("You're welcome! Is there anything else I can help with?", status=200, headers=headers)

    # --- Layer 2: Semantic Search ---
    try:
        if not knowledge_base:
            raise RuntimeError("Knowledge base is not loaded.")

        query_embedding = model.encode([user_query])[0]
        db_embeddings = [doc['embedding'] for doc in knowledge_base]
        
        similarities = cosine_similarity([query_embedding], db_embeddings)[0]
        best_match_index = np.argmax(similarities)
        best_match_score = similarities[best_match_index]

        best_match_answer = "I'm sorry, I don't seem to have the answer to that. Please try rephrasing your question or visit the official IST website for more information."

        if best_match_score > 0.60: # Confidence threshold
            best_match_answer = knowledge_base[best_match_index]['answer']
        
        return https_fn.Response(best_match_answer, status=200, headers=headers)

    except Exception as e:
        print(f"An error occurred during semantic search: {e}")
        return https_fn.Response("An internal error occurred. Could not process the request.", status=500, headers=headers)
