#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Google Calendar integration for event management.
This module handles connecting to Google Calendar API and provides
functions for managing calendar events.
"""

import os
import datetime
import pytz
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import config

# Define the scopes
SCOPES = [
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/calendar.events'
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

def get_calendar_service():
    """Get Google Calendar service."""
    creds = get_credentials()
    if not creds:
        return None
    
    try:
        service = build('calendar', 'v3', credentials=creds)
        return service
    except Exception as e:
        print(f"Error creating calendar service: {e}")
        return None

def create_event(summary, start_time, end_time=None, description="", location=""):
    """
    Create a new calendar event.
    
    Args:
        summary (str): Event title/summary
        start_time (datetime): Start time of the event
        end_time (datetime, optional): End time of the event. If None, defaults to 1 hour after start_time
        description (str, optional): Event description
        location (str, optional): Event location
    
    Returns:
        tuple: (success, event_id or error_message)
    """
    service = get_calendar_service()
    if not service:
        return False, "Impossibile accedere al servizio Calendar."
    
    try:
        # Set default end time if not provided
        if end_time is None:
            end_time = start_time + datetime.timedelta(hours=1)
        
        # Format times for Google Calendar API
        start_time_str = start_time.isoformat()
        end_time_str = end_time.isoformat()
        
        # Create event body
        event = {
            'summary': summary,
            'location': location,
            'description': description,
            'start': {
                'dateTime': start_time_str,
                'timeZone': 'Europe/Rome',
            },
            'end': {
                'dateTime': end_time_str,
                'timeZone': 'Europe/Rome',
            },
            'reminders': {
                'useDefault': True,
            },
        }
        
        # Create the event
        event = service.events().insert(calendarId=config.CALENDAR_ID, body=event).execute()
        
        return True, event.get('id')
    except HttpError as e:
        print(f"Error creating event: {e}")
        return False, f"Errore nella creazione dell'evento: {str(e)}"
    except Exception as e:
        print(f"Unexpected error creating event: {e}")
        return False, "Errore imprevisto nella creazione dell'evento."

def update_event(event_id, summary=None, start_time=None, end_time=None, description=None, location=None):
    """
    Update an existing calendar event.
    
    Args:
        event_id (str): ID of the event to update
        summary (str, optional): New event title/summary
        start_time (datetime, optional): New start time
        end_time (datetime, optional): New end time
        description (str, optional): New description
        location (str, optional): New location
    
    Returns:
        tuple: (success, message)
    """
    service = get_calendar_service()
    if not service:
        return False, "Impossibile accedere al servizio Calendar."
    
    try:
        # Get the existing event
        event = service.events().get(calendarId=config.CALENDAR_ID, eventId=event_id).execute()
        
        # Update fields if provided
        if summary:
            event['summary'] = summary
        
        if description is not None:
            event['description'] = description
            
        if location is not None:
            event['location'] = location
            
        if start_time:
            event['start']['dateTime'] = start_time.isoformat()
            
        if end_time:
            event['end']['dateTime'] = end_time.isoformat()
        
        # Update the event
        updated_event = service.events().update(
            calendarId=config.CALENDAR_ID, 
            eventId=event_id, 
            body=event
        ).execute()
        
        return True, f"Evento '{updated_event.get('summary')}' aggiornato con successo."
    except HttpError as e:
        print(f"Error updating event: {e}")
        return False, f"Errore nell'aggiornamento dell'evento: {str(e)}"
    except Exception as e:
        print(f"Unexpected error updating event: {e}")
        return False, "Errore imprevisto nell'aggiornamento dell'evento."

def delete_event(event_id):
    """
    Delete a calendar event.
    
    Args:
        event_id (str): ID of the event to delete
    
    Returns:
        tuple: (success, message)
    """
    service = get_calendar_service()
    if not service:
        return False, "Impossibile accedere al servizio Calendar."
    
    try:
        # Get the event first to confirm it exists and get its summary
        event = service.events().get(calendarId=config.CALENDAR_ID, eventId=event_id).execute()
        event_summary = event.get('summary', 'Evento sconosciuto')
        
        # Delete the event
        service.events().delete(calendarId=config.CALENDAR_ID, eventId=event_id).execute()
        
        return True, f"Evento '{event_summary}' eliminato con successo."
    except HttpError as e:
        print(f"Error deleting event: {e}")
        return False, f"Errore nell'eliminazione dell'evento: {str(e)}"
    except Exception as e:
        print(f"Unexpected error deleting event: {e}")
        return False, "Errore imprevisto nell'eliminazione dell'evento."

def get_upcoming_events(max_results=10, time_min=None):
    """
    Get upcoming calendar events.
    
    Args:
        max_results (int, optional): Maximum number of events to return
        time_min (datetime, optional): Minimum time for events. If None, defaults to now
    
    Returns:
        tuple: (success, events_list or error_message)
    """
    service = get_calendar_service()
    if not service:
        return False, "Impossibile accedere al servizio Calendar."
    
    try:
        # Set default time_min if not provided
        if time_min is None:
            time_min = datetime.datetime.utcnow()
        
        # Format time for Google Calendar API
        time_min_str = time_min.isoformat() + 'Z'  # 'Z' indicates UTC time
        
        # Get events
        events_result = service.events().list(
            calendarId=config.CALENDAR_ID,
            timeMin=time_min_str,
            maxResults=max_results,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        if not events:
            return True, "Nessun evento in programma."
        
        # Format events for display
        formatted_events = []
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            
            # Parse the datetime
            if 'T' in start:  # This is a dateTime, not just a date
                start_dt = datetime.datetime.fromisoformat(start.replace('Z', '+00:00'))
                # Convert to local time (Europe/Rome)
                rome_tz = pytz.timezone('Europe/Rome')
                start_dt = start_dt.astimezone(rome_tz)
                start_str = start_dt.strftime('%d/%m/%Y %H:%M')
            else:
                # This is an all-day event
                start_str = datetime.datetime.fromisoformat(start).strftime('%d/%m/%Y (tutto il giorno)')
            
            formatted_events.append({
                'id': event['id'],
                'summary': event.get('summary', 'Evento senza titolo'),
                'start': start_str,
                'location': event.get('location', ''),
                'description': event.get('description', '')
            })
        
        return True, formatted_events
    except HttpError as e:
        print(f"Error getting events: {e}")
        return False, f"Errore nel recupero degli eventi: {str(e)}"
    except Exception as e:
        print(f"Unexpected error getting events: {e}")
        return False, "Errore imprevisto nel recupero degli eventi."

def format_events_message(events):
    """
    Format a list of events into a readable message.
    
    Args:
        events (list): List of event dictionaries
    
    Returns:
        str: Formatted message
    """
    if isinstance(events, str):
        return events
    
    message = "📅 *Eventi in programma:*\n\n"
    
    for i, event in enumerate(events, 1):
        message += f"*{i}. {event['summary']}*\n"
        message += f"📆 {event['start']}\n"
        
        if event['location']:
            message += f"📍 {event['location']}\n"
            
        if event['description']:
            # Truncate description if too long
            desc = event['description']
            if len(desc) > 50:
                desc = desc[:47] + "..."
            message += f"📝 {desc}\n"
            
        message += f"ID: `{event['id']}`\n\n"
    
    return message

if __name__ == "__main__":
    # Test the module
    print("Testing Google Calendar integration...")
    service = get_calendar_service()
    if service:
        print("Successfully connected to Google Calendar API")
        
        # Test getting upcoming events
        success, events = get_upcoming_events(max_results=5)
        if success:
            if isinstance(events, str):
                print(events)
            else:
                print(f"Found {len(events)} upcoming events:")
                for event in events:
                    print(f"- {event['summary']} ({event['start']})")
    else:
        print("Failed to connect to Google Calendar API")