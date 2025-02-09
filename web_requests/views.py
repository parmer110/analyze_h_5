import os
import re
import json
import requests
import base64
import jdatetime
import datetime
import time
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
from django.shortcuts import render
from .serializers import SendCodeSerializer, LoginSerializer, cm10Serializer
from .models import RequestLog, Requests


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
            # Request executation duration time
            starting_time = time.time()
            # Directories path
            shared_dir = r'C:\Users\eshraghi\Documents\esh\share\cm10\temp'
            calc_file_path = r'C:\Users\eshraghi\Documents\esh\share\cm10\source\میسکال  مشاوران - Main.xlsm'
            
            # Jalali Date Time
            now_jalali = jdatetime.datetime.now()
            formatted_jalali_date = now_jalali.strftime('%Y_%m_%d_%H_%M_%S')
            year = now_jalali.year
            month = now_jalali.month
            day = now_jalali.day
            
            # Gregorian Date Time
            gregorian_now = datetime.datetime.now()
            date_gregorian = gregorian_now.date()

            # Time handling
            hour = gregorian_now.hour
            # For "comand_center-10min" sheet and "comand_center kol" one in formula source
            nearest_hour = f"{hour:02}:00"
            # For "comand_center-10min" sheet in formula source
            ten_minutes_later = f"{hour:02}:10"
            # Handling request dynamically
            start_at_gregorian = serializer.validated_data.get('start_at', f"{date_gregorian} 00:00")
            end_at_gregorian = serializer.validated_data.get('end_at', f"{date_gregorian} {ten_minutes_later}")

            app = xw.App(visible=False)
            app.screen_updating = False
            
            # Login's token
            token = request.session.get('token')
            headers = {
                'Authorization': f'Bearer {token}'
            }
            
            # request parameters
            params = {
                'export_data': serializer.validated_data['export_data'],
                'call_type[]': serializer.validated_data['call_type'],
                'start_at':  start_at_gregorian,
                'end_at': end_at_gregorian
            }
            #endregion Initialization


            ########################################################
            #region Preparing Excel files
            # Downloading source Excel file
            # Request simulation core
            response = requests.post('https://api.hamkadeh.com/api/accounting/call-log/index', headers=headers, params=params)

            downloaded_df = pd.read_excel(BytesIO(response.content))
            # downloaded_df.to_excel(f'{shared_dir}\downloaded_df.xlsx', index=False)
            max_row = len(downloaded_df) + 1
            
            # Uploading reference Excel file + manipulation and merge before
            try:
                if calc_file_path in [book.fullname for book in app.books]:
                    workbook = app.books[calc_file_path]
                else:
                    try:
                        workbook = app.books.open(calc_file_path, update_links=False)
                    except FileNotFoundError:
                        print("The source file for CM10 was not found.")
                        # Handle the error appropriately, maybe return or exit
            #endregion Preparing Excel files

                workbook.app.calculation = 'manual'


                ########################################################
                # region Manipulation, Mixing, Calculate
                # Access the sheets
                # range for data entry
                sheet1 = workbook.sheets['comand_center kol']
                sheet2 = workbook.sheets['comand_center-10min']
                sheet3 = workbook.sheets['Tamas_kol']
                # range for convert same value
                sheet11 = workbook.sheets['miscal-Kol-10min']
                sheet12 = workbook.sheets['miss-Balla-10min']
                sheet13 = workbook.sheets['miss-Balla']
                sheet14 = workbook.sheets['miscal-Kol']


                # Perform the manipulations
                values_sheet1 = [
                    [f"{year}{month}{day}"],
                    [f"{year}{month}{day}"],
                    ['00:00'],
                    [nearest_hour]
                ]
                sheet1.range('B3:B6').value = values_sheet1
                values_sheet2 = [
                    [f"{year}{month}{day}"],
                    [f"{year}{month}{day}"],
                    [nearest_hour],
                    [ten_minutes_later]
                ]
                sheet2.range('B3:B6').value = values_sheet2                

                # Clear range A:M in Tamas_kol
                last_row = sheet3.range('A1').end('down').row
                sheet3.range(f'A1:M{last_row}').clear_contents()

                # Copy data to Tamas_kol
                sheet3.range('A1').options(index=False).value = downloaded_df.iloc[:, :13]

                # Extend formulas in range N:AM
                last_row = sheet3.range('N1').end('down').row
                if last_row < max_row:
                    formulas = [sheet3.cells(last_row, col).formula for col in range(14, 40)]
                    for col, formula in enumerate(formulas, start=14):
                        sheet3.range((last_row + 1, col), (max_row, col)).formula = formula
                # Clear any extra rows beyond max_row
                elif last_row > max_row:
                    sheet3.range(f'N{max_row + 1}:AM{last_row}').clear_contents()
                
                workbook.app.calculate()
                
                # Converting sheets to value
                for sheet in [sheet11, sheet12, sheet13, sheet14]:
                    range = sheet.used_range
                    range.value = range.value

                # sorting specific filtered column
                sheet12.range('B8:V8').expand('down').api.Sort(
                    Key1=sheet12.range("M9").api,
                    Order1=2,
                    Header=1,
                    Orientation=1
                )
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
                        filename = f"{filename}_{formatted_jalali_date}.xlsx"
                    else:
                        filename = f"response_{formatted_jalali_date}.xlsx"
                else:
                    filename = f"response_{formatted_jalali_date}.xlsx"

                # Save exported file 
                file_path = os.path.join(shared_dir, filename)
                with open(file_path, 'wb') as f:
                    f.write(response.content)

                # Reference (formulas)
                workbook.save(f'C:\\Users\\eshraghi\\Documents\\esh\\share\\cm10\\result_{formatted_jalali_date}.xlsm')
            
            finally:
                app.quit()
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

            ext_duration = datetime.timedelta(seconds=time.time() - starting_time)

            log = RequestLog.objects.create(
                request_name="Consultant Misscall 10 minutes",
                username=request.session.get('username'),
                request_type='POST',
                request_data=serializer.validated_data,
                response_data=response_data if response.headers.get('Content-Type') == 'application/json' else None,
                file_path=file_path if response.headers.get('Content-Type') != 'application/json' else None,
                additional_info={'status_code': response.status_code},
                execution_time=ext_duration
                
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
    
###########################################
def run(request):
    req = Requests.objects.all()
    return render(request, "web_requests/index.html", {
        "requests": req
    })
