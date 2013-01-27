# -*- coding: utf-8 -*-
'''
Created on 26.01.2013

@author: Michael Vorotyntsev (https://github.com/unaxfromsibiria/)
'''

from django.contrib import admin
from .models import QiwiPayment, FakeAnswer


class QiwiPaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "qiwi_user", "qiwi_status", "amount", "external_order")
    readonly_fields = ('status_description', 'successful', 'failed')

admin.site.register(QiwiPayment, QiwiPaymentAdmin)


class FakeAnswerAdmin(admin.ModelAdmin):
    readonly_fields = ('qiwi_status', 'completed')
    list_display = ("id", "fake_status", "qiwi_status", "completed")

admin.site.register(FakeAnswer, FakeAnswerAdmin)
