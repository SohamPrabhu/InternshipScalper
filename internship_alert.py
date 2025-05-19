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
    
    def start_mointering(self):
        interval_minutes = int(self.config['SETTINGS']['check_interval_minutes'])

        
if __name__ == "__main__":
    try:
        mointer = InternshipMoniter()
        mointer.start_mointering()
    except KeyboardInterrupt:
        logging.info("Mointer Stopped by user")
    except Exception as e:
        logging.critical(f"Fatal error: {e}")
    
    

