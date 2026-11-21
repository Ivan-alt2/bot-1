import json
import time
from dotenv import load_dotenv
import os
import telegram
import requests
import logging
from http import HTTPStatus
from exception import (IsNot200Error,
                       EmptyDictorListError,
                       StatusResponceError,
                       ApiError,
                       JSONDecoderError)


load_dotenv()


PRACTICUM_TOKEN = os.getenv('TOKEN')
TELEGRAM_TOKEN = os.getenv('TOKEN_TELEGRAM_BOT')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    '%(asctime)s, %(levelname)s, %(message)s'
)
handler = logging.StreamHandler()
handler.setFormatter(formatter)
logger.addHandler(handler)


def send_message(bot, message):
    """Отправка сообщений."""
    try:
        message_info = f'Сообщение готово к отправке: {message}'
        logger.info(message_info)
        bot.send_message(TELEGRAM_CHAT_ID, message)
        message_info = f'Сообщение отправлено: {message}'
        logger.info(message_info)
    except telegram.TelegramError:
        message_error = f'Сообщение не удалось отправить: {message}'
        logger.error(message_error)


def get_api_answer(current_timestamp):
    """Получение ответа от API Практикума."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        homework = requests.get(
            url=ENDPOINT,
            headers=HEADERS,
            params=params
        )
        status_code = homework.status_code
        if status_code != HTTPStatus.OK:
            message_error = (f'API {ENDPOINT} недоступен, '
                             f'код ошибки {status_code}')
            raise IsNot200Error(message_error)
        return homework.json()
    except requests.exceptions.RequestException as error_request:
        message_error = f'Ошибка в запросе API: {error_request}'
        raise ApiError(message_error)
    except json.JSONDecodeError as json_error:
        message_error = f'Ошибка json: {json_error}'
        raise JSONDecoderError(message_error) from json_error


def check_response(response):
    """Проверка валидности полученных данных."""
    if response.get('homeworks') == []:
        return {}
    if not isinstance(response, dict):
        response_type = type(response)
        message = f'Ответ пришел в некорректном формате: {response_type}'
        raise EmptyDictorListError(message)
    if 'homeworks' not in response:
        message = 'В ответе отсутствуют необходимые ключи'
        raise StatusResponceError(message)
    homework = response.get('homeworks')
    if not isinstance(homework, list):
        message = 'Некорректное значение в ответе у домашней работы'
        raise StatusResponceError(message)
    return homework


def parse_status(homework):
    """Формирование сообщения о статусе задания."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status is None:
        message_error = f'Пустой статус: {homework_status}'
        raise StatusResponceError(message_error)
    if homework_name is None:
        message_error = f'Пустое имя работы: {homework_name}'
        raise KeyError(message_error)
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка наличия обязательных токенов."""
    is_check_tokens = all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])
    if not is_check_tokens:
        message_error = 'Отсутствует критически важная для работы переменная'
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
                message = parse_status(homework)
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
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
