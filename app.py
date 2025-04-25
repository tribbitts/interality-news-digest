import os
import requests
from flask import Flask, render_template, request, make_response
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

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

def get_newsapi_sources():
    """Fetch available sources from NewsAPI"""
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
    """Fetch articles from specified API"""
    config = APIS[api_name]
    try:
        # Add API key to params
        final_params = params.copy()
        if api_name == 'newsapi':
            final_params['apiKey'] = config['key']
        elif api_name == 'gnews':
            final_params['apikey'] = config['key']

        print(f"Fetching {api_name.upper()} with params:", final_params)  # Debug
        
        response = requests.get(config['url'], params=final_params)
        data = response.json()
        
        print(f"{api_name.upper()} response:", data)  # Debug
        
        return data.get('articles', [])
    except Exception as e:
        print(f"Error fetching from {api_name}: {str(e)}")
        return []

@app.route('/')
def home():
    # Get filters from request
    source = request.args.get('source', 'all')
    category = request.args.get('category', 'general')
    query = request.args.get('q', '').strip()

    # Get available sources and categories
    sources_list = get_newsapi_sources()
    all_sources = sorted(sources_list, key=lambda x: x['name'])
    all_categories = sorted({src['category'] for src in sources_list})

    # Build API parameters
    articles = []
    
    # --- NewsAPI Parameters ---
    newsapi_params = {}
    if source != 'all':
        newsapi_params['sources'] = source
    else:
        newsapi_params['country'] = 'us'
        if category != 'general':
            newsapi_params['category'] = category
    
    if query:
        newsapi_params['q'] = query
    
    # Clean None values
    newsapi_params = {k: v for k, v in newsapi_params.items() if v is not None}
    
    # --- GNews Parameters ---
    gnews_params = {'lang': 'en'}
    if query:
        gnews_params['q'] = query
    else:
        if category != 'general':
            gnews_params['topic'] = category
    
    # Fetch from both APIs
    articles += fetch_news('newsapi', newsapi_params)
    articles += fetch_news('gnews', gnews_params)

    return render_template(
        'home.html',
        articles=articles,
        sources=all_sources,
        categories=all_categories
    )

if __name__ == '__main__':
    app.run(debug=True)
