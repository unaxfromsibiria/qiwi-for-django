# -*- coding: utf-8 -*-
'''
Created on 26.01.2013

@author: Michael Vorotyntsev (https://github.com/unaxfromsibiria/)
'''

import logging
from .models import QiwiPayment
from .soap_client import QiwiSoapClient
from annoying.functions import get_object_or_None
from constants import QiwiPaymentStatus
from django.conf import settings


def check_and_finish_payment(payment_id):
    """
    Контрольная проверка счета (запрос к серверу soap) и завершение транзакции
    """
    logger = logging.getLogger('payment')
    logger.debug('finish payment task: call for payment: {0}'\
                 .format(str(payment_id)))

    payment = get_object_or_None(QiwiPayment, id=payment_id)
    if payment is None:
        logger.error('finish payment task: payment not found! {0}'\
                     .format(str(payment_id)))
        return

    client = QiwiSoapClient(**settings.QIWI)
    result = client.checkBill(int(payment.id))
    if 'error' in result:
        payment.finish(QiwiPaymentStatus.REJECTED_UNKNOWN_ERROR,
                       successful=False,
                       description=result.get('error'))
    else:
        # проверка что счет оплачен
        try:
            status = int(result.get('status'))
        except (TypeError, ValueError):
            # формат статуса не совпадает с ожидаемым, прервать транзакцию
            logger.error('finish payment task: payment {0} has unknown qiwi status {1}'\
                     .format(str(payment_id, result.get('status'))))
            payment.finish(QiwiPaymentStatus.REJECTED_UNKNOWN_ERROR,
                           successful=False,
                           description="has unknown qiwi status {1}"\
                                        .format(result.get('status')))
            return

        if status == QiwiPaymentStatus.HAS_PAID:
            # суммы должны совпадать
            if payment.charge_amount == result.get('amount'):
                payment.finish(
                    status,
                    description='Correct finished. Created on qiwi: {0}, lifetime: {1}'\
                                .format(result.get('date_str'),
                                        result.get('lifetime_str')))
            else:
                logger.error('finish payment task: payment: {0} not found! Amount not equal! qiwi amount: {1}'\
                             .format(str(payment_id),
                                     result.get('amount')))
                payment.finish(
                    status,
                    successful=False,
                    description='Error! Amount changed! {0} != {1}'\
                                .format(payment.charge_amount, result.get('amount')))
        else:
            # такого статуса не должно случаться, только если у qiwi будут проблемы
            logger.error('finish payment task: payment: {0} has status {1} after successful paymen'\
                         .format(payment.id, status))
            payment.log_status(
                status,
                description="qiwi: {0}"\
                    .format(QiwiPaymentStatus.status_msg_by_code(status)))


def check_order_create(payment_id):
    logger = logging.getLogger('payment')
    logger.debug('check payment create task: call for payment: {0}'\
                 .format(str(payment_id)))

    payment = get_object_or_None(QiwiPayment, id=payment_id)
    if payment is None:
        logger.error('check payment create task: payment not found! {0}'\
                     .format(str(payment_id)))
        return

    client = QiwiSoapClient(**settings.QIWI)
    result = client.checkBill(int(payment.id))
    if 'error' in result:
        payment.finish(
            successful=False,
            QiwiPaymentStatus.REJECTED_UNKNOWN_ERROR,
            description=result.get('error'))
    else:
        try:
            status = int(result.get('status'))
        except (TypeError, ValueError):
            # формат статуса не совпадает с ожидаемым, прервать транзакцию
            logger.error('check payment create task: payment {0} has unknown qiwi status {1}'\
                     .format(str(payment_id, result.get('status'))))
            return
        payment.qiwi_status = status
        payment.save()
        logger.debug('check payment create task: payment {0} set qiwi status {1}'\
                     .format(str(payment_id, status)))
        # может быть ошибка счета сразу после создания, в этом случае транзакция завершится
        if QiwiPaymentStatus.is_error(status):
            logger.error('check payment create task: payment {0} has error qiwi status {1}'\
                     .format(str(payment_id, status)))
            payment.finish(
                status,
                successful=False,
                description="qiwi: {0}"\
                    .format(QiwiPaymentStatus.status_msg_by_code(status)))
