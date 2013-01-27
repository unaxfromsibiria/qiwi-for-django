# -*- coding: utf-8 -*-
'''
Created on 25.01.2013

@author: Michael Vorotyntsev (https://github.com/unaxfromsibiria/)
'''

# имя логера для платежей через qiwi
LOGGER_NAME = 'qiwi'

# используется celery
CELERY_USED = True

# время жизни счета 2-ое суток
DEFAULT_LIFETIME = 3600 * 48

ALARM_CHOICES = ((0, u"Не отправлялось"),
                 (1, u"SMS"),
                 (2, u"Звонок по телефону"),)


# Справочник кодов завершения
class QiwiFinalState:
    SUCCESSFUL = 0
    SERVER_BUSY = 13
    AUTH_REJECTED = 150
    PAYMENT_NOTFOUND = 210
    PAYMENT_ALREADY_EXIST = 215
    AMOUNT_TO_SMALL = 241
    AMOUNT_TO_MUCH = 242
    TIME_INTERVAL_OUT_OF_BAND = 278
    UNKNOWN_AGENT = 298
    UNKNOWN_ERROR = 300
    ENCRYPTION_ERROR = 330
    DATA_FORMAT_ERROR = 341
    LOAD_LIMIT_EXTENDED = 370

    CHOICES = (
        (None, u"Неизвестно"),
        (SUCCESSFUL, u"Успех"),
        (SERVER_BUSY, u"Сервер занят, повторите запрос позже"),
        (AUTH_REJECTED, u"Ошибка авторизации (неверный логин/пароль)"),
        (PAYMENT_NOTFOUND, u"Счет не найден"),
        (PAYMENT_ALREADY_EXIST, u"Счет с таким txn-id уже существует"),
        (AMOUNT_TO_SMALL, u"Сумма слишком мала"),
        (AMOUNT_TO_MUCH, u"Превышена максимальная сумма платежа – 15 000р."),
        (TIME_INTERVAL_OUT_OF_BAND, u"Превышение максимального интервала получения списка счетов"),
        (UNKNOWN_AGENT, u"Агента не существует в системе"),
        (UNKNOWN_ERROR, u"Неизвестная ошибка"),
        (ENCRYPTION_ERROR, u"Ошибка шифрования"),
        (DATA_FORMAT_ERROR, u"Ошибка в форматах данных"),
        (LOAD_LIMIT_EXTENDED, u"Превышено максимальное кол-во одновременно выполняемых запросов"),)

    @classmethod
    def state_msg_by_code(cls, code):
        for has_code, msg in cls.CHOICES:
            if code == has_code:
                return u'Qiwi: {0}'.format(msg)
        return u'Qiwi: Неизвестный код завершения: {0}'.format(code)


# Справочник статусов счетов
class QiwiPaymentStatus:
    UNKNOWN = 0
    CREATED = 50
    PROCESSING = 52
    HAS_PAID = 60
    REJECTED_TERMINAL_ERROR = 150
    REJECTED_COMPLEX_ERROR = 151
    REJECTED_UNKNOWN_ERROR = 160
    REJECTED_TIMEOUT_ERROR = 161

    CHOICES = (
    (UNKNOWN, u"Ошибка не на стороне Qiwi"),
    (CREATED, u"Выставлен"),
    (PROCESSING, u"Проводится"),
    (HAS_PAID, u"Оплачен"),
    (REJECTED_TERMINAL_ERROR, u"Отменен (ошибка на терминале)"),
    (REJECTED_COMPLEX_ERROR, u"Отменен (ошибка авторизации: недостаточно средств на балансе, отклонен абонентом при оплате с лицевого счета оператора сотовой связи и т.п.)."),
    (REJECTED_UNKNOWN_ERROR, u"Отменен"),
    (REJECTED_TIMEOUT_ERROR, u"Отменен (Истекло время)"),)

    @classmethod
    def status_msg_by_code(cls, code):
        for has_code, msg in cls.CHOICES:
            if code == has_code:
                return u'Qiwi: {0}'.format(msg)
        return u'Qiwi: Неизвестный код завершения: {0}'.format(code)

    @classmethod
    def is_error(cls, code):
        return  code in [cls.REJECTED_COMPLEX_ERROR,
                         cls.REJECTED_TERMINAL_ERROR,
                         cls.REJECTED_TIMEOUT_ERROR,
                         cls.REJECTED_UNKNOWN_ERROR]
