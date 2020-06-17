from telegram import (
    KeyboardButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ParseMode,
)
from telegram.ext import (
    ConversationHandler,
)
import logging
import re
from services.watchlists import get_car_message
from bot.db import (
    get_user,
    get_watchlists,
    get_watchlist,
    get_cars,
    insert_watchlist as insert_watchlist_db,
    update_watchlist as update_watchlist_db,
    delete_watchlist as remove_watchlist_db,
    insert_feedback,
)
from bot.telegram_utils import create_buttons, create_menu
from bot.letter_makes_utils import LETTER_MAKE_MODEL
from utils.list_utils import chunks


(
    INPUT_WATCHLIST_LETTER,
    INPUT_WATCHLIST_MAKE,
    INPUT_WATCHLIST_MODEL,
    INPUT_WATCHLIST_MORE_MODELS,
    INPUT_WATCHLIST_DETAILS_CONFIRM,
    INPUT_WATCHLIST_FROM_YEAR,
    INPUT_WATCHLIST_TO_YEAR,
    INPUT_WATCHLIST_MILES,
    INPUT_WATCHLIST_PRICE,
    INPUT_CAR_PARAMETERS,
    SELECT_WATCHLIST,
    SELECT_WATCHLIST_ACTION,
    SELECT_WATCHLIST_FOR_EDITING,
    SELECT_WATCHLIST_FOR_REMOVAL,
    LIST_MATCHING_CARS,
    INPUT_FEEDBACK,
    CANCEL,
) = range(17)
MODEL_PAGE_SIZE = 39
INVALID_INPUT_MESSAGE = 'Sorry, I don\'t understand :( Please try again'

RE_WATCHLIST = re.compile(r'(?P<make>\w+) (?P<model>\w+) (?P<min_year>\d+) (?P<max_year>\d+) (?P<max_mileage>\d+) (?P<max_price>\d+)', flags=re.IGNORECASE)
RE_YEAR = re.compile(r'(?P<year>19\d{2}|20\d{2})$', flags=re.IGNORECASE)
RE_NUMBER = re.compile(r'(?P<number>\d+)', flags=re.IGNORECASE)
HOURGLASS_ICON = u'\U000023F3'
ROCKET_ICON = u'\U0001F680'
MAX_TOTAL_CARS = 30


def build_watchlist(user, raw_watchlist):
    watchlist_doc = {
        'userId': user['_id'],
        'make': raw_watchlist['make'],
        'model': raw_watchlist['model'],
    }
    if raw_watchlist.get('min_year') and raw_watchlist.get('max_year'):
        year = {
            'min': int(raw_watchlist['min_year']),
            'max': int(raw_watchlist['max_year']),
        }
        watchlist_doc['year'] = year
    if raw_watchlist.get('max_mileage'):
        mileage = int(raw_watchlist['max_mileage'])
        watchlist_doc['mileage'] = {
            'max': mileage,
        }
    if raw_watchlist.get('max_price'):
        price = int(raw_watchlist['max_price'])
        watchlist_doc['price'] = {
            'max': price,
        }

    return watchlist_doc


def start(update, context):
    menu_options = [
        [KeyboardButton('/find_car')],
        [KeyboardButton('/list_watchlists')],
        [KeyboardButton('/add_watchlist')],
        [KeyboardButton('/edit_watchlist')],
        [KeyboardButton('/remove_watchlist')],
        [KeyboardButton('/list_matching_cars')],
        [KeyboardButton('/contact_us')],
    ]

    keyboard = ReplyKeyboardMarkup(menu_options)

    update.message.reply_text('Please choose:', reply_markup=keyboard)


def cancel_action(query, message):
    query.answer()
    query.bot.send_message(query.message.chat_id, message, parse_mode=ParseMode.MARKDOWN)
    return ConversationHandler.END


def restart(update, context):
    update.message.reply_text('You don\'t have any watchlists')
    return start(update, context)


def list_watchlists(update, context):
    user = get_user(update.effective_user.id)
    watchlists = get_watchlists(user)

    if not watchlists:
        return restart(update, context)

    reply_markup = get_watchlists_keyboard(watchlists)
    update.message.reply_text('Your watchlists:', reply_markup=reply_markup)
    return SELECT_WATCHLIST


def show_watchlist_actions(update, context):
    query = update.callback_query
    watchlist_id = query.data
    if watchlist_id == '/cancel':
        return cancel_action(query, 'Cancelled')

    query.answer()
    context.user_data['watchlist_id'] = watchlist_id
    options = [
        'View matching cars',
        'Edit watchlist',
        'Remove watchlist'
    ]
    keyboard = [
        [InlineKeyboardButton(option, callback_data=str(option))]
        for option in options
    ] + [[InlineKeyboardButton('/cancel', callback_data='/cancel')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.bot.send_message(query.message.chat_id, 'Select option:', reply_markup=reply_markup)
    return SELECT_WATCHLIST_ACTION


def perform_watchlist_action(update, context):
    query = update.callback_query
    option = query.data
    if option == '/cancel':
        return cancel_action(query, 'Cancelled')

    watchlist_id = context.user_data['watchlist_id']
    if option == 'View matching cars':
        show_matching_car(query, watchlist_id, update, context)
        return ConversationHandler.END

    if option == 'Edit watchlist':
        query.answer()
        return input_watchlist(update, context)

    if option == 'Remove watchlist':
        perform_watchlist_removal(query, watchlist_id)
        return ConversationHandler.END


def list_matching_cars(update, context):
    user = get_user(update.effective_user.id)
    watchlists = get_watchlists(user)

    if not watchlists:
        return restart(update, context)

    reply_markup = get_watchlists_keyboard(watchlists)
    update.message.reply_text('Select watchlist to list matching cars:', reply_markup=reply_markup)
    return LIST_MATCHING_CARS


def list_cars_watchlist_selected(update, context):
    query = update.callback_query
    watchlist_id = query.data
    if watchlist_id == '/cancel':
        return cancel_action(query, 'Cancelled')
    show_matching_car(query, watchlist_id, update, context)
    return ConversationHandler.END


def show_matching_car(query, watchlist_id, update, context):
    try:
        watchlist = get_watchlist(watchlist_id)
        query.answer()
        if not watchlist:
            query.edit_message_text('Error: such watchlist does not exist anymore')
            return start(update, context)

        find_and_print_cars(update, query, watchlist)
    except:
        query.bot.send_message(query.message.chat_id, 'An error occurred when listing cars', parse_mode=ParseMode.MARKDOWN)
    return ConversationHandler.END


def find_and_print_cars(update, query, watchlist):
    (cars, car_count) = get_cars(watchlist, MAX_TOTAL_CARS)
    if not cars:
        query.bot.send_message(query.message.chat_id, 'No cars found', parse_mode=ParseMode.MARKDOWN)
    else:
        query.bot.send_message(query.message.chat_id, f'Found {car_count} matching cars', parse_mode=ParseMode.MARKDOWN)
        print_cars(update, cars, car_count)


def print_cars(update, cars, count):
    query = update.callback_query
    for i, car in enumerate(cars):
        (url, message) = get_car_message(car)
        query.bot.send_message(query.message.chat_id, f'{i + 1}.\n{message}')
    if count > len(cars):
        query.bot.send_message(query.message.chat_id, f'Displayed first {MAX_TOTAL_CARS} of out {count} cars.\n\nDue to Telegram limitations we can\'t display more.\n\nBut it\'ll be possible in our website that\'s coming soon {ROCKET_ICON}\n\nStay tuned!', parse_mode=ParseMode.MARKDOWN)


def print_watchlists(update, watchlists):
    for i, s in enumerate(watchlists):
        watchlist_text = print_watchlist(s)
        update.message.reply_text(f'*{i + 1}*:\n\n{watchlist_text}', parse_mode=ParseMode.MARKDOWN)


def print_watchlist(watchlist):
    make = watchlist['make']
    model = watchlist['model']
    printing_watchlist = f'Make: *{make}*\nModel: *{model}*'
    if watchlist.get('year'):
        min_year = watchlist['year']['min']
        max_year = watchlist['year']['max']
        printing_watchlist += f'\nYears: *{min_year}-{max_year}*'
    if watchlist.get('mileage'):
        max_mileage = watchlist['mileage']['max']
        printing_watchlist += f'\nMax mileage: *{max_mileage}*'
    if watchlist.get('price'):
        max_price = watchlist['price']['max']
        printing_watchlist += f'\nMax price: *{max_price}*'
    return printing_watchlist


def print_watchlist_short(watchlist):
    make = watchlist['make']
    model = watchlist['model']
    watchlist_str = f'{make} {model}'
    if watchlist.get('year'):
        min_year = int(watchlist['year']['min'])
        max_year = int(watchlist['year']['max'])
        watchlist_str += f' {min_year}-{max_year}'
    if watchlist.get('mileage'):
        max_mileage = int(watchlist['mileage']['max'])
        watchlist_str += f' {max_mileage}mi'
    if watchlist.get('price'):
        max_price = int(watchlist['price']['max'])
        watchlist_str += f' {max_price}'
    return watchlist_str


def get_watchlists_keyboard(watchlists):
    keyboard = create_buttons(
        watchlists,
        button_getter=lambda x: [x],
        caption_getter=print_watchlist_short,
        value_getter=lambda x: str(x['_id']),
    )
    keyboard.append([InlineKeyboardButton('/cancel', callback_data='/cancel')])
    return InlineKeyboardMarkup(keyboard)


def add_watchlist(update, context):
    context.user_data.pop('watchlist_id', None)
    context.user_data.pop('find_car', None)
    return input_watchlist(update, context)


def get_reply_func(update):
    query = update.callback_query

    if query:
        return lambda text, reply_markup: query.bot.send_message(query.message.chat_id, text, reply_markup=reply_markup)
    return update.message.reply_text


def input_watchlist(update, context):
    buttons = create_buttons(list(LETTER_MAKE_MODEL.keys()))
    buttons.append(InlineKeyboardButton(text='/cancel', callback_data='/cancel'))

    letter_keyboard = create_menu(buttons, n_cols=4)
    reply_func = get_reply_func(update)
    reply_func('Select make first letter:', reply_markup=letter_keyboard)
    return INPUT_WATCHLIST_LETTER


def watchlist_letter_inputted(update, context):
    query = update.callback_query
    letter = query.data
    if letter == '/cancel':
        return cancel_action(query, 'Adding watchlist cancelled')
    query.answer()

    context.user_data['letter'] = letter
    buttons = create_buttons(list(LETTER_MAKE_MODEL[letter].keys()))
    buttons.append(InlineKeyboardButton(text='/cancel', callback_data='/cancel'))
    make_keyboard = create_menu(buttons, n_cols=2)
    query.bot.send_message(query.message.chat_id, 'Select make:', reply_markup=make_keyboard)
    return INPUT_WATCHLIST_MAKE


def watchlist_make_inputted(update, context):
    query = update.callback_query
    make = query.data
    if make == '/cancel':
        return cancel_action(query, 'Adding watchlist cancelled')

    query.answer()
    context.user_data['watchlist'] = {'make': make}
    letter = context.user_data['letter']
    models = [
        model['title']
        for model in LETTER_MAKE_MODEL[letter][make]['models']
    ]

    if len(models) > MODEL_PAGE_SIZE:
        model_page = 0
        model_pages = list(chunks(models, MODEL_PAGE_SIZE))
        models = model_pages[model_page]
        model_page += 1
        context.user_data['model_pages'] = model_pages
        context.user_data['model_page'] = model_page
        return list_models(query, models, has_more_models=True)

    return list_models(query, models, has_more_models=False)


def list_models(query, models, has_more_models=False):
    buttons = create_buttons(models)
    if has_more_models:
        buttons.append(InlineKeyboardButton(text='more...', callback_data='more'))
        result = INPUT_WATCHLIST_MORE_MODELS
    else:
        buttons.append(InlineKeyboardButton(text='/cancel', callback_data='/cancel'))
        result = INPUT_WATCHLIST_MODEL

    model_keyboard = create_menu(buttons, n_cols=2)
    query.bot.send_message(query.message.chat_id, 'Select model:', reply_markup=model_keyboard)
    return result


def watchlist_more_models_selected(update, context):
    query = update.callback_query
    model = query.data
    if model != 'more':
        return watchlist_model_inputted(update, context)
    query.answer()

    model_pages = context.user_data['model_pages']
    model_page = context.user_data['model_page']
    models = model_pages[model_page]
    model_page += 1
    context.user_data['model_page'] = model_page

    has_more_models = model_page < len(model_pages)
    return list_models(query, models, has_more_models)


def watchlist_model_inputted(update, context):
    query = update.callback_query
    model = query.data
    if model == '/cancel':
        return cancel_action(query, 'Adding watchlist cancelled')
    query.answer()

    context.user_data['watchlist']['model'] = model
    user = get_user(update.effective_user.id)
    watchlist = build_watchlist(user, context.user_data['watchlist'])

    if context.user_data.get('find_car'):
        confirm_details_keyboard = get_confirm_details_keyboard('Find car')
    else:
        confirm_details_keyboard = get_confirm_details_keyboard('Save watchlist')

    query.bot.send_message(query.message.chat_id, print_watchlist(watchlist), parse_mode=ParseMode.MARKDOWN)
    query.bot.send_message(query.message.chat_id, 'Please choose:', reply_markup=confirm_details_keyboard)
    return INPUT_WATCHLIST_DETAILS_CONFIRM


def get_confirm_details_keyboard(first_button):
    options = [first_button, 'Add more details']
    buttons = create_buttons(options)
    buttons.append(InlineKeyboardButton(text='/cancel', callback_data='/cancel'))
    confirm_details_keyboard = create_menu(buttons, n_cols=2)
    return confirm_details_keyboard


def save_watchlist(update, context):
    query = update.callback_query
    try:
        query.answer()
        user = get_user(update.effective_user.id)
        watchlist = build_watchlist(user, context.user_data['watchlist'])
        watchlist['userId'] = user['_id']
        if context.user_data.get('watchlist_id'):
            result = watchlist_edited(query, watchlist, context)
        else:
            result = watchlist_added(query, watchlist)
    except:
        query.bot.send_message(query.message.chat_id, 'An error occurred when adding watchlist', parse_mode=ParseMode.MARKDOWN)
    return result


def confirm_watchlist_details(update, context):
    query = update.callback_query
    user_answer = query.data
    if user_answer == '/cancel' or user_answer == 'No':
        return cancel_action(query, 'Adding watchlist cancelled')
    if user_answer == 'Save watchlist' or user_answer == 'Yes':
        return save_watchlist(update, context)
    if user_answer == 'Find car':
        return car_query_inputted(update, context)

    try:
        query.answer()
        options = [
            'Add year',
            'Add max mileage',
            'Add max price'
        ]
        buttons = create_buttons(options)
        buttons.append(InlineKeyboardButton(text='/cancel', callback_data='/cancel'))
        options_keyboard = create_menu(buttons, n_cols=3)
        query.bot.send_message(query.message.chat_id, 'Please choose:', reply_markup=options_keyboard)
    except:
        query.bot.send_message(query.message.chat_id, 'An error occurred when listing cars', parse_mode=ParseMode.MARKDOWN)

    return INPUT_CAR_PARAMETERS


def input_car_parameters(update, context):
    query = update.callback_query
    option = query.data
    if option == '/cancel':
        return cancel_action(query, 'Adding watchlist cancelled')

    if option == 'Add year':
        query.answer()
        year_keyboard = get_years_keyboard()
        query.bot.send_message(query.message.chat_id, 'Select from year:', reply_markup=year_keyboard)
        return INPUT_WATCHLIST_FROM_YEAR

    if option == 'Add max mileage':
        query.answer()
        query.bot.send_message(query.message.chat_id, 'Input max mileage:', parse_mode=ParseMode.MARKDOWN)
        return INPUT_WATCHLIST_MILES

    if option == 'Add max price':
        query.answer()
        query.bot.send_message(query.message.chat_id, 'Input max price:', parse_mode=ParseMode.MARKDOWN)
        return INPUT_WATCHLIST_PRICE


def back_confirm_watchlist_details(update, context):
    query = update.callback_query
    user = get_user(update.effective_user.id)
    watchlist = build_watchlist(user, context.user_data['watchlist'])
    if context.user_data.get('find_car'):
        confirm_details_keyboard = get_confirm_details_keyboard('Find car')
    else:
        confirm_details_keyboard = get_confirm_details_keyboard('Save watchlist')
    if query:
        query.answer()
        query.bot.send_message(query.message.chat_id, print_watchlist(watchlist), parse_mode=ParseMode.MARKDOWN)
        query.bot.send_message(query.message.chat_id, 'Please choose:', reply_markup=confirm_details_keyboard)
        return INPUT_WATCHLIST_DETAILS_CONFIRM
    update.message.reply_text(print_watchlist(watchlist), parse_mode=ParseMode.MARKDOWN)
    update.message.reply_text('Please choose:', reply_markup=confirm_details_keyboard)
    return INPUT_WATCHLIST_DETAILS_CONFIRM


def get_years_keyboard():
    years = [x for x in range(2000, 2021)]
    buttons = create_buttons(years)
    buttons.append(InlineKeyboardButton(text='/cancel', callback_data='/cancel'))
    return create_menu(buttons, n_cols=3)


def watchlist_from_year_inputted(update, context):
    query = update.callback_query
    from_year = query.data
    if from_year == '/cancel':
        return back_confirm_watchlist_details(update, context)
    context.user_data['watchlist']['min_year'] = from_year
    query.answer()
    year_keyboard = get_years_keyboard()
    query.bot.send_message(query.message.chat_id, 'Select to year:', reply_markup=year_keyboard)
    return INPUT_WATCHLIST_TO_YEAR


def watchlist_to_year_inputted(update, context):
    query = update.callback_query
    to_year = query.data
    if to_year != '/cancel':
        context.user_data['watchlist']['max_year'] = to_year

    return back_confirm_watchlist_details(update, context)


def watchlist_miles_inputted(update, context):
    match = RE_NUMBER.search(update.message.text)
    if not match:
        update.message.reply_text(INVALID_INPUT_MESSAGE)
        return watchlist_model_inputted(update, context)

    miles = match.group('number')
    context.user_data['watchlist']['max_mileage'] = miles
    return back_confirm_watchlist_details(update, context)


def watchlist_price_inputted(update, context):
    match = RE_NUMBER.search(update.message.text)
    if not match:
        update.message.reply_text(INVALID_INPUT_MESSAGE)
        return watchlist_model_inputted(update, context)

    price = match.group('number')
    context.user_data['watchlist']['max_price'] = price
    return back_confirm_watchlist_details(update, context)


def find_car(update, context):
    context.user_data['find_car'] = True
    return input_watchlist(update, context)


def car_query_inputted(update, context):
    query = update.callback_query
    try:
        query.answer()
        query.bot.send_message(query.message.chat_id, f'Searching {HOURGLASS_ICON} Please wait', parse_mode=ParseMode.MARKDOWN)

        # FIXME redundant build_watchlist call
        user = get_user(update.effective_user.id)
        watchlist = build_watchlist(user, context.user_data['watchlist'])

        find_and_print_cars(update, query, watchlist)
    except:
        query.bot.send_message(query.message.chat_id, 'An error occurred when finding watchlist', parse_mode=ParseMode.MARKDOWN)
    return offer_save_watchlist(update, context)


def offer_save_watchlist(update, context):
    query = update.callback_query
    buttons = create_buttons(['Yes', 'No'])
    answers_keyboard = create_menu(buttons, n_cols=2)
    query.bot.send_message(query.message.chat_id, 'Would you like to get notifications about new such cars?', reply_markup=answers_keyboard)
    return INPUT_WATCHLIST_DETAILS_CONFIRM


def watchlist_added(query, watchlist):
    insert_watchlist_db(watchlist)
    query.bot.send_message(query.message.chat_id, f'Watchlist added:\n' + print_watchlist(watchlist), parse_mode=ParseMode.MARKDOWN)
    return ConversationHandler.END


def watchlist_edited(query, watchlist, context):
    watchlist_id = context.user_data['watchlist_id']
    update_watchlist_db(watchlist_id, watchlist)
    context.user_data.pop('watchlist_id', None)
    query.bot.send_message(query.message.chat_id, 'Watchlist has been edited\nWhat else can I do for you?', parse_mode=ParseMode.MARKDOWN)
    return ConversationHandler.END


def edit_watchlist(update, context):
    context.user_data.pop('find_car', None)
    user = get_user(update.effective_user.id)
    watchlists = get_watchlists(user)

    if not watchlists:
        return restart(update, context)

    watchlists_keyboard = get_watchlists_keyboard(watchlists)
    update.message.reply_text('Select watchlist to edit:', reply_markup=watchlists_keyboard)
    return SELECT_WATCHLIST_FOR_EDITING


def watchlist_selected_for_edit(update, context):
    query = update.callback_query
    watchlist_id = query.data
    if watchlist_id == '/cancel':
        return cancel_action(query, 'Editing watchlist cancelled')

    query.answer()
    context.user_data['watchlist_id'] = watchlist_id
    return input_watchlist(update, context)


def remove_watchlist(update, context):
    user = get_user(update.effective_user.id)
    watchlists = get_watchlists(user)

    if not watchlists:
        return restart(update, context)

    reply_markup = get_watchlists_keyboard(watchlists)
    update.message.reply_text('Select watchlist to remove:', reply_markup=reply_markup)
    return SELECT_WATCHLIST_FOR_REMOVAL


def watchlist_selected_for_removal(update, context):
    query = update.callback_query
    watchlist_id = query.data
    if watchlist_id == '/cancel':
        return cancel_action(query, 'Removing watchlist cancelled')

    perform_watchlist_removal(query, watchlist_id)
    return ConversationHandler.END


def perform_watchlist_removal(query, watchlist_id):
    try:
        remove_watchlist_db(watchlist_id)
        query.answer()
        query.bot.send_message(query.message.chat_id, 'Watchlist has been removed\nWhat else can I do for you?', parse_mode=ParseMode.MARKDOWN)
    except:
        query.bot.send_message(query.message.chat_id, 'An error occurred when removing watchlist', parse_mode=ParseMode.MARKDOWN)


def contact_us(update, context):
    update.message.reply_text('What can we do for you?\nPlease input your message')
    return INPUT_FEEDBACK


def feedback_inputted(update, context):
    user = get_user(update.effective_user.id)
    insert_feedback(user, update.message.text)
    update.message.reply_text('Thank you! We\'re on it.')
    return ConversationHandler.END


def cancel_conversation(update, context):
    start(update, context)
    return ConversationHandler.END


def help(update, context):
    update.message.reply_text('Use /start to test this bot.')


def error(update, context):
    '''Log Errors caused by Updates.'''
    logging.getLogger().warning(f'Update {update} caused error {context.error}')
