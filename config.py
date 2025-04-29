#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Configuration settings for the Telegram Chatbot application.
"""

import os
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).resolve().parent

# Credentials directory
CREDENTIALS_DIR = BASE_DIR / "credentials"
os.makedirs(CREDENTIALS_DIR, exist_ok=True)

# Google API credentials files
GOOGLE_CREDENTIALS_FILE = CREDENTIALS_DIR / "google_credentials.json"
TOKEN_FILE = CREDENTIALS_DIR / "token.json"

# Google Sheets settings
EXPENSES_SPREADSHEET_NAME = "Expense Tracker"
EXPENSES_WORKSHEET_NAME = "Expenses"

# Expense categories
EXPENSE_CATEGORIES = [
    "Alimentari",
    "Trasporti",
    "Casa",
    "Bollette",
    "Salute",
    "Intrattenimento",
    "Abbigliamento",
    "Regali",
    "Altro"
]

# Google Calendar settings
CALENDAR_ID = "primary"  # Use 'primary' for the user's primary calendar

# OpenAI settings
OPENAI_MODEL = "gpt-3.5-turbo"

# Telegram bot settings
MAX_MESSAGE_LENGTH = 4096  # Maximum message length for Telegram messages