import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from pygooglenews import GoogleNews
import feedparser
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# User Model
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

# Saved Article Model
class SavedArticle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    image = db.Column(db.String(500))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def fetch_google_news(query=None):
    try:
        gn = GoogleNews(lang='en', country='US')
        results = gn.search(query) if query else gn.top_news()
        return [{
            'title': entry.title,
            'url': entry.link,
            'description': entry.description,
            'source': getattr(entry, 'source', {}).get('title', 'Google News'),
            'image': None
        } for entry in results['entries']]
    except Exception as e:
        print(f"Google News error: {e}")
        return []

def fetch_custom_rss(url):
    try:
        feed = feedparser.parse(url)
        return [{
            'title': entry.title,
            'url': entry.link,
            'description': entry.description,
            'source': feed.feed.title,
            'image': None
        } for entry in feed.entries]
    except Exception as e:
        print(f"RSS error ({url}): {e}")
        return []

def fetch_hybrid_news(query=None):
    articles = []
    
    # Google News (general)
    articles += fetch_google_news(query)
    
    # Newscatcher (specific sources)
    articles += fetch_newscatcher('reuters.com')
    articles += fetch_newscatcher('theverge.com')
    
    # Custom RSS feeds
    articles += fetch_custom_rss('http://feeds.bbci.co.uk/news/technology/rss.xml')
    
    # Remove duplicates
    seen = set()
    return [article for article in articles 
            if not (article['url'] in seen or seen.add(article['url']))]

@app.route('/')
def home():
    query = request.args.get('q')
    articles = fetch_hybrid_news(query)
    return render_template('home.html', 
                         articles=articles, 
                         search_query=query or "")

# Keep your existing auth routes and save functionality
# [Register, Login, Logout, Save Article routes here...]

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
