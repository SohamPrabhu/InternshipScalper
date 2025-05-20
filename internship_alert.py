import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import sqlite3
import time
import logging
import configparser
import os
import json
import re
import sched
from datetime import datetime

logging.basicConfig(
    level= logging.info, #Debug detailed information for diagonsing problems WARNING Indication that something unexpected happened Error More critical problems CRTICAL Serious issues
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=logging.FileHandler("internships_mointer.log",logging.StreamHandler()
 )
)

class InternshipMoniter:
    def __init__(self, config_file = 'config.ini'):
        self.config = self._load_config(config_file)
        self.db_conn = self._initialize_database()
        with open(self.config['FILES']['job_boards_file'], 'r') as f:
            self.job_boards = json.load(f)
        
        with open(self.config['FILES']['companies_file'], 'r') as f:
            self.companies = json.load(f)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }



    def _load_config(self, config_file):
        config = configparser.ConfigParser()
        config.read(config_file)
        return config



    def _initialize_database(self):
        conn = sqlite3.connect('internships.db')
        cursor =  conn.cursor()
        cursor.execute(''' 
        CREATE TABLE IF NOT EXISTS internships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT,
            title TEXT,
            company TEXT,
            url TEXT UNIQUE,
            description TEXT,
            location TEXT,
            posted_date TEXT,
            discovered_date TEXT,
            is_notified INTEGER DEFAULT 0
        )
        ''')
        conn.commit()
        return conn
    def _extract_job_info(self, source_type, listing, selectors, base_url = ""):
        job_info = {'source_type': source_type}
        try:
            if title_elem := listing.select_one(selectors.get('title', '')):
                job_info['title'] = title_elem.text.strip()
            if company_elem := listing.select_one(selectors.get('company','')):
                job_info['company'] = company_elem.text.strip()
            if link_elem := listing.select_one(selectors.get('link','')):
                href = link_elem.get('href', '')
                if href.startswith('/'):
                    job_info['url'] = base_url + href
                else:
                    job_info['url'] = href
            if location_elem := listing.select_one(selectors.get('location','')):
                job_info['location'] = location_elem.text.strip()
            if desc_elem := listing.select_one(selectors.get('description','')):
                job_info['description'] = desc_elem.text.strip()
            job_info['discovered_date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            return job_info
        except Exception as e:
            logging.error(f"Error extracting job info: {e}")
            return None
            

                                   
    def check_job_board(self, job_board):
        logging.info(f"Chekcing {job_board} for new internship........")
        try:
            response = requests.get(job_board['url'], headers=self.headers, timeout = 30)
            if response != 30:
                logging.error(f"Failed to access {job_board['name']}: Status code {response.status_code}")
                return[]
            soup = BeautifulSoup(response.text, 'html.parser')
            base_url = re.match(r'(https?://[^/]+)', job_board['url']).group(1)
            listings = soup.select(job_board['selectors']['listings'])
            logging.info(f"Found {len(listings)} potential listings on {job_board['name']}")
            new_jobs = []
            for listing in listings:
                
                job_info = self._extract_job_info(
                    job_board['name'], 
                    listing, 
                    job_board['selectors'],
                    base_url
                )
                if job_info and self._is_relevant_internship(job_info):
                    if self._save_job_to_db(job_info):
                        new_jobs.append(job_info)
            logging.info(f"Found {len(new_jobs)} new relevant internships on {job_board['name']}")
            return new_jobs
        except Exception as e:
            logging.error(f"Error checking {job_board['name']}: {e}")
            return []

            

    def run_check(self):
        all_new_jobs = []
        for job_board in self.job_boards:
            new_jobs = self.check_job_board(job_board)
        


    def start_mointering(self):
        interval_minutes = int(self.config['SETTINGS']['check_interval_minutes'])
        logging.info(f"Starting internhsips mointering ever{interval_minutes}")
        self.check()


if __name__ == "__main__":
    try:
        mointer = InternshipMoniter()
        mointer.start_mointering()
    except KeyboardInterrupt:
        logging.info("Mointer Stopped by user")
    except Exception as e:
        logging.critical(f"Fatal error: {e}")
    
    

