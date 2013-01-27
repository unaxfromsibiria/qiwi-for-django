# -*- coding: utf-8 -*-
'''
Created on 26.01.2013

@author: Michael Vorotyntsev (https://github.com/unaxfromsibiria/)
'''

from annoying.functions import get_object_or_None
from constants import (
    QiwiFinalState,
    QiwiPaymentStatus,
    DEFAULT_LIFETIME,
    ALARM_CHOICES
)
from datetime import timedelta
from django.db import models
from django.utils.timezone import now as datetime_now
from random import randint
from time import time
from django.utils.encoding import smart_unicode


def create_id():
    return int(time() * 100) * 1000 + randint(100, 999)


class FakeAnswer(models.Model):
    """
    Это подделка ответа.
    Статус, который получит в ответ qiwi сервис на запрс обновления счета может быть любой.
    Можно создать запись с любым id, и любым статусом.
    """
    id = models.CharField(u"Псеводозаказ",
        max_length=30, primary_key=True)

    fake_status = models.IntegerField(u"Вернуть статус QIWI",
        default=0, blank=True, choices=QiwiFinalState.CHOICES)

    qiwi_status = models.IntegerField(u"Статус в системе QIWI",
        default=0, blank=True, choices=QiwiPaymentStatus.CHOICES)

    completed = models.DateField(u'Была запрошена',
        default=None, blank=False, null=True)

    class Meta:
        verbose_name = u'Фэйк ответа для QIWI'
        verbose_name_plural = u'Фэйк ответов для QIWI'


class QiwiPayment(models.Model):
    """ Платеж в системе QIWI """

    id = models.BigIntegerField(u"Идентификатор", primary_key=True)

    successful = models.DateTimeField(u"Оплачено",
                                      default=None, null=True, blank=False)
    failed = models.DateTimeField(u"Завершено с ошибкой",
                                  default=None, null=True, blank=False)

    external_order = models.IntegerField(u"Идентификатор заказа в магазине",
        default=None, blank=False, null=True, db_index=True)
    """ это может быть индефикатор сущности заказа (внешний ключ) если он вам нужен """

    amount = models.DecimalField("Сумма", decimal_places=2, max_digits=12)

    qiwi_timeout = models.IntegerField(u"Время жизни заказа",
        blank=True, default=DEFAULT_LIFETIME)
    """ liftime - время действия счета в секундах"""

    alarm = models.IntegerField(u"Уведомление клиента",
        default=0, choices=ALARM_CHOICES)
    """ уведомление """

    qiwi_user = models.CharField(u"Идентификатор пользователя (номер телефона)",
        max_length=16, default=None, blank=False, null=True)
    """ id пользователя (телефон) может быть пустой на момет создания """

    qiwi_status = models.IntegerField(u"Статус в системе QIWI",
        default=0, blank=True, choices=QiwiPaymentStatus.CHOICES)
    """ статус платежа в системе QIWI """

    qiwi_user_create = models.BooleanField(u"Создавать QIWI аккаунт",
        default=False)
    """ запрос на создание аккаунта в системе QIWI """

    status_description = models.CharField(u"Пометка о состоянии платежа",
                                          max_length=255, null=True, blank=False, default=None)

    class Meta:
        verbose_name = u'Счет в QIWI'
        verbose_name_plural = u'Счета в системе QIWI'

    @property
    def lifetime(self):
        """ возвращается дату завершения """
        created = self.created_at
        if not created:
            created = datetime_now()
        return created + timedelta(seconds=self.qiwi_timeout)

    @property
    def qiwi_user_number(self):
        """ id кошелька или номер должны конвертироваться в целочисленный тип """
        try:
            return int(self.qiwi_user)
        except (TypeError, ValueError):
            return 0

    def shop_oreder(self, model_class):
        """ получение объекта заказа """
        if issubclass(model_class, models.Model)\
        and isinstance(self.external_order, int):
            return get_object_or_None(model_class, id=self.external_order)

    def save(self, force_insert=False, force_update=False, using=None):
        new_id = create_id()
        while QiwiPayment.objects.filter(id=new_id).exists():
                new_id = create_id()
        super(QiwiPayment, self).save(force_insert=force_insert,
                                      force_update=force_update,
                                      using=using)

    def finish(self, status, successful=True, description=None):
        if successful:
            self.successful = datetime_now()
            self.failed = None
        else:
            self.failed = datetime_now()
            self.successful = None
        if description:
            self.status_description = smart_unicode(description)[:255]
        else:
            self.status_description =\
            smart_unicode(QiwiPaymentStatus.status_msg_by_code(status))[:255]
        self.qiwi_status = status
        self.save()
