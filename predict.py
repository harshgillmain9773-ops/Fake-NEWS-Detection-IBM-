import joblib
import re
import string

model = joblib.load(
    "models/model.pkl"
)

vectorizer = joblib.load(
    "models/vectorizer.pkl"
)

def preprocess(text):

    text = text.lower()

    text = re.sub(
        r"http\S+",
        "",
        text
    )

    text = re.sub(
        r"\d+",
        "",
        text
    )

    text = text.translate(
        str.maketrans(
            "",
            "",
            string.punctuation
        )
    )

    return text

def predict_news(news):

    news = preprocess(news)

    vector = vectorizer.transform(
        [news]
    )

    prediction = model.predict(
        vector
    )[0]

    if prediction == 1:
        return "REAL NEWS"

    return "FAKE NEWS"


sample = """
NASA successfully launches a new
satellite into orbit.
"""

print(
    predict_news(sample)
)