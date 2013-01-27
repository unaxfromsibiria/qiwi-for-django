# -*- coding: utf-8 -*-
'''
Created on 27.01.2013

@author: Michael Vorotyntsev (https://github.com/unaxfromsibiria/)
'''

from django.conf.urls import url, patterns

urlpatterns = patterns(
    'your_project.qiwi_for_django.views',
    url('^soap/$', 'soap_server', name='qiwi_soap_server'),
)
