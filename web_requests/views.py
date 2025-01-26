import os
import re
import json
import requests
import base64
from django.conf import settings
from django.http import FileResponse
from rest_framework import viewsets
from rest_framework.response import Response
from django.http import HttpResponse
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from openpyxl import load_workbook
import xlwings as xw
import pandas as pd
from io import BytesIO
from .serializers import SendCodeSerializer, LoginSerializer, cm10Serializer
from .models import RequestLog


class SendSMSCodeViewSeHamkadeh(viewsets.ViewSet):
    def create(self, request):
        serializer = SendCodeSerializer(data=request.data)
        if serializer.is_valid():
            response = requests.post('https://api.hamkadeh.com/api/auth/login/send-code', json=serializer.validated_data)
            log = RequestLog.objects.create(
                username=serializer.validated_data['username'],
                request_type='send_code',
                request_data=serializer.validated_data,
                response_data=response.json()
            )
            return Response(response.json())
        return Response(serializer.errors, status=400)

class LoginViewSetHamkadeh(viewsets.ViewSet):
    def create(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            response = requests.post('https://api.hamkadeh.com/api/auth/login', json=serializer.validated_data)
            log = RequestLog.objects.create(
                username=serializer.validated_data['username'],
                request_type='login',
                request_data=serializer.validated_data,
                response_data=response.json()
            )
            token = response.json().get('token')
            if token:
                request.session['token'] = token
                request.session['username'] = serializer.validated_data['username']
                # request.session['token'] = response.data.get('token')
            return Response(response.json())
        return Response(serializer.errors, status=400)
    

class cm10(viewsets.ViewSet):
    def create(self, request):
        serializer = cm10Serializer(data=request.data)
        if serializer.is_valid():

            # Initialization
            token = request.session.get('token')
            headers = {
                'Authorization': f'Bearer {token}'
            }
            params = {
                'export_data': serializer.validated_data['export_data'],
                'call_type[]': serializer.validated_data['call_type'],
                'start_at': serializer.validated_data['start_at'],
                'end_at': serializer.validated_data['end_at']
            }
            shared_dir = '/mnt/shared'

            # Request simulation core
            response = requests.post('https://api.hamkadeh.com/api/accounting/call-log/index', headers=headers, params=params)
            df = pd.read_excel(BytesIO(response.content))

            existing_wb = xw.Book('/mnt/shared/source/میسکال  مشاوران - Main.xlsm')
            
            combined_file_path = '/mnt/shared/combined_response.xlsm'
            existing_wb.save(combined_file_path)





            # File exporting
            content_disposition = response.headers.get('Content-Disposition')
            if not os.path.exists(shared_dir):
                os.makedirs(shared_dir)

            if content_disposition:
                filename = re.findall('filename="(.+)"', content_disposition)
                if filename:
                    filename = filename[0]
                else:
                    filename = 'response.xlsx'
            else:
                filename = 'response.xlsx'
                            
            file_path = os.path.join(shared_dir, filename)
            with open(file_path, 'wb') as f:
                f.write(response.content)

            if response.headers.get('Content-Type') == 'application/json':
                try:
                    response_data = response.json()
                except json.JSONDecodeError:
                    response_data = response.text
            else:
                response_data = base64.b64encode(response.content).decode('utf-8')

            # request simulation logging
            log = RequestLog.objects.create(
                username=request.session.get('username'),
                request_type='POST',
                request_data=serializer.validated_data,
                response_data=response_data if response.headers.get('Content-Type') == 'application/json' else None,
                file_path=file_path if response.headers.get('Content-Type') != 'application/json' else None,
                additional_info={'status_code': response.status_code}
            )

            # Django response
            if response.headers.get('Content-Type') == 'application/json':
                try:
                    return Response(response.json())
                except json.JSONDecodeError:
                    return Response(response.text, status=response.status_code)
            else:
                return Response(response.text, status=response.status_code)

        return Response(serializer.errors, status=400)