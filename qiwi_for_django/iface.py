# -*- coding: utf-8 -*-
'''
Created on 27.01.2013

@author: Michael Vorotyntsev (https://github.com/unaxfromsibiria/)
'''
import logging
from .constants import (
    CELERY_USED,
    LOGGER_NAME,
    QiwiPaymentStatus,
    QiwiFinalState
)
from .models import QiwiPayment
from .soap_client import QiwiSoapClient
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.encoding import smart_str

if CELERY_USED:
    from .celery_tasks import check_order_create_task
    check_payment = check_order_create_task.delay
else:
    from .verification import check_order_create
    check_payment = check_order_create


def create_payment(phone, amount, shop_order=None):
    """
    простой интерфейс создание платежа
    phone - в формате 9031005000
    amount - сумма счета
    shop_order - 
    """
    logger = logging.getLogger(LOGGER_NAME)
    payment = QiwiPayment(amount=amount,
                          qiwi_user=smart_str(phone))

    if isinstance(shop_order, models.Model):
        payment.external_order = shop_order.id

    operation_data = {'msg': None}
    try:
        payment.save()
    except ValidationError as err:
        operation_data.update(error=True,
                              msg=str(err))

    if 'error' in operation_data:
        return operation_data

    qiwi_client = QiwiSoapClient(**settings.QIWI)
    try:
        result_status = qiwi_client.createBill(
            user=payment.qiwi_user_number,
            amount=payment.charge_amount,
            payment_id=int(payment.id),
            comment=payment.description,
            lifetime=payment.lifetime,
            alarm=payment.alarm,
            create=payment.qiwi_user_create)
        logger.debug('QiwiSoapClient.createBill: for payment {0} call result: {1}'\
                     .format(payment.id, result_status))
    except (TypeError, ValueError) as err:
        logger.error('QiwiSoapClient.createBill: for payment {0} call error ({1})'\
                     .format(payment.id, err))
        payment.finish(QiwiPaymentStatus.UNKNOWN,
                       successful=False,
                       description=str(err))
        operation_data.update(error=True)
    #TODO: обработать ошибки soap подключения (HTTPError и другие)
    except Exception as err:
        logger.error('QiwiSoapClient.createBill: for payment {0} failed soap call ({1})'\
                     .format(payment.id, err))
        payment.finish(QiwiPaymentStatus.UNKNOWN,
                       successful=False,
                       description=str(err))
        operation_data.update(error=True)

    try:
        result_status = int(result_status)
    except (TypeError, ValueError):
        logger.error('QiwiSoapClient.createBill: for payment {0} result incorrect format ({1})'
                     .format(payment.id, result_status))
        payment.finish(QiwiPaymentStatus.UNKNOWN,
                       successful=False,
                       description='createBill result incorrect format ({0})'
                              .format(result_status))
        operation_data.update(error=True)

    # проверка результата
    if result_status == QiwiFinalState.SUCCESSFUL:
        # создалась
        payment.qiwi_status = QiwiPaymentStatus.CREATED
        payment.save()
        operation_data.update(wait=True)
    else:
        # вернулась ошибка
        logger.error('QiwiPayment: createBill for payment {0} result error ({1})'
                     .format(payment.id, result_status))
        state_message = QiwiFinalState.state_msg_by_code(result_status)
        payment.finish(payment,
                       successful=False,
                       description=state_message)
        operation_data.update(error=True,
                              msg=state_message)

    # и проверка статуса с задержкой
    if 'error' not in operation_data:
        check_payment(payment_id=payment.id)
    return operation_data


def create_fake_answer(txn, answer=0):
    """
    Быстрое создание поддельного ответа.
    answer должен быть числом из доступных в .constants.QiwiFinalState
    """
    from .models import FakeAnswer
    FakeAnswer(id=txn, fake_status=answer).save()
