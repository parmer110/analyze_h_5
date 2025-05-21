import requests
import jdatetime
import logging
import re
import os
from datetime import timedelta
from typing import List, Dict
from email.parser import HeaderParser
from urllib.parse import unquote

logger = logging.getLogger(__name__)


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

def handle_request(method, url, headers, data, start_date, end_date, shared_dir, lock, responseflag):
    response = None
    counter = 0
    if method == 'GET':
        while (not response or not response.ok) and counter <= 3:
            counter += 1

            logger.info(f"Attempting GET request to {url} with headers {headers} and params {data}.")

            try:
                print(f'→ count: {counter}, url: {url}, start date: {start_date}, end date: {end_date}←')
                response = requests.get(url, headers=headers, params=data, timeout=1200)
            except requests.exceptions.ConnectionError:
                response = None
            except requests.exceptions.Timeout:
                response = None
            
            if response is not None and response.ok:
                # print(f"GET request to {response.url} Header is {headers} Succeeded with status code {response.status_code}.")
                logger.info(f"GET request to {response.url} succeeded with status code {response.status_code}.")
            else:
                if response:
                    logger.error(f"GET request to {response.url} failed with status code {response.status_code}.")
                else:
                    logger.error(f"GET request to {url}, start date: {start_date}, end date: {end_date} failed 666!!!")
                # Perform tokens updatation while request issued.
                if url.split('.')[1] == "5040":
                    if responseflag:
                        print(f'5040 issue→→→→Locked←←←←, url: {url}, start date: {start_date}, end date: {end_date} ')
                        lock.acquire()
                        lock.release()
                        print(f'5040 issue→→→→Locke ♥♥Release♥♥←←←←, url: {url}, start date: {start_date}, end date: {end_date} ')
                    else:
                        lock.acquire()
                        responseflag = True
                        response_temp = requests.get('http://192.168.134.10:8002/web_requests/5/refresh/?username=aeshraghi', timeout=300)
                        responseflag = False
                        lock.release()
                        print(f'5040 Refreshing→→→→{response_temp}←←←←')
                    
                # Perform tokens updatation while request issued.

    elif method == 'POST':
        while (not response or not response.ok) and counter <= 3:
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
                if url.split('.')[1] == "5040":
                    # response_temp = requests.get('http://192.168.134.10:8002/web_requests/5/refresh/?username=aeshraghi', timeout=300)
                    # print(f'→→→→{response_temp}←←←←')
                    pass
        
    counter = 0

    print(f"request to {response.url} Header is {headers} with status code {response.status_code}.")
    return response, start_date, end_date, shared_dir

def parse_jalali_datetime(date_str: str, format_with_sec: str, format_without_sec: str) -> jdatetime.datetime:
    """Parse Jalali date string with flexible seconds handling"""
    try:
        return jdatetime.datetime.strptime(date_str, format_with_sec)
    except ValueError:
        parsed = jdatetime.datetime.strptime(date_str, format_without_sec)
        return parsed.replace(second=0)  # Set missing seconds to zero

from datetime import datetime, timedelta
import jdatetime
from typing import List, Dict

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


def generate_daily_intervals(
    start_str: str,
    end_str: str
) -> List[Dict[str, str]]:
    """
    Generate daily intervals as Gregorian date strings.
    
    - start_str, end_str: Jalali strings like '1404/02/10 12:30' or '1404/02/10 12:30:45'
    - Returns: [{'start_date': 'YYYY/MM/DD HH:MM:SS', 'end_date': 'YYYY/MM/DD HH:MM:SS'}, ...]
    """
    primary_format = '%Y/%m/%d %H:%M:%S'
    fallback_format = '%Y/%m/%d %H:%M'

    jstart = parse_jalali_datetime(start_str, primary_format, fallback_format)
    jend   = parse_jalali_datetime(end_str,   primary_format, fallback_format)

    start = jstart.togregorian()
    end   = jend.togregorian()

    if start > end:
        raise ValueError("Start date must be before end date")

    intervals: List[Dict[str, str]] = []
    current = start

    while current <= end:
        day_start = current if current == start else current.replace(
            hour=0, minute=0, second=0
        )

        if current.date() == end.date():
            day_end = end
        else:
            day_end = current.replace(hour=23, minute=59, second=59)

        intervals.append({
            'start_date': day_start.strftime(primary_format),
            'end_date':   day_end.strftime(primary_format),
        })

        current = day_end + timedelta(seconds=1)

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
