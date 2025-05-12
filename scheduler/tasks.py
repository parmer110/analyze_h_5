import requests
import logging
from rest_framework.response import Response
from celery import shared_task
from rest_framework import status
from selenium import webdriver
from web_requests.models import WebTokens
from common.models import User


logger = logging.getLogger(__name__)

def web_request_5040_refresh(username=None, token_5=None, loginExpire_5=None, **kwargs):
    """
    Scheduled task to call the RefreshSessionViewSet5040 view
    for refreshing the 5040 login session.
    Handles both direct parameters and legacy nested structure.
    """
    # Recover parameters from direct arguments or flat kwargs
    if username is None:
        username = kwargs.get('username')
    if token_5 is None:
        token_5 = kwargs.get('token_5')
    if loginExpire_5 is None:
        loginExpire_5 = kwargs.get('loginExpire_5')

    # Handle legacy nested 'kwargs' key if present
    nested = kwargs.get('kwargs') if isinstance(kwargs.get('kwargs'), dict) else None
    if nested:
        username = username or nested.get('username')
        token_5 = token_5 or nested.get('token_5')
        loginExpire_5 = loginExpire_5 or nested.get('loginExpire_5')

    # Validate required parameters
    if not (username and token_5 and loginExpire_5):
        logger.error(
            "Missing parameters for web_request_5040_refresh: %s", 
            {'username': username, 'token_5': token_5, 'loginExpire_5': loginExpire_5}
        )
        return

    # Construct internal request URL
    url = (
        f"http://192.168.134.10:8002/web_requests/5/refresh/"
        f"?username={username}&token_5={token_5}&loginExpire_5={loginExpire_5}"
    )
    headers = {'X-Internal-Request': 'true'}

    try:
        response = requests.get(url, headers=headers, timeout=300)
        response.raise_for_status()
        logger.info(
            "[5040 Refresh] User %s refreshed successfully, status: %s",
            username, response.status_code
        )
        return response.text

    except requests.HTTPError as e:
        logger.error(
            "[5040 Refresh] HTTP error for user %s: %s", username, e
        )
        return f"HTTPError: {e}"

    except requests.RequestException as e:
        logger.error(
            "[5040 Refresh] Request error for user %s: %s", username, e
        )
        return f"RequestException: {e}"


@shared_task
def open_browser(user, token, loginExpire):

    driver = webdriver.Chrome()

    driver.get('https://panel.5040.me')
    driver.add_cookie({'name': 'token', 'value': token})
    driver.add_cookie({'name': 'loginExpire', 'value': loginExpire})

    driver.get('https://panel.5040.me')
