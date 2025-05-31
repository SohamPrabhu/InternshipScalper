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
import random
from urllib.parse import urljoin, urlparse
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("internships_monitor.log"),
        logging.StreamHandler()
    ]
)

class InternshipMonitor:  # Fixed typo: Moniter -> Monitor
    def __init__(self, config_file='config.ini'):
        self.config = self._load_config(config_file)
        self.db_conn = self._initialize_database()
        self.job_boards = self._load_job_boards()  # Fixed typo
        self.companies = self._load_companies()    # Fixed typo
        self.session = self._setup_session()

        self.min_delay = 3  # Increased delay
        self.max_delay = 8

    def _setup_session(self):
        session = requests.Session()

        retry_strategy = Retry(
            total=5,  # Increased retries
            backoff_factor=2,  # Increased backoff
            status_forcelist=[429, 500, 502, 503, 504]
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # More comprehensive headers to avoid blocking
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0'
        })
        return session

    def _load_config(self, config_file):
        config = configparser.ConfigParser()
        
        # Set defaults first
        config.read_dict({
            'EMAIL': {
                'smtp_server': os.getenv('SMTP_SERVER', 'smtp.gmail.com'),
                'smtp_port': os.getenv('SMTP_PORT', '587'),
                'sender_email': os.getenv('SENDER_EMAIL', ''),
                'sender_password': os.getenv('SENDER_PASSWORD', ''),
                'recipient_email': os.getenv('RECIPIENT_EMAIL', '')
            },
            'SETTINGS': {
                'check_interval_minutes': os.getenv('CHECK_INTERVAL', '60'),  # Increased interval
                'keywords': os.getenv('KEYWORDS', 'software,intern,internship,developer,engineering,coding,programming,python,java,javascript')
            },
            'FILES': {
                'job_boards_file': 'job_boards.json',
                'companies_file': 'companies.json'
            }
        })
        
        if os.path.exists(config_file):
            config.read(config_file)
            logging.info(f"Loaded configuration from {config_file}")
        else:
            logging.warning(f"Config file {config_file} not found, using environment variables and defaults")
            
        # Validate email configuration
        if not config['EMAIL']['sender_email'] or not config['EMAIL']['sender_password']:
            logging.error("Email credentials not found in config or environment variables")
            raise ValueError("Email credentials required. Set SENDER_EMAIL and SENDER_PASSWORD environment variables")
            
        return config
    
    def _load_job_boards(self):  # Fixed method name
        job_boards_file = self.config.get('FILES', 'job_boards_file', fallback='job_boards.json')
        try:
            with open(job_boards_file, 'r') as f:
                boards = json.load(f)
                logging.info(f"Loaded {len(boards)} job boards from {job_boards_file}")
                return boards
        except FileNotFoundError:
            logging.error(f"Job boards file {job_boards_file} not found")
            return []
        except json.JSONDecodeError as e:
            logging.error(f"Error parsing job boards JSON: {e}")
            return []

    def _load_companies(self):
        companies_file = self.config.get('FILES', 'companies_file', fallback='companies.json')
        try:
            with open(companies_file, 'r') as f:
                companies = json.load(f)
                logging.info(f"Loaded {len(companies)} companies from {companies_file}")
                return companies
        except FileNotFoundError:
            logging.warning(f"Companies file {companies_file} not found, skipping company checks")
            return []
        except json.JSONDecodeError as e:
            logging.error(f"Error parsing companies JSON: {e}")
            return []

    def _initialize_database(self):
        try:
            conn = sqlite3.connect('internships.db')
            cursor = conn.cursor()
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
            logging.info("Database initialized successfully")
            return conn
        except sqlite3.Error as e:
            logging.error(f"Database initialization failed: {e}")
            raise

    def _rate_limit(self):
        delay = random.uniform(self.min_delay, self.max_delay)
        logging.debug(f"Rate limiting: waiting {delay:.2f} seconds")
        time.sleep(delay)

    def _test_selector(self, url, selector, description=""):
        try:
            # Add longer timeout and better error handling
            response = self.session.get(url, timeout=45)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                elements = soup.select(selector)
                logging.info(f"Selector test for {description}: found {len(elements)} elements with '{selector}'")
                return len(elements) > 0
            else:
                logging.warning(f"Selector test failed: HTTP {response.status_code} for {url}")
                return False
        except requests.exceptions.Timeout:
            logging.error(f"Timeout testing selector for {url}")
            return False
        except Exception as e:
            logging.error(f"Selector test error for {url}: {e}")
            return False

    def test_all_selectors(self):
        logging.info("Testing all CSS selectors...")
        for job_board in self.job_boards:
            name = job_board.get('name', 'Unknown')
            url = job_board.get('url', '')
            
            if not url:
                logging.warning(f"No URL found for job board: {name}")
                continue
                
            logging.info(f"Testing selectors for {name}...")
            
            # Test main listings selector first
            if self._test_selector(url, job_board['selectors']['listings'], f"{name} listings"):
                # Test other selectors
                for selector_name, selector in job_board['selectors'].items():
                    if selector_name != 'listings' and selector:
                        self._test_selector(url, selector, f"{name} {selector_name}")
            else:
                logging.warning(f"Main listings selector failed for {name} - this job board may not work")
            
            self._rate_limit()
        for company in self.companies:
            name = company.get('name', 'Unknown')
            url = company.get('careers_url', '')
            
            if not url:
                logging.warning(f"No URL found for job board: {name}")
                continue
                
            logging.info(f"Testing selectors for {name}...")
            
            # Test main listings selector first
            if self._test_selector(url, company['selectors']['listings'], f"{name} listings"):
                # Test other selectors
                for selector_name, selector in company['selectors'].items():
                    if selector_name != 'listings' and selector:
                        self._test_selector(url, selector, f"{name} {selector_name}")
            else:
                logging.warning(f"Main listings selector failed for {name} - this job board may not work")
            
            self._rate_limit()

    def _make_request_with_retry(self, url, max_retries=3):
        for attempt in range(max_retries):
            try:
                logging.debug(f"Attempting to fetch {url} (attempt {attempt + 1})")
                
                # Add random delay between attempts
                if attempt > 0:
                    delay = random.uniform(5, 15) * attempt
                    logging.info(f"Waiting {delay:.1f} seconds before retry...")
                    time.sleep(delay)
                
                response = self.session.get(url, timeout=45)
                
                if response.status_code == 200:
                    logging.debug(f"Successfully fetched {url}")
                    return response
                elif response.status_code == 429:
                    wait_time = 2 ** attempt * 60
                    logging.warning(f"Rate limited on {url}, waiting {wait_time} seconds")
                    time.sleep(wait_time)
                elif response.status_code in [403, 404]:
                    logging.error(f"HTTP {response.status_code} for {url} - may be blocked or URL changed")
                    break
                else:
                    logging.warning(f"HTTP {response.status_code} for {url}")
                    
            except requests.exceptions.Timeout:
                logging.warning(f"Timeout for {url} on attempt {attempt + 1}")
            except requests.exceptions.ConnectionError as e:
                logging.warning(f"Connection error for {url}: {e}")
            except requests.exceptions.RequestException as e:
                logging.error(f"Request error for {url}: {e}")
            
            self._rate_limit()
        
        logging.error(f"Failed to fetch {url} after {max_retries} attempts")
        return None

    def _extract_job_info(self, source_type, listing, selectors, base_url=""):
        job_info = {'source_type': source_type}
        try:
            # Extract title
            title_selector = selectors.get('title', '')
            if title_selector:
                if title_elem := listing.select_one(title_selector):
                    job_info['title'] = title_elem.get_text(strip=True)
                    logging.debug(f"Extracted title: {job_info['title']}")

            # Extract company
            company_selector = selectors.get('company', '')
            if company_selector:
                if company_elem := listing.select_one(company_selector):
                    job_info['company'] = company_elem.get_text(strip=True)
                    logging.debug(f"Extracted company: {job_info['company']}")

            # Extract link
            link_selector = selectors.get('link', '')
            if link_selector:
                if link_elem := listing.select_one(link_selector):
                    href = link_elem.get('href', '')
                    if href:
                        job_info['url'] = urljoin(base_url, href)
                        logging.debug(f"Extracted URL: {job_info['url']}")

            # Extract location
            location_selector = selectors.get('location', '')
            if location_selector:
                if location_elem := listing.select_one(location_selector):
                    job_info['location'] = location_elem.get_text(strip=True)
                    logging.debug(f"Extracted location: {job_info['location']}")

            # Extract description
            desc_selector = selectors.get('description', '')
            if desc_selector:
                if desc_elem := listing.select_one(desc_selector):
                    job_info['description'] = desc_elem.get_text(strip=True)[:500]

            job_info['discovered_date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Validate required fields
            if not job_info.get('title'):
                logging.warning(f"Missing title for job from {source_type}")
                return None
            
            if not job_info.get('url'):
                logging.warning(f"Missing URL for job from {source_type}")
                return None

            return job_info
            
        except Exception as e:
            logging.error(f"Error extracting job info: {e}")
            return None

    def _is_relevant_internship(self, job_info):
        title = job_info.get('title', '').lower()
        description = job_info.get('description', '').lower()
        company = job_info.get('company', '').lower()

        # Check for internship keywords
        internship_keywords = ['intern', 'internship', 'co-op', 'coop', 'student', 'entry level']
        text_to_search = f"{title} {description} {company}"
        
        if not any(keyword in text_to_search for keyword in internship_keywords):
            logging.debug(f"Rejected - no internship keywords: {title}")
            return False

        # Check for relevant skills/keywords
        keywords = [kw.strip().lower() for kw in self.config['SETTINGS']['keywords'].split(',')]
        if any(keyword in text_to_search for keyword in keywords):
            logging.debug(f"Accepted relevant internship: {title}")
            return True
            
        logging.debug(f"Rejected - no relevant keywords: {title}")
        return False
        

    def _save_job_to_db(self, job_info):
        try:
            cursor = self.db_conn.cursor()
            cursor.execute("SELECT id FROM internships WHERE url = ?", (job_info.get('url', ''),))
            if cursor.fetchone():
                logging.debug(f"Job already exists in database: {job_info.get('url')}")
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
            logging.info(f"Saved new job to database: {job_info.get('title')} at {job_info.get('company', 'Unknown')}")
            return True
            
        except sqlite3.Error as e:
            logging.error(f"Database error while saving job: {e}")
            return False

    def _send_email_notification(self, new_jobs):  # Fixed method name
        if not new_jobs:
            return
            
        try:
            sender_email = self.config['EMAIL']['sender_email']
            recipient_email = self.config['EMAIL']['recipient_email']
            password = self.config['EMAIL']['sender_password']

            msg = MIMEMultipart()
            msg['From'] = sender_email
            msg['To'] = recipient_email
            msg['Subject'] = f"🚨 New Software Internship Alerts ({len(new_jobs)} positions)"
            
            body = self._create_email_body(new_jobs)
            msg.attach(MIMEText(body, 'html'))
            
            with smtplib.SMTP(self.config['EMAIL']['smtp_server'], int(self.config['EMAIL']['smtp_port'])) as server:
                server.starttls()
                server.login(sender_email, password)
                server.send_message(msg)
                
            logging.info(f"Email notification sent for {len(new_jobs)} new internships")
            self._mark_jobs_notified(new_jobs)
            
        except smtplib.SMTPAuthenticationError:
            logging.error("Email authentication failed - check credentials")
        except smtplib.SMTPException as e:
            logging.error(f"SMTP error: {e}")
        except Exception as e:
            logging.error(f"Failed to send email notification: {e}")

    def _create_email_body(self, new_jobs):
        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; margin: 20px;">
        <h2 style="color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px;">
            🎯 New Software Internship Opportunities
        </h2>
        <p style="font-size: 16px;">Found <strong style="color: #e74c3c;">{len(new_jobs)}</strong> new software internship positions:</p>
        
        <table border="1" cellpadding="12" cellspacing="0" style="border-collapse: collapse; width: 100%; margin-top: 20px;">
        <tr style="background-color: #3498db; color: white;">
            <th style="text-align: left;">Company</th>
            <th style="text-align: left;">Position</th>
            <th style="text-align: left;">Location</th>
            <th style="text-align: left;">Source</th>
            <th style="text-align: center;">Action</th>
        </tr>
        """
        
        for i, job in enumerate(new_jobs):
            bg_color = "#f8f9fa" if i % 2 == 0 else "#ffffff"
            body += f"""
            <tr style="background-color: {bg_color};">
                <td><strong>{job.get('company', 'N/A')}</strong></td>
                <td style="color: #2c3e50;">{job.get('title', 'N/A')}</td>
                <td>{job.get('location', 'N/A')}</td>
                <td><span style="background-color: #ecf0f1; padding: 3px 8px; border-radius: 3px; font-size: 12px;">{job.get('source_type', 'N/A')}</span></td>
                <td style="text-align: center;">
                    <a href="{job.get('url', '#')}" 
                       style="background-color: #27ae60; color: white; padding: 8px 16px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                       Apply Now 🚀
                    </a>
                </td>
            </tr>
            """
        
        body += f"""
        </table>
        <p style="margin-top: 30px; color: #7f8c8d; font-size: 14px; border-top: 1px solid #ecf0f1; padding-top: 15px;">
            📅 Alert generated on: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}<br>
            🤖 Automated by InternshipMonitor
        </p>
        </body>
        </html>
        """
        return body

    def _mark_jobs_notified(self, new_jobs):
        try:
            cursor = self.db_conn.cursor()
            for job in new_jobs:
                cursor.execute("UPDATE internships SET is_notified = 1 WHERE url = ?", (job.get('url', ''),))
            self.db_conn.commit()
            logging.debug(f"Marked {len(new_jobs)} jobs as notified")
        except sqlite3.Error as e:
            logging.error(f"Error marking jobs as notified: {e}")

    def check_company_career_page(self, company):  # Fixed method name
        logging.info(f"Checking {company['name']} careers page for new internships...")
        try:
            response = self._make_request_with_retry(company['careers_url'])
            if not response:
                return []
                
            soup = BeautifulSoup(response.text, 'html.parser')
            base_url = re.match(r'(https?://[^/]+)', company['careers_url']).group(1)
            
            listings = soup.select(company['selectors']['listings'])
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
        name = job_board.get('name', 'Unknown')
        logging.info(f"Checking {name} for new internships...")
        
        try:
            response = self._make_request_with_retry(job_board['url'])
            if not response:
                return []
                
            soup = BeautifulSoup(response.text, 'html.parser')
            parsed_url = urlparse(job_board['url'])
            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"

            listings = soup.select(job_board['selectors']['listings'])
            logging.info(f"Found {len(listings)} potential listings on {name}")

            if not listings:
                logging.warning(f"No listings found - selectors may be outdated for {name}")
                return []

            new_jobs = []
            for i, listing in enumerate(listings[:20]):  # Limit to first 20 listings
                logging.debug(f"Processing listing {i+1}/{min(len(listings), 20)} from {name}")

                job_info = self._extract_job_info(
                    name, 
                    listing, 
                    job_board['selectors'],
                    base_url
                )
                
                if job_info and self._is_relevant_internship(job_info):
                    if self._save_job_to_db(job_info):
                        new_jobs.append(job_info)
                        logging.info(f"New relevant internship found: {job_info['title']} at {job_info.get('company', 'Unknown')}")
                
                # Small delay between processing listings
                if i < min(len(listings), 20) - 1:
                    time.sleep(random.uniform(0.5, 1.5))
                    
            logging.info(f"Found {len(new_jobs)} new relevant internships on {name}")
            return new_jobs
            
        except Exception as e:
            logging.error(f"Error checking {name}: {e}")
            return []

    def run_check(self):
        all_new_jobs = []
        logging.info("=" * 50)
        logging.info("Starting internship check cycle")
        logging.info("=" * 50)
        
        # Check job boards
        for job_board in self.job_boards:
            try:
                new_jobs = self.check_job_board(job_board)
                all_new_jobs.extend(new_jobs)
                self._rate_limit()
            except Exception as e:
                logging.error(f"Unexpected error checking {job_board.get('name', 'unknown')}: {e}")
        
        # Check company career pages
        for company in self.companies:
            try:
                new_jobs = self.check_company_career_page(company)
                all_new_jobs.extend(new_jobs)
                self._rate_limit()
            except Exception as e:
                logging.error(f"Unexpected error checking company {company.get('name', 'unknown')}: {e}")
        
        # Send notifications if new jobs found
        if all_new_jobs:
            self._send_email_notification(all_new_jobs)
            logging.info(f"✅ Check complete. Found {len(all_new_jobs)} new internships!")
        else:
            logging.info("ℹ️  Check complete. No new internships found.")
            
        logging.info("=" * 50)

    def start_monitoring(self):  # Fixed method name
        interval_minutes = int(self.config['SETTINGS']['check_interval_minutes'])
        logging.info(f"🚀 Starting internship monitoring every {interval_minutes} minutes")
        logging.info(f"📧 Notifications will be sent to: {self.config['EMAIL']['recipient_email']}")
        
        # Run initial check
        self.run_check()
        
        # Schedule recurring checks
        schedule.every(interval_minutes).minutes.do(self.run_check)
        
        try:
            while True:
                schedule.run_pending()
                time.sleep(60)  # Check every minute for scheduled tasks
        except KeyboardInterrupt:
            logging.info("👋 Monitor stopped by user")
        finally:
            self.cleanup()

    def cleanup(self):
        if hasattr(self, 'db_conn'):
            self.db_conn.close()
            logging.info("Database connection closed")
        if hasattr(self, 'session'):
            self.session.close()
            logging.info("HTTP session closed")

if __name__ == "__main__":
    try:
        monitor = InternshipMonitor()  # Fixed variable name
        monitor.test_all_selectors()
        monitor.start_monitoring()     # Fixed method name
    except KeyboardInterrupt:
        logging.info("Monitor stopped by user")
    except Exception as e:
        logging.critical(f"Fatal error: {e}")