from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline


class RewardModel:
    def __init__(self):
        self.model = make_pipeline(TfidfVectorizer(), Ridge())

    def train(self, logs):
        texts = [entry["prompt"] + "\n" + entry["code"] for entry in logs]
        rewards = [-entry["cost"] for entry in logs]
        self.model.fit(texts, rewards)

    def score(self, prompt, completions):
        """
        Rank multiple completions by predicted reward.
        Returns: list of (completion, predicted_reward)
        """
        inputs = [prompt + "\n" + c for c in completions]
        preds = self.model.predict(inputs)
        return list(zip(completions, preds))
