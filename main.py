"""
Основной модуль телеграм-бота для конвертации валют
Все ошибки исправлены, добавлены инлайн-клавиатуры
"""

import re
import telebot
from telebot import types
from datetime import datetime
from config import Config, logger
from extensions import APIException, CryptoConverter

# Инициализация бота
bot = telebot.TeleBot(Config.TOKEN)

# Состояния пользователя для интерактивного режима
user_states = {}

def create_inline_markup(items: list, row_width: int = 3) -> types.InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру с кнопками"""
    markup = types.InlineKeyboardMarkup(row_width=row_width)
    buttons = [types.InlineKeyboardButton(item, callback_data=item) for item in items]
    
    # Разбиваем кнопки на ряды
    for i in range(0, len(buttons), row_width):
        markup.add(*buttons[i:i+row_width])
    
    return markup

def create_main_menu() -> types.ReplyKeyboardMarkup:
    """Создает клавиатуру с основными командами бота"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = ['/convert', '/values', '/help']
    markup.add(*buttons)
    return markup

def format_timestamp(ts: float) -> str:
    """Форматирует timestamp в читаемую дату"""
    if not ts:
        return "неизвестное время"
    return datetime.fromtimestamp(ts).strftime('%d.%m.%Y %H:%M:%S')

@bot.message_handler(commands=['start', 'help'])
def start(message: telebot.types.Message):
    """Обработчик /start и /help с примерами сложных выражений"""
    logger.info(f"Пользователь {message.chat.id} запустил /start")
    text = (
        '💱 *Конвертер валют и криптовалют* 💱\n\n'
        '🔹 *Простые запросы (скопируйте и измените):*\n'
        '```\n'
        '<из валюты> <в валюту> <сумма>\n'
        'Доллар Рубль 100\n'
        'Биткоин Евро 0.5\n'
        'Эфириум Рубль 1.2 --commission=1.5\n'
        '```\n\n'
        '🔹 *Сложные выражения (скопируйте и измените):*\n'
        '```\n'
        '100 USD + 50 EUR в RUB\n'
        '0.5 BTC * 42000 USD в EUR\n'
        '(100 USD * 1.1) в JPY\n'
        '5000 RUB / 75.5 в USD\n'
        '100 USD to BTC + 0.01 ETH to BTC\n'
        '```\n\n'
        '⚙️ *Доступные команды:*\n'
        '/convert - пошаговая конвертация\n'
        '/values - список валют\n'
        '/help - справка\n\n'
        '💡 *Подсказки:*\n'
        '- Выделяйте примеры и копируйте их для быстрого использования\n'
        '- Валюту можно указывать в любом падеже (Рубль, Рублей, Рубли)\n'
        '- Комиссия указывается через `--commission=X`\n'
        '- Результат округляется до 3 знаков после запятой\n'
        '- При ошибке API используются кэшированные курсы'
    )
    bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=create_main_menu())

@bot.message_handler(commands=['values'])
def values(message: telebot.types.Message):
    """Обработчик команды /values - показывает список поддерживаемых валют"""
    logger.info(f"Пользователь {message.chat.id} запросил /values")
    text = '📊 *Доступные валюты:*\n'
    for name, code in Config.CURRENCIES.items():
        text += f"\n- {name} ({code})"
    bot.reply_to(message, text, parse_mode='Markdown', reply_markup=create_main_menu())

@bot.message_handler(commands=['convert'])
def convert_command(message: telebot.types.Message):
    """
    Обработчик команды /convert
    """
    logger.info(f"Пользователь {message.chat.id} запустил /convert")
    if len(message.text.split()) > 1:
        # Если есть параметры - обрабатываем как текстовую команду
        process_text_command(message)
    else:
        # Запускаем интерактивный режим
        user_states[message.chat.id] = {'step': 1, 'base': None, 'quote': None}
        text = '🔹 *Шаг 1 из 3:* Выберите валюту, *из* которой конвертировать:'
        currencies = list(Config.CURRENCIES.keys())
        bot.send_message(message.chat.id, text, parse_mode='Markdown', 
                         reply_markup=create_inline_markup(currencies))

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call: types.CallbackQuery):
    """Обработчик выбора валюты в интерактивном режиме"""
    chat_id = call.message.chat.id
    state = user_states.get(chat_id, {})
    
    if state.get('step') == 1:
        # Шаг 1: Выбор исходной валюты
        base_currency = call.data
        state['base'] = base_currency
        state['step'] = 2
        
        text = '🔹 *Шаг 2 из 3:* Выберите валюту, *в* которую конвертировать:'
        currencies = [c for c in Config.CURRENCIES.keys() if c != base_currency]
        bot.edit_message_text(text, chat_id, call.message.message_id, 
                             parse_mode='Markdown', 
                             reply_markup=create_inline_markup(currencies))
    
    elif state.get('step') == 2:
        # Шаг 2: Выбор целевой валюты
        quote_currency = call.data
        state['quote'] = quote_currency
        state['step'] = 3
        
        text = f'🔹 *Шаг 3 из 3:* Введите количество {state["base"]} для конвертации в {state["quote"]}:'
        bot.edit_message_text(text, chat_id, call.message.message_id, parse_mode='Markdown')
    
    user_states[chat_id] = state
    bot.answer_callback_query(call.id)

@bot.message_handler(func=lambda message: user_states.get(message.chat.id, {}).get('step') == 3)
def amount_handler(message: telebot.types.Message):
    """Обработчик ввода количества и выполнение конвертации"""
    chat_id = message.chat.id
    state = user_states.get(chat_id, {})
    if not state:
        bot.send_message(chat_id, "❌ Сессия устарела. Начните заново с /convert", reply_markup=create_main_menu())
        return
        
    amount_str = message.text.strip()
    base_key = state.get('base')
    quote_key = state.get('quote')
    
    logger.info(f"Пользователь {chat_id} ввел сумму: {amount_str} для конвертации {base_key}->{quote_key}")
    
    try:
        # Преобразуем в число
        amount = float(amount_str)
        
        # Выполнение конвертации
        result, timestamp = CryptoConverter.get_price(base_key, quote_key, amount)
        # Форматирование до 3 знаков после запятой
        formatted_result = f"{result:.3f}"
        time_str = format_timestamp(timestamp)
        
        answer_text = (
            f'💱 *Результат конвертации:*\n'
            f'`{amount} {base_key} = {formatted_result} {quote_key}`\n'
            f'📅 *Курс актуален на:* {time_str}'
        )
        bot.send_message(chat_id, answer_text, parse_mode='Markdown', reply_markup=create_main_menu())
        logger.info(f"Успешная конвертация: {amount} {base_key} -> {formatted_result} {quote_key}")
    except ValueError:
        error_text = f"❌ Ошибка: '{amount_str}' не является числом\n🔹 Пожалуйста, введите количество {base_key} для конвертации"
        bot.send_message(chat_id, error_text, reply_markup=create_main_menu())
        logger.error(f"Ошибка преобразования числа: {amount_str}")
    except APIException as e:
        error_text = f'❌ Ошибка конвертации:\n{e}\n🔹 Используйте /help для справки'
        bot.send_message(chat_id, error_text, reply_markup=create_main_menu())
        logger.error(f"Ошибка конвертации для {chat_id}: {str(e)}")
    except Exception as e:
        error_text = f'❌ Неизвестная ошибка:\n{str(e)}\n🔹 Пожалуйста, попробуйте снова'
        bot.send_message(chat_id, error_text, reply_markup=create_main_menu())
        logger.error(f"Неизвестная ошибка конвертации: {str(e)}")
    finally:
        # Сбрасываем состояние
        if chat_id in user_states:
            del user_states[chat_id]

def process_text_command(message):
    """Обработчик для команды /convert с параметрами"""
    try:
        text = message.text.replace('/convert', '').strip()
        process_text_conversion(message, text)
    except Exception as e:
        error_text = f"❌ Ошибка: {str(e)}\n🔹 Используйте /help для справки"
        bot.reply_to(message, error_text, reply_markup=create_main_menu())
        logger.error(f"Ошибка в process_text_command: {str(e)}")

def process_text_conversion(message, text):
    """
    Парсит и выполняет текстовую команду конвертации
    """
    chat_id = message.chat.id
    try:
        # Упрощенный парсинг команды
        parts = text.split()
        commission = 0.0
        
        # Проверка на комиссию в конце команды
        if len(parts) > 3 and parts[-1].startswith('--commission='):
            try:
                commission_str = parts[-1].split('=')[1].replace('%', '')
                commission = float(commission_str)
                parts = parts[:-1]  # Удаляем параметр комиссии
            except ValueError:
                error_text = (
                    "❌ Неверный формат комиссии. Используйте: --commission=1.5\n"
                    "🔹 Пример: 'Доллар Евро 100 --commission=1.5'"
                )
                bot.reply_to(message, error_text, reply_markup=create_main_menu())
                return
        
        # Проверка минимального количества частей
        if len(parts) < 3:
            bot.reply_to(
                message, 
                '❌ Недостаточно параметров!\n'
                '🔹 *Формат:* `<из валюты> <в валюту> <сумма>`\n'
                '🔹 *Примеры:*\n'
                '- `Евро Рубль 100`\n'
                '- `Биткоин Доллар 0.5`\n\n'
                '💡 Можно добавить комиссию: `--commission=1.5`',
                parse_mode='Markdown',
                reply_markup=create_main_menu()
            )
            return
        
        # Извлекаем параметры (поддержка многословных названий)
        base = ' '.join(parts[:-2])
        quote = parts[-2]
        amount_str = parts[-1]
        
        # Нормализация названий валют
        base_key = CryptoConverter.normalize_currency_name(base)
        quote_key = CryptoConverter.normalize_currency_name(quote)
        
        if not base_key:
            bot.reply_to(
                message, 
                f"❌ Неизвестная валюта: {base}\n"
                "🔹 Используйте /values для списка валют",
                reply_markup=create_main_menu()
            )
            return
            
        if not quote_key:
            bot.reply_to(
                message, 
                f"❌ Неизвестная валюта: {quote}\n"
                "🔹 Используйте /values для списка валют",
                reply_markup=create_main_menu()
            )
            return

        try:
            amount_val = float(amount_str)
        except ValueError:
            bot.reply_to(
                message, 
                f"❌ Ошибка: '{amount_str}' не является числом\n"
                f"🔹 Пожалуйста, введите количество {base_key} для конвертации",
                reply_markup=create_main_menu()
            )
            return

        try:
            # Выполнение конвертации
            result, timestamp = CryptoConverter.get_price(base_key, quote_key, amount_val, commission)
            # Форматирование до 3 знаков после запятой
            formatted_result = f"{result:.3f}"
            time_str = format_timestamp(timestamp)
            
            commission_text = f" (комиссия: {commission}%)" if commission > 0 else ""
            answer_text = (
                f'💱 *Результат конвертации:*\n'
                f'`{amount_val} {base_key} = {formatted_result} {quote_key}{commission_text}`\n'
                f'📅 *Курс актуален на:* {time_str}'
            )
            bot.reply_to(message, answer_text, parse_mode='Markdown', reply_markup=create_main_menu())
            logger.info(f"Успешная конвертация: {amount_val} {base_key} -> {formatted_result} {quote_key}")
        except APIException as e:
            error_text = f'❌ Ошибка конвертации:\n{e}\n🔹 Используйте /help для справки'
            bot.reply_to(message, error_text, reply_markup=create_main_menu())
            logger.error(f"Ошибка конвертации для {chat_id}: {str(e)}")
            
    except Exception as e:
        error_text = f"❌ Ошибка: {str(e)}\n🔹 Используйте /help для справки"
        bot.reply_to(message, error_text, reply_markup=create_main_menu())
        logger.error(f"Ошибка в process_text_conversion: {str(e)}")

@bot.message_handler(content_types=['text'])
def text_converter(message: telebot.types.Message):
    """Основной обработчик текста с поддержкой сложных выражений"""
    text = message.text.strip()
    chat_id = message.chat.id
    logger.info(f"Пользователь {chat_id} отправил запрос: {text}")
    
    # Проверка на сложное выражение
    if re.search(r'[\+\-\*\/]', text) and (' в ' in text or ' to ' in text):
        try:
            total_usd, target_currency = CryptoConverter.process_complex_expression(text)
            # Конвертируем из USD в целевую валюту
            result, timestamp = CryptoConverter.get_price('USD', target_currency, total_usd)
            formatted_result = f"{result:.3f}"
            time_str = format_timestamp(timestamp)
            
            response_text = (
                f'💱 *Результат сложного выражения:*\n'
                f'`{text}`\n\n'
                f'🔹 *Итог:* {total_usd:.2f} USD = {formatted_result} {target_currency}\n'
                f'📅 *Курс актуален на:* {time_str}'
            )
            bot.reply_to(message, response_text, parse_mode='Markdown')
            logger.info(f"Успешная обработка сложного выражения: {text}")
        except APIException as e:
            error_text = f"❌ Ошибка в выражении:\n{str(e)}"
            bot.reply_to(message, error_text)
            logger.error(f"Ошибка в сложном выражении для {chat_id}: {str(e)}")
        except Exception as e:
            error_text = f"❌ Системная ошибка: {str(e)}"
            bot.reply_to(message, error_text)
            logger.error(f"Системная ошибка в сложном выражении: {str(e)}")
    else:
        # Обработка простых запросов
        process_text_conversion(message, text)

# Запуск бота
if __name__ == '__main__':
    logger.info("Бот запущен")
    bot.polling(none_stop=True, interval=1)