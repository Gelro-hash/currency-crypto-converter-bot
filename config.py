# config.py
"""
Конфигурационный файл Telegram-бота.
Все секретные ключи (токены, API-ключи) необходимо получать из переменных окружения.
"""

import os
import logging

class Config:
    # Токен бота Telegram (получить у BotFather)
    TOKEN = os.getenv("BOT_TOKEN", "")

    # API-ключ для Open Exchange Rates (fiat-валюты)
    OPENEXCHANGE_API_KEY = os.getenv("OPENEXCHANGE_API_KEY", "")

    # URL CoinGecko API для криптовалют
    COINGECKO_API_URL = "https://api.coingecko.com/api/v3"

    # Справочник поддерживаемых валют
    CURRENCIES = {
        'Доллар': 'USD',
        'Евро': 'EUR',
        'Рубль': 'RUB',
        'Юань': 'CNY',
        'Белорусский рубль': 'BYN',
        'Индийская рупия': 'INR',
        'Биткоин': 'BTC',
        'Эфириум': 'ETH',
        'Лайткоин': 'LTC',
        'Тезер': 'USDT',
        'Бинанс': 'BNB',
        'Рипл': 'XRP',
        'Догикоин': 'DOGE'
    }

    # Настройки логирования
    LOG_FILE = "bot.log"
    LOG_LEVEL = logging.INFO
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    @staticmethod
    def setup_logging():
        """Настройка логирования"""
        logging.basicConfig(
            filename=Config.LOG_FILE,
            level=Config.LOG_LEVEL,
            format=Config.LOG_FORMAT
        )
        console_handler = logging.StreamHandler()
        console_handler.setLevel(Config.LOG_LEVEL)
        formatter = logging.Formatter(Config.LOG_FORMAT)
        console_handler.setFormatter(formatter)
        logging.getLogger().addHandler(console_handler)
        return logging.getLogger()

# Инициализация логгера
logger = Config.setup_logging()