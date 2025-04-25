import os
import requests
from flask import Flask, render_template, request, make_response, redirect, url_for, flash, jsonify
from dotenv import load_dotenv
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'devsecret')
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# API Configuration
APIS = {
    'newsapi': {
        'url': 'https://newsapi.org/v2/top-headlines',
        'key': os.getenv('NEWSAPI_KEY')
    },
    'gnews': {
        'url': 'https://gnews.io/api/v4/top-headlines',
        'key': os.getenv('GNEWS_KEY')
    }
}

# Database Models
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

# Helper Functions
def get_newsapi_sources():
    try:
        response = requests.get(
            "https://newsapi.org/v2/top-headlines/sources",
            params={'country': 'us', 'apiKey': APIS['newsapi']['key']}
        )
        data = response.json()
        return data.get('sources', [])
    except Exception as e:
        print("Error fetching sources:", str(e))
        return []

def fetch_news(api_name, params):
    config = APIS[api_name]
    try:
        final_params = params.copy()
        if api_name == 'newsapi':
            final_params['apiKey'] = config['key']
        elif api_name == 'gnews':
            final_params['apikey'] = config['key']
        response = requests.get(config['url'], params=final_params)
        data = response.json()
        return data.get('articles', [])
    except Exception as e:
        print(f"Error fetching from {api_name}: {str(e)}")
        return []

# Routes
@app.route('/')
def home():
    source = request.args.get('source', 'all')
    category = request.args.get('category', 'general')
    query = request.args.get('q', '').strip()

    sources_list = get_newsapi_sources()
    all_sources = sorted(sources_list, key=lambda x: x['name'])
    all_categories = sorted({src['category'] for src in sources_list})

    # Build API parameters
    articles = []
    newsapi_params = {}
    if source != 'all':
        newsapi_params['sources'] = source
    else:
        newsapi_params['country'] = 'us'
        if category != 'general':
            newsapi_params['category'] = category
    if query:
        newsapi_params['q'] = query
    newsapi_params = {k: v for k, v in newsapi_params.items() if v is not None}

    gnews_params = {'lang': 'en'}
    if query:
        gnews_params['q'] = query
    else:
        if category != 'general':
            gnews_params['topic'] = category

    articles += fetch_news('newsapi', newsapi_params)
    articles += fetch_news('gnews', gnews_params)

    # Clean invalid favorites
    user_favorites = []
    if current_user.is_authenticated:
        user_favorites = [fav for fav in current_user.favorites if fav.source or fav.category]

    return render_template(
        'home.html',
        articles=articles,
        sources=all_sources,
        categories=all_categories,
        user_favorites=user_favorites
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
    return render_template('register.html')

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
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

from flask import render_template

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

    # This is crucial: render the updated favorites list partial!
    user_favorites = [fav for fav in current_user.favorites if fav.source or fav.category]
    favorites_html = render_template('favorites_list.html', user_favorites=user_favorites)
    return jsonify({'status': status, 'favorites_html': favorites_html})

# Initialize DB
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)
