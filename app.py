from flask import Flask, render_template_string, request, jsonify, session, redirect, url_for
import random
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'greenrec-secret-key-2025'

# Konfiguráció
LEARNING_ROUNDS = 3
RECOMMENDATION_COUNT = 5

# Egyszerű recept adatok
RECIPES = [
    {'id': '1', 'name': 'Magyar Gulyás', 'HSI': 75, 'ESI': 45, 'PPI': 85, 'score': 72},
    {'id': '2', 'name': 'Vegán Buddha Bowl', 'HSI': 90, 'ESI': 85, 'PPI': 70, 'score': 85},
    {'id': '3', 'name': 'Grillezett Csirke', 'HSI': 85, 'ESI': 60, 'PPI': 80, 'score': 75},
    {'id': '4', 'name': 'Mediterrán Saláta', 'HSI': 80, 'ESI': 90, 'PPI': 65, 'score': 82},
    {'id': '5', 'name': 'Lencsecurry', 'HSI': 85, 'ESI': 95, 'PPI': 90, 'score': 90},
    {'id': '6', 'name': 'Sütőtökös Rizottó', 'HSI': 70, 'ESI': 75, 'PPI': 75, 'score': 73}
]

def init_user():
    if 'user_id' not in session:
        session['user_id'] = f"user_{random.randint(1000, 9999)}"
        session['user_group'] = random.choice(['A', 'B', 'C'])
        session['round'] = 1
        session['ratings'] = {}
    return session['user_id'], session['user_group'], session['round']

@app.route('/')
def index():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>GreenRec</title>
        <meta charset="UTF-8">
        <style>
            body { font-family: Arial; background: linear-gradient(135deg, #e8f5e8, #c8e6c9); margin: 0; padding: 50px; }
            .container { max-width: 600px; margin: 0 auto; background: white; padding: 40px; border-radius: 20px; text-align: center; }
            h1 { color: #2d5a27; font-size: 2.5em; }
            .btn { background: #4caf50; color: white; border: none; padding: 15px 30px; border-radius: 25px; font-size: 1.1em; cursor: pointer; }
            .btn:hover { background: #45a049; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🌱 GreenRec</h1>
            <h2>Környezettudatos Recept Ajánlórendszer</h2>
            <p>AI-alapú A/B/C teszt • 3 gyors kör • 5 perc</p>
            <br>
            <a href="/study" class="btn">🚀 Tanulmány Indítása</a>
        </div>
    </body>
    </html>
    """
    return html

@app.route('/study')
def study():
    user_id, user_group, round_num = init_user()
    
    if round_num > LEARNING_ROUNDS:
        return redirect('/results')
    
    # Ajánlások generálása
    if user_group == 'A':
        recipes = random.sample(RECIPES, 5)
    elif user_group == 'B':
        recipes = sorted(RECIPES, key=lambda x: x['score'], reverse=True)[:5]
    else:
        recipes = sorted(RECIPES, key=lambda x: x['score'], reverse=True)[:3] + random.sample(RECIPES, 2)
    
    # Template készítése
    recipe_cards = ""
    for recipe in recipes:
        show_scores = user_group in ['B', 'C']
        
        scores_html = ""
        if show_scores:
            scores_html = f"""
            <div style="margin: 10px 0;">
                <span style="background: #ff9800; color: white; padding: 5px 10px; border-radius: 10px; margin: 2px;">💚 {recipe['HSI']}</span>
                <span style="background: #26a69a; color: white; padding: 5px 10px; border-radius: 10px; margin: 2px;">🌍 {recipe['ESI']}</span>
                <span style="background: #9c27b0; color: white; padding: 5px 10px; border-radius: 10px; margin: 2px;">👤 {recipe['PPI']}</span>
            </div>
            """
        
        recipe_cards += f"""
        <div style="background: white; border-radius: 15px; padding: 20px; margin: 20px 0; box-shadow: 0 4px 15px rgba(0,0,0,0.1);">
            <h3 style="color: #2d5a27;">{recipe['name']}</h3>
            <div style="height: 150px; background: linear-gradient(45deg, #e8f5e8, #c8e6c9); border-radius: 10px; display: flex; align-items: center; justify-content: center; margin: 15px 0;">
                <span style="font-size: 3em;">🍽️</span>
            </div>
            {scores_html}
            <div style="margin: 15px 0;">
                <p>Mennyire tetszik ez a recept?</p>
                <div class="rating" data-recipe="{recipe['id']}">
                    <span class="star" data-rating="1">⭐</span>
                    <span class="star" data-rating="2">⭐</span>
                    <span class="star" data-rating="3">⭐</span>
                    <span class="star" data-rating="4">⭐</span>
                    <span class="star" data-rating="5">⭐</span>
                </div>
                <button class="rate-btn" data-recipe="{recipe['id']}" disabled>Értékelés Mentése</button>
            </div>
        </div>
        """
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>GreenRec - {round_num}. Kör</title>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial; background: linear-gradient(135deg, #e8f5e8, #c8e6c9); margin: 0; padding: 20px; }}
            .container {{ max-width: 800px; margin: 0 auto; }}
            .header {{ background: linear-gradient(135deg, #2d5a27, #4caf50); color: white; padding: 20px; border-radius: 15px; text-align: center; margin-bottom: 20px; }}
            .star {{ font-size: 1.5em; cursor: pointer; margin: 2px; }}
            .star:hover {{ transform: scale(1.2); }}
            .rate-btn {{ background: #4caf50; color: white; border: none; padding: 10px 20px; border-radius: 15px; cursor: pointer; margin-top: 10px; }}
            .rate-btn:disabled {{ background: #ccc; cursor: not-allowed; }}
            .next-btn {{ background: #2d5a27; color: white; border: none; padding: 15px 30px; border-radius: 25px; font-size: 1.1em; cursor: pointer; margin: 20px; }}
            #next-section {{ display: none; text-align: center; background: white; padding: 30px; border-radius: 15px; margin-top: 30px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🌱 GreenRec Tanulmány</h1>
                <p>{round_num}. kör a {LEARNING_ROUNDS}-ból • {user_group} Csoport • {user_id}</p>
            </div>
            
            {recipe_cards}
            
            <div id="next-section">
                <h3>Kör befejezve!</h3>
                <button class="next-btn" onclick="window.location.href='/next'">Következő Kör</button>
            </div>
        </div>
        
        <script>
            let ratedCount = 0;
            const totalRecipes = {len(recipes)};
            
            document.querySelectorAll('.star').forEach(star => {{
                star.addEventListener('click', function() {{
                    const rating = this.dataset.rating;
                    const recipeId = this.parentElement.dataset.recipe;
                    const btn = document.querySelector(`button[data-recipe="${{recipeId}}"]`);
                    
                    // Highlight stars
                    const stars = this.parentElement.querySelectorAll('.star');
                    stars.forEach((s, i) => {{
                        s.style.color = i < rating ? '#ffc107' : '#ddd';
                    }});
                    
                    btn.disabled = false;
                    btn.textContent = `Mentés (${rating} csillag)`;
                    btn.onclick = () => rateRecipe(recipeId, rating, btn);
                }});
            }});
            
            function rateRecipe(recipeId, rating, btn) {{
                fetch('/rate', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{recipe_id: recipeId, rating: rating}})
                }})
                .then(response => response.json())
                .then(data => {{
                    if (data.success) {{
                        btn.textContent = `✓ Elmentve (${rating} csillag)`;
                        btn.style.background = '#4caf50';
                        btn.disabled = true;
                        
                        ratedCount++;
                        if (ratedCount >= totalRecipes) {{
                            document.getElementById('next-section').style.display = 'block';
                        }}
                    }}
                }});
            }}
        </script>
    </body>
    </html>
    """
    return html

@app.route('/rate', methods=['POST'])
def rate():
    data = request.get_json()
    recipe_id = data.get('recipe_id')
    rating = int(data.get('rating'))
    
    if 'ratings' not in session:
        session['ratings'] = {}
    
    session['ratings'][recipe_id] = rating
    session.permanent = True
    
    return jsonify({'success': True})

@app.route('/next')
def next_round():
    session['round'] = session.get('round', 1) + 1
    session.permanent = True
    
    if session['round'] > LEARNING_ROUNDS:
        return redirect('/results')
    
    return redirect('/study')

@app.route('/results')
def results():
    user_id = session.get('user_id', 'Unknown')
    user_group = session.get('user_group', 'Unknown')
    ratings = session.get('ratings', {})
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>GreenRec - Eredmények</title>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial; background: linear-gradient(135deg, #e8f5e8, #c8e6c9); margin: 0; padding: 50px; }}
            .container {{ max-width: 600px; margin: 0 auto; background: white; padding: 40px; border-radius: 20px; text-align: center; }}
            h1 {{ color: #2d5a27; }}
            .btn {{ background: #4caf50; color: white; border: none; padding: 15px 30px; border-radius: 25px; cursor: pointer; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎉 Köszönjük!</h1>
            <h2>Tanulmány befejezve</h2>
            <p><strong>Felhasználó:</strong> {user_id}</p>
            <p><strong>Csoport:</strong> {user_group}</p>
            <p><strong>Értékelések:</strong> {len(ratings)}</p>
            <br>
            <a href="/" class="btn">Vissza a főoldalra</a>
        </div>
    </body>
    </html>
    """
    return html

@app.route('/health')
def health():
    return "OK"

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
