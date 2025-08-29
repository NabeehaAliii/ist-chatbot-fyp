// The firebaseConfig object is loaded from the separate config.js file

// Initialize Firebase
firebase.initializeApp(firebaseConfig);
const db = firebase.firestore(); // Get a reference to the Firestore database

// --- DOM Element References ---
const chatMessages = document.getElementById('chat-messages');
const chatInput = document.getElementById('chat-input');
const sendButton = document.getElementById('send-button');

// --- Event Listeners ---
sendButton.addEventListener('click', sendMessage);
chatInput.addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
        sendMessage();
    }
});

/**
 * Handles sending a message from the user.
 */
function sendMessage() {
    const messageText = chatInput.value.trim();
    if (messageText === '') return;

    addMessage(messageText, 'user-message');
    chatInput.value = '';
    chatInput.disabled = true;
    sendButton.disabled = true;

    showTypingIndicator();
    getBotResponse(messageText); // Get response from Firebase
}

/**
 * Creates and appends a message bubble to the chat window.
 * @param {string} text - The message content.
 * @param {string} className - The CSS class for styling ('user-message' or 'bot-message').
 */
function addMessage(text, className) {
    const messageDiv = document.createElement('div');
    messageDiv.classList.add('message', className);
    messageDiv.textContent = text;
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

/**
 * Displays the typing indicator.
 */
function showTypingIndicator() {
    const indicatorDiv = document.createElement('div');
    indicatorDiv.classList.add('message', 'bot-message', 'typing-indicator');
    indicatorDiv.innerHTML = '<span></span><span></span><span></span>';
    indicatorDiv.id = 'typing-indicator';
    chatMessages.appendChild(indicatorDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

/**
 * Removes the typing indicator.
 */
function hideTypingIndicator() {
    const indicator = document.getElementById('typing-indicator');
    if (indicator) {
        indicator.remove();
    }
}

/**
 * Finds the BEST bot response by querying Firestore and scoring the results.
 * @param {string} userText - The user's original message.
 */
async function getBotResponse(userText) {
    const defaultResponse = "I'm sorry, I don't have the answer to that. Please try asking in a different way or visit the official IST website for more information.";
    
    // List of common "stop words" to ignore
    const stopWords = new Set(['i','me','my','myself','we','our','ours','ourselves','you','your','yours','yourself','yourselves','he','him','his','himself','she','her','hers','herself','it','its','itself','they','them','their','theirs','themselves','what','which','who','whom','this','that','these','those','am','is','are','was','were','be','been','being','have','has','had','having','do','does','did','doing','a','an','the','and','but','if','or','because','as','until','while','of','at','by','for','with','about','against','between','into','through','during','before','after','above','below','to','from','up','down','in','out','on','off','over','under','again','further','then','once','here','there','when','where','why','how','all','any','both','each','few','more','most','other','some','such','no','nor','not','only','own','same','so','than','too','very','s','t','can','will','just','don','should','now']);

    // 1. Convert user's message to lowercase keywords and filter out stop words
    const allWords = userText.toLowerCase().match(/\b(\w+)\b/g) || [];
    const userKeywords = allWords.filter(word => !stopWords.has(word));
    const limitedKeywords = userKeywords.slice(0, 10);

    if (limitedKeywords.length === 0) {
        hideTypingIndicator();
        addMessage(defaultResponse, 'bot-message');
        // Re-enable input
        chatInput.disabled = false;
        sendButton.disabled = false;
        chatInput.focus();
        return;
    }
    
    try {
        // 2. Query Firestore to find all possible matches
        const q = db.collection('qna').where('keywords', 'array-contains-any', limitedKeywords);
        const querySnapshot = await q.get();

        hideTypingIndicator();

        if (querySnapshot.empty) {
            addMessage(defaultResponse, 'bot-message');
        } else {
            // --- Scoring Logic to find the BEST match ---
            let bestMatch = { score: 0, answer: defaultResponse };

            querySnapshot.forEach(doc => {
                const docData = doc.data();
                let currentScore = 0;
                // Calculate score based on how many keywords match
                docData.keywords.forEach(keyword => {
                    if (limitedKeywords.includes(keyword)) {
                        currentScore++;
                    }
                });

                // If this document has a better score, it's our new best match
                if (currentScore > bestMatch.score) {
                    bestMatch = { score: currentScore, answer: docData.answer };
                }
            });
            
            addMessage(bestMatch.answer, 'bot-message');
        }
    } catch (error) {
        console.error("Error querying Firestore:", error);
        hideTypingIndicator();
        addMessage("Sorry, I'm having trouble connecting to my knowledge base right now.", 'bot-message');
    } finally {
        // Re-enable the input field
        chatInput.disabled = false;
        sendButton.disabled = false;
        chatInput.focus();
    }
}
