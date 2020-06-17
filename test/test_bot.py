# flake8: noqa
import pytest
import os
import mock
import ptbtest
import pymongo
from bson.objectid import ObjectId
from bot.handlers import (
    watchlist_letter_inputted,
    watchlist_make_inputted,
    watchlist_model_inputted,
    watchlist_more_models_selected,
    watchlist_from_year_inputted,
    watchlist_to_year_inputted,
    watchlist_miles_inputted,
    watchlist_price_inputted,
    confirm_watchlist_details,
    list_watchlists,
    show_watchlist_actions,
    input_car_parameters,
    perform_watchlist_action,
    add_watchlist,
    edit_watchlist,
    watchlist_selected_for_edit,
    remove_watchlist,
    watchlist_selected_for_removal,
    list_matching_cars,
    list_cars_watchlist_selected,
    find_car
)
from bot.release import send_new_release_message
from bot.db import _set_db
import mongomock
import json
from telegram.ext import Dispatcher
from telegram import Message
from datetime import datetime
from services import notification
from freezegun import freeze_time


REAL_TEST_MONGODB_URI = os.environ['REAL_TEST_MONGODB_URI']
REAL_TEST_MONGODB_DB = os.environ['REAL_TEST_MONGODB_DB']

DEFAULT_CAR_ITEM = {
    'post': [
        {
            'platform': 'craigslist',
            'city': 'city',
            'sellerId': 'sellerId',
            'postId': 'postId1',
            'postUrl': 'postUrl',
            'postDate': datetime.utcnow(),
        },
    ],
    'title': 'title',
    'description': ['text'],
    'photos': ['url1', 'url2'],
    'address': {
        'line1': 'line1',
        'lat': 'lat',
        'lon': 'lon'
    },
    'mileage': 96202,
    'price': {
        'amount': 5000,
        'currency': 'USD'
    },
    'carInfo': {
        'year': 2015,
        'make': 'Honda',
        'model': 'Saber',
        'vin': 'SOMEVIN',
    },
    'dealer': 'dealer'
}


def init_telegram():
    mock_bot = ptbtest.Mockbot()
    update = ptbtest.MessageGenerator(bot=mock_bot).get_message()
    telegram_user_id = update.effective_user.id
    return (mock_bot, update, telegram_user_id)


def get_user_chat_telegram_message(update):
    user = update.effective_user
    chat = update.effective_chat
    telegram_message = Message(message_id='1', from_user=user, date=datetime.today(), chat=chat)
    return(user, chat, telegram_message)


def get_mock_callback_query(mock_bot, update, data):
    mock_callback_query = ptbtest.callbackquerygenerator.CallbackQueryGenerator(bot=mock_bot)
    (user, chat, telegram_message) = get_user_chat_telegram_message(update)
    update = mock_callback_query.get_callback_query(user=user, message=telegram_message, data=data)
    return update


def get_mock_message(mock_bot, update, text):
    mock_mesasage = ptbtest.MessageGenerator(bot=mock_bot)
    (user, chat, telegram_message) = get_user_chat_telegram_message(update)
    update = mock_mesasage.get_message(user=user, chat=chat, reply_to_message=telegram_message, text=text)
    return update


def test_list_watchlists_empty_db():
    (mock_bot, update, telegram_user_id) = init_telegram()

    list_watchlists(update, context={})

    assert mock_bot.sent_messages == [
        {
            'chat_id': telegram_user_id,
            'method': 'sendMessage',
            'text': "You don't have any watchlists"
        },
        {
            'chat_id': telegram_user_id,
            'method': 'sendMessage',
            'reply_markup': json.dumps(
                {
                    'keyboard':
                    [
                        [{'text': '/find_car'}],
                        [{'text': '/list_watchlists'}],
                        [{'text': '/add_watchlist'}],
                        [{'text': '/edit_watchlist'}],
                        [{'text': '/remove_watchlist'}],
                        [{'text': '/list_matching_cars'}],
                        [{'text': '/contact_us'}],
                    ],
                    'resize_keyboard': False,
                    'one_time_keyboard': False,
                    'selective': False}),
            'text': 'Please choose:'
        }
    ]


def test_list_watchlists():
    (mock_bot, update, telegram_user_id) = init_telegram()
    from bot.db import db
    user = {
        'telegram': {
            'id': telegram_user_id
        }
    }
    user_id = db.users.insert(user)

    watchlist = {
        'userId': user_id,
        'make': 'Toyota',
        'model': 'Prius',
        'year': {
            'min': 2004,
            'max': 2009
        },
        'mileage': {
            'max': 200000
        },
        'price': {
            'max': 3500
        }
    }
    watchlist_id = db.watchlists.insert(watchlist)

    list_watchlists(update, context={})

    assert mock_bot.sent_messages == [
        {
            'chat_id': telegram_user_id,
            'method': 'sendMessage',
            'reply_markup': json.dumps(
                {
                    'inline_keyboard': [
                        [
                            {
                                'text': 'Toyota Prius 2004-2009 200000mi 3500',
                                'callback_data': str(watchlist_id)
                            }
                        ],
                        [
                            {
                                'text': '/cancel',
                                'callback_data': '/cancel'
                            }
                        ]
                    ]
                }),
            'text': 'Your watchlists:'
        }
    ]


def test_add_min_watchlist():
    (mock_bot, update, telegram_user_id) = init_telegram()
    from bot.db import db
    user = {
        'telegram': {
            'id': telegram_user_id
        }
    }
    user_id = db.users.insert(user)
    context = Dispatcher(bot=mock_bot, update_queue=update)

    add_watchlist(update, context)
    update = get_mock_callback_query(mock_bot, update, data='T')
    watchlist_letter_inputted(update, context)
    update = get_mock_callback_query(mock_bot, update, data='Toyota')
    watchlist_make_inputted(update, context)
    update = get_mock_callback_query(mock_bot, update, data='Aqua')
    watchlist_model_inputted(update, context)
    update = get_mock_callback_query(mock_bot, update, data='Save watchlist')
    confirm_watchlist_details(update, context)

    watchlist = db.watchlists.find_one({'userId': user_id})

    assert watchlist['make'] == 'Toyota'
    assert watchlist['model'] == 'Aqua'
    assert watchlist.get('year') == None
    assert watchlist.get('mileage') == None
    assert watchlist.get('price') == None


def test_add_half_watchlist():
    (mock_bot, update, telegram_user_id) = init_telegram()
    from bot.db import db
    user = {
        'telegram': {
            'id': telegram_user_id
        }
    }
    user_id = db.users.insert(user)
    context = Dispatcher(bot=mock_bot, update_queue=update)

    add_watchlist(update, context)
    update = get_mock_callback_query(mock_bot, update, data='T')
    watchlist_letter_inputted(update, context)
    update = get_mock_callback_query(mock_bot, update, data='Toyota')
    watchlist_make_inputted(update, context)
    update = get_mock_callback_query(mock_bot, update, data='Aqua')
    watchlist_model_inputted(update, context)
    update = get_mock_callback_query(mock_bot, update, data='Add more details')
    confirm_watchlist_details(update, context)
    update = get_mock_callback_query(mock_bot, update, data='Add max mileage')
    input_car_parameters(update, context)
    update = get_mock_message(mock_bot, update, text='200000')
    watchlist_miles_inputted(update, context)
    update = get_mock_callback_query(mock_bot, update, data='Save watchlist')
    confirm_watchlist_details(update, context)

    watchlist = db.watchlists.find_one({'userId': user_id})

    assert watchlist['make'] == 'Toyota'
    assert watchlist['model'] == 'Aqua'
    assert watchlist.get('year') == None
    assert watchlist['mileage']['max'] == 200000
    assert watchlist.get('price') == None


def test_add_full_watchlist():
    (mock_bot, update, telegram_user_id) = init_telegram()
    from bot.db import db
    user = {
        'telegram': {
            'id': telegram_user_id
        }
    }
    user_id = db.users.insert(user)
    context = Dispatcher(bot=mock_bot, update_queue=update)

    add_watchlist(update, context)
    update = get_mock_callback_query(mock_bot, update, data='T')
    watchlist_letter_inputted(update, context)
    update = get_mock_callback_query(mock_bot, update, data='Toyota')
    watchlist_make_inputted(update, context)
    update = get_mock_callback_query(mock_bot, update, data='Aqua')
    watchlist_model_inputted(update, context)
    update = get_mock_callback_query(mock_bot, update, data='Add more details')
    confirm_watchlist_details(update, context)
    update = get_mock_callback_query(mock_bot, update, data='Add year')
    input_car_parameters(update, context)
    update = get_mock_callback_query(mock_bot, update, data='2010')
    watchlist_from_year_inputted(update, context)
    update = get_mock_callback_query(mock_bot, update, data='2020')
    watchlist_to_year_inputted(update, context)
    update = get_mock_callback_query(mock_bot, update, data='Add more details')
    confirm_watchlist_details(update, context)
    update = get_mock_callback_query(mock_bot, update, data='Add max mileage')
    input_car_parameters(update, context)
    update = get_mock_message(mock_bot, update, text='200000')
    watchlist_miles_inputted(update, context)
    update = get_mock_callback_query(mock_bot, update, data='Add more details')
    confirm_watchlist_details(update, context)
    update = get_mock_callback_query(mock_bot, update, data='Add max price')
    input_car_parameters(update, context)
    update = get_mock_message(mock_bot, update, text='15500')
    watchlist_price_inputted(update, context)
    update = get_mock_callback_query(mock_bot, update, data='Save watchlist')
    confirm_watchlist_details(update, context)

    watchlist = db.watchlists.find_one({'userId': user_id})

    assert watchlist['make'] == 'Toyota'
    assert watchlist['model'] == 'Aqua'
    assert watchlist['year'] == {
        'min': 2010,
        'max': 2020
    }
    assert watchlist['mileage']['max'] == 200000
    assert watchlist['price']['max'] == 15500


def test_edit_watchlist():
    (mock_bot, update, telegram_user_id) = init_telegram()
    from bot.db import db
    user = {
        'telegram': {
            'id': telegram_user_id
        }
    }
    user_id = db.users.insert(user)

    watchlist = {
        'userId': user_id,
        'make': 'Honda',
        'model': 'Saber',
        'year': {
            'min': 2004,
            'max': 2009
        },
        'mileage': {
            'max': 300000
        },
        'price': {
            'max': 3500
        }
    }
    watchlist_id = db.watchlists.insert(watchlist)
    context = Dispatcher(bot=mock_bot, update_queue=update)

    edit_watchlist(update, context)
    update = get_mock_callback_query(mock_bot, update, data=str(watchlist_id))
    watchlist_selected_for_edit(update, context)
    update = get_mock_callback_query(mock_bot, update, data='T')
    watchlist_letter_inputted(update, context)
    update = get_mock_callback_query(mock_bot, update, data='Toyota')
    watchlist_make_inputted(update, context)
    update = get_mock_callback_query(mock_bot, update, data='Aqua')
    watchlist_model_inputted(update, context)
    update = get_mock_callback_query(mock_bot, update, data='Add more details')
    confirm_watchlist_details(update, context)
    update = get_mock_callback_query(mock_bot, update, data='Add year')
    input_car_parameters(update, context)
    update = get_mock_callback_query(mock_bot, update, data='2010')
    watchlist_from_year_inputted(update, context)
    update = get_mock_callback_query(mock_bot, update, data='2020')
    watchlist_to_year_inputted(update, context)
    update = get_mock_callback_query(mock_bot, update, data='Add more details')
    confirm_watchlist_details(update, context)
    update = get_mock_callback_query(mock_bot, update, data='Add max mileage')
    input_car_parameters(update, context)
    update = get_mock_message(mock_bot, update, text='200000')
    watchlist_miles_inputted(update, context)
    update = get_mock_callback_query(mock_bot, update, data='Add more details')
    confirm_watchlist_details(update, context)
    update = get_mock_callback_query(mock_bot, update, data='Add max price')
    input_car_parameters(update, context)
    update = get_mock_message(mock_bot, update, text='15500')
    watchlist_price_inputted(update, context)
    update = get_mock_callback_query(mock_bot, update, data='Save watchlist')
    confirm_watchlist_details(update, context)

    old_watchlist = db.watchlists.find_one({'userId': user_id, 'make': 'Honda'})
    watchlist = db.watchlists.find_one({'_id': watchlist_id})

    assert old_watchlist == None
    assert watchlist['make'] == 'Toyota'
    assert watchlist['model'] == 'Aqua'
    assert watchlist['year'] == {
        'min': 2010,
        'max': 2020
    }
    assert watchlist['mileage']['max'] == 200000
    assert watchlist['price']['max'] == 15500


def test_remove_watchlist():
    (mock_bot, update, telegram_user_id) = init_telegram()
    from bot.db import db
    user = {
        'telegram': {
            'id': telegram_user_id
        }
    }
    user_id = db.users.insert(user)

    watchlist_1 = {
        'userId': user_id,
        'make': 'Honda',
        'model': 'Saber',
        'year': {
            'min': 2004,
            'max': 2009
        },
        'mileage': {
            'max': 300000
        },
        'price': {
            'max': 3500
        }
    }
    watchlist_2 = {
        'userId': user_id,
        'make': 'Toyota',
        'model': 'Aqua',
        'year': {
            'min': 2010,
            'max': 2020
        },
        'mileage': {
            'max': 200000
        },
        'price': {
            'max': 15500
        }
    }
    watchlist_1_id = db.watchlists.insert(watchlist_1)
    db.watchlists.insert(watchlist_2)
    context = Dispatcher(bot=mock_bot, update_queue=update)

    remove_watchlist(update, context)
    update = get_mock_callback_query(mock_bot, update, data=str(watchlist_1_id))
    watchlist_selected_for_removal(update, context)

    user_watchlists = list(db.watchlists.find({'userId': user_id}))
    removed_watchlist = db.watchlists.find_one({'_id': watchlist_1_id})

    assert removed_watchlist == None
    assert len(user_watchlists) == 1


@freeze_time("2020-05-01")
def test_list_matching_cars():
    (mock_bot, update, telegram_user_id) = init_telegram()
    client = pymongo.MongoClient(REAL_TEST_MONGODB_URI)
    client.drop_database(REAL_TEST_MONGODB_DB)
    db = client[REAL_TEST_MONGODB_DB]
    _set_db(db)
    user = {
        'telegram': {
            'id': telegram_user_id
        }
    }
    user_id = db.users.insert(user)

    watchlist_1 = {
        'userId': user_id,
        'make': 'Honda',
        'model': 'Saber',
        'year': {
            'min': 2012,
            'max': 2019
        },
        'mileage': {
            'max': 300000
        },
        'price': {
            'max': 7500
        }
    }
    watchlist_2 = {
        'userId': user_id,
        'make': 'Toyota',
        'model': 'Aqua',
        'year': {
            'min': 2010,
            'max': 2020
        },
        'mileage': {
            'max': 200000
        },
        'price': {
            'max': 15500
        }
    }
    watchlist_1_id = db.watchlists.insert(watchlist_1)
    db.watchlists.insert(watchlist_2)
    car_1 = {
        **DEFAULT_CAR_ITEM
    }
    car_2 = {
        **DEFAULT_CAR_ITEM,
        'mileage': 109207,
        'price': {
            'amount': 6200,
            'currency': 'USD'
        },
        'carInfo': {
            'year': 2017,
            'make': 'Honda',
            'model': 'Saber',
            'vin': 'SOMEVIN_2'
        }
    }
    car_3 = {
        **DEFAULT_CAR_ITEM,
        'mileage': 109507,
        'price': {
            'amount': 6000,
            'currency': 'USD'
        },
        'carInfo': {
            'year': 2011,
            'make': 'Honda',
            'model': 'Saber',
            'vin': 'SOMEVIN_3'
        },
    }
    db.cars.remove({})
    db.cars.insert_many([car_1, car_2, car_3])
    context = Dispatcher(bot=mock_bot, update_queue=update)

    list_matching_cars(update, context)
    update = get_mock_callback_query(mock_bot, update, data=str(watchlist_1_id))
    list_cars_watchlist_selected(update, context)

    sent_messages = mock_bot.sent_messages

    assert sent_messages[2] == {
        'chat_id': telegram_user_id,
        'method': 'sendMessage',
        'parse_mode': 'Markdown',
        'text': 'Found 2 matching cars',
    }
    assert sent_messages[3] == {
        'chat_id': telegram_user_id,
        'method': 'sendMessage',
        'text': '1.\n2015 Honda Saber\n96202 miles\n$5000\npostUrl'
    }
    assert sent_messages[4] == {
        'chat_id': telegram_user_id,
        'method': 'sendMessage',
        'text': '2.\n2017 Honda Saber\n109207 miles\n$6200\npostUrl'
    }


@freeze_time("2020-05-01")
def test_find_car():
    (mock_bot, update, telegram_user_id) = init_telegram()
    client = pymongo.MongoClient(REAL_TEST_MONGODB_URI)
    db = client[REAL_TEST_MONGODB_DB]
    client.drop_database(REAL_TEST_MONGODB_DB)
    _set_db(db)
    user = {
        'telegram': {
            'id': telegram_user_id
        }
    }
    user_id = db.users.insert(user)
    car_1 = {
        **DEFAULT_CAR_ITEM
    }
    car_2 = {
        **DEFAULT_CAR_ITEM,
        'mileage': 109207,
        'price': {
            'amount': 6200,
            'currency': 'USD'
        },
        'carInfo': {
            'year': 2017,
            'make': 'Honda',
            'model': 'Saber',
            'vin': 'SOMEVIN_2'
        }
    }
    car_3 = {
        **DEFAULT_CAR_ITEM,
        'mileage': 109507,
        'price': {
            'amount': 6000,
            'currency': 'USD'
        },
        'carInfo': {
            'year': 2011,
            'make': 'Honda',
            'model': 'Saber',
            'vin': 'SOMEVIN_3'
        },
    }
    db.cars.insert_many([car_1, car_2, car_3])
    context = Dispatcher(bot=mock_bot, update_queue=update)

    find_car(update, context)
    update = get_mock_callback_query(mock_bot, update, data='H')
    watchlist_letter_inputted(update, context)
    update = get_mock_callback_query(mock_bot, update, data='Honda')
    watchlist_make_inputted(update, context)
    update = get_mock_callback_query(mock_bot, update, data='Saber')
    watchlist_model_inputted(update, context)
    update = get_mock_callback_query(mock_bot, update, data='Add more details')
    confirm_watchlist_details(update, context)
    update = get_mock_callback_query(mock_bot, update, data='Add year')
    input_car_parameters(update, context)
    update = get_mock_callback_query(mock_bot, update, data='2012')
    watchlist_from_year_inputted(update, context)
    update = get_mock_callback_query(mock_bot, update, data='2019')
    watchlist_to_year_inputted(update, context)
    update = get_mock_callback_query(mock_bot, update, data='Add more details')
    confirm_watchlist_details(update, context)
    update = get_mock_callback_query(mock_bot, update, data='Add max mileage')
    input_car_parameters(update, context)
    update = get_mock_message(mock_bot, update, text='300000')
    watchlist_miles_inputted(update, context)
    update = get_mock_callback_query(mock_bot, update, data='Add more details')
    confirm_watchlist_details(update, context)
    update = get_mock_callback_query(mock_bot, update, data='Add max price')
    input_car_parameters(update, context)
    update = get_mock_message(mock_bot, update, text='7500')
    watchlist_price_inputted(update, context)
    update = get_mock_callback_query(mock_bot, update, data='Find car')
    confirm_watchlist_details(update, context)
    update = get_mock_callback_query(mock_bot, update, data='No')
    confirm_watchlist_details(update, context)

    sent_messages = mock_bot.sent_messages

    assert sent_messages[-6] == {
        'chat_id': telegram_user_id,
        'method': 'sendMessage',
        'parse_mode': 'Markdown',
        'text': 'Found 2 matching cars'
    }
    assert sent_messages[-5] == {
        'chat_id': telegram_user_id,
        'method': 'sendMessage',
        'text': '1.\n2015 Honda Saber\n96202 miles\n$5000\npostUrl'
    }
    assert sent_messages[-4] == {
        'chat_id': telegram_user_id,
        'method': 'sendMessage',
        'text': '2.\n2017 Honda Saber\n109207 miles\n$6200\npostUrl'
    }
    assert sent_messages[-3] == {
        'chat_id': telegram_user_id,
        'method': 'sendMessage',
        'reply_markup': json.dumps({
            'inline_keyboard': [[
                {'text': 'Yes', 'callback_data': 'Yes'},
                {'text': 'No', 'callback_data': 'No'}
            ]]
        }),
        'text': 'Would you like to get notifications about new such cars?'
    }
    assert sent_messages[-1] == {
        'chat_id': telegram_user_id,
        'method': 'sendMessage',
        'parse_mode': 'Markdown',
        'text': 'Adding watchlist cancelled'
    }
