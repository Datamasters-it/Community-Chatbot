#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Natural Language Processing module for understanding user requests.
This module uses OpenAI's API to parse natural language requests
and extract structured information for calendar events.
"""

import os
import re
import json
import datetime
import pytz
from dateutil import parser
from openai import OpenAI

import config

def get_openai_client():
    """Get OpenAI client."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("OpenAI API key not found in environment variables")
        return None
    
    try:
        client = OpenAI(api_key=api_key)
        return client
    except Exception as e:
        print(f"Error creating OpenAI client: {e}")
        return None

def parse_event_request(text):
    """
    Parse a natural language request for calendar event creation.
    
    Args:
        text (str): The natural language request
    
    Returns:
        tuple: (success, event_data or error_message)
    """
    client = get_openai_client()
    if not client:
        return False, "Impossibile accedere al servizio OpenAI. Verifica la chiave API."
    
    try:
        # Define the system message
        system_message = """
        Sei un assistente che aiuta a estrarre informazioni sugli eventi dal testo in italiano.
        Estrai le seguenti informazioni:
        1. Titolo dell'evento
        2. Data e ora di inizio
        3. Data e ora di fine (se specificata)
        4. Luogo (se specificato)
        5. Descrizione (se specificata)
        
        Rispondi SOLO con un oggetto JSON con i seguenti campi:
        {
            "summary": "Titolo dell'evento",
            "start_time": "YYYY-MM-DD HH:MM",
            "end_time": "YYYY-MM-DD HH:MM" o null se non specificato,
            "location": "Luogo dell'evento" o "" se non specificato,
            "description": "Descrizione dell'evento" o "" se non specificata
        }
        
        Se la data non è specificata, usa la data di oggi.
        Se l'ora non è specificata, usa le 12:00 come orario predefinito.
        Se la data è specificata come "domani", "dopodomani", "lunedì", ecc., convertila nella data effettiva.
        """
        
        # Call the OpenAI API
        response = client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": text}
            ],
            temperature=0.1,  # Low temperature for more deterministic results
        )
        
        # Extract the response content
        content = response.choices[0].message.content.strip()
        
        # Parse the JSON response
        try:
            event_data = json.loads(content)
            
            # Validate required fields
            if not event_data.get("summary"):
                return False, "Non è stato possibile identificare il titolo dell'evento."
            
            if not event_data.get("start_time"):
                return False, "Non è stato possibile identificare la data e l'ora dell'evento."
            
            # Parse start_time
            try:
                start_time = parser.parse(event_data["start_time"])
                # Set timezone to Rome
                rome_tz = pytz.timezone('Europe/Rome')
                start_time = rome_tz.localize(start_time)
                event_data["start_time"] = start_time
            except Exception as e:
                return False, f"Errore nel parsing della data di inizio: {str(e)}"
            
            # Parse end_time if provided
            if event_data.get("end_time"):
                try:
                    end_time = parser.parse(event_data["end_time"])
                    # Set timezone to Rome
                    rome_tz = pytz.timezone('Europe/Rome')
                    end_time = rome_tz.localize(end_time)
                    event_data["end_time"] = end_time
                except Exception as e:
                    # If end_time parsing fails, set it to start_time + 1 hour
                    event_data["end_time"] = event_data["start_time"] + datetime.timedelta(hours=1)
            else:
                # If end_time is not provided, set it to start_time + 1 hour
                event_data["end_time"] = event_data["start_time"] + datetime.timedelta(hours=1)
            
            return True, event_data
        except json.JSONDecodeError:
            return False, "Errore nel parsing della risposta. Riprova con una richiesta più chiara."
    except Exception as e:
        print(f"Error in parse_event_request: {e}")
        return False, f"Errore nell'elaborazione della richiesta: {str(e)}"

def parse_event_update_request(text, event_id):
    """
    Parse a natural language request for calendar event update.
    
    Args:
        text (str): The natural language request
        event_id (str): The ID of the event to update
    
    Returns:
        tuple: (success, event_data or error_message)
    """
    client = get_openai_client()
    if not client:
        return False, "Impossibile accedere al servizio OpenAI. Verifica la chiave API."
    
    try:
        # Define the system message
        system_message = """
        Sei un assistente che aiuta a estrarre informazioni per aggiornare un evento esistente dal testo in italiano.
        Estrai le seguenti informazioni, solo se menzionate nel testo:
        1. Nuovo titolo dell'evento
        2. Nuova data e ora di inizio
        3. Nuova data e ora di fine
        4. Nuovo luogo
        5. Nuova descrizione
        
        Rispondi SOLO con un oggetto JSON con i seguenti campi:
        {
            "summary": "Nuovo titolo dell'evento" o null se non menzionato,
            "start_time": "YYYY-MM-DD HH:MM" o null se non menzionato,
            "end_time": "YYYY-MM-DD HH:MM" o null se non menzionato,
            "location": "Nuovo luogo dell'evento" o null se non menzionato,
            "description": "Nuova descrizione dell'evento" o null se non menzionata
        }
        
        Se la data è specificata come "domani", "dopodomani", "lunedì", ecc., convertila nella data effettiva.
        """
        
        # Call the OpenAI API
        response = client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": text}
            ],
            temperature=0.1,  # Low temperature for more deterministic results
        )
        
        # Extract the response content
        content = response.choices[0].message.content.strip()
        
        # Parse the JSON response
        try:
            update_data = json.loads(content)
            
            # Check if any fields were extracted
            if all(value is None for value in update_data.values()):
                return False, "Non è stato possibile identificare alcuna modifica da apportare all'evento."
            
            # Parse start_time if provided
            if update_data.get("start_time"):
                try:
                    start_time = parser.parse(update_data["start_time"])
                    # Set timezone to Rome
                    rome_tz = pytz.timezone('Europe/Rome')
                    start_time = rome_tz.localize(start_time)
                    update_data["start_time"] = start_time
                except Exception as e:
                    return False, f"Errore nel parsing della nuova data di inizio: {str(e)}"
            
            # Parse end_time if provided
            if update_data.get("end_time"):
                try:
                    end_time = parser.parse(update_data["end_time"])
                    # Set timezone to Rome
                    rome_tz = pytz.timezone('Europe/Rome')
                    end_time = rome_tz.localize(end_time)
                    update_data["end_time"] = end_time
                except Exception as e:
                    update_data["end_time"] = None
            
            # Add event_id to the update data
            update_data["event_id"] = event_id
            
            return True, update_data
        except json.JSONDecodeError:
            return False, "Errore nel parsing della risposta. Riprova con una richiesta più chiara."
    except Exception as e:
        print(f"Error in parse_event_update_request: {e}")
        return False, f"Errore nell'elaborazione della richiesta: {str(e)}"

def parse_event_deletion_request(text, events):
    """
    Parse a natural language request for calendar event deletion.
    
    Args:
        text (str): The natural language request
        events (list): List of event dictionaries
    
    Returns:
        tuple: (success, event_id or error_message)
    """
    client = get_openai_client()
    if not client:
        return False, "Impossibile accedere al servizio OpenAI. Verifica la chiave API."
    
    if isinstance(events, str):
        return False, events  # This is an error message
    
    if not events:
        return False, "Non ci sono eventi da eliminare."
    
    try:
        # Create a formatted list of events for the AI
        events_text = ""
        for i, event in enumerate(events, 1):
            events_text += f"{i}. {event['summary']} - {event['start']}\n"
        
        # Define the system message
        system_message = f"""
        Sei un assistente che aiuta a identificare quale evento eliminare dal calendario.
        Ecco l'elenco degli eventi disponibili:
        
        {events_text}
        
        Analizza la richiesta dell'utente e identifica quale evento vuole eliminare.
        Rispondi SOLO con il numero dell'evento da eliminare (1, 2, 3, ecc.) o con "non trovato" se non riesci a identificare l'evento.
        """
        
        # Call the OpenAI API
        response = client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": text}
            ],
            temperature=0.1,  # Low temperature for more deterministic results
        )
        
        # Extract the response content
        content = response.choices[0].message.content.strip().lower()
        
        # Check if the AI couldn't identify the event
        if "non trovato" in content:
            return False, "Non è stato possibile identificare quale evento eliminare. Prova a essere più specifico."
        
        # Try to extract a number from the response
        match = re.search(r'\d+', content)
        if match:
            event_index = int(match.group()) - 1
            if 0 <= event_index < len(events):
                return True, events[event_index]['id']
            else:
                return False, "Numero evento non valido."
        else:
            return False, "Non è stato possibile identificare quale evento eliminare. Prova a essere più specifico."
    except Exception as e:
        print(f"Error in parse_event_deletion_request: {e}")
        return False, f"Errore nell'elaborazione della richiesta: {str(e)}"

if __name__ == "__main__":
    # Test the module
    print("Testing NLP processing...")
    
    # Test event creation parsing
    test_text = "Crea una riunione di lavoro domani alle 15:00 in ufficio per discutere del progetto"
    success, result = parse_event_request(test_text)
    
    if success:
        print("Successfully parsed event request:")
        print(f"Summary: {result['summary']}")
        print(f"Start time: {result['start_time']}")
        print(f"End time: {result['end_time']}")
        print(f"Location: {result['location']}")
        print(f"Description: {result['description']}")
    else:
        print(f"Failed to parse event request: {result}")