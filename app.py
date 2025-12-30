from flask import Flask
from routes.health import health_bp
from routes.crypto import crypto_bp
from routes.jupiter import jupiter_bp
from routes.twitterRapid import twitter_bp
from routes.intel import intel_bp
from routes.discord import discord_bp
from routes.telegram import telegram_bp
from routes.commerce import commerce_bp
from routes.geo import geo_bp
from routes.weather import weather_bp
from utils.scheduler import start_scheduler

app = Flask(__name__)

# Register blueprints
app.register_blueprint(health_bp, url_prefix="/healthz")
app.register_blueprint(crypto_bp, url_prefix="/crypto")
app.register_blueprint(jupiter_bp, url_prefix="/jupiter")
app.register_blueprint(twitter_bp, url_prefix="/twitterRapid")
app.register_blueprint(intel_bp, url_prefix="/intel")
app.register_blueprint(discord_bp, url_prefix="/discord")
app.register_blueprint(telegram_bp, url_prefix="/telegram")
app.register_blueprint(commerce_bp, url_prefix="/commerce")
app.register_blueprint(geo_bp, url_prefix="/geo")
app.register_blueprint(weather_bp, url_prefix="/weather")

@app.route("/")
def home():
    return "🧠 MirroraX Flask Backend Active"

if __name__ == "__main__":
    start_scheduler()
    app.run(host="0.0.0.0", port=10000)
