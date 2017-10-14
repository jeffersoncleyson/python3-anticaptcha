import requests
import time
import tempfile
import hashlib
import os
import base64

from .config import create_task_url, get_result_url, app_key
#from .errors import RuCaptchaError


class ImageToTextTask:
    '''
    Данный метод подходит как для загрузки и решения обычной капчи
    так и для большой капчи.
    Требуется передать API ключ сайта, ссылку на изображение и,по желанию, время ожидания решения капчи
    Подробней информацию смотрите в методе 'captcha_handler'
    '''

    def __init__(self, anticaptcha_key, sleep_time=5, save_format = 'temp', language = 'en',**kwargs):
        '''
        Инициализация нужных переменных, создание папки для изображений и кэша
        После завершения работы - удалются временные фалйы и папки
        :param rucaptcha_key:  АПИ ключ капчи из кабинета пользователя
        :param sleep_time: Вермя ожидания решения капчи
        :param save_format: Формат в котором будет сохраняться изображение, либо как временный фпйл - 'temp',
                            либо как обычное изображение в папку созданную библиотекой - 'const'.
        '''

        self.ANTICAPTCHA_KEY = anticaptcha_key
        self.sleep_time = sleep_time
        self.save_format = save_format

        # Пайлоад для создания задачи
        self.task_payload = {"clientKey": self.ANTICAPTCHA_KEY,
                             "task":
                                 {
                                       "type": "ImageToTextTask",
                                 },
                             "languagePool": language
                             }
        # Если переданы ещё параметры - вносим их в payload
        if kwargs:
            for key in kwargs:
                self.task_payload['task'].update({key: kwargs[key]})

    def image_temp_saver(self, content):
        '''
        Метод сохраняет файл изображения как временный и отправляет его сразу на сервер для расшифровки.
        :return: Возвращает ID капчи
        '''
        with tempfile.NamedTemporaryFile(suffix='.png') as out:
            out.write(content)
            with open(out.name, 'rb') as captcha_image:
                # Создаём пайлоад, вводим ключ от сайта, выбираем метод ПОСТ и ждём ответа в JSON-формате
                self.task_payload['task'].update({"body": base64.b64encode(captcha_image.read()).decode('utf-8')})
                # Отправляем на рукапча изображение капчи и другие парметры,
                # в результате получаем JSON ответ с номером решаемой капчи и получая ответ - извлекаем номер
                captcha_id = (requests.post(create_task_url,
                                            json = self.task_payload).json())
        return captcha_id

    def image_const_saver(self, content):
        '''
        Метод создаёт папку и сохраняет в неё изображение, затем передаёт его на расшифровку и удалет файл.
        :return: Возвращает ID капчи
        '''
        img_path = 'PythonRuCaptchaImages'

        if not os.path.exists(img_path):
            os.mkdir(img_path)

        # Высчитываем хэш изображения, для того что бы сохранить его под уникальным именем
        image_hash = hashlib.sha224(content).hexdigest()

        with open(os.path.join(img_path, 'im-{0}.png'.format(image_hash)), 'wb') as out_image:
            out_image.write(content)

        with open(os.path.join(img_path, 'im-{0}.png'.format(image_hash)), 'rb') as captcha_image:
            # Добавляем в пайлоад картинку и отправляем
            self.task_payload['task'].update({"body": base64.b64encode(captcha_image.read()).decode('utf-8')})
            # Отправляем на антикапча изображение капчи и другие парметры,
            # в результате получаем JSON ответ с номером решаемой капчи и получая ответ - извлекаем номер
            captcha_id = (requests.post(create_task_url,
                                        json=self.task_payload).json())

        # удаляем файл капчи и врменные файлы
        os.remove(os.path.join(img_path, "im-{0}.png".format(image_hash)))

        return captcha_id

    # Работа с капчёй
    def captcha_handler(self, captcha_link):
        '''
        Метод получает от вас ссылку на изображение, скачивает его, отправляет изображение на сервер
        RuCaptcha, дожидается решения капчи и вовзращает вам результат
        :param captcha_link: Ссылка на изображение
        :return: Возвращает список из 2 элементов: 1. Решённая капча; 2. Весь ответ сервера.
        '''

        content = requests.get(captcha_link).content

        # согласно значения переданного параметра выбираем функцию для сохранения изображения
        if self.save_format == 'const':
            captcha_id = self.image_const_saver(content)
        elif self.save_format == 'temp':
            captcha_id = self.image_temp_saver(content)
        else:
            return """Wrong 'save_format' parameter. Valid formats: 'const' or 'temp'.\n 
                    Неправильный 'save_format' параметр. Возможные форматы: 'const' или 'temp'."""

        # Проверка статуса создания задачи, если создано без ошибок - извлекаем ID задачи, иначе возвращаем тело ошибки
        if captcha_id['errorId'] == 0:
            captcha_id = captcha_id["taskId"]
        else:
            return captcha_id

        # Ожидаем решения капчи
        time.sleep(self.sleep_time)
        while True:
            # отправляем запрос на результат решения капчи, если ещё капча не решена - ожидаем 5 сек
            # если всё ок - идём дальше
            result_payload = {"clientKey": self.ANTICAPTCHA_KEY,
                              "taskId": captcha_id
                              }
            # отправляем запрос на результат решения капчи, если не решена ожидаем
            captcha_response = requests.post(get_result_url, json = result_payload)

            if captcha_response.json()['errorId'] == 0:
                if captcha_response.json()["status"] == "processing":
                    time.sleep(self.sleep_time)
                elif captcha_response.json()["status"] == "ready":
                    return captcha_response.json()["solution"]["text"], captcha_response.json()
                else:
                    return captcha_response.json()
            else:
                return captcha_response.json()