#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Google Sheets integration for expense management.
This module handles connecting to Google Sheets API, creating and managing spreadsheets,
and reading/writing expense data.
"""

import os
import datetime
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import config

# Define the scopes
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

def get_credentials():
    """Get valid credentials for Google API access."""
    try:
        # Check if credentials file exists
        if not os.path.exists(config.GOOGLE_CREDENTIALS_FILE):
            raise FileNotFoundError(f"Google credentials file not found at {config.GOOGLE_CREDENTIALS_FILE}")
        
        # Load credentials from the credentials file
        creds = Credentials.from_service_account_file(
            config.GOOGLE_CREDENTIALS_FILE, scopes=SCOPES
        )
        return creds
    except Exception as e:
        print(f"Error getting credentials: {e}")
        return None

def get_sheets_service():
    """Get Google Sheets service."""
    creds = get_credentials()
    if not creds:
        return None
    
    try:
        # Create gspread client
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        print(f"Error creating sheets service: {e}")
        return None

def get_or_create_expense_sheet():
    """Get or create the expense tracking spreadsheet."""
    client = get_sheets_service()
    if not client:
        return None
    
    try:
        # Try to open existing spreadsheet
        try:
            spreadsheet = client.open(config.EXPENSES_SPREADSHEET_NAME)
        except gspread.exceptions.SpreadsheetNotFound:
            # Create new spreadsheet if it doesn't exist
            spreadsheet = client.create(config.EXPENSES_SPREADSHEET_NAME)
            
            # Share with the service account email (optional)
            # spreadsheet.share(client.auth.service_account_email, perm_type='user', role='writer')
            
            # Create and format the expenses worksheet
            worksheet = spreadsheet.sheet1
            worksheet.update_title(config.EXPENSES_WORKSHEET_NAME)
            
            # Set up headers
            headers = ["Data", "Importo", "Categoria", "Descrizione"]
            worksheet.update('A1:D1', [headers])
            
            # Format headers (bold)
            worksheet.format('A1:D1', {'textFormat': {'bold': True}})
        
        return spreadsheet
    except Exception as e:
        print(f"Error getting or creating expense sheet: {e}")
        return None

def add_expense(amount, category, description=""):
    """
    Add a new expense to the spreadsheet.
    
    Args:
        amount (float): The expense amount
        category (str): The expense category
        description (str, optional): A description of the expense
    
    Returns:
        bool: True if successful, False otherwise
    """
    if category not in config.EXPENSE_CATEGORIES:
        return False, f"Categoria non valida. Categorie disponibili: {', '.join(config.EXPENSE_CATEGORIES)}"
    
    try:
        amount = float(amount)
    except ValueError:
        return False, "L'importo deve essere un numero."
    
    spreadsheet = get_or_create_expense_sheet()
    if not spreadsheet:
        return False, "Impossibile accedere al foglio delle spese."
    
    try:
        # Open the worksheet
        worksheet = spreadsheet.worksheet(config.EXPENSES_WORKSHEET_NAME)
        
        # Prepare the new row
        date = datetime.datetime.now().strftime("%d/%m/%Y")
        new_row = [date, amount, category, description]
        
        # Append the new row
        worksheet.append_row(new_row)
        
        return True, f"Spesa di {amount}€ aggiunta nella categoria '{category}'."
    except Exception as e:
        print(f"Error adding expense: {e}")
        return False, "Errore nell'aggiunta della spesa."

def get_expense_report(period="month", category=None):
    """
    Generate an expense report.
    
    Args:
        period (str): The time period for the report ('day', 'week', 'month', 'year', 'all')
        category (str, optional): Filter by category
    
    Returns:
        tuple: (success, report_text or error_message)
    """
    spreadsheet = get_or_create_expense_sheet()
    if not spreadsheet:
        return False, "Impossibile accedere al foglio delle spese."
    
    try:
        # Open the worksheet
        worksheet = spreadsheet.worksheet(config.EXPENSES_WORKSHEET_NAME)
        
        # Get all records
        records = worksheet.get_all_records()
        if not records:
            return True, "Nessuna spesa registrata."
        
        # Convert to DataFrame
        df = pd.DataFrame(records)
        
        # Convert date strings to datetime objects
        df['Data'] = pd.to_datetime(df['Data'], format='%d/%m/%Y')
        
        # Filter by date
        now = datetime.datetime.now()
        if period == "day":
            df = df[df['Data'].dt.date == now.date()]
            period_text = "oggi"
        elif period == "week":
            start_of_week = now - datetime.timedelta(days=now.weekday())
            df = df[df['Data'] >= start_of_week]
            period_text = "questa settimana"
        elif period == "month":
            df = df[df['Data'].dt.month == now.month]
            df = df[df['Data'].dt.year == now.year]
            period_text = "questo mese"
        elif period == "year":
            df = df[df['Data'].dt.year == now.year]
            period_text = "quest'anno"
        else:  # 'all'
            period_text = "totali"
        
        # Filter by category if specified
        if category:
            if category not in config.EXPENSE_CATEGORIES:
                return False, f"Categoria non valida. Categorie disponibili: {', '.join(config.EXPENSE_CATEGORIES)}"
            df = df[df['Categoria'] == category]
            category_text = f" nella categoria '{category}'"
        else:
            category_text = ""
        
        if df.empty:
            return True, f"Nessuna spesa {period_text}{category_text}."
        
        # Calculate totals
        total = df['Importo'].sum()
        
        # Group by category
        category_totals = df.groupby('Categoria')['Importo'].sum().to_dict()
        
        # Format the report
        report = f"📊 *Report spese {period_text}{category_text}*\n\n"
        report += f"Totale: {total:.2f}€\n\n"
        
        if not category:
            report += "*Dettaglio per categoria:*\n"
            for cat, amount in category_totals.items():
                report += f"- {cat}: {amount:.2f}€\n"
        
        return True, report
    except Exception as e:
        print(f"Error generating expense report: {e}")
        return False, "Errore nella generazione del report."

if __name__ == "__main__":
    # Test the module
    print("Testing Google Sheets integration...")
    sheet = get_or_create_expense_sheet()
    if sheet:
        print(f"Successfully connected to spreadsheet: {sheet.title}")
    else:
        print("Failed to connect to spreadsheet.")