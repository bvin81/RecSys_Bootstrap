# app.py - GreenRec Minimal Version
from flask import Flask, render_template_string, request, session
import json
import pandas as pd
import hashlib

app = Flask(__name__)
app.secret_key = 'greenrec-secret-key'

# Globális változók
recipes_df = None

def load_json_data():
    """JSON adatok betöltése"""
    global recipes_df
    try:
        with open('greenrec_dataset.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        recipes_data = data.get('recipes', [])
        recipes_df = pd.DataFrame(recipes_data)
        print(f"✅ {len(recipes_df)} recept betöltve")
        return True
    except Exception as e:
        print(f"❌ Hiba: {e}")
        return False

@app.route('/')
def home():
    """Főoldal"""
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>GreenRec</title>
        <meta charset="UTF-8">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body>
        <div class="container mt-4">
            <h1>🍃 GreenRec</h1>
            <p>Fenntartható receptajánló rendszer</p>
            
            <form method="POST" action="/search">
                <div class="input-group mb-3">
                    <input type="text" name="query" class="form-control" 
                           placeholder="Keresés... pl: paradicsom mozzarella">
                    <button class="btn btn-success" type="submit">Keresés</button>
                </div>
            </form>
            
            <p><strong>Státusz:</strong> {{ 'Adatok betöltve' if recipes_loaded else 'Adatok betöltése...' }}</p>
        </div>
    </body>
    </html>
    """, recipes_loaded=(recipes_df is not None))

@app.route('/search', methods=['POST'])
def search():
    """Egyszerű keresés"""
    query = request.form.get('query', '')
    
    if recipes_df is None:
        return "Adatok nem elérhetők"
    
    # Egyszerű szűrés
    results = recipes_df[recipes_df['ingredients'].str.contains(query, case=False, na=False)]
    
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Keresési Eredmények</title>
        <meta charset="UTF-8">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body>
        <div class="container mt-4">
            <h2>Keresési eredmények: "{{ query }}"</h2>
            
            {% for _, recipe in results.iterrows() %}
            <div class="card mb-3">
                <div class="card-body">
                    <h5>{{ recipe['title'] }}</h5>
                    <p>Összetevők: {{ recipe['ingredients'] }}</p>
                </div>
            </div>
            {% endfor %}
            
            <a href="/" class="btn btn-primary">Vissza</a>
        </div>
    </body>
    </html>
    """, query=query, results=results)

if __name__ == '__main__':
    load_json_data()
    app.run(host='0.0.0.0', port=5000, debug=True)
