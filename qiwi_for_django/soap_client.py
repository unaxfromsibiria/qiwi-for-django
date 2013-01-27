# -*- coding: utf-8 -*-
'''
Created on 26.01.2013

@author: Michael Vorotyntsev (https://github.com/unaxfromsibiria/)
'''

import SOAPpy
import logging
from constants import QiwiPaymentStatus, LOGGER_NAME
from datetime import datetime
from decimal import Decimal
from django.utils.timezone import utc


class QiwiSoapClient(object):
    """ простая обертка над клиентом + проверка валидности параметров """
    __soappy_connection = None
    _logger = None
    __configuration = None
    __datetime_format = "%d.%m.%Y %H:%M:%S"

    @property
    def soappy_connection(self):
        if self.__soappy_connection is None:
            self.__soappy_connection = SOAPpy.SOAPProxy(self.__configuration.get('soap_url'))
        return self.__soappy_connection

    def __init__(self, **configuration):
        """
        Формат настроект такой же как у settings.QIWI (login, password, soap_url)
        """
        self._logger = logging.getLogger(LOGGER_NAME)
        if configuration:
            self.__configuration = configuration 
        else:
            self._logger.warn(self.__message_format("Client configuration doesn't exist!"))
            raise Exception("Client configuration doesn't exist!")

    def __message_format(self, text):
        return u'{0}: {1}'.format(self.__class__.__name__, text)

    def createBill(self, user, amount, payment_id, comment, lifetime, alarm=0, create=False):
        """
        Запрос на выставление счета пользователю.

        user - id (телефон)
        amount - сумма на которую выставляется счет. тип: Decimal
        payment_id - id платежа
        comment - комментарий к счету. тип: unicode
        lifetime - время завершения жизни счета. тип: datetime
        alarm - отправить оповещение пользователю (смс - 1, звонок - 2, не оповещать - 0)
        create - флаг для создания нового пользователя (если он не зарегистрирован в системе)
        """

        if not isinstance(user, int) or user < 1:
            raise ValueError(self.__message_format('User incorrect!'))

        if not isinstance(amount, Decimal) or amount < 0.01:
            raise ValueError(self.__message_format('Amount incorrect!'))

        if not isinstance(payment_id, int) or payment_id < 1:
            raise ValueError(self.__message_format('Payment id incorrect!'))

        if not isinstance(comment, (unicode, str)):
            comment = 'payment: {0}'.format(payment_id)
        elif len(comment) > 255:
            comment = comment[0:255]

        if not isinstance(lifetime, datetime):
            raise ValueError('Life time incorrect!')

        if not isinstance(alarm, int) or alarm not in [0, 1, 2]:
            raise ValueError('Alarm incorrect!')

        create_user = 0
        if create:
            create_user = 1

        res = self.soappy_connection.createBill(
            login=self.__configuration.get('login'),
            password=self.__configuration.get('password'),
            user='{0}'.format(user),
            amount=str(amount),
            comment=comment,
            txn=str(payment_id),
            lifetime=lifetime.strftime(self.__datetime_format),
            alarm=alarm,
            create=create_user)

        try:
            return int(res)
        except:
            raise TypeError('Answer of createBill has incorrect format!')

    def cancelBill(self, payment_id):
        """
        Запрос на отмену неоплаченного счета.
        """
        if not isinstance(payment_id, int) or payment_id < 1:
            raise ValueError(self.__message_format('Payment id incorrect!'))

        res = self.soappy_connection.cancelBill(
            login=self.__configuration.get('login'),
            password=self.__configuration.get('password'),
            txn=str(payment_id))

        try:
            return int(res)
        except (TypeError, ValueError):
            raise TypeError('Answer of createBill has incorrect format!')

    def checkBill(self, payment_id):
        """
        Запрос на получение информации о выставленном счете.
        В случае успешной обработки запроса в параметре status указывается положительное число - статус платежа,
        в случае ошибки - отрицательное число с кодом ошибки.
        Возвращает dict с обязательным 'status', с возможным описанием ошибки 'error'
        payment_id - уникальный идентификатор счета
        """
        if not isinstance(payment_id, int) or payment_id < 1:
            raise ValueError(self.__message_format('Payment id incorrect!'))

        res = self.soappy_connection.checkBill(
            login=self.__configuration.get('login'),
            password=self.__configuration.get('password'),
            txn=str(payment_id))

        payment_data = {}
        try:
            payment_data.update(status=int(res.status))
        except (TypeError, ValueError):
            return {'error': 'Answer of createBill has incorrect format of status!',
                    'status': QiwiPaymentStatus.REJECTED_UNKNOWN_ERROR}

        if payment_data.get('status') < 0:
            return {'error': QiwiPaymentStatus.status_msg_by_code(
                                abs(payment_data.get('status'))),
                    'status': abs(payment_data.get('status'))}

        try:
            payment_data.update(
                user = res.user,
                date = datetime.strptime(res.date, self.__datetime_format).replace(tzinfo=utc),
                date_str = res.date,
                lifetime = datetime.strptime(res.lifetime, self.__datetime_format).replace(tzinfo=utc),
                lifetime_str = res.lifetime,
                amount = Decimal(res.amount)
            )
        except (TypeError, ValueError):
            return {'error': 'Answer of createBill has incorrect data format!',
                    'status': QiwiPaymentStatus.REJECTED_UNKNOWN_ERROR}
        return payment_data
