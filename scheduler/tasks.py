import requests
import logging


logger = logging.getLogger(__name__)

def web_request_5040_refresh():
    url = "http://192.168.134.10:8001/web_requests/5/refresh/"
    try:
        response = requests.get(url, timeout=10)
        logger.info(f"Request sent. Status code: {response.status_code}")
        return f"Status Code: {response.status_code}"
    except requests.RequestException as e:
        logger.error(f"Error sending request: {e}")
        return f"Error: {e}"
