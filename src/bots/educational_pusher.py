from bots.telegram_bot import send_parlay_to_telegram
from analytics.mirrax.parlay_builder import generate_multiple_parlays

def push_educational_drop():
    parlays = generate_multiple_parlays()
    first_parlay = parlays[0]

    # You can expand this to generate deeper write-ups
    send_parlay_to_telegram(first_parlay)
