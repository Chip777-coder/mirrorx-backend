from services.agents.wallet_watch import run as wallet_watch
from services.agents.whale_flow import run as whale_flow
from services.agents.pump_dump_detector import run as pump_dump_detector
from services.agents.liquidity_guard import run as liquidity_guard

AVAILABLE_AGENTS = {
    "wallet_watch": wallet_watch,
    "whale_flow": whale_flow,
    "pump_dump_detector": pump_dump_detector,
    "liquidity_guard": liquidity_guard,
}
