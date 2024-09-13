# analysis.py

import requests
import pandas as pd
from ta import add_all_ta_features
from ta.utils import dropna
from pyfinmod.financials import Financials
from pyfinmod.ev import fcf, dcf
from pyfinmod.wacc import wacc
import numpy as np
from utils import rate_limit
import yfinance as yf

class Analyzer:
    def __init__(self, config):
        self.config = config

    @rate_limit(5)  # Limit to 5 requests per second
    def summarize_findings(self, text):
        # Use OpenRouter and FAST_LLM for summarization
        headers = {
            "Authorization": f"Bearer {self.config['OPENROUTER_API_KEY']}",
        }
        data = {
            "model": self.config['FAST_LLM'],
            "messages": [
                {"role": "user", "content": f"Summarize the following text:\n\n{text}"}
            ]
        }
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=data
        )
        if response.status_code == 200:
            result = response.json()
            return result['choices'][0]['message']['content'].strip()
        else:
            print(f"Error in LLM summarization: {response.text}")
            return ""

    def analyze_sec_filings(self, filings):
        important_sections = []
        for filing in filings:
            try:
                if filing.form in ['10-K', '10-Q', 'S-1']:
                    sections = filing.sections()
                    key_sections = {k: v for k, v in sections.items() if k in ['Business', 'Risk Factors', 'Management’s Discussion and Analysis']}
                    important_sections.append(key_sections)
                else:
                    important_sections.append(filing.full_text_submission())
            except Exception as e:
                print(f"Error processing filing: {e}")
                continue
        return important_sections

    def perform_dcf_analysis(self, financials):
        try:
            cash_flows = fcf(financials.cash_flow_statement)
            cost_of_capital = wacc(
                financials.mktCap,
                financials.balance_sheet_statement,
                financials.income_statement,
                financials.beta,
                risk_free_interest_rate=0.02,
                market_return=0.08
            )
            dcf_value = dcf(
                cash_flows,
                cost_of_capital,
                short_term_growth=0.05,
                long_term_growth=0.03
            )
            return dcf_value
        except Exception as e:
            print(f"Error performing DCF analysis: {e}")
            return None

    def perform_technical_analysis(self, stock_data):
        df = stock_data.history(period='1y')
        df = dropna(df)
        df = add_all_ta_features(
            df, open="Open", high="High", low="Low", close="Close", volume="Volume"
        )
        return df

    def analyze_insider_trading(self, ticker):
        company = yf.Ticker(ticker)
        insider_trades = company.get_insider_transactions()
        return insider_trades