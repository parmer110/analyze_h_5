import os
import re
import json
import requests
import base64
import jdatetime
from django.conf import settings
from django.http import FileResponse
from rest_framework import viewsets
from rest_framework.response import Response
from django.http import HttpResponse
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import openpyxl
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
            shared_dir = r'C:\Users\eshraghi\Documents\esh\share\cm10\temp'
            calc_file_path = r'C:\Users\eshraghi\Documents\esh\share\cm10\source\میسکال  مشاوران - Main.xlsm'

            now = jdatetime.datetime.now()
            formatted_date = now.strftime('%Y_%m_%d_%H_%M_%S')

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
            
            ########################################################
            ########################################################
            # Export data file preparation
            # Request simulation core
            response = requests.post('https://api.hamkadeh.com/api/accounting/call-log/index', headers=headers, params=params)

            # Getting file name
            content_disposition = response.headers.get('Content-Disposition')

            if not os.path.exists(shared_dir):
                os.makedirs(shared_dir)

            if content_disposition:
                filename = re.findall('filename=(.+)', content_disposition)
                if filename:
                    filename = filename[0]
                    filename = f"{filename}_{formatted_date}.xlsx"
                else:
                    filename = f"{formatted_date}_response.xlsx"
            else:
                filename = f"{formatted_date}_response.xlsx"

            # Save exported file 
            file_path = os.path.join(shared_dir, filename)
            with open(file_path, 'wb') as f:
                f.write(response.content)

            
            ########################################################
            ########################################################
            # Calculation source loading & manipulation
            workbook = openpyxl.load_workbook(calc_file_path, keep_vba=True)

            # Access the sheets
            sheet1 = workbook['comand_center kol']
            sheet2 = workbook['comand_center-10min']
            sheet3 = workbook['Tamas_kol']

            # Perform the manipulations
            sheet1['B3'] = 14031026
            sheet1['B4'] = 14031026
            sheet1['B5'] = '12:00'
            sheet1['B6'] = '12:10'
            sheet2['B3'] = 14031026
            sheet2['B4'] = 14031026
            sheet2['B5'] = '00:00'
            sheet2['B6'] = '12:00'

            # Delete range A:M in Tamas_kol
            for row in sheet3.iter_rows(min_col=1, max_col=13):
                for cell in row:
                    cell.value = None

            # Extend formulas in range N:AM
            for row in sheet3.iter_rows(min_col=14, max_col=39):
                for cell in row:
                    # Assuming you want to copy formulas from A:M to N:AM
                    base_cell = sheet3.cell(row=cell.row, column=cell.column - 13)
                    cell.value = base_cell.value

            # Save the workbook
            workbook.save(r'C:\Users\eshraghi\Documents\esh\share\cm10\result.xlsm')

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