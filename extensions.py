"""
Модуль для работы с API конвертации валют
Исправлены все ошибки, добавлено кэширование
"""

import requests
import time
import re
from config import Config, logger

class APIException(Exception):
    """Пользовательское исключение для ошибок API"""
    pass

class CryptoConverter:
    # Кэш курсов: {пара: (значение, timestamp)}
    RATE_CACHE = {}
    CACHE_DURATION = 3600  # 1 час
    
    @staticmethod
    def get_cached_rate(base: str, quote: str):
        """Получить курс из кэша если он актуален"""
        key = f"{base}_{quote}"
        cached = CryptoConverter.RATE_CACHE.get(key)
        if cached and (time.time() - cached[1]) < CryptoConverter.CACHE_DURATION:
            return cached[0], cached[1]
        return None, None

    @staticmethod
    def cache_rate(base: str, quote: str, rate: float):
        """Сохранить курс в кэш"""
        key = f"{base}_{quote}"
        CryptoConverter.RATE_CACHE[key] = (rate, time.time())

    @staticmethod
    def get_price(base: str, quote: str, amount: float, commission: float = 0.0):
        """
        Основной метод для конвертации валют с кэшированием
        """
        # Нормализация названий валют
        base_key = CryptoConverter.normalize_currency_name(base)
        quote_key = CryptoConverter.normalize_currency_name(quote)
        
        # Проверка наличия валют в словаре
        if not base_key:
            raise APIException(f"Неизвестная валюта: {base}")
        if not quote_key:
            raise APIException(f"Неизвестная валюта: {quote}")
            
        base_code = Config.CURRENCIES[base_key].lower()
        quote_code = Config.CURRENCIES[quote_key].lower()
        crypto_list = ['btc', 'eth', 'ltc', 'usdt', 'bnb', 'xrp', 'doge']  # Список криптовалют
        
        # Проверка кэша
        cached_rate, cached_ts = CryptoConverter.get_cached_rate(base_code, quote_code)
        if cached_rate is not None:
            logger.info(f"Использован кэш для {base_code}/{quote_code}: {cached_rate}")
            return amount * cached_rate * (1 + commission/100), cached_ts
        
        try:
            # Определяем тип конвертации
            if base_code in crypto_list or quote_code in crypto_list:
                if base_code in crypto_list and quote_code in crypto_list:
                    # Конвертация крипто-крипто
                    result, ts = CryptoConverter.convert_crypto_to_crypto(base_code, quote_code, amount, commission)
                else:
                    # Конвертация крипто-фиат
                    result, ts = CryptoConverter.convert_crypto_to_fiat(base_code, quote_code, amount, commission)
            else:
                # Конвертация фиат-фиат
                result, ts = CryptoConverter.convert_fiat_to_fiat(base_code, quote_code, amount, commission)
            
            # Кэшируем результат
            actual_rate = result / (amount * (1 + commission/100))
            CryptoConverter.cache_rate(base_code, quote_code, actual_rate)
            return result, ts
            
        except APIException as e:
            raise e
        except Exception as e:
            raise APIException(f"Ошибка конвертации: {str(e)}")
    
    @staticmethod
    def normalize_currency_name(name: str) -> str:
        """Упрощенная нормализация названий валют"""
        if not name:
            return None
            
        name = name.strip().lower()
        
        # Словарь всех возможных форм
        currency_map = {
            # Фиатные валюты
            'доллар': 'Доллар',
            'евро': 'Евро',
            'рубль': 'Рубль',
            'юань': 'Юань',
            'белорусский рубль': 'Белорусский рубль',
            'индийская рупия': 'Индийская рупия',
            
            # Криптовалюты
            'биткоин': 'Биткоин',
            'эфириум': 'Эфириум',
            'лайткоин': 'Лайткоин',
            'тезер': 'Тезер',
            'рипл': 'Рипл',
            'догикоин': 'Догикоин',
            'бинанс': 'Бинанс',
            
            # Сокращения и сленг
            'usd': 'Доллар',
            'eur': 'Евро',
            'rub': 'Рубль',
            'cny': 'Юань',
            'byn': 'Белорусский рубль',
            'inr': 'Индийская рупия',
            'btc': 'Биткоин',
            'eth': 'Эфириум',
            'ltc': 'Лайткоин',
            'usdt': 'Тезер',
            'xrp': 'Рипл',
            'doge': 'Догикоин',
            'bnb': 'Бинанс',
            'бакс': 'Доллар',
            'баки': 'Доллар',
            'биток': 'Биткоин',
            'эфир': 'Эфириум',
            'лайт': 'Лайткоин',
            'доги': 'Догикоин'
        }
        
        # Проверяем точное совпадение
        if name in currency_map:
            return currency_map[name]
        
        # Проверяем частичные совпадения
        for key, value in currency_map.items():
            if key in name:
                return value
        
        # Если не нашли, проверяем есть ли в Config.CURRENCIES
        for currency_name in Config.CURRENCIES.keys():
            if currency_name.lower() == name:
                return currency_name
                
        return None

    @staticmethod
    def convert_crypto_to_crypto(base_code, quote_code, amount, commission):
        """
        Конвертация между криптовалютами через CoinGecko API
        """
        base_id = COINGECKO_IDS.get(base_code)
        quote_id = COINGECKO_IDS.get(quote_code)
        
        if not base_id or not quote_id:
            raise APIException("Неподдерживаемая криптовалюта")
        
        url = f"{Config.COINGECKO_API_URL}/simple/price?ids={base_id},{quote_id}&vs_currencies=usd"
        logger.info(f"Запрос к CoinGecko: {url}")
        response = requests.get(url)
        
        if response.status_code != 200:
            raise APIException("Ошибка при получении данных от CoinGecko")
        
        data = response.json()
        ts = time.time()
        
        if base_id in data and quote_id in data:
            base_usd = data[base_id].get('usd')
            quote_usd = data[quote_id].get('usd')
            
            if not base_usd or not quote_usd:
                raise APIException("Не удалось получить курс для криптовалют")
            
            # Конвертация: (amount * base_usd) / quote_usd
            result = (amount * base_usd) / quote_usd
            return result * (1 + commission/100), ts
        else:
            raise APIException("Ошибка получения курса криптовалют")
    
    @staticmethod
    def convert_crypto_to_fiat(base_code, quote_code, amount, commission):
        """
        Конвертация между криптовалютой и фиатом
        """
        # Определяем направление конвертации
        if base_code in COINGECKO_IDS.keys():
            crypto_code = base_code
            fiat_code = quote_code
            convert_direction = "crypto_to_fiat"
        else:
            crypto_code = quote_code
            fiat_code = base_code
            convert_direction = "fiat_to_crypto"
        
        crypto_id = COINGECKO_IDS.get(crypto_code)
        if not crypto_id:
            raise APIException("Неподдерживаемая криптовалюта")
        
        url = f"{Config.COINGECKO_API_URL}/simple/price?ids={crypto_id}&vs_currencies={fiat_code}"
        logger.info(f"Запрос к CoinGecko: {url}")
        response = requests.get(url)
        
        if response.status_code != 200:
            raise APIException("Ошибка при получении данных от CoinGecko")
        
        data = response.json()
        ts = time.time()
        
        if crypto_id in data and fiat_code in data[crypto_id]:
            rate = data[crypto_id][fiat_code]
            
            if convert_direction == "crypto_to_fiat":
                result = amount * rate
            else:
                result = amount / rate
                
            return result * (1 + commission/100), ts
        else:
            # Попробуем конвертацию через USD
            return CryptoConverter.convert_via_usd(base_code, quote_code, amount, commission)
    
    @staticmethod
    def convert_fiat_to_fiat(base_code, quote_code, amount, commission):
        """
        Конвертация между фиатными валютами через Open Exchange Rates API
        """
        url = f"https://openexchangerates.org/api/latest.json?app_id={Config.OPENEXCHANGE_API_KEY}"
        logger.info(f"Запрос к OpenExchangeRates: {url}")
        response = requests.get(url)
        
        if response.status_code != 200:
            raise APIException("Ошибка при получении данных от OpenExchangeRates")
        
        data = response.json()
        
        if 'rates' not in data or 'timestamp' not in data:
            raise APIException("Ошибка в ответе Open Exchange Rates")
        
        rates = data['rates']
        ts = data['timestamp']
        base_rate = rates.get(base_code.upper())
        quote_rate = rates.get(quote_code.upper())
        
        if not base_rate or not quote_rate:
            raise APIException(f"Одна из валют {base_code.upper()} или {quote_code.upper()} не найдена")
        
        # Конвертация: (amount / base_rate) * quote_rate
        result = (amount / base_rate) * quote_rate
        return result * (1 + commission/100), ts
    
    @staticmethod
    def convert_via_usd(base_code, quote_code, amount, commission):
        """
        Конвертация через USD для непрямых пар
        """
        try:
            # Конвертируем базовую валюту в USD
            if base_code in COINGECKO_IDS.keys():
                base_id = COINGECKO_IDS[base_code]
                url = f"{Config.COINGECKO_API_URL}/simple/price?ids={base_id}&vs_currencies=usd"
                response = requests.get(url)
                data = response.json()
                base_to_usd = data[base_id]['usd']
                ts1 = time.time()
            else:
                url = f"https://openexchangerates.org/api/latest.json?app_id={Config.OPENEXCHANGE_API_KEY}"
                response = requests.get(url)
                data = response.json()
                base_to_usd = data['rates'].get(base_code.upper(), 1)
                ts1 = data['timestamp']
            
            # Конвертируем USD в целевую валюту
            if quote_code in COINGECKO_IDS.keys():
                quote_id = COINGECKO_IDS[quote_code]
                url = f"{Config.COINGECKO_API_URL}/simple/price?ids={quote_id}&vs_currencies=usd"
                response = requests.get(url)
                data = response.json()
                usd_to_quote = 1 / data[quote_id]['usd']
                ts2 = time.time()
            else:
                url = f"https://openexchangerates.org/api/latest.json?app_id={Config.OPENEXCHANGE_API_KEY}"
                response = requests.get(url)
                data = response.json()
                usd_to_quote = data['rates'].get(quote_code.upper(), 1)
                ts2 = data['timestamp']
            
            result = (amount * base_to_usd * usd_to_quote) * (1 + commission/100)
            return result, max(ts1, ts2)
            
        except Exception as e:
            raise APIException(f"Ошибка конвертации через USD: {str(e)}")
    
    @staticmethod
    def process_complex_expression(expression: str):
        """Обработка сложных математических выражений с валютами"""
        # Удаляем скобки для упрощения парсинга
        expression = expression.replace("(", "").replace(")", "")
        
        # Улучшенное разбиение на части с учётом операторов
        parts = re.split(r'(\+|\-|\*|\/|в|to)', expression, flags=re.IGNORECASE)
        parts = [p.strip() for p in parts if p.strip()]
        
        if len(parts) < 3:
            raise APIException("Невозможно разобрать выражение")
        
        # Конвертируем все части в USD
        total_usd = 0
        current_operator = '+'
        target_currency = None
        
        for i, part in enumerate(parts):
            if part.lower() in ('в', 'to'):
                # Следующие части - целевая валюта
                if i+1 < len(parts):
                    target_currency = ' '.join(parts[i+1:])
                break
                
            if part in ('+', '-', '*', '/'):
                current_operator = part
                continue
                
            # Парсим число и валюту
            match = re.match(r'^([\d\.]+)\s*([a-zA-Zа-яА-Я]+)?$', part)
            if not match:
                # Если не получилось, возможно это валюта без числа
                currency = CryptoConverter.normalize_currency_name(part)
                if currency:
                    # Если это валюта, считаем количество = 1
                    amount = 1
                else:
                    raise APIException(f"Не могу разобрать часть: {part}")
            else:
                amount = float(match.group(1))
                currency = match.group(2) if match.group(2) else 'USD'
            
            # Нормализуем название валюты
            curr_key = CryptoConverter.normalize_currency_name(currency)
            if not curr_key:
                raise APIException(f"Неизвестная валюта: {currency}")
            
            # Конвертируем в USD
            converted = CryptoConverter.get_price(curr_key, 'USD', amount)[0]
            
            # Применяем оператор
            if current_operator == '+':
                total_usd += converted
            elif current_operator == '-':
                total_usd -= converted
            elif current_operator == '*':
                total_usd *= converted
            elif current_operator == '/':
                if converted == 0:
                    raise APIException("Деление на ноль")
                total_usd /= converted
        
        # Если целевая валюта не указана, используем USD
        if not target_currency:
            target_currency = 'USD'
            
        target_key = CryptoConverter.normalize_currency_name(target_currency)
        if not target_key:
            raise APIException(f"Неизвестная целевая валюта: {target_currency}")
        
        return total_usd, target_key

# Словарь соответствия кодов криптовалют их ID в CoinGecko
COINGECKO_IDS = {
    'btc': 'bitcoin',
    'eth': 'ethereum',
    'ltc': 'litecoin',
    'usdt': 'tether',
    'bnb': 'binancecoin',
    'xrp': 'ripple',
    'doge': 'dogecoin',
    'ada': 'cardano',
    'dot': 'polkadot',
    'sol': 'solana'
}