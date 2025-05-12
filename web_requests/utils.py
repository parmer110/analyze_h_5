import requests
import jdatetime
from datetime import timedelta
from typing import List, Dict

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

def handle_request(method, url, headers, data):
    response = None
    counter = 0
    if method == 'GET':
        while not response or counter > 3:
            response = requests.get(url, headers=headers, params=data)
            counter += 1
    elif method == 'POST':
        while not response or counter > 3:
            response = requests.post(url, headers=headers, json=data)
            counter += 1
    return response

def parse_jalali_datetime(date_str: str, format_with_sec: str, format_without_sec: str) -> jdatetime.datetime:
    """Parse Jalali date string with flexible seconds handling"""
    try:
        return jdatetime.datetime.strptime(date_str, format_with_sec)
    except ValueError:
        parsed = jdatetime.datetime.strptime(date_str, format_without_sec)
        return parsed.replace(second=0)  # Set missing seconds to zero

def generate_daily_intervals(start_str: str, end_str: str) -> List[Dict[str, str]]:
    """
    Generate daily intervals with automatic seconds handling
    Accepts both formats: '1404/02/01 12:30' and '1404/02/01 12:30:45'
    """
    # Define formats
    primary_format = '%Y/%m/%d %H:%M:%S'
    fallback_format = '%Y/%m/%d %H:%M'
    
    try:
        # Parse with flexible format handling
        start = parse_jalali_datetime(start_str, primary_format, fallback_format)
        end = parse_jalali_datetime(end_str, primary_format, fallback_format)
    except ValueError as e:
        raise ValueError(
            f"Invalid date format. Use either {primary_format} or {fallback_format}"
        ) from e

    if start > end:
        raise ValueError("Start date must be before end date")

    intervals = []
    current = start

    while current <= end:
        # Start time logic
        day_start = current if current == start else current.replace(
            hour=0, minute=0, second=0
        )
        
        # End time logic
        if current.date() == end.date():
            day_end = end
        else:
            day_end = current.replace(
                hour=23, minute=59, second=59
            )

        intervals.append({
            'start_date': day_start.strftime(primary_format),
            'end_date': day_end.strftime(primary_format)
        })

        # Move to next day (00:00:00)
        current = day_end + timedelta(seconds=1)

    return intervals