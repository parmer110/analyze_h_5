import requests
import jdatetime
import datetime
import logging
import re
import os
import time
import random
import threading
import urllib.parse
import copy
import curlify
import asyncio
import string
from django.utils import timezone
from django_q.tasks import schedule
from django_q.models import Schedule
from playwright.sync_api import sync_playwright
from concurrent.futures import ThreadPoolExecutor, as_completed
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError
from collections import defaultdict
from dateutil.relativedelta import relativedelta
import pandas as pd
from io import BytesIO
from datetime import timedelta
from typing import Optional, Any, List, Dict, Tuple
from email.parser import HeaderParser
from itertools import islice
from urllib.parse import unquote
from common.locks import redlock_instance
from common.exceptions import RequestDoesNotExistError

from common.models import User, Companies
from .models import RequestsForeign, WebTokens
from .serializers import DynamicRequestSerializer
from .request_params import (
    _5_sale_entries_extraction_request_params,
    _h_extract_numbers_request_params,
    _5_call_logs_list_request_params,
    _h_call_log_index_request_params,
    _5_factors_list_request_params,
    _5_v1_factor_extraction_params,
    _h_factor_index_request_params,
    _h_accounting_call_log_index,
    _h_reservation_index,
    _5_v1_extraction,
    _h_entryـextractـnumbersـnew,
)

logger = logging.getLogger(__name__)
EXCEL_MAX_ROWS = 1_048_576
MAX_EXCEL_COLS = 16_384


def fetch_data():
    url = 'https://api.hamkadeh.com/api/accounting/call-log/index'
    params = {
        'export_data': 1,
        'call_type[]': 1,
        'start_at': '2025-01-15 00:00',
        'end_at': '2025-01-15 20:10'
    }
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/json, text/plain, */*',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'Cookie': 'token=148807%7CXIUHv1njGq6sV67ZJrhThwjl3XGi34KC2agTG8Lhedc82f1f; io=miA5p6jcNGikIQVIAXyU'
    }
    response = requests.post(url, params=params, headers=headers)
    return response.content


# Generate a pseudo-random "t" query parameter similar to what the browser's Socket.IO client uses.
# This value changes on each request to prevent caching and to make the handshake unique.
def generate_t_value() -> str:
    """Return a short pseudo-random string + millisecond timestamp, used as 't' cache-busting query."""
    rand = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
    return f"{rand}{int(time.time() * 1000)}"


def run_once_under_lock(lock_key: str,
                       lock_ttl_ms: int,
                       block_timeout_s: int,
                       action_fn,
                       *action_args,
                       **action_kwargs):
    """
    Acquire a distributed lock (via redlock-py) identified by lock_key.
    - If first to acquire, run action_fn(*action_args, **action_kwargs).
    - Others block until the first finishes, then skip action_fn.
    """
    # create the lock object
    lock = redlock_instance.lock(lock_key, lock_ttl_ms)

    # non-blocking try: only first caller succeeds
    is_first = lock.acquire(blocking=False)
    if is_first:
        try:
            logger.info(f"[Lock:{lock_key}] First caller: running action.")
            action_fn(*action_args, **action_kwargs)
        except Exception as exc:
            logger.error(f"[Lock:{lock_key}] Action failed: {exc}")
            raise
        finally:
            try:
                redlock_instance.unlock(lock)
                logger.info(f"[Lock:{lock_key}] Lock released by first caller.")
            except Exception as e:
                logger.error(f"[Lock:{lock_key}] Failed to release lock: {e}")
    else:
        # block until the first caller releases
        logger.info(f"[Lock:{lock_key}] Waiting for first caller to finish...")
        lock.acquire(blocking=True, blocking_timeout=block_timeout_s)
        # immediately release and skip action
        lock.release()
        logger.info(f"[Lock:{lock_key}] Continuing without running action.")

def _perform_refresh(username: str):
    """
    The actual refresh HTTP call.
    """
    resp = requests.get(
        f"http://192.168.134.10:8002/web_requests/5/refresh/?username={username}",
        timeout=300
    )
    resp.raise_for_status()
    logger.info(f"[Refresh] Completed with status {resp.status_code}")

def debug_request(method, url, **kwargs):
    """
    اجرای یک درخواست با requests و چاپ معادل cURL برای دیباگ
    """
    # درخواست رو بساز
    req = requests.Request(method, url, **kwargs)
    prepared = req.prepare()

    # چاپ معادل cURL
    print("=== cURL ===")
    print(curlify.to_curl(prepared))
    print("============")

    # ارسال درخواست
    with requests.Session() as s:
        resp = s.send(prepared, timeout=kwargs.get("timeout", 30))
    
    return resp

def handle_request(method, url, headers, data, start_date, end_date, shared_dir, company, name, idn, esp_opt):

    # if company == "hamkadeh":
    #     headers = headers_h
    # elif company == "5040":
    #     headers = headers_5

    response = None
    counter = 0
    if method == 'GET':
        while (not response or not response.ok) and counter <= 0:
            counter += 1

            logger.info(f"Attempting GET request to {url} with headers {headers} and params {data}.")

            try:
                print(f'→ count: {counter}, url: {url}, start date: {start_date}, end date: {end_date}←')
                response = requests.get(url, headers=headers, params=data, timeout=1200)
                # rsp = debug_request("POST", url, headers=headers, json=data)
                # print(response)
            except requests.exceptions.ConnectionError:
                print("requests.exceptions.ConnectionError")
                response = None
            except requests.exceptions.Timeout:
                print("requests.exceptions.Timeout")
                response = None
            finally:
                if response is None:
                    logger.error(
                        f"GET request to {url}, start_date: {start_date}, end_date: {end_date} failed: no response"
                    )
                elif response.ok:
                    # status_code < 400
                    logger.info(f"GET to {response.url} succeeded: status {response.status_code}")
                else:
                    # response موجود اما خطای HTTP (status_code >= 400)
                    logger.error(f"GET to {response.url} failed: status {response.status_code}")
                    # Perform tokens updatation while request issued.
                    if "5040" in url:
                        continue
                        run_once_under_lock(
                            lock_key="refresh_lock_5040",
                            lock_ttl_ms=300_000,
                            block_timeout_s=310,
                            action_fn=_perform_refresh,
                            username="aeshraghi"
                        )

    elif method == 'POST':
        while (not response or not response.ok) and counter <= 0:
            counter += 1

            logger.info(f"Attempting POST request to {url} with headers {headers} and params {data}.")
            
            try:
                # Debug
                print(f'◄count: {counter}, url: {url}, start date: {start_date}, end date: {end_date}►')
                response = requests.post(url, headers=headers, json=data, timeout=1200)

                # Debug
                # url = "https://api.hamkadeh.com/api/entry/extract-numbers-new"

                # headers = {
                #     # "accept": "application/json, text/plain, */*",
                #     # "origin": "https://samane.hamkadeh.com",
                #     # "referer": "https://samane.hamkadeh.com/",
                #     # "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                #     # "content-type": "application/json",
                #     "cookie": "io=XJcvBhQYLYfkYwbRCXZh; token=78002%7CBwoiTi48KzoxEH0IGBf7Y2xOntmLhTANdRVhiledda1b5da9",
                # }

                # data = {
                #     "product_id": 3,
                #     "reference": ["landing", "sms"],
                #     "entry_date_start": "2025-09-13 00:00:00",
                #     "entry_date_end": "2025-09-13 23:59:59",
                # }
                # rsp = debug_request("POST", url, headers=headers, json=data)
                # response = requests.post(url, headers=headers, json=data, timeout=1200)
                # print("stat☼☼☼☼☼☼☼☼☼☼☼☼☼☼☼☼☼☼☼☼☼☼☼")
                # print(rsp.status_code)
                # print(rsp.json())
                # print("↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑")

            except requests.exceptions.ConnectionError:
                print("requests.exceptions.ConnectionError")
                response = None
            except requests.exceptions.Timeout:
                print("requests.exceptions.Timeout")
                response = None

            if response is not None and response.ok:
                # print(f"POST request to {response.url} Succeeded with status code {response.status_code}.")
                logger.info(f"POST request to {response.url} succeeded with status code {response.status_code}.")
            else:
                if response:
                    logger.error(f"POST request to {response.url} failed with status code {response.status_code}.")
                else:
                    logger.error(f"POST request to {url}, start date: {start_date}, end date: {end_date} failed 666!!!")
                # Perform tokens updatation while request issued.
                if "5040" in url:
                    continue
                    run_once_under_lock(
                        lock_key="refresh_lock_5040",
                        lock_ttl_ms=300_000,
                        block_timeout_s=310,
                        action_fn=_perform_refresh,
                        username="aeshraghi"
                    )
       
    counter = 0

    # print(f"request to {response.url} Header is {headers} with status code {response.status_code}.")
    return response, start_date, end_date, shared_dir, company, name, idn, esp_opt


def parse_jalali_datetime(
    date_str: str,
    format_with_sec: str,
    format_without_sec: str,
) -> Tuple[jdatetime.datetime, str]:
    """Parse a Jalali date string, filling missing seconds if needed."""
    try:
        parsed = jdatetime.datetime.strptime(date_str, format_with_sec)
        return parsed, 'with_sec'
    except ValueError:
        parsed = jdatetime.datetime.strptime(date_str, format_without_sec)
        return parsed.replace(second=0), 'without_sec'


def generate_intervals(
    start_str: str,
    end_str: str,
    idn: Dict[str, int],
    esp_opt: Optional[Dict[str, Any]] = None
) -> List[Dict[str, str]]:
    """
    Generate time-based intervals according to integration_days_num (idn).

    - start_str, end_str: Jalali strings like '1404/02/10 12:30:45'
    - idn: {'year':0, 'month':0, 'day':0, 'hour':h, 'minute':m, 'second':s}
    - Returns: [{'start_date': 'YYYY/MM/DD HH:MM:SS', 'end_date': 'YYYY/MM/DD HH:MM:SS'}, ...]
    """

    # Check if esp_opt is not None and contains the 'datesep' key
    if esp_opt is not None and 'datesep' in esp_opt and esp_opt['datesep'] != "":
        date_separator = esp_opt['datesep']
    else:
        date_separator = '/'

    primary_init_fmt = '%Y/%m/%d %H:%M:%S'
    primary_fmt = f'%Y{date_separator}%m{date_separator}%d %H:%M:%S'
    fallback_init_fmt = '%Y/%m/%d %H:%M'
    fallback_fmt = f'%Y{date_separator}%m{date_separator}%d %H:%M'

    # Default idn to 1 day if not provided
    if idn is None:
        idn = {'year': 0, 'month': 0, 'day': 1, 'hour': 0, 'minute': 0, 'second': 0}

    # convert Jalali to Gregorian datetime
    jstart, start_format_used = parse_jalali_datetime(start_str, primary_init_fmt, fallback_init_fmt)
    jend, end_format_used   = parse_jalali_datetime(end_str,   primary_init_fmt, fallback_init_fmt)

    # Determine the appropriate format for jstart
    if start_format_used == 'with_sec':
        start_format = primary_fmt
    else:
        start_format = fallback_fmt

    # Determine the appropriate format for jend
    if end_format_used == 'with_sec':
        end_format = primary_fmt
    else:
        end_format = fallback_fmt

    start = jstart.togregorian()
    end   = jend.togregorian()

    if start > end:
        raise RequestDoesNotExistError("Start date must be before end date")

    # Devide littelest interval
    step = timedelta(0)
    if idn.get("second", 0) > 0:
        step = timedelta(seconds=idn["second"])
    if idn.get("minute", 0) > 0:
        step += timedelta(minutes=idn["minute"])
    if idn.get("hour", 0) > 0:
        step += timedelta(hours=idn["hour"])
    if step is None or step == timedelta(0):
        # Dayly defalut
        step = timedelta(days=1)

    intervals: List[Dict[str, str]] = []
    current_start = start

    while current_start <= end:
        current_end = current_start + step
        # deviding end time override.
        if current_end > end:
            current_end = end

        intervals.append({
            'start_date': current_start.strftime(start_format),
            'end_date':   current_end.strftime(end_format),
        })

        # Devide indifinite loop
        if current_end == current_start:
            break

        # next step
        current_start = current_end + timedelta(seconds=1)

    return intervals

def extract_filename(content_disposition: str) -> str | None:
    if not content_disposition:
        return None

    parser = HeaderParser()
    msg = parser.parsestr(f'Content-Disposition: {content_disposition}')
    params = msg.get_params(header='content-disposition', unquote=False)

    for key, val in params:
        if key.lower() == 'filename*' and val:
            if isinstance(val, tuple) and len(val) == 3:
                encoding, lang, filename_enc = val
                try:
                    return unquote(filename_enc, encoding=encoding)
                except LookupError:
                    return unquote(filename_enc, encoding='utf-8')
            return unquote(val)

    for key, val in params:
        if key.lower() == 'filename' and val:
            if isinstance(val, tuple):
                val = val[0]
            return str(val)

    return None


def sanitize_filename(name) -> str:
    if isinstance(name, tuple):
        name = name[-1]
    name = str(name)
    return re.sub(r'[\\\/:*?"<>|]', '_', name)

def fallback_extract(content_disp: str) -> str | None:
    # بررسی filename*=UTF-8''Name.ext
    m = re.search(r"filename\*\s*=\s*UTF-8''(?P<name>[^;]+)", content_disp)
    if m:
        # decode درصدگذاری شده
        return unquote(m.group('name'))
    # بررسی filename="Name.ext" یا filename=Name.ext
    m2 = re.search(r'filename\s*=\s*"?(?P<name>[^";]+)"?', content_disp)
    if m2:
        return m2.group('name')
    return None

def remove_all_extensions(filename):
    while True:
        base, ext = os.path.splitext(filename)
        if not ext:
            return base
        filename = base


def get_filename_and_extension_from_response(response):
    """
    Extracts the filename and extension from the response headers.
    Handles Farsi and Unicode filenames correctly.
    
    Returns:
        (filename, extension) or (None, None) if not found.
    """
    content_disposition = response.headers.get('Content-Disposition', '')
    
    # Try filename*= for encoded UTF-8 filenames (RFC 5987)
    match_utf8 = re.search(r"filename\*\s*=\s*UTF-8''(.+)", content_disposition)
    if match_utf8:
        filename_encoded = match_utf8.group(1)
        filename = urllib.parse.unquote(filename_encoded)
        extension = filename.split('.')[-1].lower() if '.' in filename else None
        return filename, extension

    # Try normal filename=
    match_ascii = re.search(r'filename\*?="?([^";]+)"?', content_disposition)
    if match_ascii:
        filename = match_ascii.group(1)
        extension = filename.split('.')[-1].lower() if '.' in filename else None
        return filename, extension

    mime_map = {
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'xlsx',
        'application/vnd.ms-excel': 'xls',
        'text/csv': 'csv',
        'application/pdf': 'pdf',
    }

    # Fallback: try Content-Type header
    content_type = response.headers.get('Content-Type', '').lower()
    for mime, ext in mime_map.items():
        if mime in content_type:
            return None, ext

    return None, None


def extraction(request, headers_h, headers_5, gregorian_now):

    username = request.query_params.get('username')
    # Functions requesting web_app
    # Will made automization
    request_handler_map = {
        ('5040', 'sale/entries/extraction'): _5_sale_entries_extraction_request_params,
        ('hamkadeh', 'entry/extract-numbers'): _h_extract_numbers_request_params,

        ('5040', 'call/logs/list'): _5_call_logs_list_request_params,
        ('hamkadeh', 'call-log/index'): _h_call_log_index_request_params,

        ('5040', 'factors/list'): _5_factors_list_request_params,
        ('5040', 'v1/factor-extraction'): _5_v1_factor_extraction_params,
        ('hamkadeh', 'factor/index'): _h_factor_index_request_params,

        ('hamkadeh', 'accounting/call-log/index'): _h_accounting_call_log_index,

        ('hamkadeh', 'reservation/index'): _h_reservation_index,

        ('5040', 'v1/extraction'): _5_v1_extraction,
        ('hamkadeh', 'entry/extract-numbers-new'): _h_entryـextractـnumbersـnew,
    }

    # Dynamic Serializer: Iteration loop over each company-name request perform data valication and initalize.
    expanded_tasks = []
    for req in request.data:

        company = req.get("company").lower()
        name = req.get("name").lower()
        dir_hlp_name = req.get("directory_helper")
        body_parameters = req.get("body", None)
        query_parameters = req.get("query", None)
        idn = req.get("integration_days_num", None)

        specific_dir = sanitize_filename(company)
        specific_dir = os.path.join(specific_dir, sanitize_filename(name))
        if dir_hlp_name:
            specific_dir = os.path.join(specific_dir, sanitize_filename(dir_hlp_name))
        
        try:
            company_inst = Companies.objects.get(name=company)
        except RequestsForeign.DoesNotExist:
            raise RequestDoesNotExistError(f'The Company: {company} does not exist!' , status=405)
        
        try:
            request_instance = RequestsForeign.objects.get(company=company_inst, name=name)
        except RequestsForeign.DoesNotExist:
            raise RequestDoesNotExistError(f'The {name} does not exist for {company} company defined requests!')
        
        # Dynamic serializer
        serializer = DynamicRequestSerializer(data={**body_parameters, **query_parameters}, request_foreign=request_instance)

        if not serializer.is_valid():
            raise ValidationError(
                {f'Company "{company}", Request "{name}" serializer error!': serializer.errors}
            )

        company_name_pair = (company, name)
        if company_name_pair in request_handler_map:
            request_params_func = request_handler_map[company_name_pair](serializer, gregorian_now)
            if len(request_params_func) == 3:
                parameters, start_date_name, end_date_name = request_params_func
            elif len(request_params_func) == 4:
                parameters, start_date_name, end_date_name, esp_opt = request_params_func
        else:
            return Response(f"No requesting function defined for company: {company}, name: {name}", status=400)

        if company == "hamkadeh":
            headers = headers_h
        elif company == "5040":
            headers = headers_5

        task = (request_instance.method, request_instance.endpoint, headers, parameters)

        start_date = parameters[start_date_name].strftime('%Y/%m/%d %H:%M:%S')
        end_date = parameters[end_date_name].strftime('%Y/%m/%d %H:%M:%S')
        
        # separate date rage each day individual considering first starting and lans ending hours
        if len(request_params_func) == 3:
            dates = generate_intervals(start_date, end_date, idn)
        elif len(request_params_func) == 4:
            dates = generate_intervals(start_date, end_date, idn, esp_opt)

        method, url, headers, params = task
        for interval in dates:
            new_params = copy.deepcopy(params)

            new_params[start_date_name] = interval['start_date']
            new_params[end_date_name] = interval['end_date']

            expanded_tasks.append((
                method, url, headers, new_params, interval['start_date'], interval['end_date'],
                specific_dir, company, name, idn, esp_opt if 'esp_opt' in locals() else ""
            ))

    # Preparing requested data download
    max_retries = 3
    retry_count = 0
    completed_tasks = []
    while expanded_tasks and retry_count < max_retries:

        delay = random.randint(1 * 60, 10 * 60)  # seconds
        retry_count += 1
        
        # Printing company listed in tasks.
        # for idx, task in enumerate(expanded_tasks, start=1):
        #     print(f'☼ → {idx}. company: {task[7]}')
        
        if retry_count > 1:
            print(f"☻♣Sleeping for {delay} seconds")
            time.sleep(delay)

            # Refreshing targets
            if any(task[7] == "5040" for task in expanded_tasks):
                cookies_5 = refresh_5040(username)
                if not cookies_5:
                    logger.error("♪5040 panel refreshing issued while request tasks pool before executation ♪")
                    continue
                else:
                    print("♪5040 panel refreshing while encountered 5040 task.♪ Performs refreshed...")

        print(f"--- Try #{retry_count} for {len(expanded_tasks)} tasks ---")
        failed_tasks = []

        def delayed_handle_request(delay, *task_args):
            time.sleep(delay)
            return handle_request(*task_args)

        with ThreadPoolExecutor(max_workers=7) as executor:
            future_to_task = {}
            for idx, task in enumerate(expanded_tasks):
                interval = random.randint(1, 12)  # seconds
                print(f"→→→ task'th {idx + 1} delayed: {interval}")
                delay = interval * idx
                future = executor.submit(delayed_handle_request, delay, *task)
                future_to_task[future] = task


            for future in as_completed(future_to_task):
                
                task = future_to_task[future]

                try:
                    result, start_date, end_date, specific_dir, company, name, idn, esp_opt = future.result()
                except Exception as exc:
                    failed_tasks.append(task)
                    continue

                if result is None or not result.ok:
                    failed_tasks.append(task)
                    logger.error(
                        f"Error in fetching {company}'s {name} report in {start_date} to {end_date} "
                    )                    
                else:
                    print(f"☻☻Success fetching {company}'s {name} report in {start_date} to {end_date}.☺☺")

                    completed_tasks.append(future)

        expanded_tasks = failed_tasks

    return completed_tasks, failed_tasks


class DummyResponse:
    """A minimal stand‑in for a requests.Response-like object with headers."""
    def __init__(self, content: bytes, ext: str):
        self.content = content
        self.ok = True
        # Provide a Content-Disposition header so get_filename... can extract ext
        self.headers = {'Content-Disposition': f'attachment; filename=merged_file.{ext}'}

class MergedTask:
    """
    Mimics a Future whose .result() returns:
      (response_obj, start_str, end_str, shared_dir, company, name, idn)
    """
    def __init__(self, content_bytes, start_str, end_str, shared_dir, company, name, idn, ext, esp_opt):
        self._response = DummyResponse(content_bytes, ext)
        # ext is embedded in headers; do not include in meta unpack
        self._meta = (start_str, end_str, shared_dir, company, name, idn, esp_opt)

    def result(self):
        return (self._response, *self._meta)


def merge_completed_tasks(completed_tasks):
    """
    Input:
      completed_tasks: list of futures/tasks whose .result() returns
        (response_obj, s_jstr, e_jstr, shared_dir, company, name, idn)
        where s_jstr/e_jstr are Jalali strings '%Y/%m/%d %H:%M:%S'.
    Output:
      new list of MergedTask: for each shared_dir, if idn > 1 day then
      merge tasks in XLSX or CSV batches (never exceeding Excel row limit),
      otherwise pass tasks through unchanged.
    """
    raw = []
    for fut in completed_tasks:
        resp, s_jstr, e_jstr, shared_dir, company, name, idn, esp_opt = fut.result()

        # Check if esp_opt is not None and contains the 'datesep' key
        if esp_opt != "" and 'datesep' in esp_opt and esp_opt['datesep'] != "":
            date_separator = esp_opt['datesep']
        else:
            date_separator = '/'

        s_dt = datetime.datetime.strptime(s_jstr, f'%Y{date_separator}%m{date_separator}%d %H:%M:%S')
        e_dt = datetime.datetime.strptime(e_jstr, f'%Y{date_separator}%m{date_separator}%d %H:%M:%S')
        cd = getattr(resp, 'headers', {}).get('Content-Disposition', '')
        ext = 'csv' if '.csv' in cd.lower() else 'xlsx'
        raw.append({'resp': resp, 's_dt': s_dt, 'e_dt': e_dt,
                    's_jstr': s_jstr, 'e_jstr': e_jstr,
                    'shared_dir': shared_dir, 'company': company,
                    'name': name, 'idn': idn, 'ext': ext, 'esp_opt': esp_opt})

    groups = defaultdict(list)
    for item in raw:
        groups[item['shared_dir']].append(item)

    merged_tasks = []
    for shared_dir, items in groups.items():
        idn = items[0]['idn']
        # Default idn to 1 day if not provided
        if idn is None:
            idn = {'year': 0, 'month': 0, 'day': 1, 'hour': 0, 'minute': 0, 'second': 0}
        secs = (idn.get('year',0)*365*86400 + idn.get('month',0)*30*86400 +
                idn.get('day',0)*86400 + idn.get('hour',0)*3600 +
                idn.get('minute',0)*60 + idn.get('second',0))

        items.sort(key=lambda x: x['s_dt'])

        if secs <= 86400:
            for it in items:
                merged_tasks.append(MergedTask(it['resp'].content,
                                               it['s_jstr'], it['e_jstr'],
                                               it['shared_dir'], it['company'],
                                               it['name'], it['idn'], it['ext'], it['esp_opt']))
            continue

        current_df = None
        cur_esp_opt = None
        cur_start_dt = None
        cur_end_dt = None
        cur_meta = None
        group_ext = items[0]['ext']

        def flush_batch():
            nonlocal current_df, cur_esp_opt, cur_start_dt, cur_end_dt, cur_meta, group_ext
            if current_df is None:
                return
            with BytesIO() as buf:
                if group_ext == 'csv':
                    current_df.to_csv(buf, index=False, encoding='utf-8-sig')
                else:
                    current_df.to_excel(buf, index=False, engine='openpyxl')
                data = buf.getvalue()
                
            
            s_j = jdatetime.datetime.fromgregorian(datetime=cur_start_dt).strftime(f'%Y{date_separator}%m{date_separator}%d %H:%M:%S')
            e_j = jdatetime.datetime.fromgregorian(datetime=cur_end_dt).strftime(f'%Y{date_separator}%m{date_separator}%d %H:%M:%S')
            merged_tasks.append(MergedTask(data, s_j, e_j,
                                           cur_meta['shared_dir'], cur_meta['company'],
                                           cur_meta['name'], cur_meta['idn'], cur_meta['esp_opt'], group_ext))
            current_df = None

        for it in items:
            bio = BytesIO(it['resp'].content)
            df = pd.read_csv(bio) if it['ext'] == 'csv' else pd.read_excel(bio)
            if len(df) > EXCEL_MAX_ROWS:
                logger.error(f"Skipped task {it['s_jstr']}→{it['e_jstr']} (rows {len(df)}) > Excel limit")
                continue
            if current_df is None:
                current_df = df
                cur_esp_opt = it['esp_opt']
                cur_start_dt = it['s_dt']
                cur_end_dt = it['e_dt']
                cur_meta = it
            elif it['s_dt'] > (cur_start_dt + datetime.timedelta(seconds=secs)):
                flush_batch()
                current_df = df
                cur_esp_opt = it['esp_opt']
                cur_start_dt = it['s_dt']
                cur_end_dt = it['e_dt']
                cur_meta = it
            elif len(current_df) + len(df) > EXCEL_MAX_ROWS:
                flush_batch()
                current_df = df
                cur_esp_opt = it['esp_opt']
                cur_start_dt = it['s_dt']
                cur_end_dt = it['e_dt']
                cur_meta = it
            else:
                current_df = pd.concat([current_df, df], ignore_index=True)
                cur_end_dt = it['e_dt']
        flush_batch()
    return merged_tasks


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


class Missing(Exception):
    pass

def refresh_5040(username):
    
    # Load user object from DB
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        # Return error if user does not exist
        return Response(
            {'message': 'User not found'},
            status=status.HTTP_401_UNAUTHORIZED
        )

    # Load tokens from DB
    try:
        token = WebTokens.objects.get(user=user, name='token_5').value
        loginExpire = WebTokens.objects.get(user=user, name='loginExpire_5').value
    except WebTokens.DoesNotExist:
        raise Missing("Tokens missing")

    count_refresh_5 = 0
    while(True):
        result = asyncio.run(run_playwright_for_refresh(token, loginExpire))
        login_form, cookies = result

        if login_form:
            print(f"♠♠Login issued, Preparing refresh 5040!")
            if count_refresh_5 > 3:
                # Session expired; cancel scheduled job
                task_name = f"web_request_5040_refresh_{user.username}"
                schedule_cancelation(task_name)
                return None
            else:
                count_refresh_5 += 1
                delay = random.randint(3, 10)  # seconds
                time.sleep(delay)
        else:
            break
    
    # Update WebTokens with fresh cookies
    cookie_map = {'token': 'token_5', 'loginExpire': 'loginExpire_5'}
    refresh_kwargs = {}
    for c in cookies:
        key = cookie_map.get(c['name'])
        if key:
            refresh_kwargs[key] = c['value']
            WebTokens.objects.filter(user=user, name=key).update(value=c['value'])

    return cookies
