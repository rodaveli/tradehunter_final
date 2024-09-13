# utils.py

import logging
import requests
import feedparser
from datetime import datetime
from email.mime.text import MIMEText
import smtplib
import os
import json
import time
from functools import wraps
import threading

CACHE_DIR = 'cache'

def setup_logging():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def fetch_rss_feeds(feed_urls):
    articles = []
    for url in feed_urls:
        feed = feedparser.parse(url)
        for entry in feed.entries:
            articles.append({
                'title': entry.title,
                'link': entry.link,
                'published': entry.get('published', ''),
                'summary': entry.get('summary', '')
            })
    return articles

def send_email(subject, body, config):
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = config.EMAIL_SENDER
    msg['To'] = config.EMAIL_RECIPIENT

    with smtplib.SMTP_SSL(config.SMTP_SERVER, config.SMTP_PORT) as server:
        server.login(config.EMAIL_SENDER, config.EMAIL_PASSWORD)
        server.sendmail(config.EMAIL_SENDER, config.EMAIL_RECIPIENT, msg.as_string())

def cache_data(key, data):
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)
    file_path = os.path.join(CACHE_DIR, f'{key}.json')
    with open(file_path, 'w') as f:
        json.dump(data, f)

def get_cached_data(key):
    file_path = os.path.join(CACHE_DIR, f'{key}.json')
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            data = json.load(f)
        return data
    return None

# Rate limiting decorator
def rate_limit(max_per_second):
    min_interval = 1.0 / float(max_per_second)
    lock = threading.Lock()
    last_time_called = [0.0]

    def decorator(func):
        @wraps(func)
        def rate_limited_function(*args, **kwargs):
            with lock:
                elapsed = time.time() - last_time_called[0]
                left_to_wait = min_interval - elapsed
                if left_to_wait > 0:
                    time.sleep(left_to_wait)
                last_time_called[0] = time.time()
            return func(*args, **kwargs)
        return rate_limited_function
    return decorator