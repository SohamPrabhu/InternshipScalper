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
import schedule
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("internships_monitor.log"),
        logging.StreamHandler()
    ]
)

class InternshipMoniter:
    def __init__(self, config_file = 'config.ini'):
        self.config = self._load_config(config_file)
        self.db_conn = self._initialize_database()
        with open(self.config['FILES']['job_boards_file'], 'r') as f:
            self.job_boards = json.load(f)['job_boards']
        
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
            
    def _is_relevant_internship(self, job_info):
        keywords = self.config['SETTINGS']['keywords'].lower().split(',')
        title = job_info.get('title','').lower()
        description = job_info.get('description','').lower()
        if not any(k in title for k in ['intern','internship']):
            return False
        software_kw = ['software', 'developer', 'programming', 'coding', 'development']
        if not any(k in title or k in description for k in software_kw):
            return False
        return True


    def _save_job_to_db(self, job_info):
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT id FROM internships WHERE url = ?", (job_info.get('url', ''),))
        if cursor.fetchone():
            return False
        cursor.execute('''
        INSERT INTO internships (
            source, title, company, url, description, location, posted_date, discovered_date
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            job_info.get('source_type', ''),
            job_info.get('title', ''),
            job_info.get('company', ''),
            job_info.get('url', ''),
            job_info.get('description', ''),
            job_info.get('location', ''),
            job_info.get('posted_date', ''),
            job_info.get('discovered_date', '')
        ))
        
        self.db_conn.commit()
        return True


    def _send_emailnotification(self,new_jobs):
        if not new_jobs:
            return
        sender_email = self.config['EMAIL']['sender_email']
        recipient_email = self.config['EMAIL']['recipient_email']
        password = self.config['EMAIL']['sender_password']

        self.config['EMAIL']['sender_password']
        msg  = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = f"New Software Internship Alerts({len(new_jobs)} positions)"
        body = f"""<html>
        <body>
        <h2>New Software Internship Opportunities</h2>
        <p>Found {len(new_jobs)} new software internship positions:</p>
        <table border="1" cellpadding="5" cellspacing="0">
        <tr>
            <th>Company</th>
            <th>Position</th>
            <th>Location</th>
            <th>Link</th>
        </tr>
        """
        
        # Add each job to the email
        for job in new_jobs:
            body += f"""
            <tr>
                <td>{job.get('company', 'N/A')}</td>
                <td>{job.get('title', 'N/A')}</td>
                <td>{job.get('location', 'N/A')}</td>
                <td><a href="{job.get('url', '#')}">Apply Now</a></td>
            </tr>
            """
        
        body += """
        </table>
        </body>
        </html>
        """
        msg.attach(MIMEText(body,'html'))
        try:
            server  = smtplib.SMTP(self.config['EMAIL']['smtp_server'], self.config['EMAIL']['smtp_port'])
            server.starttls()
            server.login(sender_email,password)
            server.send(msg)
            server.quit()
            logging.info(f"Email notification sent for {len(new_jobs)} new internships")
            cursor = self.db_conn.cursor()
            for job in new_jobs:
                cursor.execute("UPDATE internships SET is_notified = 1 WHERE url = ?", (job.get('url', ''),))
            self.db_conn.commit()
        except Exception as e:
            logging.error(f"Failed to send email notification: {e}")


    def check_company_caeer_page(self,company):
        logging.info(f"Checking {company['name']} careers page for new internships...")
        try:
            response = requests.get(company['url'], headers=self.headers, timeout=30)
            if response.status_code != 200:
                logging.error(f"Failed to access {company['name']}: Status code {response.status_code}")
                return []
            soup = BeautifulSoup(response.text,'html.parser')
            base_url = re.match(r'(https?://[^/]+)', company['url']).group(1)
            listings  = soup.select(company['selectors']['listings'])
            logging.info(f"Found {len(listings)} potential listings on {company['name']}")
            new_jobs = []
            for listing in listings:
                job_info = self._extract_job_info(
                    company['name'], 
                    listing, 
                    company['selectors'],
                    base_url
                )
                
                if job_info and self._is_relevant_internship(job_info):
                    if self._save_job_to_db(job_info):
                        new_jobs.append(job_info)
            
            logging.info(f"Found {len(new_jobs)} new relevant internships on {company['name']}")
            return new_jobs
            
        except Exception as e:
            logging.error(f"Error checking {company['name']}: {e}")
            return []

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
            all_new_jobs.extend(new_jobs)
        for company in self.companies:
            new_jobs =self.check_company_caeer_page(company)
            all_new_jobs.extend(new_jobs)
        if all_new_jobs:
            self._send_emailnotification(all_new_jobs)
        logging.info(f"Check complete. Found {len(all_new_jobs)} new internships.")

        


    def start_mointering(self):
        interval_minutes = int(self.config['SETTINGS']['check_interval_minutes'])
        logging.info(f"Starting internhsips mointering ever{interval_minutes}")
        self.run_check()
        schedule.every(interval_minutes).minutes.do(self.run_check)
        while True:
            schedule.run_pending()
            time.sleep(1)


if __name__ == "__main__":
    try:
        mointer = InternshipMoniter()
        mointer.start_mointering()
    except KeyboardInterrupt:
        logging.info("Mointer Stopped by user")
    except Exception as e:
        logging.critical(f"Fatal error: {e}")
    
    

