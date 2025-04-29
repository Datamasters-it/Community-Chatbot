#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Main entry point for the Telegram Chatbot application.
This bot provides expense management with Google Sheets integration
and calendar management with Google Calendar integration.
"""

import logging
import os
import re
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes, ConversationHandler

# Import our modules
import sheets_manager
import calendar_manager
import nlp_processor
import config

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
EXPENSE_AMOUNT, EXPENSE_CATEGORY, EXPENSE_DESCRIPTION = range(3)
CALENDAR_EVENT_DESCRIPTION, CALENDAR_EVENT_CONFIRMATION = range(2)
CALENDAR_EVENT_SELECTION, CALENDAR_EVENT_UPDATE = range(2)

# Command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    await update.message.reply_text(
        f"Ciao {user.first_name}! Sono il tuo assistente per la gestione delle spese e del calendario.\n"
        f"Usa /help per vedere i comandi disponibili."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    help_text = (
        "Ecco i comandi disponibili:\n\n"
        "*Gestione Spese:*\n"
        "/spesa - Registra una nuova spesa\n"
        "/report - Ottieni un report delle tue spese\n"
        "/report_giorno - Report spese del giorno\n"
        "/report_settimana - Report spese della settimana\n"
        "/report_mese - Report spese del mese\n"
        "/report_anno - Report spese dell'anno\n\n"
        "*Gestione Calendario:*\n"
        "/evento - Aggiungi un evento al calendario\n"
        "/eventi - Visualizza i prossimi eventi\n"
        "/modifica_evento - Modifica un evento esistente\n"
        "/cancella_evento - Cancella un evento esistente\n"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

# Expense management handlers
async def add_expense_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the expense adding conversation."""
    await update.message.reply_text(
        "Inserisci l'importo della spesa:"
    )
    return EXPENSE_AMOUNT

async def add_expense_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store the expense amount and ask for category."""
    text = update.message.text
    try:
        amount = float(text.replace(',', '.'))
        context.user_data['expense_amount'] = amount

        # Create keyboard with expense categories
        keyboard = []
        row = []
        for i, category in enumerate(config.EXPENSE_CATEGORIES):
            row.append(InlineKeyboardButton(category, callback_data=f"cat_{category}"))
            if (i + 1) % 3 == 0 or i == len(config.EXPENSE_CATEGORIES) - 1:
                keyboard.append(row)
                row = []

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Seleziona la categoria della spesa:",
            reply_markup=reply_markup
        )
        return EXPENSE_CATEGORY
    except ValueError:
        await update.message.reply_text(
            "L'importo deve essere un numero. Riprova:"
        )
        return EXPENSE_AMOUNT

async def add_expense_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store the expense category and ask for description."""
    query = update.callback_query
    await query.answer()

    category = query.data.replace("cat_", "")
    context.user_data['expense_category'] = category

    await query.edit_message_text(
        f"Categoria selezionata: {category}\n\n"
        "Inserisci una descrizione per la spesa (o invia /skip per saltare):"
    )
    return EXPENSE_DESCRIPTION

async def skip_expense_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Skip the expense description."""
    context.user_data['expense_description'] = ""
    return await add_expense_end(update, context)

async def add_expense_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store the expense description and finish the conversation."""
    context.user_data['expense_description'] = update.message.text
    return await add_expense_end(update, context)

async def add_expense_end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Add the expense to the spreadsheet and end the conversation."""
    amount = context.user_data.get('expense_amount')
    category = context.user_data.get('expense_category')
    description = context.user_data.get('expense_description', "")

    success, message = sheets_manager.add_expense(amount, category, description)

    if isinstance(update.callback_query, type(None)):
        await update.message.reply_text(message)
    else:
        await update.callback_query.edit_message_text(message)

    # Clear user data
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the conversation."""
    await update.message.reply_text(
        "Operazione annullata."
    )
    context.user_data.clear()
    return ConversationHandler.END

async def get_expense_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get an expense report."""
    command = update.message.text.split()[0].lower()

    if command == "/report_giorno":
        period = "day"
    elif command == "/report_settimana":
        period = "week"
    elif command == "/report_mese":
        period = "month"
    elif command == "/report_anno":
        period = "year"
    else:  # /report
        period = "month"  # Default to monthly report

    # Check if a category was specified
    args = context.args
    category = None
    if args:
        category = " ".join(args)
        if category not in config.EXPENSE_CATEGORIES:
            await update.message.reply_text(
                f"Categoria non valida. Categorie disponibili: {', '.join(config.EXPENSE_CATEGORIES)}"
            )
            return

    success, report = sheets_manager.get_expense_report(period, category)

    await update.message.reply_text(report, parse_mode='Markdown')

# Calendar management handlers
async def add_event_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the event adding conversation."""
    await update.message.reply_text(
        "Descrivi l'evento che vuoi aggiungere al calendario.\n"
        "Esempio: 'Riunione di lavoro domani alle 15:00 in ufficio'"
    )
    return CALENDAR_EVENT_DESCRIPTION

async def add_event_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process the event description using NLP."""
    text = update.message.text
    context.user_data['event_text'] = text

    # Show a waiting message
    wait_message = await update.message.reply_text("Sto elaborando la tua richiesta...")

    # Parse the event request
    success, result = nlp_processor.parse_event_request(text)

    # Delete the waiting message
    await wait_message.delete()

    if not success:
        await update.message.reply_text(
            f"Errore: {result}\n\n"
            "Riprova con una descrizione più chiara o usa /cancel per annullare."
        )
        return CALENDAR_EVENT_DESCRIPTION

    # Store the parsed event data
    context.user_data['event_data'] = result

    # Format the confirmation message
    summary = result['summary']
    start_time = result['start_time'].strftime('%d/%m/%Y %H:%M')
    end_time = result['end_time'].strftime('%d/%m/%Y %H:%M')
    location = result.get('location', '')
    description = result.get('description', '')

    confirmation_text = (
        f"*Evento:* {summary}\n"
        f"*Inizio:* {start_time}\n"
        f"*Fine:* {end_time}\n"
    )

    if location:
        confirmation_text += f"*Luogo:* {location}\n"

    if description:
        confirmation_text += f"*Descrizione:* {description}\n"

    confirmation_text += "\nConfermi la creazione dell'evento?"

    # Create inline keyboard for confirmation
    keyboard = [
        [
            InlineKeyboardButton("✅ Conferma", callback_data="event_confirm"),
            InlineKeyboardButton("❌ Annulla", callback_data="event_cancel")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        confirmation_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

    return CALENDAR_EVENT_CONFIRMATION

async def add_event_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle event confirmation."""
    query = update.callback_query
    await query.answer()

    if query.data == "event_cancel":
        await query.edit_message_text("Creazione evento annullata.")
        context.user_data.clear()
        return ConversationHandler.END

    # Get the event data
    event_data = context.user_data.get('event_data')

    # Create the event
    success, result = calendar_manager.create_event(
        summary=event_data['summary'],
        start_time=event_data['start_time'],
        end_time=event_data['end_time'],
        description=event_data.get('description', ''),
        location=event_data.get('location', '')
    )

    if success:
        await query.edit_message_text(
            f"✅ Evento creato con successo!\n\n"
            f"*{event_data['summary']}*\n"
            f"📆 {event_data['start_time'].strftime('%d/%m/%Y %H:%M')}",
            parse_mode='Markdown'
        )
    else:
        await query.edit_message_text(
            f"❌ Errore nella creazione dell'evento: {result}"
        )

    # Clear user data
    context.user_data.clear()
    return ConversationHandler.END

async def get_events(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get upcoming events."""
    # Show a waiting message
    wait_message = await update.message.reply_text("Sto recuperando gli eventi...")

    # Get upcoming events
    success, events = calendar_manager.get_upcoming_events(max_results=10)

    # Delete the waiting message
    await wait_message.delete()

    if not success:
        await update.message.reply_text(f"Errore: {events}")
        return

    # Format the events message
    message = calendar_manager.format_events_message(events)

    await update.message.reply_text(message, parse_mode='Markdown')

async def update_event_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the event update conversation."""
    # Show a waiting message
    wait_message = await update.message.reply_text("Sto recuperando gli eventi...")

    # Get upcoming events
    success, events = calendar_manager.get_upcoming_events(max_results=10)

    # Delete the waiting message
    await wait_message.delete()

    if not success:
        await update.message.reply_text(f"Errore: {events}")
        return ConversationHandler.END

    if isinstance(events, str):
        await update.message.reply_text(events)
        return ConversationHandler.END

    # Store events in user data
    context.user_data['events'] = events

    # Create inline keyboard with events
    keyboard = []
    for i, event in enumerate(events, 1):
        keyboard.append([InlineKeyboardButton(
            f"{i}. {event['summary']} - {event['start']}",
            callback_data=f"event_{event['id']}"
        )])

    keyboard.append([InlineKeyboardButton("❌ Annulla", callback_data="event_cancel")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Seleziona l'evento da modificare:",
        reply_markup=reply_markup
    )

    return CALENDAR_EVENT_SELECTION

async def update_event_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle event selection for update."""
    query = update.callback_query
    await query.answer()

    if query.data == "event_cancel":
        await query.edit_message_text("Modifica evento annullata.")
        context.user_data.clear()
        return ConversationHandler.END

    # Extract event ID
    event_id = query.data.replace("event_", "")
    context.user_data['event_id'] = event_id

    # Find the selected event
    events = context.user_data.get('events', [])
    selected_event = None
    for event in events:
        if event['id'] == event_id:
            selected_event = event
            break

    if not selected_event:
        await query.edit_message_text("Evento non trovato. Riprova.")
        return ConversationHandler.END

    # Store the selected event
    context.user_data['selected_event'] = selected_event

    await query.edit_message_text(
        f"Hai selezionato: *{selected_event['summary']}* - {selected_event['start']}\n\n"
        "Descrivi le modifiche che vuoi apportare all'evento.\n"
        "Esempio: 'Sposta l'evento a domani alle 16:00' o 'Cambia il titolo in Riunione importante'",
        parse_mode='Markdown'
    )

    return CALENDAR_EVENT_UPDATE

async def update_event_changes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process the event update using NLP."""
    text = update.message.text
    event_id = context.user_data.get('event_id')

    if not event_id:
        await update.message.reply_text("Errore: ID evento mancante. Riprova.")
        return ConversationHandler.END

    # Show a waiting message
    wait_message = await update.message.reply_text("Sto elaborando la tua richiesta...")

    # Parse the event update request
    success, result = nlp_processor.parse_event_update_request(text, event_id)

    # Delete the waiting message
    await wait_message.delete()

    if not success:
        await update.message.reply_text(f"Errore: {result}")
        context.user_data.clear()
        return ConversationHandler.END

    # Update the event
    success, message = calendar_manager.update_event(
        event_id=result['event_id'],
        summary=result.get('summary'),
        start_time=result.get('start_time'),
        end_time=result.get('end_time'),
        description=result.get('description'),
        location=result.get('location')
    )

    if success:
        await update.message.reply_text(f"✅ {message}")
    else:
        await update.message.reply_text(f"❌ {message}")

    # Clear user data
    context.user_data.clear()
    return ConversationHandler.END

async def delete_event_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the event deletion conversation."""
    # Show a waiting message
    wait_message = await update.message.reply_text("Sto recuperando gli eventi...")

    # Get upcoming events
    success, events = calendar_manager.get_upcoming_events(max_results=10)

    # Delete the waiting message
    await wait_message.delete()

    if not success:
        await update.message.reply_text(f"Errore: {events}")
        return ConversationHandler.END

    if isinstance(events, str):
        await update.message.reply_text(events)
        return ConversationHandler.END

    # Store events in user data
    context.user_data['events'] = events

    # Format the events message
    message = calendar_manager.format_events_message(events)

    await update.message.reply_text(
        message + "\n\nInvia il numero o il nome dell'evento che vuoi cancellare, o l'ID completo.",
        parse_mode='Markdown'
    )

    return CALENDAR_EVENT_SELECTION

async def delete_event_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle event selection for deletion."""
    text = update.message.text
    events = context.user_data.get('events', [])

    # Check if the user entered an event ID directly
    for event in events:
        if event['id'] == text:
            return await delete_event_confirmation(update, context, event['id'])

    # Check if the user entered a number
    match = re.match(r'^(\d+)$', text)
    if match:
        index = int(match.group(1)) - 1
        if 0 <= index < len(events):
            return await delete_event_confirmation(update, context, events[index]['id'])

    # Use NLP to identify the event
    # Show a waiting message
    wait_message = await update.message.reply_text("Sto elaborando la tua richiesta...")

    success, result = nlp_processor.parse_event_deletion_request(text, events)

    # Delete the waiting message
    await wait_message.delete()

    if not success:
        await update.message.reply_text(f"Errore: {result}\n\nRiprova o invia /cancel per annullare.")
        return CALENDAR_EVENT_SELECTION

    return await delete_event_confirmation(update, context, result)

async def delete_event_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE, event_id: str) -> int:
    """Delete the selected event."""
    # Show a waiting message
    wait_message = await update.message.reply_text("Sto cancellando l'evento...")

    # Delete the event
    success, message = calendar_manager.delete_event(event_id)

    # Delete the waiting message
    await wait_message.delete()

    if success:
        await update.message.reply_text(f"✅ {message}")
    else:
        await update.message.reply_text(f"❌ {message}")

    # Clear user data
    context.user_data.clear()
    return ConversationHandler.END

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the user message."""
    text = update.message.text
    await update.message.reply_text(
        "Ho ricevuto il tuo messaggio. Usa i comandi specifici per gestire spese o eventi.\n"
        "Digita /help per vedere i comandi disponibili."
    )

def main() -> None:
    """Start the bot."""
    # Create the Application
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        logger.error("No TELEGRAM_TOKEN found in environment variables")
        return

    application = Application.builder().token(token).build()

    # Add conversation handlers
    # Expense conversation handler
    expense_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("spesa", add_expense_start)],
        states={
            EXPENSE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_expense_amount)],
            EXPENSE_CATEGORY: [CallbackQueryHandler(add_expense_category, pattern=r"^cat_")],
            EXPENSE_DESCRIPTION: [
                CommandHandler("skip", skip_expense_description),
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_expense_description)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(expense_conv_handler)

    # Calendar event conversation handler
    event_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("evento", add_event_start)],
        states={
            CALENDAR_EVENT_DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_event_description)
            ],
            CALENDAR_EVENT_CONFIRMATION: [
                CallbackQueryHandler(add_event_confirmation, pattern=r"^event_")
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(event_conv_handler)

    # Update event conversation handler
    update_event_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("modifica_evento", update_event_start)],
        states={
            CALENDAR_EVENT_SELECTION: [
                CallbackQueryHandler(update_event_selection, pattern=r"^event_")
            ],
            CALENDAR_EVENT_UPDATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, update_event_changes)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(update_event_conv_handler)

    # Delete event conversation handler
    delete_event_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("cancella_evento", delete_event_start)],
        states={
            CALENDAR_EVENT_SELECTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, delete_event_selection)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(delete_event_conv_handler)

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("report", get_expense_report))
    application.add_handler(CommandHandler("report_giorno", get_expense_report))
    application.add_handler(CommandHandler("report_settimana", get_expense_report))
    application.add_handler(CommandHandler("report_mese", get_expense_report))
    application.add_handler(CommandHandler("report_anno", get_expense_report))
    application.add_handler(CommandHandler("eventi", get_events))

    # Add message handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Run the bot until the user presses Ctrl-C
    application.run_polling()

if __name__ == "__main__":
    main()
