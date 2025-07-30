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
from concurrent.futures import ThreadPoolExecutor, as_completed
from rest_framework.response import Response
from collections import defaultdict
from dateutil.relativedelta import relativedelta
import pandas as pd
from io import BytesIO
from datetime import timedelta
from typing import List, Dict
from email.parser import HeaderParser
from itertools import islice
from urllib.parse import unquote
from common.locks import redlock_instance

from common.models import User, Companies
from .models import RequestsForeign
from .serializers import DynamicRequestSerializer
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

def handle_request(method, url, headers, data, start_date, end_date, shared_dir, company, name, idn):
    response = None
    counter = 0
    if method == 'GET':
        while (not response or not response.ok) and counter <= 0:
            counter += 1

            logger.info(f"Attempting GET request to {url} with headers {headers} and params {data}.")

            try:
                print(f'→ count: {counter}, url: {url}, start date: {start_date}, end date: {end_date}←')
                response = requests.get(url, headers=headers, params=data, timeout=1200)
                print("↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓")
                print(response)
            except requests.exceptions.ConnectionError:
                print("↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓")
                print("requests.exceptions.ConnectionError")
                response = None
            except requests.exceptions.Timeout:
                print("↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓")
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
            except requests.exceptions.ConnectionError:
                response = None
            except requests.exceptions.Timeout:
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
    return response, start_date, end_date, shared_dir, company, name, idn


def parse_jalali_datetime(
    date_str: str,
    format_with_sec: str,
    format_without_sec: str
) -> jdatetime.datetime:
    """Parse a Jalali date string, filling missing seconds if needed."""
    try:
        return jdatetime.datetime.strptime(date_str, format_with_sec)
    except ValueError:
        parsed = jdatetime.datetime.strptime(date_str, format_without_sec)
        return parsed.replace(second=0)


def generate_intervals(
    start_str: str,
    end_str: str,
    idn: Dict[str, int]
) -> List[Dict[str, str]]:
    """
    Generate time-based intervals according to integration_days_num (idn).

    - start_str, end_str: Jalali strings like '1404/02/10 12:30:45'
    - idn: {'year':0, 'month':0, 'day':0, 'hour':h, 'minute':m, 'second':s}
    - Returns: [{'start_date': 'YYYY/MM/DD HH:MM:SS', 'end_date': 'YYYY/MM/DD HH:MM:SS'}, ...]
    """
    primary_fmt = '%Y/%m/%d %H:%M:%S'
    fallback_fmt = '%Y/%m/%d %H:%M'

    # Default idn to 1 day if not provided
    if idn is None:
        idn = {'year': 0, 'month': 0, 'day': 1, 'hour': 0, 'minute': 0, 'second': 0}

    # convert Jalali to Gregorian datetime
    jstart = parse_jalali_datetime(start_str, primary_fmt, fallback_fmt)
    jend   = parse_jalali_datetime(end_str,   primary_fmt, fallback_fmt)
    start = jstart.togregorian()
    end   = jend.togregorian()

    if start > end:
        raise ValueError("Start date must be before end date")

    # Devide littelest interval
    if idn.get("second", 0) > 0:
        step = timedelta(seconds=idn["second"])
    elif idn.get("minute", 0) > 0:
        step = timedelta(minutes=idn["minute"])
    elif idn.get("hour", 0) > 0:
        step = timedelta(hours=idn["hour"])
    else:
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
            'start_date': current_start.strftime(primary_fmt),
            'end_date':   current_end.strftime(primary_fmt),
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
    match_ascii = re.search(r'filename="?([^"]+)"?', content_disposition)
    if match_ascii:
        filename = match_ascii.group(1)
        extension = filename.split('.')[-1].lower() if '.' in filename else None
        return filename, extension

    # Fallback: try Content-Type header
    content_type = response.headers.get('Content-Type', '').lower()
    if 'excel' in content_type:
        return None, 'xlsx'
    elif 'csv' in content_type:
        return None, 'csv'

    return None, None


def extraction(request, headers_h, headers_5, gregorian_now):
    # Functions requesting web_app
    # Will made automization
    request_handler_map = {
        ('5040', 'sale/entries/extraction'): _5_sale_entries_extraction_request_params,
        ('hamkadeh', 'entry/extract-numbers'): _h_extract_numbers_request_params,

        ('5040', 'call/logs/list'): _5_call_logs_list_request_params,
        ('hamkadeh', 'call-log/index'): _h_call_log_index_request_params,

        ('5040', 'factors/list'): _5_factors_list_request_params,
        ('hamkadeh', 'factor/index'): _h_factor_index_request_params,

        ('hamkadeh', 'accounting/call-log/index'): _h_accounting_call_log_index,

        ('hamkadeh', 'reservation/index'): _h_reservation_index,
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
            return Response(f'The Company: {company} does not exist!' , status=405)

        try:
            request_instance = RequestsForeign.objects.get(company=company_inst, name=name)
        except RequestsForeign.DoesNotExist:
            return Response(f'The {name} does not exist for {company} company defined requests!' , status=405)
        
        # Dynamic serializer
        serializer = DynamicRequestSerializer(data={**body_parameters, **query_parameters}, request_foreign=request_instance)

        if not serializer.is_valid():
            return Response({f'Company "{company}", Request "{name}" serializer error!':serializer.errors, 'status':412})

        company_name_pair = (company, name)
        if company_name_pair in request_handler_map:
            parameters, start_date_name, end_date_name  = request_handler_map[company_name_pair](serializer, gregorian_now)
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
        dates = generate_intervals(start_date, end_date, idn)

        method, url, headers, params = task
        for interval in dates:
            new_params = copy.deepcopy(params)

            new_params[start_date_name] = interval['start_date']
            new_params[end_date_name] = interval['end_date']

            expanded_tasks.append((
                method, url, headers, new_params, interval['start_date'], interval['end_date'], specific_dir, company, name, idn
            ))
    
    #############################
    # Preparing requested data download
    max_retries = 5
    retry_count = 0

    while expanded_tasks and retry_count < max_retries:
        delay = random.randint(1 * 60, 10 * 60)  # seconds
        retry_count += 1

        if retry_count > 1:
            print(f"☻♣Sleeping for {delay} seconds")
            time.sleep(delay)

        print(f"--- Try #{retry_count} for {len(expanded_tasks)} tasks ---")
        failed_tasks = []

        def delayed_handle_request(delay, *task_args):
            time.sleep(delay)
            return handle_request(*task_args)

        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_task = {}
            for idx, task in enumerate(expanded_tasks):
                interval = random.randint(1, 12)  # seconds
                print(f"→→→ task'th {idx + 1} delayed: {interval}")
                delay = interval * idx
                future = executor.submit(delayed_handle_request, delay, *task)
                future_to_task[future] = task

            completed_tasks = []

            for future in as_completed(future_to_task):
                
                task = future_to_task[future]

                try:
                    result, start_date, end_date, specific_dir, company, name, idn = future.result()
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
    def __init__(self, content_bytes, start_str, end_str, shared_dir, company, name, idn, ext):
        self._response = DummyResponse(content_bytes, ext)
        # ext is embedded in headers; do not include in meta unpack
        self._meta = (start_str, end_str, shared_dir, company, name, idn)

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
        resp, s_jstr, e_jstr, shared_dir, company, name, idn = fut.result()
        s_dt = jdatetime.datetime.strptime(s_jstr, '%Y/%m/%d %H:%M:%S').togregorian()
        e_dt = jdatetime.datetime.strptime(e_jstr, '%Y/%m/%d %H:%M:%S').togregorian()
        cd = getattr(resp, 'headers', {}).get('Content-Disposition', '')
        ext = 'csv' if '.csv' in cd.lower() else 'xlsx'
        raw.append({'resp': resp, 's_dt': s_dt, 'e_dt': e_dt,
                    's_jstr': s_jstr, 'e_jstr': e_jstr,
                    'shared_dir': shared_dir, 'company': company,
                    'name': name, 'idn': idn, 'ext': ext})

    # Default idn to 1 day if not provided
    if idn is None:
        idn = {'year': 0, 'month': 0, 'day': 1, 'hour': 0, 'minute': 0, 'second': 0}

    groups = defaultdict(list)
    for item in raw:
        groups[item['shared_dir']].append(item)

    merged_tasks = []
    for shared_dir, items in groups.items():
        idn = items[0]['idn']
        secs = (idn.get('year',0)*365*86400 + idn.get('month',0)*30*86400 +
                idn.get('day',0)*86400 + idn.get('hour',0)*3600 +
                idn.get('minute',0)*60 + idn.get('second',0))

        items.sort(key=lambda x: x['s_dt'])

        if secs <= 86400:
            for it in items:
                merged_tasks.append(MergedTask(it['resp'].content,
                                               it['s_jstr'], it['e_jstr'],
                                               it['shared_dir'], it['company'],
                                               it['name'], it['idn'], it['ext']))
            continue

        current_df = None
        cur_start_dt = None
        cur_end_dt = None
        cur_meta = None
        group_ext = items[0]['ext']

        def flush_batch():
            nonlocal current_df, cur_start_dt, cur_end_dt, cur_meta, group_ext
            if current_df is None:
                return
            with BytesIO() as buf:
                if group_ext == 'csv':
                    current_df.to_csv(buf, index=False, encoding='utf-8-sig')
                else:
                    current_df.to_excel(buf, index=False, engine='openpyxl')
                data = buf.getvalue()
            s_j = jdatetime.datetime.fromgregorian(datetime=cur_start_dt).strftime('%Y/%m/%d %H:%M:%S')
            e_j = jdatetime.datetime.fromgregorian(datetime=cur_end_dt).strftime('%Y/%m/%d %H:%M:%S')
            merged_tasks.append(MergedTask(data, s_j, e_j,
                                           cur_meta['shared_dir'], cur_meta['company'],
                                           cur_meta['name'], cur_meta['idn'], group_ext))
            current_df = None

        for it in items:
            bio = BytesIO(it['resp'].content)
            df = pd.read_csv(bio) if it['ext'] == 'csv' else pd.read_excel(bio)
            if len(df) > EXCEL_MAX_ROWS:
                logger.error(f"Skipped task {it['s_jstr']}→{it['e_jstr']} (rows {len(df)}) > Excel limit")
                continue
            if current_df is None:
                current_df = df
                cur_start_dt = it['s_dt']
                cur_end_dt = it['e_dt']
                cur_meta = it
            elif it['s_dt'] > (cur_start_dt + datetime.timedelta(seconds=secs)):
                flush_batch()
                current_df = df
                cur_start_dt = it['s_dt']
                cur_end_dt = it['e_dt']
                cur_meta = it
            elif len(current_df) + len(df) > EXCEL_MAX_ROWS:
                flush_batch()
                current_df = df
                cur_start_dt = it['s_dt']
                cur_end_dt = it['e_dt']
                cur_meta = it
            else:
                current_df = pd.concat([current_df, df], ignore_index=True)
                cur_end_dt = it['e_dt']
        flush_batch()
    return merged_tasks