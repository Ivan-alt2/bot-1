import json
import logging
import os
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exception import (
    ApiError,
    IsNot200Error,
    JSONDecoderError,
    StatusResponceError,
)


load_dotenv()


PRACTICUM_TOKEN = os.getenv('TOKEN')
TELEGRAM_TOKEN = os.getenv('TOKEN_TELEGRAM_BOT')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s, %(levelname)s, %(message)s')
handler = logging.StreamHandler()
handler.setFormatter(formatter)
logger.addHandler(handler)


def send_message(bot, message):
    """Отправка сообщений."""
    try:
        logger.debug(f'Сообщение готово к отправке: {message}')
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f'Сообщение отправлено: {message}')
    except telegram.TelegramError:
        logger.error(f'Сообщение не удалось отправить: {message}')


def get_api_answer(current_timestamp):
    """Получение ответа от API Практикума."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(
            url=ENDPOINT,
            headers=HEADERS,
            params=params
        )
        status_code = response.status_code
        if status_code != HTTPStatus.OK:
            message_error = (
                f'API {ENDPOINT} недоступен, '
                f'код ошибки {status_code}'
            )
            raise IsNot200Error(message_error)
        return response.json()
    except requests.exceptions.RequestException as error_request:
        raise ApiError(f'Ошибка в запросе API: {error_request}')
    except json.JSONDecodeError as json_error:
        raise JSONDecoderError(f'Ошибка json: {json_error}') from json_error


def check_response(response):
    """Проверка валидности полученных данных."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API не является словарем')
    if 'homeworks' not in response:
        raise StatusResponceError('В ответе отсутствуют необходимые ключи')
    homework = response.get('homeworks')
    if not isinstance(homework, list):
        raise TypeError('Значение homeworks не является списком')
    if not homework:
        return []
    return homework


def parse_status(homework):
    """Формирование сообщения о статусе задания."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status is None:
        raise StatusResponceError('Пустой статус работы')
    if homework_name is None:
        raise KeyError('Пустое имя работы')
    if homework_status not in HOMEWORK_VERDICTS:
        raise StatusResponceError(
            f'Неизвестный статус работы: {homework_status}'
        )
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка наличия обязательных токенов."""
    is_check_tokens = all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])
    if not is_check_tokens:
        message_error = 'Отсутствует критически важная переменная окружения'
        logger.critical(message_error)
        return False
    return True


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        exit()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    send_message(bot, 'Бот включен')
    current_timestamp = int(time.time())
    last_error = ''
    while True:
        try:
            response = get_api_answer(current_timestamp)
            current_timestamp = response.get('current_date')
            homework = check_response(response)
            if homework:
                message = parse_status(homework[0])
                send_message(bot, message)
            else:
                logger.debug('Нет нового статуса')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            if message != last_error:
                last_error = message
                send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
