from flask_socketio import SocketIO, emit
from src.services.coinmarketcap import get_cmc_listings
socketio = SocketIO(cors_allowed_origins="*")

def push_fusion_update():
    data = get_cmc_listings()
    socketio.emit("fusion_update", {"data": data})
