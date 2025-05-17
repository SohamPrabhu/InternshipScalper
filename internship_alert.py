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