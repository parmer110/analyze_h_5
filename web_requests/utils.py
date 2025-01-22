import requests

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