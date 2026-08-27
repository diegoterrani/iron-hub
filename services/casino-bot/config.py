import os

from dotenv import load_dotenv

load_dotenv()


def _csv_ints(raw: str) -> list:
    out = []
    for part in (raw or "").split(","):
        part = part.strip()
        if part.isdigit():
            out.append(int(part))
    return out


# Runtime — only from environment. Upstream repo shipped live payment keys; do not restore them.
admin = _csv_ints(os.getenv("ADMIN_IDS", ""))
support_name = os.getenv("SUPPORT_NAME", "@iron_lab")
token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
client_id = os.getenv("YOOMONEY_CLIENT_ID", "")
number_qiwi = os.getenv("QIWI_NUMBER", "")
token_qiwi = os.getenv("QIWI_TOKEN", "")
token_youmoney = os.getenv("YOOMONEY_TOKEN", "")
p2p_closed_token = os.getenv("QIWI_P2P_SECRET", "")
open_coinbase = os.getenv("COINBASE_API_KEY", "")
close_coinbase = os.getenv("COINBASE_API_SECRET", "")
secret_crystal = os.getenv("CRYSTALPAY_SECRET", "")
login_crystal = os.getenv("CRYSTALPAY_LOGIN", "")
yoomoney_receiver = os.getenv("YOOMONEY_RECEIVER", "")
DB_PATH = os.getenv("DB_PATH", "bebra.db")

# Defaults used as mutable session state by the original bot
balance = 0
referals_ = 0
bill_id = None
photo_id = None
text = None
auto_output = 0
amount = None
bet = 0
game = None
referal_level = 1
referer = None
referal_profit = 0
ban = 0
cash = 0
method = None
voucher = None
promo = None
winning = 0
demobalance = 0
