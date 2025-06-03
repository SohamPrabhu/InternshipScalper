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
    def scrape_company(self,company):
        logging.info(f"Checking {company['name']} careers page...")
        jobs = []
        try:
            self.driver.get(company['careers_url'])
            time.sleep(2)
            listings = self.driver.find_elements(By.CSS_SELECTOR, company['selectors']['listings'])
            logging.info(f"Found {len(listings)} potential listings on {company['name']}")
            for idx,listing in enumerate(listings):
                try:
                    def get_text(selector):
                        try:
                            return listing.find_element(By.CSS_SELECTOR,selector).text.strip()
                        except Exception:
                            logging.info(f"Error when trying to get the selector for {selector}")
                            return ""
                    def get_attr(selector,attr):
                        try:
                            return listing.find_element(By.CSS_SELECTOR,selector).get_attribute(attr)
                        except Exception:
                            logging.info(f"Error when trying get the attrbuite for {selector}")
                            return ""
                    title = get_text(company['selectors']['title'])
                    company_name =  company['name']
                    link = get_attr(company['selectors']['link'], "href")
                    location = get_text(company['selectors']['location'])
                    description = ""  #Need to add in if possible descrption is found
                    posted_date = "" #Same thing for this
                    discovered_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    job = {
                        "source": company['name'],
                        "title": title,
                        "company": company_name,
                        "url": link,
                        "description": description,
                        "location": location,
                        "posted_date": posted_date,
                        "discovered_date": discovered_date,
                    }
                    jobs.extend(job)
                except Exception as e:
                    logging.error(f"Error extracting job info for listing {idx+1} on {company['name']}: {e}")
        except Exception as e:
            logging.error(f"Error checking {company['name']}: {e}")
        return job

def job_exists(conn,url):
    with conn.cursor() as cursor:
        cursor.excute("SELECT 1 FROM internships WHERE url = %s;", (url,))
        return cursor.fetchtone() is not None
def insert_job(conn,job):
    with conn.cusor() as cursor:
        try:
            cursor.execute('''
                INSERT INTO internships (source, title, company, url, description, location, posted_date, discovered_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (url) DO NOTHING;
            ''', (
                job['source'],
                job['title'],
                job['company'],
                job['url'],
                job['description'],
                job['location'],
                job['posted_date'],
                job['discovered_date']
            ))
            if cursor.rowcount >0:
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Error inserting job into db: {str(e).replace(POSTGRES_PASSWORD, '[CENSORED]')}")
        return False

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
            with get_pg_conn as conn:
                for company in companies:
                    jobs = scraper.scrape_company(company)
                    for job in jobs:
                        if not job_exists(conn,job['url']):
                            if insert_job(conn,job):

    except KeyboardInterrupt:
        logging.info("Shutdown requested. Exiting.")
    finally:
        scraper.close()

if __name__ == "__main__":
    main()
