# main.py

import schedule
import time
from config import *
from utils import setup_logging, send_email, rate_limit
from data_processing import DataProcessor
from analysis import Analyzer
from recommendations import Recommender
import requests
import json



config = {
    'OPENAI_API_KEY': OPENAI_API_KEY,
    'OPENROUTER_API_KEY': OPENROUTER_API_KEY,
    'EXA_API_KEY': EXA_API_KEY,
    'EMAIL_SENDER': EMAIL_SENDER,
    'EMAIL_PASSWORD': EMAIL_PASSWORD,
    'EMAIL_RECIPIENT': EMAIL_RECIPIENT,
    'SMTP_SERVER': SMTP_SERVER,
    'SMTP_PORT': SMTP_PORT,
    'FAST_LLM': FAST_LLM,
    'LONG_CONTEXT_LLM': LONG_CONTEXT_LLM,
    'SMART_LLM': SMART_LLM,
    'RSS_FEEDS': RSS_FEEDS,
}


@rate_limit(5)
def is_special_situation(article_content, config):
    # Use a fast, cheap LLM to determine if the article describes a special situation
    prompt = f"""
    Analyze the following article content and determine if it describes any of the following:

    - A corporate action (e.g., merger, acquisition, spinoff, rights offering)
    - A special situation or workout
    - A clear catalyst for short-term price movement

    Provide a JSON object with a single key "is_special_situation" and a boolean value (true or false). Do not include any additional text.

    Content: {article_content}

    Example output format:
    {{"is_special_situation": true}}
    """
    headers = {
        "Authorization": f"Bearer {config['OPENROUTER_API_KEY']}",
        "Content-Type": "application/json"
    }
    data = {
        "model": config['FAST_LLM'],
        "messages": [
            {"role": "system", "content": "You are a helpful assistant that analyzes text and determines if it describes a special situation, returning a JSON object."},
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"}
    }

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=data,
                timeout=30
            )
            response.raise_for_status()

            result = response.json()
            response_text = result['choices'][0]['message']['content'].strip()

            # Parse the JSON response
            response_json = json.loads(response_text)

            if not isinstance(response_json, dict) or "is_special_situation" not in response_json:
                raise ValueError("Expected a JSON object with key 'is_special_situation'")

            return response_json["is_special_situation"]

        except (requests.RequestException, json.JSONDecodeError, KeyError, ValueError) as e:
            if attempt == max_retries - 1:
                print(f"Error determining special situation after {max_retries} attempts: {str(e)}")
                return False
            time.sleep(2 ** attempt)  # Exponential backoff

    return False

@rate_limit(5)
def extract_tickers(article_content, config):
    # Use a fast, cheap LLM to extract company names
    prompt = f"""
    Extract all company names mentioned in the following article content.
    Provide the output as a JSON array of strings, where each string is a company name.
    Only include the JSON array in your response, with no additional text.

    Content: {article_content}

    Example output format:
    ["Apple Inc.", "Microsoft Corporation", "Amazon.com, Inc."]
    """
    headers = {
        "Authorization": f"Bearer {config['OPENROUTER_API_KEY']}",
        "Content-Type": "application/json"
    }
    data = {
        "model": config['FAST_LLM'],
        "messages": [
            {"role": "system", "content": "You are a helpful assistant that extracts company names from text and returns them in a JSON array format."},
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"}
    }
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=data,
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            company_names_json = result['choices'][0]['message']['content'].strip()
            
            # Parse the JSON response
            company_list = json.loads(company_names_json)
            
            if not isinstance(company_list, list):
                raise ValueError("Expected a JSON array of company names")
            
            tickers = []
            for company_name in company_list:
                ticker = get_ticker(company_name)
                if ticker:
                    tickers.append(ticker)
            return tickers
        
        except (requests.RequestException, json.JSONDecodeError, KeyError, ValueError) as e:
            if attempt == max_retries - 1:
                print(f"Error extracting company names after {max_retries} attempts: {str(e)}")
                return []
            time.sleep(2 ** attempt)  # Exponential backoff
    
    return []

# @rate_limit(5)
# def extract_tickers(article_content, config):
#     # Use a fast, cheap LLM to extract company names
#     prompt = f"""
#     Extract all company names mentioned in the following article content.

#     Content: {article_content}

#     Provide a list of company names.
#     """
#     headers = {
#         "Authorization": f"Bearer {config['OPENROUTER_API_KEY']}",
#     }
#     data = {
#         "model": config['FAST_LLM'],
#         "messages": [
#             {"role": "user", "content": prompt}
#         ]
#     }
#     response = requests.post(
#         url="https://openrouter.ai/api/v1/chat/completions",
#         headers=headers,
#         json=data
#     )
#     if response.status_code == 200:
#         result = response.json()
#         company_names = result['choices'][0]['message']['content'].strip()
#         # Assuming the LLM returns company names separated by commas or newlines
#         company_list = [name.strip() for name in company_names.split('\n') if name.strip()]
#         tickers = []
#         for company_name in company_list:
#             ticker = get_ticker(company_name)
#             if ticker:
#                 tickers.append(ticker)
#         return tickers
#     else:
#         print(f"Error extracting company names: {response.text}")
#         return []

def get_ticker(company_name):
    yfinance_url = "https://query2.finance.yahoo.com/v1/finance/search"
    user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36'
    params = {"q": company_name, "quotes_count": 1, "country": "United States"}

    res = requests.get(url=yfinance_url, params=params, headers={'User-Agent': user_agent})
    data = res.json()
    try:
        company_code = data['quotes'][0]['symbol']
        return company_code
    except (IndexError, KeyError):
        return None

def main():
    setup_logging()
    data_processor = DataProcessor(config)
    analyzer = Analyzer(config)
    recommender = Recommender(config)

    # Fetch RSS feeds
    articles = data_processor.fetch_rss_articles(config['RSS_FEEDS'])

    # Process each article
    analysis_results = []
    for article in articles:
        # Extract tickers or relevant companies from the article
        tickers = extract_tickers(article['description'], config)
        for ticker in tickers:
            stock_data = data_processor.get_stock_data(ticker)
            # Check if market cap is under $100 million
            market_cap = stock_data.info.get('marketCap', 0)
            if market_cap and market_cap < 100_000_000:
                # Determine if it's a special situation or obvious price catalyst
                if is_special_situation(article['description'], config):
                    # Proceed with analysis
                    financials = data_processor.get_financials(ticker)
                    sec_filings = data_processor.get_sec_filings(ticker)

                    # Perform analysis
                    sec_analysis = analyzer.analyze_sec_filings(sec_filings)
                    dcf_value = analyzer.perform_dcf_analysis(financials)
                    tech_analysis = analyzer.perform_technical_analysis(stock_data)
                    insider_trades = analyzer.analyze_insider_trading(ticker)

                    # Summarize findings
                    findings_text = f"SEC Analysis: {sec_analysis}\nDCF Value: {dcf_value}\nTechnical Analysis: {tech_analysis}\nInsider Trades: {insider_trades}"
                    findings = analyzer.summarize_findings(findings_text)
                    analysis_results.append(findings)
                else:
                    print(f"Ticker {ticker} did not meet the special situation criteria.")
            else:
                print(f"Ticker {ticker} has market cap over $100 million or missing data.")

    if not analysis_results:
        print("No analysis results to process.")
        return

    # Generate recommendations
    recommendations = recommender.generate_trade_recommendations(analysis_results)

    if not recommendations:
        print("No recommendations generated.")
        return

    # Score recommendations
    scored_recommendations = recommender.score_recommendations(recommendations)


    # Prepare email body
    email_body = '\n\n'.join([f"Recommendation:\n{rec['recommendation']}\nScore:\n{rec['score']}" for rec in scored_recommendations])

    # Save to CSV instead of sending email
    send_email("Daily Trade Recommendations", email_body, config)
    # # Send email with recommendations
    # email_body = '\n\n'.join([f"Recommendation:\n{rec['recommendation']}\nScore:\n{rec['score']}" for rec in scored_recommendations])
    # send_email("Daily Trade Recommendations", email_body, config)

# Schedule the main function to run daily
schedule.every().day.at("09:00").do(main)

if __name__ == "__main__":
    while True:
        schedule.run_pending()
        time.sleep(60)