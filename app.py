from datetime import datetime
import os
import requests
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from dotenv import load_dotenv
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'devsecret')
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

APIS = {
    'thenewsapi': {
        'url': 'https://api.thenewsapi.com/v1/news/top',
        'key': os.getenv('THENEWSAPI_KEY')
    },
    'gnews': {
        'url': 'https://gnews.io/api/v4/top-headlines',
        'key': os.getenv('GNEWS_KEY')
    }
}

ALL_CATEGORIES = [
    'business', 'entertainment', 'health', 
    'science', 'sports', 'technology', 'general'
]

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)
    favorites = db.relationship('Favorite', backref='user', lazy=True)

class Favorite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    source = db.Column(db.String(50))
    category = db.Column(db.String(50))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def fetch_news(api_name, params):
    config = APIS[api_name]
    try:
        final_params = params.copy()
        if api_name == 'thenewsapi':
            final_params['api_token'] = config['key']
        elif api_name == 'gnews':
            final_params['apikey'] = config['key']

        response = requests.get(config['url'], params=final_params)
        data = response.json()
        if api_name == 'thenewsapi':
            return data.get('data', [])
        return data.get('articles', [])
    except Exception as e:
        print(f"Error fetching from {api_name}: {str(e)}")
        return []

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/')
def home():
    category = request.args.get('category', 'general')
    query = request.args.get('q', '').strip()
    source = request.args.get('source', 'all')

    # TheNewsAPI params
    thenewsapi_params = {
        'locale': 'us',
        'categories': category if category != 'general' else None,
        'search': query,
        'limit': 20
    }
    if source != 'all':
        thenewsapi_params['sources'] = source
    thenewsapi_params = {k: v for k, v in thenewsapi_params.items() if v is not None}

    # GNews params
    gnews_params = {
        'lang': 'en',
        'country': 'us',
        'topic': category if category != 'general' else None,
        'q': query,
        'max': 10
    }
    gnews_params = {k: v for k, v in gnews_params.items() if v is not None}

    articles = []
    articles += fetch_news('thenewsapi', thenewsapi_params)
    articles += fetch_news('gnews', gnews_params)

    # --- Build unique sources list from articles ---
    sources_in_results = sorted({
        # TheNewsAPI: 'source' is a string (domain)
        article['source'] if isinstance(article.get('source'), str) else (
            article['source'].get('name') if article.get('source') and isinstance(article['source'], dict) else None
        )
        for article in articles
        if article.get('source')
    })
    sources_in_results = [src for src in sources_in_results if src]

    user_favorites = []
    if current_user.is_authenticated:
        user_favorites = [fav for fav in current_user.favorites if fav.source or fav.category]

    return render_template(
        'home.html',
        articles=articles,
        categories=ALL_CATEGORIES,
        sources=sources_in_results,
        user_favorites=user_favorites,
        year=datetime.now().year
    )

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if User.query.filter_by(username=username).first():
            flash('Username already exists. Please choose another.')
            return redirect(url_for('register'))
        hashed_password = generate_password_hash(password)
        user = User(username=username, password=hashed_password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return redirect(url_for('home'))
    return render_template('register.html', year=datetime.now().year)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('home'))
        else:
            flash('Login failed. Check your username and password.')
    return render_template('login.html', year=datetime.now().year)

@app.route('/favorite', methods=['POST'])
@login_required
def favorite():
    source = request.form.get('source')
    category = request.form.get('category')
    if not source and not category:
        return jsonify({'status': 'error', 'message': 'No source/category provided'})

    existing_fav = Favorite.query.filter_by(
        user_id=current_user.id,
        source=source,
        category=category
    ).first()

    if existing_fav:
        db.session.delete(existing_fav)
        db.session.commit()
        status = 'removed'
    else:
        fav = Favorite(user_id=current_user.id, source=source, category=category)
        db.session.add(fav)
        db.session.commit()
        status = 'added'

    user_favorites = [fav for fav in current_user.favorites if fav.source or fav.category]
    favorites_html = render_template('favorites_list.html', user_favorites=user_favorites)
    return jsonify({'status': status, 'favorites_html': favorites_html})

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)
