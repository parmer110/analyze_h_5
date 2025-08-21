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
import threading
import copy
import string
import curlify
from django.http import JsonResponse
from django.http import HttpResponse
from django.utils import timezone
from datetime import timedelta
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework import status
import xlwings as xw
import pandas as pd
from io import BytesIO
from django.shortcuts import render
from concurrent.futures import ThreadPoolExecutor, as_completed
from playwright.sync_api import sync_playwright
from selenium import webdriver
import webbrowser
from asgiref.sync import sync_to_async
from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from django_q.tasks import schedule
from django_q.models import Schedule
from django.core.exceptions import ObjectDoesNotExist
from redlock import Redlock
from concurrent.futures import ThreadPoolExecutor, as_completed


from .serializers_h import (AccountingCallLog, 
                          EntriesExtraction_f)
from .serializers_5 import (FactorsList, EntriesExtraction_5)
from .serializers import DynamicRequestSerializer, LoginSerializer
from .models import RequestLog, Requests, WebTokens, RequestsForeign
from common.models import User, Companies
from scheduler.tasks import open_browser
from .utils import (
    handle_request, generate_intervals, extract_filename, sanitize_filename, fallback_extract, remove_all_extensions,
    get_filename_and_extension_from_response, merge_completed_tasks, extraction
)
from .request_params import (
    _5_sale_entries_extraction_request_params,
    _h_extract_numbers_request_params,
    _5_call_logs_list_request_params,
    _h_call_log_index_request_params,
    _5_factors_list_request_params,
    _h_factor_index_request_params,
    _h_accounting_call_log_index,
    _h_reservation_index,
)


logger = logging.getLogger(__name__)

# Generate a pseudo-random "t" query parameter similar to what the browser's Socket.IO client uses.
# This value changes on each request to prevent caching and to make the handshake unique.
def generate_t_value() -> str:
    """Return a short pseudo-random string + millisecond timestamp, used as 't' cache-busting query."""
    rand = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
    return f"{rand}{int(time.time() * 1000)}"

class LoginViewSetHamkadeh(viewsets.ViewSet):
    def create(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            username = serializer.validated_data['username']

            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                # Return error if user is not found
                return Response(
                    {'message': f"User {username} does not exist!"},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            session = requests.Session()

            t_value = generate_t_value()

            headers={
                "Origin": "https://samane.hamkadeh.com",
                "Referer": "https://samane.hamkadeh.com/dashboard",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            }

            url = f"https://api.hamkadeh.com:6003/socket.io/?EIO=3&transport=polling&t={t_value}"
            response = session.get(url, headers=headers)


            print(f'socket.io response: {response.cookies.get_dict()}')
            print(f'socket.io session: {session.cookies.get_dict()}')

            # cookies = session.cookies.get_dict()
            # io_cookie = session.cookies.get('io')

            headers["Content-Type"] = "application/json"

            url = 'https://api.hamkadeh.com/api/auth/login/send-code'
            response = session.post(url, headers=headers, json=serializer.validated_data)

            print(f'send-code response: {response.cookies.get_dict()}')
            print(f'send-code session: {session.cookies.get_dict()}')

            # response = requests.Request('POST', 'https://api.hamkadeh.com/api/auth/login/send-code', json=serializer.validated_data)
            # prepared = response.prepare()
            # print(curlify.to_curl(prepared))

            # Prompt user input for SMS code
            sms_code = None
            while not sms_code:
                code = input("Enter the SMS code: ")
                if code.isdigit():
                    sms_code = code
            
            login_data = {
                "username": serializer.validated_data["username"],
                "code": sms_code
            }

            print("←←←←←←←←←←←←←←←←←←←←←←←")
            print(login_data)

            url = 'https://api.hamkadeh.com/api/auth/login'
            response = session.post(url, headers=headers, json=login_data)

            print(f'login response: {response.cookies.get_dict()}')
            print(f'login session: {session.cookies.get_dict()}')

            return Response(response.json())

            log = RequestLog.objects.create(
                request_name = 'login Hamkadeh',
                username=serializer.validated_data['username'],
                request_type='login',
                request_data=serializer.validated_data,
                response_data=response.json()
            )

            print(f'response: {response.cookies.get_dict()}')
            print(f'session: {session.cookies.get_dict()}')
        
            token_h = response.json().get('token')
            print(f'token_h: {token_h}')
            io = response.json().get('io')
            print(f'io: {io}')
            if token_h:
                WebTokens.objects.update_or_create(user=user, name="token_h", defaults={'value': token_h})
                request.session['token_h'] = token_h

            # Valid
            print("↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑")
            return Response(response.json())
        
        return Response(serializer.errors, status=400)


def schedule_refresh_job(user, kwargs, interval_minutes=None):
    """
    Create or update a Django-Q schedule for refreshing the 5040 login.
    Uses a unique schedule name per user to avoid duplicates.

    If interval_minutes is None, selects a random interval between 10 and 30 minutes.
    """
    task_name = f"web_request_5040_refresh_{user.username}"
    now = timezone.now()
    minutes = interval_minutes if interval_minutes is not None else random.randint(5, 40)
    seconds = random.randint(0, 59)
    try:
        # Update existing schedule
        sch = Schedule.objects.get(name=task_name)
        sch.next_run = now + timezone.timedelta(minutes=minutes, seconds=seconds)
        sch.stopped = False
        sch.kwargs = {'username': user.username, **kwargs}
        sch.repeats=1
        sch.save()

    except Schedule.DoesNotExist:
        # Create new schedule
        schedule(
            'scheduler.tasks.web_request_5040_refresh',
            name=task_name,
            schedule_type='I',
            minutes=minutes,
            next_run=now + timezone.timedelta(minutes=minutes, seconds=seconds),
            repeats=1,
            kwargs={'username': user.username, **kwargs}
        )


def run_playwright_for_login_5040(username, password):
    """
    Use Playwright to perform login on panel.5040.me,
    prompt the user for the SMS code, and return cookies.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.goto('https://panel.5040.me/auth/login', timeout=60000)

        # Fill in credentials and request SMS code
        page.fill('input[name="login-username"]', username)
        page.fill('input[name="password"]', password)
        page.click('button:has-text("ارسال کد با پیامک")')
        page.wait_for_load_state('networkidle')

        # Prompt user input for SMS code
        sms_code = None
        while not sms_code:
            code = input("Enter the SMS code: ")
            if code.isdigit():
                sms_code = code

        # Complete login with SMS code
        page.fill('input[name="login-code"]', sms_code)
        with page.expect_response(
            lambda resp: "api/auth/login" in resp.url and resp.status == 200,
            timeout=60000
        ):
            page.click('button:has-text("ورود به سیستم")')

        page.wait_for_load_state('networkidle')
        cookies = context.cookies('https://panel.5040.me')
        browser.close()
        return cookies, sms_code


class LoginViewSet5040(viewsets.ViewSet):
    """
    ViewSet to handle initial 5040 login and schedule refresh.
    """
    def create(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        username = serializer.validated_data['username']
        password = serializer.validated_data['password']

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            # Return error if user is not found
            return Response(
                {'message': f"User {username} does not exist!"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Perform Playwright login in a thread
        cookies, sms_code = ThreadPoolExecutor().submit(
            run_playwright_for_login_5040, username, password
        ).result()

        # Map cookie names to WebTokens fields
        cookie_map = {'token': 'token_5', 'loginExpire': 'loginExpire_5'}
        login_ok = all(name in [c['name'] for c in cookies] for name in cookie_map)

        # Log the login attempt
        RequestLog.objects.create(
            request_name='login_5040',
            username=username,
            request_type='login',
            request_data={**serializer.validated_data, 'sms_code': sms_code},
            response_data="Login Succeed" if login_ok else "Login Failure"
        )

        if not login_ok:
            # Only clear tokens related to 5040
            # WebTokens.objects.filter(
            #     user=user,
            #     name__in=['token_5', 'loginExpire_5']
            # ).update(value=None)
            return Response(
                {'message': 'Login failed', 'cookies': cookies},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Save or update WebTokens for 5040
        token_kwargs = {}
        for c in cookies:
            name, value = c.get('name'), c.get('value')
            key = cookie_map.get(name)
            if key:
                token_kwargs[key] = value
                WebTokens.objects.update_or_create(
                    user=user,
                    name=key,
                    defaults={'value': value}
                )

        # Schedule the periodic refresh job
        interval_minutes = None # For testing short interval schedule
        schedule_refresh_job(user, token_kwargs, interval_minutes)
        return Response({'message': 'Login successful', 'cookies': cookies})


def schedule_cancelation(task_name):
    """
    Stop a scheduled task by its unique name.
    """
    try:
        task = Schedule.objects.get(name=task_name)
        task.stopped = True
        task.save()
    except Schedule.DoesNotExist:
        pass


async def run_playwright_for_refresh(token, loginExpire):
    """
    Use Playwright to open the 5040 panel
    and verify session freshness.
    """
    def _sync_refresh():
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            # Add existing cookies for refresh
            context.add_cookies([
                {'name': 'token', 'value': token, 'domain': 'panel.5040.me', 'path': '/'},
                {'name': 'loginExpire', 'value': loginExpire, 'domain': 'panel.5040.me', 'path': '/'},
            ])
            page = context.new_page()

            max_retries = 3
            delay = random.randint(2 * 60, 7 * 60)  # seconds

            for attempt in range(max_retries):
                try:
                    page.goto('https://panel.5040.me/', timeout=60000)
                    break  # Exit the loop if successful
                except Exception as e:
                    current_time = datetime.datetime.now().strftime('%H:%M:%S')
                    logging.error(f"→→ Error found: page.goto, in {current_time})←← navigating to URL: {e}")
                    if attempt < max_retries:
                        logging.error(f'Retrying in {delay} seconds...')
                        time.sleep(delay)
                    else:
                        logging.error('Max retries reached, giving up.')


            try:
                page.goto('https://panel.5040.me/', timeout=60000)
            except Exception as e:
                logging.error(f'Error navigating to URL: {e}')
            
            page.wait_for_load_state('networkidle')
            login_form = page.query_selector('form.auth-login-form.mt-2')
            cookies = context.cookies('https://panel.5040.me')
            browser.close()
            return login_form, cookies

    return await asyncio.to_thread(_sync_refresh)


class RefreshSessionViewSet5040(viewsets.ViewSet):
    """
    ViewSet to handle periodic refresh of the 5040 login session.
    """
    @action(detail=False, methods=['get'], url_path='5/refresh')
    def refresh_5(self, request):
        username = request.query_params.get('username')
        token = request.query_params.get('token_5')
        loginExpire = request.query_params.get('loginExpire_5')
        # detect internal call
        is_internal = request.headers.get('X-Internal-Request', '').lower() == 'true'
        return async_to_sync(self.refresh_5_async)(
            request, username, token, loginExpire, is_internal
        )

    async def refresh_5_async(self, request, username, token, loginExpire, is_internal):
        refresh_kwargs = {}
        try:
            user = await sync_to_async(User.objects.get)(username=username)
        except User.DoesNotExist:
            # Return error if user does not exist
            return Response(
                {'message': 'User not found'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Load tokens from DB if not provided
        if not token or not loginExpire:
            try:
                token = (await sync_to_async(WebTokens.objects.get)(
                    user=user, name='token_5'
                )).value
                loginExpire = (await sync_to_async(WebTokens.objects.get)(
                    user=user, name='loginExpire_5'
                )).value
            except WebTokens.DoesNotExist:
                return Response(
                    {'message': 'Tokens missing'},
                    status=status.HTTP_401_UNAUTHORIZED
                )

        # Perform refresh check
        login_form, cookies = await run_playwright_for_refresh(
            token, loginExpire
        )
        if login_form:
            count_refresh_5 = request.session.get('count_refresh_5', 0)
            if count_refresh_5 > 3:
                # Session expired; cancel scheduled job
                task_name = f"web_request_5040_refresh_{user.username}"
                await sync_to_async(schedule_cancelation, thread_sensitive=True)(task_name)
            else:
                count_refresh_5 += 1
                request.session['count_refresh_5'] = count_refresh_5
            if is_internal:
                await sync_to_async(schedule_refresh_job, thread_sensitive=True)(
                    user, refresh_kwargs
                )
            return Response(
                {'status': 'Session expired; please login again.'},
                status=402
            )
        
        request.session['count_refresh_5'] = 0

        # Update WebTokens with fresh cookies
        cookie_map = {'token': 'token_5', 'loginExpire': 'loginExpire_5'}
        refresh_kwargs = {}
        for c in cookies:
            key = cookie_map.get(c['name'])
            if key:
                refresh_kwargs[key] = c['value']
                await sync_to_async(
                    WebTokens.objects.filter(user=user, name=key).update
                )(value=c['value'])

        # Reschedule the next refresh
        # For Security
        if is_internal or True: # Debug! 
            await sync_to_async(schedule_refresh_job, thread_sensitive=True)(
                user, refresh_kwargs
            )
        return Response({'Result': 'Refreshed successfully', 'status': 212})


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
            username = request.GET.get('username')
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                # Return error if user is not found
                return Response(
                    {'message': f"User {username} does not exist!"},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            # Directories path
            shared_dir = r'C:\Users\eshraghi\Documents\esh\share\cm10\temp'
            calc_file_path = r'C:\Users\eshraghi\Documents\esh\share\cm10\source\میسکال  مشاوران - Main.xlsb'
            
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
                # content_disposition = response.headers.get('Content-Disposition')

                # if not os.path.exists(shared_dir):
                #     os.makedirs(shared_dir)

                # if content_disposition:
                #     filename = re.findall('filename=(.+)', content_disposition)
                #     if filename:
                #         filename = filename[0]
                #         filename = f"{filename}_{formatted_jalali_date}.xlsx"
                #     else:
                #         filename = f"response_{formatted_jalali_date}.xlsx"
                # else:
                #     filename = f"response_{formatted_jalali_date}.xlsx"

                # # Save exported file 
                # file_path = os.path.join(shared_dir, filename)
                # with open(file_path, 'wb') as f:
                #     f.write(response.content)

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
                username=user.username,
                request_type='POST',
                request_data=serializer.validated_data,
                response_data=response_data if response.headers.get('Content-Type') == 'application/json' else None,
                file_path=calc_file_path if response.headers.get('Content-Type') != 'application/json' else None,
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
            username = request.query_params.get('username')

            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                # Return error if user is not found
                return Response(
                    {'message': f"User {username} does not exist!"},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            # Login's token
            try:
                token_h = WebTokens.objects.get(user=user, name='token_5').value
            except WebTokens.DoesNotExist:
                return Response(
                    {'message': 'Tokens missing'},
                    status=status.HTTP_401_UNAUTHORIZED
                )

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
            nearest_odd_hour_formatted = f"{nearest_odd_hour:02}:00:00"
            # Handling request dynamically
            start_at_gregorian = serializer.validated_data.get('start_at', f"{date_gregorian} 00:00:00")
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
                # content_disposition = response.headers.get('Content-Disposition')

                # if not os.path.exists(shared_dir):
                #     os.makedirs(shared_dir)

                # if content_disposition:
                #     filename = re.findall('filename=(.+)', content_disposition)
                #     if filename:
                #         filename = filename[0]
                #         filename = f"{filename}_{formatted_jalali_date}.xlsx"
                #     else:
                #         filename = f"response_{formatted_jalali_date}.xlsx"
                # else:
                #     filename = f"response_{formatted_jalali_date}.xlsx"

                # # Save exported file 
                # file_path = os.path.join(shared_dir, filename)
                # with open(file_path, 'wb') as f:
                #     f.write(response.content)

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
                username=user.username,
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

def openning_home_browser(request):
    username = request.GET.get('username')
    token = request.GET.get('token_5')
    loginExpire = request.GET.get('loginExpire_5')

    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        # Return error if user does not exist
        return JsonResponse(
            {'message': 'User not found'},
            status=status.HTTP_401_UNAUTHORIZED
        )

    # Load tokens from DB if not provided
    if not token or not loginExpire:
        try:
            token = WebTokens.objects.get(user=user, name='token_5').value
            loginExpire = WebTokens.objects.get(user=user, name='loginExpire_5').value
        except WebTokens.DoesNotExist:
            return Response(
                {'message': 'Tokens missing'},
                status=status.HTTP_401_UNAUTHORIZED
            )
    driver = webdriver.Chrome()

    driver.get('https://panel.5040.me')
    driver.add_cookie({'name': 'token', 'value': token})
    driver.add_cookie({'name': 'loginExpire', 'value': loginExpire})

    driver.get('https://panel.5040.me')


    # open_browser.delay(user, token, loginExpire)

    return HttpResponse("Browser opened")


class noname(viewsets.ViewSet):
    def create(self, request):

        username = request.query_params.get('username')
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            # Return error if user does not exist
            return Response(
                {'message': 'User not found'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        req = [
                {
                    "company": "5040",
                    "name": "v1/extraction",
                    "body": {
                        "agencies": [],
                        "callStatuses": [],
                        "containDeletedEntries": True,
                        "endEntryDate": "",
                        "factorSerial": "",
                        "factorStatuses": [],
                        "justDeletedEntries": False,
                        "maxCallNumber": None,
                        "maxSuccessCallNumber": None,
                        "minCallNumber": None,
                        "minSuccessCallNumber": None,
                        "mobile": None,
                        "numberStatuses": [],
                        "products": [],
                        "references": ["Landing", "Sms"],
                        "startEntryDate": "",
                        "withoutFactorEntries": False
                    },
                    "query": {}
                }
            ]        


        # Jalali Date Time
        jalali_now = jdatetime.datetime.now()
        jalali_five_days_ago = jalali_now - timedelta(days=5)
        jalali_rounded_time = jalali_now.replace(minute=0, second=0, microsecond=0)
        formatted_jalali_date = jalali_rounded_time.strftime('%Y/%m/%d 00:00:00')
        year_jalali = jalali_now.year
        month_jalali = jalali_now.month
        day_jalali = jalali_now.day


        return Response({
            'username': username,
            'Now Jalalli date time': formatted_jalali_date,
        },  status.HTTP_200_OK)




class ArchiveViewSet(viewsets.ViewSet):
    def create(self, request):

        # Initialization

        starting_time = time.time()

        # Gregorian Date Time
        gregorian_now = datetime.datetime.now()
        
        starting_time = time.time()
        now_jalali = jdatetime.datetime.now()
        formatted_jalali_date = now_jalali.strftime('%Y_%m_%d_%H_%M_%S')
        base_shared_dir = r'C:\Users\eshraghi\Documents\esh\share\archive'
        base_shared_dir = os.path.join(base_shared_dir, formatted_jalali_date)

        username = request.query_params.get('username')
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            # Return error if user does not exist
            return Response(
                {'message': 'User not found'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Tokens
        try:
            # 5040
            token_5 = WebTokens.objects.get(user=user, name='token_5').value
            loginExpire_5 = WebTokens.objects.get(user=user, name='loginExpire_5').value

            # Hamkadeh
            token_h = WebTokens.objects.get(user=user, name='token_h').value

        except WebTokens.DoesNotExist:
            return Response(
                {'message': 'Tokens missing'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        headers_5 = {
            'Authorization': f'Bearer {token_5}',
            'loginExpire': loginExpire_5
        }
        headers_h = {
            'Authorization': f'Bearer {token_h}'
        }


        #############################
        # Preparing download and gadering tasks
        completed_tasks, failed_tasks = extraction(request, headers_h, headers_5, gregorian_now)


        #############################
        # Preparing donwloaded data analyze end Integration
        completed_tasks = merge_completed_tasks(completed_tasks)


        for task in completed_tasks:

            result, start_date, end_date, specific_dir, company, name, idn = task.result()

            shared_dir = os.path.join(base_shared_dir, specific_dir)
            os.makedirs(shared_dir, exist_ok=True)

            filename, ext = get_filename_and_extension_from_response(result)

            start_date = datetime.datetime.strptime(start_date, '%Y/%m/%d %H:%M:%S')
            start_date = jdatetime.datetime.fromgregorian(date=start_date).strftime('%Y_%m_%d_%H_%M_%S')

            end_date = datetime.datetime.strptime(end_date, '%Y/%m/%d %H:%M:%S')                
            end_date = jdatetime.datetime.fromgregorian(date=end_date).strftime('%Y_%m_%d_%H_%M_%S')

            file_suffix = f"{start_date}__{end_date}"

            clean_name = sanitize_filename(name)
            filename   = f"{clean_name}_{file_suffix}.{ext}"

            # Save exported file 
            file_path = os.path.join(shared_dir, filename)
            try:
                with open(file_path, 'wb') as f:
                    f.write(result.content)
            except Exception as file_exc:
                print(f"✖ Saving file issued {task}: {file_exc}")
                failed_tasks.append(task)


        #############################
        # Finilize response preperation
        ext_duration = datetime.timedelta(seconds=time.time() - starting_time)
        completed_tasks_counter = len(completed_tasks)

        response_data = {
            "ext_duration": ext_duration,
            "average_duration": ext_duration/completed_tasks_counter if completed_tasks_counter !=0 else 0,
            "completed_tasks_counter": completed_tasks_counter,
            "Count of failed tasks": len(failed_tasks)
        }                

        return Response(response_data, status=201)
    
