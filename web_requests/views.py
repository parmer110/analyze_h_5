import os
import re
import json
import requests
import base64
import pickle
import jdatetime
import datetime
import time
import random
import asyncio
import logging
import ast
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework import status
import xlwings as xw
import pandas as pd
from io import BytesIO
from django.shortcuts import render
from concurrent.futures import ThreadPoolExecutor
from playwright.sync_api import sync_playwright
from concurrent.futures import ThreadPoolExecutor
from asgiref.sync import sync_to_async
from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from django_q.tasks import schedule
from django_q.models import Schedule
from django.core.exceptions import ObjectDoesNotExist
from .serializers import SendCodeSerializer, LoginSerializer, AccountingCallLog
from .models import RequestLog, Requests, WebTokens
from common.models import User


logger = logging.getLogger(__name__)

class SendSMSCodeViewSeHamkadeh(viewsets.ViewSet):
    def create(self, request):
        serializer = SendCodeSerializer(data=request.data)
        if serializer.is_valid():
            response = requests.post('https://api.hamkadeh.com/api/auth/login/send-code', json=serializer.validated_data)
            log = RequestLog.objects.create(
                request_name = 'Send SMS Hamkahdeh',
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
                request_name = 'login Hamkadeh',
                username=serializer.validated_data['username'],
                request_type='login',
                request_data=serializer.validated_data,
                response_data=response.json()
            )
            token_h = response.json().get('token')
            if token_h:
                request.session['token_h'] = token_h
                request.session['username_h'] = serializer.validated_data['username']
            return Response(response.json())
        return Response(serializer.errors, status=400)


def run_playwright_for_login_5040(username, password):
    with sync_playwright() as p:
        with p.chromium.launch(headless=True) as browser:
            context = browser.new_context()
            page = context.new_page()
            page.goto('https://panel.5040.me/auth/login', timeout=60000)
            page.fill('input[name="login-username"]', username)
            page.fill('input[name="password"]', password)
            page.click('button:has-text("ارسال کد با پیامک")')
            page.wait_for_load_state('networkidle')
            
            while True:
                try:
                    sms_code = input("Enter the SMS code: ")
                    int(sms_code)
                    break
                except:
                    pass                
            
            page.fill('input[name="login-code"]', sms_code)
            
            with page.expect_response(
                lambda response: "api/auth/login" in response.url and response.status == 200, timeout=60000
            ):
                page.click('button:has-text("ورود به سیستم")')
            
            page.wait_for_load_state('networkidle')
            cookies = context.cookies("https://panel.5040.me")
            return cookies, sms_code

################################### 5040 login handlation #####################################
class LoginViewSet5040(viewsets.ViewSet):

    scheduled_jobs = {}

    def create(self, request):
        serializer = SendCodeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        
        username = serializer.validated_data['username']
        password = serializer.validated_data['password']

        # User not exist error handling
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            log = RequestLog.objects.create(
                request_name = 'login 5040 + SMS preparation',
                username=username,
                request_type='login',
                request_data={**serializer.validated_data, 'sms_code': sms_code},
                response_data="Login Succed" if login_status else "Login failure"
            )
            return Response({
                "message": f"User {username} not exists!",
            },
            status=status.HTTP_401_UNAUTHORIZED
            )

        with ThreadPoolExecutor() as executor:
            future = executor.submit(
                run_playwright_for_login_5040,
                username,
                password
            )
            cookies, sms_code = future.result()

        cookie_names = {"token": "token_5", "loginExpire": "loginExpire_5"}

        login_status = all(name in [cookie['name'] for cookie in cookies] for name in cookie_names)

        log = RequestLog.objects.create(
            request_name = 'login 5040 + SMS preparation',
            username=username,
            request_type='login',
            request_data={**serializer.validated_data, 'sms_code': sms_code},
            response_data="Login Succeed" if login_status else "Login failure"
        )

        # Login successfull
        kwargs = {}
        if login_status:
            # Save cookies in Database
            for cookie in cookies:
                name = cookie.get('name')
                value = cookie.get('value')

                if name is None or value is None:
                    continue

                kwargs[cookie_names[name]] = value

                try:
                    token = WebTokens.objects.get(user=user, name=cookie_names[name])
                    token.value = value
                    token.save()
                except WebTokens.DoesNotExist:
                    WebTokens.objects.create(user=user, name=cookie_names[name], value=value)

            # Django-Q (Scheduling task)
            interval = random.randint(10, 30)
            interval = 2

            tasks = Schedule.objects.filter(func='scheduler.tasks.web_request_5040_refresh')
            found_user = False
            for task in tasks:
                kwargs_dict = ast.literal_eval(task.kwargs)
                inner_kwargs = kwargs_dict.get('kwargs', {})
                if inner_kwargs.get('username') == user.username:
                    if found_user:
                        logger.error(f"(DUPLICATED!) Error schedule task. user: {user.username}, taskid: {task.id}")
                    else:
                        kwargs.update({'username': user.username})
                        task.stopped = False
                        task.next_run = timezone.now() + timezone.timedelta(minutes=interval)
                        task.kwargs=kwargs
                        task.save()
                        found_user = True
            if not found_user:
                kwargs['username'] = user.username
                schedule(
                    'scheduler.tasks.web_request_5040_refresh',
                    schedule_type='I',
                    minutes=int(interval),
                    next_run = timezone.now() + timezone.timedelta(minutes=interval),
                    repeats=1,
                    kwargs=kwargs
                )
        # Login unsuccess
        else:
            for cookie in cookies:
                name = cookie.get('name')
                value = cookie.get('value')

                if name is None or value is None:
                    continue

                try:
                    token = WebTokens.objects.get(user=user, name=cookie_names[name])
                    token.value = None
                    token.save()
                except WebTokens.DoesNotExist:
                    pass
            return Response({
                "message": "Login not processed!",
                "cookies": cookies,
            },
            status=status.HTTP_401_UNAUTHORIZED
            )

        return Response({
            "message": "Login processed.",
            "cookies": cookies,
        })

################################### 5040 refresh keep auth handlation #####################################
def run_playwright_for_refresh(token, loginExpire):
    def blocking():
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            context.add_cookies([
                {'name': 'token', 'value': token, 'domain': 'panel.5040.me', 'path': '/'},
                {'name': 'loginExpire', 'value': loginExpire, 'domain': 'panel.5040.me', 'path': '/'},
            ])
            page = context.new_page()
            page.goto('https://panel.5040.me/', timeout=60000)
            page.wait_for_load_state('networkidle')
            cookies = context.cookies("https://panel.5040.me")
            login_form = page.query_selector('form.auth-login-form.mt-2')
            # content = page.content()
            browser.close()
            return login_form, cookies
    return asyncio.to_thread(blocking)

@database_sync_to_async
def create_request_log(log_data):
    return RequestLog.objects.create(**log_data)

@database_sync_to_async
def schedule_cancelation(task_name):
    try:
        task = Schedule.objects.get(func='scheduler.tasks.web_request_5040_refresh')
        task.stopped = True
        task.save()
        # Schedule.objects.filter(func='scheduler.tasks.web_request_5040_refresh').delete()
    except ObjectDoesNotExist:
        task = None
        print("There is no Scheduler refresh task before!")    

class RefreshSessionViewSet5040(viewsets.ViewSet):
    @action(detail=False, methods=['get'], url_path='5/refresh')
    def refresh_5(self, request):
        username = request.query_params.get('username')
        token_5 = request.query_params.get('token_5')
        loginExpire_5 = request.query_params.get('loginExpire_5')
        return async_to_sync(self.refresh_5_async)(request, username, token_5, loginExpire_5)

    async def refresh_5_async(self, request, username, token_5, loginExpire_5):
        # User not exist error handling
        try:
            user = await sync_to_async(User.objects.get)(username=username)
        except User.DoesNotExist:
            log = RequestLog.objects.create(
                request_name = '5040AuthRefreshing',
                username=username,
                request_type='GET',
                request_data={'username': username},
                response_data="User not exist!"
            )
            return Response({
                "message": f"User {username} not exists!",
            },
            status=status.HTTP_401_UNAUTHORIZED
            )

        # is_internal = request.headers.get('X-Internal-Request') == 'true'

        if token_5 and loginExpire_5:
            db_cookies = False
            token = token_5
            loginExpire = loginExpire_5
        else:
            db_cookies = True
            try:
                token = await sync_to_async(WebTokens.objects.get)(user=user, name='token_5')
                token = token.value
                loginExpire = await sync_to_async(WebTokens.objects.get)(user=user, name='loginExpire_5')
                loginExpire = loginExpire.value
            except WebTokens.DoesNotExist:
                log = await sync_to_async (RequestLog.objects.create)(
                    request_name = '5040AuthRefreshing',
                    username=username,
                    request_type='GET',
                    request_data={'username': user.username},
                    response_data="Error in token or loginExpire existance in database!"
                )
                return Response({
                    "message": "token or loginExpire not exist!",
                },
                status=status.HTTP_401_UNAUTHORIZED
                )
        if not (token and loginExpire):
            return Response({'error': 'توکن یافت نشد. ابتدا لاگین کنید.'}, status=401)

        session_cookie = request.COOKIES.get("sessionid")
        headers = {}
        if session_cookie:
                headers['Cookie'] = f"sessionid={session_cookie}"

        try:
            login_form, cookies = await run_playwright_for_refresh(token, loginExpire)
            # Login form visible in page simulation means login expire
            if login_form:
                await create_request_log({
                    'request_name': '5040AuthRefreshing',
                    'username': user.username,
                    'request_type': 'GET',
                    'response_data': None,
                    'additional_info': {'error': 'کاربر اعتبار ندارد. نیاز به لاگین مجدد.'},
                })
                await schedule_cancelation('your_app.tasks.web_request_5040_refresh')
                return Response({'status': 'کاربر اعتبار ندارد. نیاز به لاگین مجدد.'}, status=402)
            
            cookie_names = {"token": "token_5", "loginExpire": "loginExpire_5"}
            login_status = all(name in [cookie['name'] for cookie in cookies] for name in cookie_names)

            kwargs = {}
            if login_status:
                for cookie in cookies:
                    name = cookie.get('name')
                    value = cookie.get('value')

                    if name is None or value is None:
                        continue

                    kwargs[cookie_names[name]] = value

                    if db_cookies:
                        try:
                        # Database cookies prepare
                            token = WebTokens.objects.get(user=user, name=cookie_names[name])
                            token.value = value
                            token.save()
                        
                        except WebTokens.DoesNotExist:
                            await create_request_log({
                                'request_name': '5040AuthRefreshing',
                                'username': user.username,
                                'request_type': 'GET',
                                'response_data': None,
                                'additional_info': {'error': 'توکن‌ها در پایگاه‌داده ذخیره نشدند. خطای پایگاه داده. رفرش متوقف شد.'},
                            })
                            await schedule_cancelation('your_app.tasks.web_request_5040_refresh')
                            return Response({'status': 'توکن‌ها در پایگاه‌داده ذخیره نشدند. خطای پایگاه داده. رفرش متوقف شد.'}, status=403)

            # Django-Q
            interval = random.randint(10, 30)

            tasks = Schedule.objects.filter(func='scheduler.tasks.web_request_5040_refresh')
            found_user = False
            for task in tasks:
                kwargs_dict = ast.literal_eval(task.kwargs)
                inner_kwargs = kwargs_dict.get('kwargs', {})
                if inner_kwargs.get('username') == user.username:
                    kwargs.update({'username': user.username})
                    task.stopped = False
                    task.next_run = timezone.now() + timezone.timedelta(minutes=interval)
                    task.kwargs=kwargs
                    task.save()
                    found_user = True
                    break
            if not found_user:
                await create_request_log({
                    'request_name': '5040AuthRefreshing',
                    'username': user.username,
                    'request_type': 'GET',
                    'response_data': None,
                    'additional_info': {'Result': 'Refreshing اشکال!؛ اعتبار لاگین تمدید شد ولی زمان‌بندی رفرش یافت نشد.'},
                })
                return Response({'status': 'صفحه با موفقیت رفرش شد ولی زمان‌بندی تکرار رفرش یافت نشد!'}, status=404)
            await create_request_log({
                'request_name': '5040AuthRefreshing',
                'username': user.username,
                'request_type': 'GET',
                'response_data': None,
                'additional_info': {'Result': 'Refreshing موفق؛ اعتبار لاگین تمدید شد.'},
            })
            return Response({'status': 'صفحه با موفقیت رفرش شد'}, status=200)
        except Exception as e:
            return Response({'error': str(e)}, status=500)

################################### 5040 Logout #####################################
class LogoutViewSet5040(viewsets.ViewSet):
    def create(self, request):
        token_5 = request.session.get('token_5')
        loginExpire_5 = request.session.get('loginExpire_5')
        if not token_5:
            return Response({'error': 'لاگین نیستید.'}, status=401)
        # For Developing step
        del request.session['token_5']

        try:
            url = 'https://api.5040.me/api/auth/logout'
            headers = {
                'Authorization': f'Bearer {token_5}',
                'Origin': 'https://panel.5040.me',
                'Referer': 'https://panel.5040.me/',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36',
                'Content-Length': '0',
                'Accept': 'application/json, text/plain, */*',
                'cookie': loginExpire_5
            }

            response = requests.post(url, headers=headers)
            return Response(response.json(), status=response.status_code)

        except requests.exceptions.RequestException as e:
            return Response({'error': str(e)}, status=500)

def run(request):
    req = Requests.objects.all()
    return render(request, "web_requests/index.html", {
        "requests": req
    })


###########################################
################################### Hamkadeh Requests #####################################
# ده دقیقه میسکال مشاور
class cm10(viewsets.ViewSet):
    def create(self, request):
        serializer = AccountingCallLog(data=request.data)
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
            token_h = request.session.get('token_h')
            headers = {
                'Authorization': f'Bearer {token_h}'
            }
            
            # request parameters
            params = {
                'export_data': serializer.validated_data.get('export_data', "1"),
                'call_type[]': serializer.validated_data.get('call_type', ["1"]),
                'start_at':  start_at_gregorian,
                'end_at': end_at_gregorian
            }
            #endregion Initialization


            ########################################################
            #region Preparing Excel files
            # Downloading source Excel file
            # Request simulation core
            response = requests.post('https://api.hamkadeh.com/api/accounting/call-log/index', headers=headers, params=params)

            # print("↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓")
            # print(response.headers.get('Content-Type'))

            try:
                downloaded_df = pd.read_excel(BytesIO(response.content))
            except ValueError as e:
                logging.error("Error reading downloaded Excel data: %s", e)
                return Response({'issue':e, 'status':400})                

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
                    [f"{year}{str(month).zfill(2)}{str(day).zfill(2)}"],
                    [f"{year}{str(month).zfill(2)}{str(day).zfill(2)}"],
                    ['00:00'],
                    [nearest_hour]
                ]
                sheet1.range('B3:B6').value = values_sheet1
                values_sheet2 = [
                    [f"{year}{str(month).zfill(2)}{str(day).zfill(2)}"],
                    [f"{year}{str(month).zfill(2)}{str(day).zfill(2)}"],
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
                    source = sheet3.range((last_row, 14), (last_row, 39))
                    target = sheet3.range((last_row, 14), (max_row, 39))
                    source.autofill(target)

                # Clear any extra rows beyond max_row
                elif last_row > max_row:
                    sheet3.range(f'N{max_row + 1}:AM{last_row}').clear_contents()

                workbook.app.calculate()
                
                # Converting sheets to value
                for sheet in [sheet11, sheet12, sheet13, sheet14]:
                    sheet_range = sheet.used_range
                    sheet_range.value = sheet_range.value

                # sorting specific filtered column
                sheet12.range('B8:V8').expand('down').api.Sort(
                    Key1=sheet12.range("M9").api,
                    Order1=2,
                    Header=1,
                    Orientation=1
                )
                sheet13.range('B8:T8').expand('down').api.Sort(
                    Key1=sheet13.range("L9").api,
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
                workbook.save(f'C:\\Users\\eshraghi\\Documents\\esh\\share\\cm10\\cm10_{formatted_jalali_date}.xlsm')
            
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
                request_name="cm10",
                username=request.session.get('username_h'),
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
# آمار عملکرد پشتیبانٍ مشاور
# region Consultant’s support functioning statistics
class c_sup(viewsets.ViewSet):
    def create(self, request):
        serializer = AccountingCallLog(data=request.data)
        if serializer.is_valid():
            
            ########################################################
            #region Initialization
            # Request executation duration time
            starting_time = time.time()
            # Directories path
            shared_dir = r'C:\Users\eshraghi\Documents\esh\share\c_sup\temp'
            calc_file_path = r'C:\Users\eshraghi\Documents\esh\share\c_sup\source\misscall--Poshtiban-MAIN.xlsb'

            # Jalali Date Time
            now_jalali = jdatetime.datetime.now()
            formatted_jalali_date = now_jalali.strftime('%Y_%m_%d_%H_%M_%S')
            year_jalali = now_jalali.year
            month_jalali = now_jalali.month
            day_jalali = now_jalali.day
            
            # Gregorian Date Time
            gregorian_now = datetime.datetime.now()
            date_gregorian = gregorian_now.date()

            # Time handling
            hour = gregorian_now.hour
            nearest_odd_hour = hour if hour % 2 == 1 else hour - 1
            # For "comand_center" sheet
            nearest_odd_hour_formatted = f"{nearest_odd_hour:02}:00"
            # Handling request dynamically
            start_at_gregorian = serializer.validated_data.get('start_at', f"{date_gregorian} 00:00")
            end_at_gregorian = serializer.validated_data.get('end_at', f"{date_gregorian} {nearest_odd_hour_formatted}")

            app = xw.App(visible=False)
            app.screen_updating = False
            app.calculation = 'manual'
            app.enable_events = False
            app.display_alerts = False

            # Login's token
            token_h = request.session.get('token_h')
            headers = {
                'Authorization': f'Bearer {token_h}'
            }

            # request parameters
            params = {
                'export_data': serializer.validated_data.get('export_data', "1"),
                'call_type[]': serializer.validated_data.get('call_type', ["4"]),
                'start_at':  start_at_gregorian,
                'end_at': end_at_gregorian
            }

            response = requests.post('https://api.hamkadeh.com/api/accounting/call-log/index', headers=headers, params=params)
            # print("↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓")
            # print(response.headers.get('Content-Type'))

            try:
                downloaded_df = pd.read_excel(BytesIO(response.content))
            except ValueError as e:
                logging.error("Error reading Excel file: %s", e)
                return Response({'issue':'Please log in before making a request.', 'status':400})

            max_row = len(downloaded_df) + 1

            try:
                if calc_file_path in [book.fullname for book in app.books]:
                    workbook = app.books[calc_file_path]
                else:
                    try:
                        workbook = app.books.open(calc_file_path, update_links=False, read_only=True)
                    except FileNotFoundError:
                        print("The source file for c_sup was not found.")
                        # Handle the error appropriately, maybe return or exit
            #endregion Preparing Excel files

                # region Manipulation, Mixing, Calculate
                # Access the sheets
                # range for data entry
                sheet1 = workbook.sheets['command_center']
                sheet2 = workbook.sheets['Tamas_Vorodi']
                sheet4 = workbook.sheets['میسکال ساعتی پش']
                sheet5 = workbook.sheets['تعداد تماس']
                sheet6 = workbook.sheets['ResultH']

                # Perform the manipulations
                values_sheet1 = [
                    [f"{year_jalali}{str(month_jalali).zfill(2)}{str(day_jalali).zfill(2)}"],
                    [f"{year_jalali}{str(month_jalali).zfill(2)}{str(day_jalali).zfill(2)}"],
                    ['00:00'],
                    [nearest_odd_hour_formatted]
                ]
                sheet1.range('B3:B6').value = values_sheet1

                # Clear range A:N in Tamas_Vorodi
                last_row = sheet2.range('A1').end('down').row
                sheet2.range(f'A1:N{last_row}').clear_contents()

                # Copy data to Tamas_kol
                sheet2.range('A1').options(index=False).value = downloaded_df.iloc[:, :14]

                # Extend formulas in range O:AD
                last_row = sheet2.range('O1').end('down').row
                if last_row < max_row:
                    source = sheet2.range((last_row, 15), (last_row, 30))
                    target = sheet2.range((last_row, 15), (max_row, 30))
                    source.autofill(target)

                # Clear any extra rows beyond max_row
                elif last_row > max_row:
                    sheet2.range(f'N{max_row + 1}:AD{last_row}').clear_contents()
                
                # sorting specific filtered column
                sheet2.range('A1:AD1').expand('down').api.Sort(
                    Key1=sheet2.range("M2").api,
                    Order1=1,
                    Header=1,
                    Orientation=1
                )

                workbook.app.calculate()

                # Converting sheets to value
                range5 = sheet5.used_range
                range5.value = range5.value

                # sorting specific filtered column
                sheet6.range('B3:N3').expand('down').api.Sort(
                    Key1=sheet6.range("D4").api,
                    Order1=2,
                    Header=1,
                    Orientation=1
                )

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
                workbook.save(f'C:\\Users\\eshraghi\\Documents\\esh\\share\\c_sup\\c_sup_{formatted_jalali_date}.xlsb')

            finally:
                workbook.close()
                app.quit()

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
                request_name="c_sup",
                username=request.session.get('username_h'),
                request_type='POST',
                request_data=serializer.validated_data,
                response_data=response_data if response.headers.get('Content-Type') == 'application/json' else None,
                # file_path=file_path if response.headers.get('Content-Type') != 'application/json' else None,
                additional_info={'status_code': response.status_code},
                execution_time=ext_duration
            )
            #endregion  Database logging

            if response.headers.get('Content-Type') == 'application/json':
                try:
                    return Response(response.json())
                except json.JSONDecodeError:
                    return Response(response.text, status=response.status_code)
            else:
                return Response(response.text, status=response.status_code)
    
# endregion Consultant’s support functioning statistics


################################### 5040 Requests #####################################