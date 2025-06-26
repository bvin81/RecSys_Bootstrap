from flask import Flask, render_template_string

app = Flask(__name__)
app.secret_key = 'greenrec-secret-key'

# Szép HTML template
HOME_TEMPLATE = """
<!DOCTYPE html>
<html lang="hu">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GreenRec - Környezettudatos Receptek</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #e8f5e8 0%, #c8e6c9 100%);
            margin: 0;
            padding: 20px;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .container {
            max-width: 600px;
            background: white;
            padding: 40px;
            border-radius: 15px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.1);
            text-align: center;
        }
        h1 {
            color: #2d5a27;
            margin-bottom: 20px;
            font-size: 2.5em;
        }
        .subtitle {
            color: #666;
            margin-bottom: 30px;
            font-size: 1.2em;
        }
        .btn {
            background: linear-gradient(135deg, #4caf50, #2d5a27);
            color: white;
            border: none;
            padding: 15px 30px;
            border-radius: 25px;
            font-size: 1.1em;
            cursor: pointer;
            transition: transform 0.3s ease;
            margin: 10px;
        }
        .btn:hover {
            transform: translateY(-2px);
        }
        .feature {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 10px;
            margin: 20px 0;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🌱 GreenRec</h1>
        <p class="subtitle">Környezettudatos Recept Ajánlórendszer</p>
        
        <div class="feature">
            <h3>🔬 AI-alapú Kutatás</h3>
            <p>Vegyen részt egy innovatív A/B/C tesztben!</p>
        </div>
        
        <div class="feature">
            <h3>📊 Fenntarthatósági Metrikák</h3>
            <p>ESI • HSI • PPI pontszámok alapján</p>
        </div>
        
        <button class="btn" onclick="startStudy()">🚀 Tanulmány Indítása</button>
        <button class="btn" onclick="viewAnalytics()">📊 Eredmények</button>
        
        <p style="margin-top: 30px; color: #888; font-size: 0.9em;">
            5 percet vesz igénybe • Segítsen a fenntartható jövő építésében
        </p>
    </div>
    
    <script>
        function startStudy() {
            alert('A tanulmány funkció hamarosan elérhető lesz!');
        }
        function viewAnalytics() {
            alert('Az analytics funkció fejlesztés alatt!');
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HOME_TEMPLATE)

@app.route('/health')
def health():
    return {"status": "healthy", "version": "1.0"}

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
