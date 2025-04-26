import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import requests

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-default-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# --- Custom Categories for Pills UI ---
CUSTOM_CATEGORIES = {
    "technology": {"thenewsapi": "technology", "gnews": "technology", "keywords": ["tech", "ai", "innovation"]},
    "video-games": {"thenewsapi": "gaming", "gnews": None, "keywords": ["gaming", "video games", "esports"]},
    "politics": {"thenewsapi": "politics", "gnews": "world", "keywords": ["politics", "election"]},
    "economy": {"thenewsapi": "business", "gnews": "business", "keywords": ["economy", "markets"]},
    "stock-market": {"thenewsapi": "finance", "gnews": "business", "keywords": ["stocks", "wall street"]},
    "science": {"thenewsapi": "science", "gnews": "science", "keywords": ["space", "physics", "biology"]},
    "sports": {"thenewsapi": "sports", "gnews": "sports", "keywords": ["sports", "football", "basketball"]},
    "general": {"thenewsapi": "general", "gnews": "general", "keywords": []}
}

# --- Database Models ---
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    saved_articles = db.relationship('SavedArticle', backref='user', lazy=True)

    @property
    def password(self):
        raise AttributeError('Password is write-only.')

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

class SavedArticle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    image = db.Column(db.String(500))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- News Fetching Functions ---
def fetch_thenewsapi_articles(api_key, category=None, query=None):
    url = "https://api.thenewsapi.com/v1/news/all"
    params = {
        "api_token": api_key,
        "language": "en",
        "country": "us",
        "limit": 20
    }
    if category and category in CUSTOM_CATEGORIES:
        params["categories"] = CUSTOM_CATEGORIES[category]["thenewsapi"]
    if query:
        params["search"] = query
    resp = requests.get(url, params=params)
    data = resp.json()
    articles = []
    for item in data.get("data", []):
        articles.append({
            "title": item.get("title"),
            "description": item.get("description"),
            "url": item.get("url"),
            "image": item.get("image_url"),
            "source": item.get("source"),
            "categories": item.get("categories", []),
            "publishedAt": item.get("published_at")
        })
    return articles

def fetch_gnews_articles(api_key, category=None, query=None):
    url = "https://gnews.io/api/v4/top-headlines"
    params = {
        "token": api_key,
        "lang": "en",
        "country": "us",
        "max": 20
    }
    if category and category in CUSTOM_CATEGORIES:
        gnews_cat = CUSTOM_CATEGORIES[category]["gnews"]
        if gnews_cat:
            params["topic"] = gnews_cat
        else:
            params["q"] = " OR ".join(CUSTOM_CATEGORIES[category]["keywords"])
    if query:
        params["q"] = query
    resp = requests.get(url, params=params)
    data = resp.json()
    articles = []
    for item in data.get("articles", []):
        articles.append({
            "title": item.get("title"),
            "description": item.get("description"),
            "url": item.get("url"),
            "image": item.get("image"),
            "source": item.get("source", {}).get("name", "GNews"),
            "categories": [],
            "publishedAt": item.get("publishedAt")
        })
    return articles

def fetch_news(category=None, query=None):
    thenewsapi_key = os.getenv("THENEWSAPI_KEY")
    gnews_key = os.getenv("GNEWS_API_KEY")
    articles = []
    if thenewsapi_key:
        try:
            articles += fetch_thenewsapi_articles(thenewsapi_key, category, query)
        except Exception as e:
            print("TheNewsAPI error:", e)
    if gnews_key:
        try:
            articles += fetch_gnews_articles(gnews_key, category, query)
        except Exception as e:
            print("GNews error:", e)
    articles.sort(key=lambda x: x.get("publishedAt", ""), reverse=True)
    return articles

# --- Routes ---
@app.route('/')
def home():
    selected_category = request.args.get('category', 'general')
    query = request.args.get('q')
    articles = fetch_news(category=selected_category, query=query)
    return render_template(
        'home.html',
        articles=articles,
        categories=CUSTOM_CATEGORIES.keys(),
        selected_category=selected_category,
        search_query=query or ""
    )

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'danger')
            return redirect(url_for('register'))
        user = User(username=username)
        user.password = password
        db.session.add(user)
        db.session.commit()
        flash('Registration successful. Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.verify_password(password):
            login_user(user)
            flash('Logged in successfully.', 'success')
            return redirect(url_for('home'))
        flash('Invalid credentials.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out.', 'info')
    return redirect(url_for('home'))

@app.route('/save_article', methods=['POST'])
@login_required
def save_article():
    article_data = request.get_json()
    if not SavedArticle.query.filter_by(
        user_id=current_user.id,
        url=article_data['url']
    ).first():
        saved = SavedArticle(
            title=article_data['title'],
            url=article_data['url'],
            image=article_data.get('image', ''),
            user_id=current_user.id
        )
        db.session.add(saved)
        db.session.commit()
        return jsonify({'status': 'saved'})
    return jsonify({'status': 'exists'})

@app.route('/saved')
@login_required
def saved():
    saved_articles = current_user.saved_articles
    return render_template('saved.html', articles=saved_articles)

@app.route('/manifest.json')
def manifest():
    return send_from_directory('static', 'manifest.json')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
