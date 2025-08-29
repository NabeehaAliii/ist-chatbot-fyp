#
#  IST Chatbot FYP - Semantic Search Cloud Function
#  ------------------------------------------------
#  This is the main Python code for the backend "brain" of the chatbot.
#  It's designed to be deployed as a Google Cloud Function.
#

import functions_framework
from flask import jsonify, make_response
from firebase_admin import initialize_app, firestore
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import re

# --- GLOBAL VARIABLES (INITIALIZED ONCE) ---

# Initialize Firebase Admin SDK.
# The credentials will be automatically handled by the Google Cloud environment.
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
        # Ensure the document has an 'embedding' field
        if 'embedding' in doc_data and doc_data['embedding']:
             knowledge_base.append(doc_data)
    print(f"Knowledge base fetched successfully. {len(knowledge_base)} documents loaded.")
except Exception as e:
    print(f"Error fetching knowledge base: {e}")


# --- MAIN CLOUD FUNCTION ---

@functions_framework.http
def find_answer(request):
    """
    HTTP Cloud Function that receives a user's question and returns the best answer.
    """
    # Set CORS headers to allow requests from any origin (your chatbot widget)
    if request.method == 'OPTIONS':
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Max-Age': '3600'
        }
        return ('', 204, headers)

    headers = {'Access-Control-Allow-Origin': '*'}

    # Get the user's question from the request body
    request_json = request.get_json(silent=True)
    if not request_json or 'question' not in request_json:
        return (jsonify({"error": "Invalid request. 'question' field is missing."}), 400, headers)

    user_query = request_json['question'].strip()

    if not user_query:
        return (jsonify({"answer": "Please ask a question."}), 200, headers)

    # --- Layer 1: Conversational Greetings ---
    greetings = {'hi', 'hello', 'hey', 'hy', 'greetings', 'yo'}
    thanks = {'thanks', 'thank you', 'thx'}

    # Use regex to check for simple greetings, ignoring punctuation
    if re.fullmatch(r"[\w\s]*\b(" + "|".join(greetings) + r")\b[\w\s]*!?", user_query.lower()):
        return (jsonify({"answer": "Hello! How can I assist you with IST today?"}), 200, headers)
    if re.fullmatch(r"[\w\s]*\b(" + "|".join(thanks) + r")\b[\w\s]*!?", user_query.lower()):
        return (jsonify({"answer": "You're welcome! Is there anything else I can help with?"}), 200, headers)


    # --- Layer 2: Semantic Search ---
    try:
        if not knowledge_base:
             # Fallback if the knowledge base failed to load on startup
            raise RuntimeError("Knowledge base is not loaded.")

        # 1. Create an embedding for the user's query
        query_embedding = model.encode([user_query])[0]

        # 2. Compare the query embedding with all embeddings in the knowledge base
        best_match_score = -1
        best_match_answer = "I'm sorry, I don't seem to have the answer to that. Please try rephrasing your question or visit the official IST website for more information."

        # Extract the list of embeddings from our in-memory knowledge base
        db_embeddings = [doc['embedding'] for doc in knowledge_base]
        
        # Calculate cosine similarity between the user's query and all DB questions
        similarities = cosine_similarity([query_embedding], db_embeddings)[0]
        
        # Find the index of the highest similarity score
        best_match_index = np.argmax(similarities)
        best_match_score = similarities[best_match_index]

        # 3. If a good match is found, return the corresponding answer
        # The threshold (0.60) can be adjusted to make the bot more or less strict.
        if best_match_score > 0.60:
            best_match_answer = knowledge_base[best_match_index]['answer']
        
        return (jsonify({"answer": best_match_answer}), 200, headers)

    except Exception as e:
        print(f"An error occurred during semantic search: {e}")
        return (jsonify({"error": "An internal error occurred. Could not process the request."}), 500, headers)
