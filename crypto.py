from flask import Blueprint
crypto_bp = Blueprint('crypto', __name__)

@crypto_bp.route('/')
def placeholder():
    return {'status': 'Crypto route placeholder'}
