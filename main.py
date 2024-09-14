# main.py

import schedule
import logging
import time
import config
from utils import setup_logging, send_email, rate_limit
from data_processing import DataProcessor
from analysis import Analyzer
from recommendations import Recommender
import requests
import json
import argparse
from tests import run_all_tests
import os
from dotenv import load_dotenv
import sys
from datetime import datetime

@rate_limit(5)
def is_special_situation(article_content, config):
    logging.info("Checking if article describes a special situation")
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
        "Authorization": f"Bearer {config.OPENROUTER_API_KEY}"
    }
    data = {
        "model": config.FAST_LLM,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant that analyzes text and determines if it describes a special situation, returning a JSON object."},
            {"role": "user", "content": prompt}
        ]
    }

    max_retries = 5
    for attempt in range(max_retries):
        try:
            response = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=data,
                timeout=60
            )
            response.raise_for_status()

            result = response.json()
            response_text = result['choices'][0]['message']['content'].strip()
            logging.debug(f"LLM response: {response_text}")

            # Parse the JSON response
            try:
                response_json = json.loads(response_text)
            except json.JSONDecodeError:
                logging.error(f"Failed to parse JSON from LLM response: {response_text}")
                return False

            if not isinstance(response_json, dict) or "is_special_situation" not in response_json:
                logging.error(f"Unexpected response format: {response_json}")
                return False

            return response_json["is_special_situation"]

        except requests.exceptions.RequestException as e:
            logging.error(f"Error in API request: {str(e)}")
            if hasattr(e, 'response'):
                logging.error(f"Status code: {e.response.status_code}")
                logging.error(f"Error message: {e.response.text}")
            
            if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 429:
                wait_time = 60 * (2 ** attempt)  # Start with 60 seconds, then double each time
                logging.warning(f"Rate limit exceeded. Waiting for {wait_time} seconds before retrying...")
                time.sleep(wait_time)
            elif attempt == max_retries - 1:
                logging.error(f"Error determining special situation after {max_retries} attempts")
                return False
            else:
                time.sleep(2 ** attempt)  # Exponential backoff for other errors

    return False

@rate_limit(5)
def extract_tickers(article_content, config):
    logging.info("Extracting tickers from article content")
    prompt = f"""
    Extract all company names mentioned in the following article content.
    Provide the output as a JSON array of strings, where each string is a company name.
    Only include the JSON array in your response, with no additional text.

    Content: {article_content}

    Example output format:
    ["Apple Inc.", "Microsoft Corporation", "Amazon.com, Inc."]
    """
    headers = {
        "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": config.FAST_LLM,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant that extracts company names from text and returns them in a JSON array format."},
            {"role": "user", "content": prompt}
        ]
    }
    
    max_retries = 5
    for attempt in range(max_retries):
        try:
            response = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=data,
                timeout=60
            )
            response.raise_for_status()
            
            result = response.json()
            company_names_json = result['choices'][0]['message']['content'].strip()
            logging.debug(f"LLM response: {company_names_json}")
            
            # Parse the JSON response
            try:
                company_list = json.loads(company_names_json)
            except json.JSONDecodeError:
                logging.error(f"Failed to parse JSON from LLM response: {company_names_json}")
                return []
            
            if not isinstance(company_list, list):
                logging.error(f"Expected a JSON array of company names, got: {type(company_list)}")
                return []
            
            tickers = []
            for company_name in company_list:
                ticker = get_ticker(company_name)
                if ticker:
                    tickers.append(ticker)
            logging.info(f"Extracted tickers: {tickers}")
            return tickers
        
        except requests.exceptions.RequestException as e:
            logging.error(f"Error in API request: {str(e)}")
            if hasattr(e, 'response'):
                logging.error(f"Status code: {e.response.status_code}")
                logging.error(f"Error message: {e.response.text}")
            
            if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 429:
                wait_time = 60 * (2 ** attempt)  # Start with 60 seconds, then double each time
                logging.warning(f"Rate limit exceeded. Waiting for {wait_time} seconds before retrying...")
                time.sleep(wait_time)
            elif attempt == max_retries - 1:
                logging.error(f"Error extracting company names after {max_retries} attempts")
                return []
            else:
                time.sleep(2 ** attempt)  # Exponential backoff for other errors
    
    return []

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

class OutputRedirector:
    def __init__(self, original_stream, log_file):
        self.original_stream = original_stream
        self.log_file = log_file

    def write(self, text):
        self.original_stream.write(text)
        with open(self.log_file, 'a') as f:
            f.write(text)

    def flush(self):
        self.original_stream.flush()

def main():
    # Set up output redirection
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = f"output_{timestamp}.txt"
    sys.stdout = OutputRedirector(sys.stdout, log_file)
    sys.stderr = OutputRedirector(sys.stderr, log_file)

    load_dotenv()  # Load environment variables
    setup_logging()
    logging.info("Starting main process")

    # Check for required environment variables
    required_env_vars = ['OPENROUTER_API_KEY', 'EXA_API_KEY', 'FAST_LLM', 'SMART_LLM']
    for var in required_env_vars:
        if not os.getenv(var):
            logging.error(f"Missing required environment variable: {var}")
            return

    try:
        data_processor = DataProcessor(config)
        analyzer = Analyzer(config)
        recommender = Recommender(config)

        # Fetch RSS feeds
        articles = data_processor.fetch_rss_articles(config.RSS_FEEDS)
        logging.info(f"Fetched {len(articles)} articles from RSS feeds")

        # Process each article
        analysis_results = []
        for i, article in enumerate(articles):
            logging.info(f"Processing article {i+1}/{len(articles)}")
            try:
                # Extract tickers or relevant companies from the article
                tickers = extract_tickers(article['description'], config)
                logging.debug(f"Extracted tickers: {tickers}")

                if not tickers:
                    logging.info("No tickers found in article, skipping")
                    continue

                for ticker in tickers:
                    try:
                        stock_data = data_processor.get_stock_data(ticker)
                        # Check if market cap is under $500 million
                        market_cap = stock_data.info.get('marketCap')
                        if market_cap is None:
                            logging.warning(f"Market cap data missing for {ticker}, skipping")
                            continue
                        if market_cap < 500_000_000:
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
                                logging.info(f"Completed analysis for {ticker}")
                            else:
                                logging.info(f"Ticker {ticker} did not meet the special situation criteria")
                        else:
                            logging.info(f"Ticker {ticker} has market cap over $500 million, skipping")
                    except Exception as e:
                        logging.error(f"Error processing ticker {ticker}: {str(e)}")
            except Exception as e:
                logging.error(f"Error processing article: {str(e)}")

        if not analysis_results:
            logging.warning("No analysis results to process")
            return

        # Generate recommendations
        recommendations = recommender.generate_trade_recommendations(analysis_results)

        if not recommendations:
            logging.warning("No recommendations generated")
            return

        # Score recommendations
        scored_recommendations = recommender.score_recommendations(recommendations)

        # Prepare email body
        email_body = '\n\n'.join([f"Recommendation:\n{rec['recommendation']}\nScore:\n{rec['score']}" for rec in scored_recommendations])

        # Save to CSV instead of sending email
        send_email("Daily Trade Recommendations", email_body, config)
        logging.info("Process completed successfully")

    except Exception as e:
        logging.exception("An unexpected error occurred in the main process")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the main program or tests")
    parser.add_argument("--test", action="store_true", help="Run tests instead of the main program")
    args = parser.parse_args()

    if args.test:
        run_all_tests()
    else:
        main()