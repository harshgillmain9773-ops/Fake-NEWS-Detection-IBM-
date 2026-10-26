import os
from flask import Flask, request, render_template
import joblib
import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "models", "model.pkl")
VECTORIZER_PATH = os.path.join(BASE_DIR, "models", "vectorizer.pkl")

app = Flask(__name__)
model = joblib.load(MODEL_PATH)
vectorizer = joblib.load(VECTORIZER_PATH)

NEWS_API_EVERYTHING_URL = "https://newsapi.org/v2/everything"


def get_news_api_key():
    api_key = os.environ.get("NEWS_API_KEY")
    if api_key:
        return api_key.strip()

    if os.name != "nt":
        return None

    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as environment:
            api_key, _ = winreg.QueryValueEx(environment, "NEWS_API_KEY")
            return api_key.strip() if api_key else None
    except FileNotFoundError:
        return None


def fetch_headlines(page_size=100, api_key=None):
    api_key = api_key or get_news_api_key()
    if not api_key:
        return []

    response = requests.get(
        NEWS_API_EVERYTHING_URL,
        params={
            "q": "world OR politics OR business OR technology OR science OR health OR sports OR entertainment",
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": min(page_size, 100),
            "apiKey": api_key,
        },
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("status") == "error":
        raise requests.exceptions.RequestException(
            payload.get("message", "NewsAPI returned an error.")
        )
    return payload.get("articles", []) or []


@app.route("/", methods=["GET", "POST"])
def index():
    prediction = None
    validation_error = None
    if request.method == "POST":
        news = request.form.get("news", "").strip()
        if not news:
            validation_error = "Paste a headline or article before analyzing it."
        else:
            data = vectorizer.transform([news])
            pred = model.predict(data)[0]
            prediction = "Real News ✅" if pred == 1 else "Fake News ❌"
    return render_template(
        "index.html",
        prediction=prediction,
        validation_error=validation_error,
    )


def render_headlines_page(real_only=False):
    page_data = {
        "results": [],
        "error": None,
        "real_only": real_only,
        "page_title": "Stories the model classifies as real" if real_only else "Today's headlines",
        "page_description": (
            "Recent English-language headlines from international sources that the model classified as real. This is an automated estimate, not independent verification."
            if real_only
            else "Recent English-language headlines from international sources across world news, business, technology, science, health, sports, and more."
        ),
    }

    api_key = get_news_api_key()
    if not api_key:
        page_data["error"] = "Live headlines are not configured. Set the NEWS_API_KEY environment variable for your Windows user account."
        return render_template("today.html", **page_data)

    try:
        articles = fetch_headlines(api_key=api_key)
        if not articles:
            page_data["error"] = "NewsAPI is available, but it returned no headlines for these topics. Try refreshing later."
            return render_template("today.html", **page_data)

        results = []
        for article in articles:
            headline = (article.get("title") or "").strip()
            if not headline or headline == "[Removed]":
                continue

            prediction_text = " ".join(
                value.strip()
                for value in (
                    headline,
                    article.get("description") or "",
                    article.get("content") or "",
                )
                if isinstance(value, str) and value.strip() and value != "[Removed]"
            )
            data = vectorizer.transform([prediction_text])
            is_real = model.predict(data)[0] == 1
            if real_only and not is_real:
                continue
            label = "Real ✅" if is_real else "Fake ❌"
            article_url = article.get("url") or ""
            if not article_url.startswith(("https://", "http://")):
                article_url = ""
            results.append({
                "headline": headline,
                "label": label,
                "source": (article.get("source") or {}).get("name") or "News source",
                "url": article_url,
            })

        results = results[:20]
        if not results:
            page_data["error"] = (
                "No headlines in this batch were classified as real by the model. Refresh to check a new batch."
                if real_only
                else "No readable headlines were returned. Try refreshing in a little while."
            )
            return render_template("today.html", **page_data)

        page_data["results"] = results
        return render_template("today.html", **page_data)

    except requests.exceptions.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        if status_code in (401, 403):
            page_data["error"] = "NewsAPI rejected the key or this account does not have access to the requested endpoint. Check the key and plan."
        elif status_code == 429:
            page_data["error"] = "NewsAPI rate limit or quota reached. Check your plan and try again later."
        else:
            page_data["error"] = f"NewsAPI returned an HTTP {status_code or 'error'}. Try again later."
        return render_template("today.html", **page_data)
    except requests.exceptions.RequestException:
        page_data["error"] = "Could not reach NewsAPI right now. Check your internet connection and try again."
        return render_template("today.html", **page_data)


@app.route("/today")
def today_news():
    return render_headlines_page()


@app.route("/real-news")
def real_news():
    return render_headlines_page(real_only=True)


if __name__ == "__main__":
    app.run(debug=False)
