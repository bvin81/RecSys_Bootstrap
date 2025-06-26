from flask import Flask, render_template, redirect, url_for, session, jsonify
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key')

@app.route('/')
def index():
    """Főoldal - Egyszerű verzió"""
    return """
    <html>
    <head>
        <title>GreenRec - Környezettudatos Receptek</title>
        <style>
            body { font-family: Arial; margin: 50px; background: linear-gradient(135deg, #e8f5e8, #c8e6c9); }
            .container { max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 15px; }
            .btn { background: #4caf50; color: white; padding: 15px 30px; border: none; border-radius: 5px; cursor: pointer; }
            .btn:hover { background: #45a049; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🌱 GreenRec</h1>
            <h2>Környezettudatos Recept Ajánlórendszer</h2>
            <p>Az alkalmazás hamarosan elérhető lesz!</p>
            <p>A/B/C teszt verzió építés alatt...</p>
            <button class="btn" onclick="window.location.reload()">Frissítés</button>
        </div>
    </body>
    </html>
    """

@app.route('/health')
def health():
    """Health check"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'message': 'GreenRec basic version running'
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
