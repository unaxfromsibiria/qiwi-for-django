# -*- coding: utf-8 -*-
'''
Created on 26.01.2013

@author: Michael Vorotyntsev (https://github.com/unaxfromsibiria/)
'''

import logging
from .models import QiwiPayment, FakeAnswer
from annoying.functions import get_object_or_None
from constants import (
    QiwiFinalState,
    QiwiPaymentStatus,
    LOGGER_NAME,
    CELERY_USED
)
from django.conf import settings
from django.http import HttpResponse
from django.utils.encoding import smart_str, smart_unicode
from django.utils.timezone import now as datetime_now
from hashlib import md5
from spyne.application import Application
from spyne.decorator import rpc
from spyne.interface.wsdl import Wsdl11
from spyne.model.primitive import Integer, String
from spyne.protocol.soap import Soap11
from spyne.server.wsgi import WsgiApplication
from spyne.service import ServiceBase


if CELERY_USED:
    from .celery_tasks import check_and_finish_payment_task
    finish_payment = check_and_finish_payment_task.delay
else:
    from .verification import check_and_finish_payment
    finish_payment = check_and_finish_payment


def check_auth(login, password, txn):
    """
    сверка подписи (смотреть документацию qiwi)
    """
    qiwi_conf = settings.QIWI
    return password == md5(smart_str(txn) + md5(qiwi_conf.get('password'))\
                           .hexdigest().upper()).hexdigest().upper()\
           and login == qiwi_conf.get('login')


# ======= методы изменения состояния платежа ========
def payment_created(payment=None, **kwargs):
    payment.qiwi_status = QiwiPaymentStatus.CREATED
    payment.save()
    return QiwiFinalState.SUCCESSFUL


def payment_processing(payment=None, **kwargs):
    payment.qiwi_status = QiwiPaymentStatus.PROCESSING
    payment.save()
    return QiwiFinalState.SUCCESSFUL


def payment_finish(payment=None, **kwargs):
    """
    Успешное завершение платежа с проверкой через дополнитеьный запрос к qiwi api
    """
    # смена qiwi статуса будет в любом случае
    payment.qiwi_status = kwargs.get('status')
    payment.save()
    # а вот системе статус поменяется только после дополнительной проверки
    finish_payment(payment_id=payment.id)
    return QiwiFinalState.SUCCESSFUL


def payment_failed(payment=None,
                   status=QiwiPaymentStatus.REJECTED_UNKNOWN_ERROR,
                   logger=None,
                   **kwargs):
    payment.finish(status, successful=False)
    if logger:
        who = kwargs.get('who')
        if who is None:
            who = 'payment_failed'
        logger.debug(u"{1}: qiwi notes of rejected payment: {0}"\
                     .format(payment.id, who))
    return QiwiFinalState.SUCCESSFUL

# набор функций изменения транзакции
update_payment_methods = {
    QiwiPaymentStatus.CREATED: payment_created,
    QiwiPaymentStatus.PROCESSING: payment_processing,
    QiwiPaymentStatus.HAS_PAID: payment_finish,
    QiwiPaymentStatus.REJECTED_COMPLEX_ERROR: payment_failed,
    QiwiPaymentStatus.REJECTED_TERMINAL_ERROR: payment_failed,
    QiwiPaymentStatus.REJECTED_TIMEOUT_ERROR: payment_failed,
    QiwiPaymentStatus.REJECTED_UNKNOWN_ERROR: payment_failed,
}


def check_fake(payment_id, qiwi_status):
    """
    Проверка есть ли поддельный ответ для qiwi
    """
    fake = get_object_or_None(FakeAnswer, id=payment_id,
                              completed__isnull=True)
    if fake:
        fake.completed = datetime_now()
        if isinstance(qiwi_status, int):
            fake.qiwi_status = qiwi_status
        fake.save()
        return fake.fake_status


def update_qiwi_payment(login=None, password=None, txn=None, status=None,
                            params=[], who='QiwiSoapServer'):
    """
    Реализация обновления платежа в системе.
    После предварительных действий смена состояния платежа будет передано функциям из update_payment_methods
    """
    logger = logging.getLogger(LOGGER_NAME)
    logger.debug(u"==>> {5}: login='{0}' password='{1}' txn='{2}' status='{3}' params count='{4}'"\
                 .format(login, password, txn, status, len(params), who))

    if not check_auth(login, password, txn):
        logger.error(u"{2}: login='{0}' payment='{1}' auth rejected!"\
                     .format(login, txn, who))
        return QiwiFinalState.AUTH_REJECTED
    try:
        # статусы платежа у qiwi целочисленные
        status = int(status)
    except (TypeError, ValueError):
        logger.error(u"{2}: incorrect status ({0}) of payment: {1}"\
                     .format(status, txn, who))
        return QiwiFinalState.UNKNOWN_ERROR

    # проверка поддельного ответа (до того как будет известно что txn должно быть целым числом)
    fake_answer = check_fake(smart_unicode(txn), status)
    if isinstance(fake_answer, int):
        logger.info(u"{2}: fake answer: {0} for payment: {1}"\
                    .format(fake_answer, txn, who))
        return fake_answer

    try:
        payment_id = int(txn)
    except (TypeError, ValueError):
        logger.error(u"{1}: incorrect payment id: {0}".format(txn, who))
        return QiwiFinalState.PAYMENT_NOTFOUND

    payment = get_object_or_None(QiwiPayment, id=payment_id)
    if payment is None:
        logger.error(u"{1}: payment not found id: {0}".format(payment_id, who))
        return QiwiFinalState.PAYMENT_NOTFOUND

    # выбор дальнейших действий над платежем 
    update_payment_method = update_payment_methods.get(status)
    if update_payment_method is None:
        # возможно если у qiwi появятся новые статусы платежей
        logger.error(u"{1}: unknown status: {0}".format(status, who))
        return QiwiFinalState.UNKNOWN_ERROR
    else:
        logger.info(u"{2}: payment: {0} updating to status: {1}"\
                    .format(payment_id, status, who))

        return update_payment_method(
                    payment=payment,
                    status=status,
                    logger=logger,
                    who=who,
                    params=params)


# для soap сервера пришлось сделать немного 
class DjangoApplication(WsgiApplication):
    debug_mode = None

    def __call__(self, request):
        django_response = HttpResponse()

        def start_response(status, headers):
            status, reason = status.split(' ', 1)

            django_response.status_code = int(status)
            for header, value in headers:
                django_response[header] = value

        environ = request.META.copy()
        environ['wsgi.input'] = request
        environ['wsgi.multithread'] = False
        response = WsgiApplication.__call__(self, environ, start_response)
        #TODO: можно сказать, что это костыль, без него не работает.
        #Может быть когда то spyne научится делать это сам, как надо sopa клиенту qiwi
        data = (u"".join(response))\
                    .replace('tns:updateBillResult', 'updateBillResult')

        if self.debug_mode is None:
            self.debug_mode = bool(settings.DEBUG)

        if self.debug_mode:
            logger = logging.getLogger(LOGGER_NAME)
            logger.debug(u'soap response content: {0}'.format(data))

        django_response.content = data
        if django_response.has_header('Content-Length'):
            django_response['Content-Length'] = len(data)

        return django_response


class QiwiSoapServer(ServiceBase):
    """
    Обработчик ответов от Qiwi
    """
    @rpc(String(encoding='utf-8'),
         String(encoding='utf-8'),
         String(encoding='utf-8'),
         Integer,
          _body_style='bare',
          _soap_body_style='rpc',
          _returns=Integer)
    def updateBill(self, login=None, password=None, txn=None, status=None):
        return update_qiwi_payment(
            login=login,
            password=password,
            txn=txn,
            status=status,
            who='QiwiSoapServer.updateBill')

    @classmethod
    def create(cls):
        return DjangoApplication(
            Application(
                [cls],
                'http://client.ishop.mw.ru/',
                name='IShopClientWS',
                in_protocol=Soap11(),
                out_protocol=Soap11(),
                interface=Wsdl11()
            ))
