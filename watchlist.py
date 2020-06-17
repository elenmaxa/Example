from flask import request, Response
from flask_cors import CORS
from bson.objectid import ObjectId
import json
from models import db
from pymongo import ASCENDING, DESCENDING
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import app
from routes.processes import is_not_valid, create_response
from models.utils import get_filters
from utils.make_model_utils import MAKE_WITH_MODEL_NAMES
from flask import jsonify, request
from services.watchlists import fetch_matching_cars


CORS(app)


@app.route('/users/me/watchlists', methods=['GET'])
@jwt_required
def get_watchlists():
    current_user_id = get_jwt_identity()

    watchlists = list(db['watchlists'].find(
       {'userId': ObjectId(current_user_id)} 
    ))
    return create_response(json.dumps(watchlists, default=str))


@app.route('/watchlists', methods=['POST'])
@jwt_required
def add_watchlist():
    current_user_id = get_jwt_identity()
    req = request.get_json()
    watchlist = {
        'userId' : ObjectId(current_user_id),
        'make' : req.get('make'),
        'model' : req.get('model'),
    }
    if req.get('fromYear') and req.get('toYear'):
        watchlist['year'] = {
            'min' : req.get('fromYear'),
            'max' : req.get('toYear')
        }
    if req.get('maxMileage'):
         watchlist['mileage'] = {
            'max' : req.get('maxMileage')
        }
    if req.get('maxPrice'):
        watchlist['price'] = {
            'max' : req.get('maxPrice')
        }
    db['watchlists'].insert_one(watchlist)
    return create_response()


@app.route('/watchlists/<id>', methods=['PATCH'])
@jwt_required
def update_watchlist_by_id(id):
    if is_not_valid(id):
        return create_response(is_not_valid(id), 400)
    current_user_id = get_jwt_identity()
    watchlist = db['watchlists'].find_one(
        {'_id': ObjectId(id)}
    )
    req = request.get_json()
    if not watchlist:
        return create_response(f'Watchlist with id: {id} does not exist', 404)
    if str(watchlist['userId']) != current_user_id:
        return create_response(f'User not authorized to update this watchlist', 403)
    db['watchlists'].update_one(
        {'_id': ObjectId(id)},
        {'$set': req}
    )
    return create_response()


@app.route('/watchlists/<id>', methods=['DELETE'])
@jwt_required
def delete_watchlist_by_id(id):
    if is_not_valid(id):
        return create_response(is_not_valid(id), 400)
    current_user_id = get_jwt_identity()
    watchlist = db['watchlists'].find_one(
        {'_id': ObjectId(id)}
    )
    if not watchlist:
        return create_response(f'Watchlist with id: {id} does not exist', 404)
    if str(watchlist['userId']) != current_user_id:
        return create_response(f'User not authorized to delete this watchlist', 403)
    db['watchlists'].delete_one({'_id': ObjectId(id)})
    return create_response()


@app.route('/watchlists/<id>/cars', methods=['GET'])
@jwt_required
def get_matching_cars(id):
    if is_not_valid(id):
        return create_response(is_not_valid(id), 400)
    current_user_id = get_jwt_identity()
    watchlist = db['watchlists'].find_one(
        {'_id': ObjectId(id)}
    )
    if not watchlist:
        return create_response(f'Watchlist with id: {id} does not exist', 404)
    if str(watchlist['userId']) != current_user_id:
        return create_response(f'User not authorized to view this watchlist', 403)
    
    limit = int(request.args.get('limit', 10))
    (cars, count) = fetch_matching_cars(db, watchlist, limit=limit)
    resp = create_response(json.dumps(cars, default=str))
    resp.headers['X-Total-Count'] = str(count)
    return resp
