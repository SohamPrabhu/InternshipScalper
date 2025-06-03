import logging
import time
import json
import psycopg2
import os
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import smtplib
from email.message import EmailMessage

POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.environ.get("POSTGRES_PORT", 5432))
POSTGRES_DB = os.environ.get("POSTGRES_DB", "internships")
POSTGRES_USER = os.environ.get("POSTGRES_USER", "intern_user")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "")
COMPANIES_JSON = os.environ.get("COMPANIES_JSON", "companies.json")
EMAIL_FROM = os.environ.get("EMAIL_FROM", "")
EMAIL_TO = os.environ.get("EMAIL_TO", "")
EMAIL_SUBJECT = "New Internship Alert"
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "")
EMAIL_SMTP_SERVER = os.environ.get("EMAIL_SMTP_SERVER", "smtp.gmail.com")
EMAIL_SMTP_PORT = int(os.environ.get("EMAIL_SMTP_PORT", 465))
WAIT_TIME_SECONDS = int(os.environ.get("WAIT_TIME_SECONDS", 1800)) 



class InternshipScraper:
    def __init__(self):
        option = Options()
        option.add_argument("--headless")
        self.driver = webdriver.Chrome(options=option)
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s"
        )
        logging.info(f"Connecting to Postgres at host={POSTGRES_HOST}, port={POSTGRES_PORT}, db={POSTGRES_DB}, user={POSTGRES_USER}")
        logging.info(f"Email notifications from {EMAIL_FROM} to {EMAIL_TO} via {EMAIL_SMTP_SERVER}:{EMAIL_SMTP_PORT}")

    def close(self):
        self.driver.quit()

def get_pg_conn():
    return psycopg2.connect(host=POSTGRES_HOST, port=POSTGRES_PORT, dbname=POSTGRES_DB,user=POSTGRES_USER,password=POSTGRES_PASSWORD)

def setup_db():
    with get_pg_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS internships (
                    id SERIAL PRIMARY KEY,
                    source TEXT,
                    title TEXT,
                    company TEXT,
                    url TEXT UNIQUE,
                    description TEXT,
                    location TEXT,
                    posted_date TEXT,
                    discovered_date TEXT
                );
            ''')
        conn.commit()

def main():
    setup_db()
    with open(COMPANIES_JSON,"r", encoding="utf-8") as f:
        companies = json.load(f)
    scraper = InternshipScraper()
    try:
        while True:
            logging.info("Starting Scrapping Cycle")
    except KeyboardInterrupt:
        logging.info("Shutdown requested. Exiting.")
    finally:
        scraper.close()

if __name__ == "__main__":
    main()
