from bson.objectid import ObjectId
from models import db
from app import app
from helpers import create_authorization_headers
import pytest
from datetime import datetime


DEFAULT_CAR = {
    'post': [
        {
        'platform' : 'platform',
        'postId': 'postId',
        'title': 'title',
        }
    ],
    'carInfo' : {
        'year' : 2005,
        'make' : 'Subaru',
        'model' : 'Forester',
    },
    'price' : {
        'amount' : 2250,
        'currency' : 'USD'
    },
    'mileage' : 20000,
}
DEFAULT_USER = {
    'telegram' : {
        'id' : 'id'
    }
}
DEFAULT_DEALER = {
    'address': 'address',
    'phone': '123456789',
    'website': 'website'
}
DEFAULT_WATCHLIST = {
    'make': 'Subaru',
    'model': 'Forester',
    'year': {
        'min': 2000,
        'max': 2020
    },
    'mileage': {
        'max': 100000
    },
    'price': {
        'max': 10000
    }
}

user_id = '5cffffffffffffffffffffff'
email = 'admin@mail.com'
headers = create_authorization_headers(user_id, email)


@pytest.fixture
def clear_db():
    db['cars'].drop()
    db['users'].drop()
    db['dealers'].drop()
    db['watchlists'].drop()


def test_get_watchlists(clear_db):
    user_id = db['users'].insert_one(DEFAULT_USER).inserted_id
    watchlist = {
        **DEFAULT_WATCHLIST,
        'userId': user_id
    }
    watchlist_id = db['watchlists'].insert_one(watchlist).inserted_id
    headers = create_authorization_headers(str(user_id), email)

    with app.test_client() as c:
        rv = c.get(
            f'/users/me/watchlists',
            mimetype="application/json",
            headers=headers
        )

    assert rv.json[0] == {
        '_id': str(watchlist_id),
        'userId': str(user_id),
        'make': 'Subaru',
        'model': 'Forester',
        'year': {
            'min': 2000,
            'max': 2020
        },
        'mileage': {
            'max': 100000
        },
        'price': {
            'max': 10000
        }
    }


def test_add_watchlist(clear_db):
    user_id = db['users'].insert_one(DEFAULT_USER).inserted_id
    headers = create_authorization_headers(str(user_id), email)
    watchlist = {
        'make': 'Subaru',
        'model': 'Forester',
        'maxPrice': 20000 
    }

    with app.test_client() as c:
        rv = c.post(
            f'/watchlists',
            json=watchlist,
            mimetype="application/json",
            headers=headers
        )

    watchlists = list(db['watchlists'].find({'userId': user_id}))

    assert b'' in rv.data
    assert rv.status_code == 200
    assert watchlists[0]['userId'] == user_id
    assert watchlists[0]['make'] == 'Subaru'
    assert watchlists[0]['model'] == 'Forester'
    assert watchlists[0]['price'] == {'max': 20000}
    assert watchlists[0].get('year') is None


def test_update_watchlist_by_id(clear_db):
    user_id = db['users'].insert_one(DEFAULT_USER).inserted_id
    watchlist = {
        **DEFAULT_WATCHLIST,
        'userId': user_id
    }
    watchlist_id = db['watchlists'].insert_one(watchlist).inserted_id
    headers = create_authorization_headers(str(user_id), email)

    with app.test_client() as c:
        rv = c.patch(
            f'/watchlists/{watchlist_id}',
            json={'mileage': {'max': 187000}},
            mimetype="application/json",
            headers=headers
        )

    updated_watchlist = db['watchlists'].find_one({'_id': watchlist_id})

    assert b'' in rv.data
    assert rv.status_code == 200
    assert updated_watchlist == {
        '_id': watchlist_id,
        'userId': user_id,
        'make': 'Subaru',
        'model': 'Forester',
        'year': {
            'min': 2000,
            'max': 2020
        },
        'mileage': {
            'max': 187000
        },
        'price': {
            'max': 10000
        }
    }


def test_delete_watchlist_by_id(clear_db):
    user_id = db['users'].insert_one(DEFAULT_USER).inserted_id
    watchlist_id_1 = db['watchlists'].insert_one(
        {
            **DEFAULT_WATCHLIST,
            'userId': user_id
        }
    ).inserted_id 
    watchlist_id_2 = db['watchlists'].insert_one(
        {
            **DEFAULT_WATCHLIST,
            'make': 'Toyota',
            'model': 'Prius',
            'userId': user_id
        }
    ).inserted_id 
    headers = create_authorization_headers(str(user_id), email)

    with app.test_client() as c:
        rv = c.delete(
            f'/watchlists/{watchlist_id_1}',
            mimetype="application/json",
            headers=headers
        )

    watchlists = list(db['watchlists'].find({'userId': user_id}))

    assert b'' in rv.data
    assert rv.status_code == 200
    assert len(watchlists) == 1
    assert watchlists[0] == {
        '_id': watchlist_id_2,
        'userId': user_id,
        'make': 'Toyota',
            'model': 'Prius',
        'year': {
            'min': 2000,
            'max': 2020
        },
        'mileage': {
            'max': 100000
        },
        'price': {
            'max': 10000
        }
    }


def test_get_matching_cars(clear_db):
    db['cars'].insert_one(DEFAULT_CAR)
    user_id = db['users'].insert_one(DEFAULT_USER).inserted_id
    watchlist_id = db['watchlists'].insert_one(
        {
            **DEFAULT_WATCHLIST,
            'userId': user_id,
            'mileage': {
                'max': 300000
            },
        }
    ).inserted_id 
    headers = create_authorization_headers(str(user_id), email)

    with app.test_client() as c:
        rv = c.get(
            f'/watchlists/{watchlist_id}/cars',
            mimetype="application/json",
            headers=headers
        )

    assert rv.json[0]['post'] == [
        {
        'platform' : 'platform',
        'postId': 'postId',
        'title': 'title',
        }
    ]
    assert rv.json[0]['carInfo'] == {
        'year' : 2005,
        'make' : 'Subaru',
        'model' : 'Forester'
    }
