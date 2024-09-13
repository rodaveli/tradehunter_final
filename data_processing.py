# data_processing.py

import yfinance as yf
from edgar import Company
from exa_py import Exa
from pyfinmod.financials import Financials
from pyfinmod.ev import fcf, dcf
from pyfinmod.wacc import wacc
import pandas as pd
import requests
from bs4 import BeautifulSoup

class DataProcessor:
    def __init__(self, config):
        self.exa = Exa(api_key=config.EXA_API_KEY)
        self.config = config

    def get_stock_data(self, ticker):
        stock = yf.Ticker(ticker)
        return stock

    def get_sec_filings(self, ticker):
        company = Company(ticker)
        # Expanded list of forms to include more relevant filings
        forms_to_include = [
            '10-K', '10-Q', '8-K', '6-K', '20-F', 'S-1', 'S-4', '424B2', '424B3',
            'SC 13D', 'SC 13G', 'DEFA14A', 'DEF 14A', 'PRE 14A', 'POS AM',
            'Form 3', 'Form 4', 'Form 5', 'SD', '11-K'
        ]
        filings = company.get_filings().filter(form=forms_to_include)
        return filings

    def get_financials(self, ticker):
        parser = Financials(ticker)
        return parser

    def get_news_articles(self, query):
        response = self.exa.search_and_contents(query, type='neural', num_results=5)
        articles = []
        for result in response.results:
            articles.append({
                'title': result.title,
                'url': result.url,
                'content': result.text
            })
        return articles

    def fetch_rss_articles(self, feed_urls):
        articles = []
        for url in feed_urls:
            response = requests.get(url)
            soup = BeautifulSoup(response.content, features='xml')
            items = soup.findAll('item')
            for item in items:
                articles.append({
                    'title': item.title.text,
                    'link': item.link.text,
                    'published': item.pubDate.text,
                    'description': item.description.text
                })
        return articles