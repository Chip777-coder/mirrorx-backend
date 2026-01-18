import requests
import os

API_KEY = os.getenv("APISPORTS_KEY")
BASE_URL = "https://v1.api-sports.io/baseball"

HEADERS = {
    "x-rapidapi-key": API_KEY,
    "x-rapidapi-host": "v1.api-sports.io",
}

def get_mlb_games(date: str):
    response = requests.get(
        f"{BASE_URL}/games",
        headers=HEADERS,
        params={"date": date}
    )
    if response.status_code == 200:
        return response.json().get("response", [])
    return []
