# recommendations.py

import requests
from utils import rate_limit

class Recommender:
    def __init__(self, config):
        self.config = config

    @rate_limit(5)
    def generate_trade_recommendations(self, analysis_results):
        recommendations = []
        for result in analysis_results:
            prompt = f"""
            Based on the following analysis, generate a trade recommendation with specific details, including the ticker symbol, entry price, stop-loss, take-profit levels, and time horizon. Include rationale and supporting evidence.

            Analysis: {result}
            """
            # Use OpenRouter and SMART_LLM for generating recommendations
            headers = {
                "Authorization": f"Bearer {self.config.OPENROUTER_API_KEY}",
            }
            data = {
                "model": self.config.SMART_LLM,
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            }
            response = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=data
            )
            if response.status_code == 200:
                result = response.json()
                recommendation = result['choices'][0]['message']['content'].strip()
                recommendations.append(recommendation)
            else:
                print(f"Error generating recommendation: {response.text}")
        return recommendations

    @rate_limit(5)
    def score_recommendations(self, recommendations):
        scored_recommendations = []
        for rec in recommendations:
            prompt = f"""
            Evaluate the following trade recommendation based on the likelihood of significant upside, well-understood downside risk, and opportunity cost of capital. Provide a score between 1 and 10 and justify your rating.

            Recommendation: {rec}
            """
            # Use OpenRouter and SMART_LLM for scoring
            headers = {
                "Authorization": f"Bearer {self.config.OPENROUTER_API_KEY}",
            }
            data = {
                "model": self.config.SMART_LLM,
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            }
            response = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=data
            )
            if response.status_code == 200:
                result = response.json()
                score = result['choices'][0]['message']['content'].strip()
                scored_recommendations.append({
                    'recommendation': rec,
                    'score': score
                })
            else:
                print(f"Error scoring recommendation: {response.text}")
        return scored_recommendations