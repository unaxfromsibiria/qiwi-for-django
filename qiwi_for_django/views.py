# -*- coding: utf-8 -*-
'''
Created on 27.01.2013

@author: Michael Vorotyntsev (https://github.com/unaxfromsibiria/)
'''
from .handler import QiwiSoapServer
from django.views.decorators.csrf import csrf_exempt


soap_server = csrf_exempt(QiwiSoapServer.create())
