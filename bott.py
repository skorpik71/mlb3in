import requests
from datetime import datetime, timedelta, timezone
import time
import os
import threading
from flask import Flask

# Настройки
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
YEKT = timezone(timedelta(hours=5))
LOG_FILE = "mlb_signal_log.txt"
app = Flask(__name__)

# Полный словарь названий команд
TEAM_NAMES = {
    "d-backs": "dbacks", "diamondbacks": "dbacks",
    "white sox": "whitesox", "blue jays": "bluejays",
    "red sox": "redsox", "royals": "royals",
    "tigers": "tigers", "twins": "twins",
    "indians": "guardians", "guardians": "guardians",
    "astros": "astros", "angels": "angels",
    "athletics": "athletics", "mariners": "mariners",
    "rangers": "rangers", "braves": "braves",
    "marlins": "marlins", "mets": "mets",
    "phillies": "phillies", "nationals": "nationals",
    "cubs": "cubs", "reds": "reds",
    "brewers": "brewers", "pirates": "pirates",
    "cardinals": "cardinals", "dodgers": "dodgers",
    "padres": "padres", "giants": "giants",
    "rockies": "rockies", "rays": "rays",
    "orioles": "orioles", "yankees": "yankees"
}

def clean_team_name(name):
    """Приводим названия команд к формату MLB"""
    name = name.lower().strip()
    short_name = name.split()[-1] if " " in name else name
    return TEAM_NAMES.get(short_name, short_name)

def format_game_url(game):
    """Генерируем ссылку на матч"""
    home_team = game.get("teams", {}).get("home", {}).get("team", {})
    away_team = game.get("teams", {}).get("away", {}).get("team", {})
    home_name = clean_team_name(home_team.get("name", ""))
    away_name = clean_team_name(away_team.get("name", ""))
    date_utc = game.get("gameDate", "").split("T")[0]
    game_pk = game.get("gamePk")
    
    return f"https://www.mlb.com/gameday/{away_name}-vs-{home_name}/{date_utc.replace('-', '/')}/{game_pk}/live"

def utc_to_yekt(dt_str):
    """Конвертируем UTC в Екатеринбург"""
    try:
        dt = datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%SZ")
        return dt.replace(tzinfo=timezone.utc).astimezone(YEKT).strftime("%H:%M:%S")
    except:
        return dt_str

def send_telegram_message(text):
    """Отправка сообщения в Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    params = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    try:
        requests.post(url, params=params)
    except Exception as e:
        print(f"Ошибка отправки: {e}")

def check_games():
    """Основная логика проверки матчей"""
    while True:
        try:
            print(f"\n{datetime.now(YEKT)}: Проверка матчей...")
            url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={datetime.utcnow().strftime('%Y-%m-%d')}&hydrate=linescore"
            response = requests.get(url, headers={"User-Agent": "MLB-Tracker/1.0"})
            games = response.json().get("dates", [{}])[0].get("games", [])

            sent_signals = set()
            if os.path.exists(LOG_FILE):
                with open(LOG_FILE, "r") as f:
                    sent_signals = set(f.read().splitlines())

            for game in games:
                status = game.get("status", {}).get("detailedState", "")
                linescore = game.get("linescore", {})
                
                if (status == "In Progress" and 
                    linescore.get("inningHalf") == "Top" and 
                    4 <= linescore.get("currentInning", 0) <= 9 and
                    game.get("teams", {}).get("home", {}).get("score") == 0 and
                    game.get("teams", {}).get("away", {}).get("score") == 0):
                    
                    game_pk = str(game.get("gamePk"))
                    if game_pk not in sent_signals:
                        home_team = game["teams"]["home"]["team"]["name"]
                        away_team = game["teams"]["away"]["team"]["name"]
                        message = (
                            f"⚾ <b>MLB Signal (Inning {linescore['currentInning']})</b>\n"
                            f"▸ {away_team} vs {home_team}\n"
                            f"▸ Time: {utc_to_yekt(game['gameDate'])}\n"
                            f"▸ Score: 0-0 (Top {linescore['currentInning']})\n"
                            f"▸ <a href='{format_game_url(game)}'>View on MLB.com</a>"
                        )
                        send_telegram_message(message)
                        with open(LOG_FILE, "a") as f:
                            f.write(f"{game_pk}\n")

        except Exception as e:
            print(f"Ошибка: {e}")
        time.sleep(300)  # Пауза 5 минут

@app.route('/')
def home():
    return f"MLB Tracker Active | Last check: {datetime.now(YEKT)}"

if __name__ == "__main__":
    # Запускаем Flask в отдельном потоке
    flask_thread = threading.Thread(target=lambda: app.run(host="0.0.0.0", port=10000))
    flask_thread.daemon = True
    flask_thread.start()
    
    # Запускаем основную логику
    print("Bot started. Waiting for games...")
    check_games()