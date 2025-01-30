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
            
            ########################################################
            #region Initialization
            # Directories path
            shared_dir = r'C:\Users\eshraghi\Documents\esh\share\cm10\temp'
            calc_file_path = r'C:\Users\eshraghi\Documents\esh\share\cm10\source\میسکال  مشاوران - Main.xlsm'
            
            # Hijri Date Time
            now = jdatetime.datetime.now()
            formatted_date = now.strftime('%Y_%m_%d_%H_%M_%S')
            year = now.year
            month = now.month
            day = now.day
            hour = now.hour
            minute = now.minute
            nearest_hour = f"{hour:02}:00"
            ten_minutes_later = f"{hour:02}:10"
            date_part = '-'.join(formatted_date.split('_')[:3])
            start_at = request.data.get('start_at', f"{date_part} 00:00")
            end_at = request.data.get('end_at', f"{date_part} {ten_minutes_later}")
            
            # Login's token
            token = request.session.get('token')
            headers = {
                'Authorization': f'Bearer {token}'
            }
            
            # request parameters
            params = {
                'export_data': serializer.validated_data['export_data'],
                'call_type[]': serializer.validated_data['call_type'],
                'start_at':  start_at,
                'end_at': end_at
            }

            #endregion Initialization


            ########################################################
            #region Preparing Excel files
            # Downloading source Excel file
            # Request simulation core
            response = requests.post('https://api.hamkadeh.com/api/accounting/call-log/index', headers=headers, params=params)

            downloaded_workbook = openpyxl.load_workbook(BytesIO(response.content))
            # Set calculation mode to manual
            downloaded_workbook.calculation = openpyxl.workbook.properties.CalcProperties(calcMode='manual')

            downloaded_sheet1 = downloaded_workbook['Sheet1']
            
            max_row = downloaded_sheet1.max_row
            max_col = 13
            
            # Uploading reference Excel file + manipulation and merge before
            try:
                workbook = openpyxl.load_workbook(calc_file_path, keep_vba=True)
                workbook.calculation =openpyxl.workbook.properties.CalcProperties(calcMode='manual')
            except FileNotFoundError:
                print("The source file for CM10 was not found.")
            #endregion Preparing Excel files


            ########################################################
            # region Manipulation, Mixing, Calculate
            # Access the sheets
            sheet1 = workbook['comand_center kol']
            sheet2 = workbook['comand_center-10min']
            sheet3 = workbook['Tamas_kol']

            # Perform the manipulations            
            sheet1['B3'] = f"{year}{month}{day}"
            sheet1['B4'] = f"{year}{month}{day}"
            sheet1['B5'] = '00:00'
            sheet1['B6'] = nearest_hour
            sheet2['B3'] = f"{year}{month}{day}"
            sheet2['B4'] = f"{year}{month}{day}"
            sheet2['B5'] = nearest_hour
            sheet2['B6'] = ten_minutes_later

            # Delete range A:M in Tamas_kol
            for row in sheet3.iter_rows(min_col=1, max_col=13):
                for cell in row:
                    cell.value = None

            # Copy data to Tamas_kol
            for row in range(1, max_row + 1):
                for col in range(1, max_col + 1):
                    cell_value = downloaded_sheet1.cell(row=row, column=col).value
                    sheet3.cell(row=row, column=col).value = cell_value

            # Extend formulas in range N:AM
            for row in range(1, max_row + 1):
                for col in range(14, 40):  # Columns N to AM
                    formula_cell = sheet3.cell(row=row, column=col)
                    base_formula = formula_cell.value
                    formula_cell.value = base_formula

            # Clear any extra rows beyond max_row
            for row in range(max_row + 1, sheet3.max_row + 1):
                for col in range(14, 40):  # Columns N to AM
                    sheet3.cell(row=row, column=col).value = None
            #endregion Manipulation, Mixing, Calculate


            ########################################################
            # Save workbooks
            # Downloaded
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
                    filename = f"response_{formatted_date}.xlsx"
            else:
                filename = f"response_{formatted_date}.xlsx"

            # Save exported file 
            file_path = os.path.join(shared_dir, filename)
            with open(file_path, 'wb') as f:
                f.write(response.content)

            # Reference (formulas)
            workbook._calculation_mode = 'auto'
            workbook.save(f'C:\\Users\\eshraghi\\Documents\\esh\\share\\cm10\\result_{formatted_date}.xlsm')
            #endregion Save workbooks


            ########################################################
            #region Database logging
            if response.headers.get('Content-Type') == 'application/json':
                try:
                    response_data = response.json()
                except json.JSONDecodeError:
                    response_data = response.text
            else:
                response_data = base64.b64encode(response.content).decode('utf-8')

            log = RequestLog.objects.create(
                username=request.session.get('username'),
                request_type='POST',
                request_data=serializer.validated_data,
                response_data=response_data if response.headers.get('Content-Type') == 'application/json' else None,
                file_path=file_path if response.headers.get('Content-Type') != 'application/json' else None,
                additional_info={'status_code': response.status_code}
            )
            #endregion  Database logging


            ########################################################
            #region Django response
            if response.headers.get('Content-Type') == 'application/json':
                try:
                    return Response(response.json())
                except json.JSONDecodeError:
                    return Response(response.text, status=response.status_code)
            else:
                return Response(response.text, status=response.status_code)
            #endregion Django response


        return Response(serializer.errors, status=400)