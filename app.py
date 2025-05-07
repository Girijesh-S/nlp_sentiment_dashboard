from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from scipy.special import softmax
import torch
from functools import wraps
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY') or 'dev-secret-key'

# Company Configuration
app.config['COMPANY_NAME'] = "HRC Ltd"
app.config['COMPANY_EMAIL'] = "HRC@gmail.com"
app.config['COMPANY_PHONE'] = "923312334"
app.config['ADMIN_CREDENTIALS'] = {
    'Girijesh': 'Giri123',
    'Hari': 'Hari123'
}

# Model Configuration
MODEL = "cardiffnlp/twitter-roberta-base-sentiment"
tokenizer = AutoTokenizer.from_pretrained(MODEL)
model = AutoModelForSequenceClassification.from_pretrained(MODEL)
labels = ['Negative', 'Neutral', 'Positive']

# Data Storage
feedback_store = []

def analyze_sentiment(text):
    encoded_input = tokenizer(text, return_tensors='pt', truncation=True, max_length=128)
    with torch.no_grad():
        output = model(**encoded_input)
    scores = output.logits[0].numpy()
    probs = softmax(scores)
    
    # Force "excellent" feedback to be positive
    if "excellent" in text.lower():
        return {'Negative': 0.0, 'Neutral': 0.0, 'Positive': 1.0}
    
    return {label: float(prob) for label, prob in zip(labels, probs)}

def get_customer_response(sentiment, text):
    # Special case for "excellent" feedback
    if "excellent" in text.lower():
        return {
            'title': 'Thank You!',
            'message': 'We truly appreciate your excellent feedback!',
            'type': 'success',
            'icon': 'fa-grin-stars'  # Special icon for excellent feedback
        }
    
    responses = {
        'Positive': {
            'title': 'Thank You!',
            'message': 'We appreciate your positive feedback! Have a wonderful day.',
            'type': 'success',
            'icon': 'fa-smile'
        },
        'Neutral': {
            'title': 'Thanks for Your Feedback',
            'message': f'We value your input. For any questions, contact us at {app.config["COMPANY_EMAIL"]} or {app.config["COMPANY_PHONE"]}',
            'type': 'info',
            'icon': 'fa-meh'
        },
        'Negative': {
            'title': 'We Apologize',
            'message': f'Please contact us at {app.config["COMPANY_EMAIL"]} or call {app.config["COMPANY_PHONE"]} so we can make it right',
            'type': 'error',
            'icon': 'fa-frown'
        }
    }
    return responses.get(sentiment)

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def home():
    return render_template('index.html', company=app.config['COMPANY_NAME'])

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username in app.config['ADMIN_CREDENTIALS'] and app.config['ADMIN_CREDENTIALS'][username] == password:
            session['logged_in'] = True
            session['username'] = username
            return redirect(url_for('admin_dashboard'))
        return render_template('login.html', error="Invalid credentials", company=app.config['COMPANY_NAME'])
    return render_template('login.html', company=app.config['COMPANY_NAME'])

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        data = request.json
        required_fields = ['product', 'customer', 'date', 'feedback']
        if not all(field in data for field in required_fields):
            return jsonify({'error': 'Missing required fields'}), 400

        probs = analyze_sentiment(data['feedback'])
        sentiment = max(probs, key=probs.get)
        
        response = get_customer_response(sentiment, data['feedback'])
        
        entry = {
            'product': data['product'],
            'customer': data['customer'],
            'date': data['date'],
            'feedback': data['feedback'],
            'sentiment': sentiment,
            'scores': probs,
            'timestamp': datetime.now().isoformat()
        }
        feedback_store.append(entry)

        return jsonify({
            'sentiment': sentiment,
            'response': response,
            'scores': probs
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin')
@login_required
def admin_dashboard():
    counts = {label: 0 for label in labels}
    for entry in feedback_store:
        counts[entry['sentiment']] += 1
    
    # Get current time for display
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    return render_template('dashboard.html',
                         counts=counts,
                         feedback=feedback_store[-10:][::-1],
                         company=app.config['COMPANY_NAME'],
                         username=session.get('username'),
                         current_time=current_time)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
