import requests
import logging


logger = logging.getLogger(__name__)

def web_request_5040_refresh(**kwargs):
    inner_kwargs = kwargs.get('kwargs', {})
    username = inner_kwargs.get('username')
    token_5 = inner_kwargs.get('token_5')
    loginExpire_5 = inner_kwargs.get('loginExpire_5')

    headers = {'X-Internal-Request': 'true'}
    url = f"http://192.168.134.10:8001/web_requests/5/refresh/?username={username}&token_5={token_5}&loginExpire_5={loginExpire_5}"
    try:
        response = requests.get(url, headers=headers, timeout=300)
        logger.info(f"Request sent. Status code: {response.status_code}")
        return f"Status Code: {response.status_code}"
    except requests.RequestException as e:
        logger.error(f"Error sending request: {e}")
        return f"Error: {e}"
