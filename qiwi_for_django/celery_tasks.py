# -*- coding: utf-8 -*-
'''
Created on 27.01.2013

@author: Michael Vorotyntsev (https://github.com/unaxfromsibiria/)
'''

from .verification import check_and_finish_payment, check_order_create
from celery.task import task


@task
def check_and_finish_payment_task(payment_id):
    check_and_finish_payment(payment_id)


@task
def check_order_create_task(payment_id):
    check_order_create(payment_id)
