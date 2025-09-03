import logging
import datetime
import random
import time
import asyncio
from asgiref.sync import sync_to_async
from playwright.sync_api import sync_playwright
from common.models import User
from web_requests.models import WebTokens


logger = logging.getLogger(__name__)


async def refresh_5040_session(user: User, token: str = None, loginExpire: str = None, is_internal: bool = False):
    """
    Central service function to refresh 5040 panel session.
    Returns dict with status and message.
    """

    # Load tokens from DB if not provided
    if not token or not loginExpire:
        try:
            token = (await sync_to_async(WebTokens.objects.get)(user=user, name="token_5")).value
            loginExpire = (await sync_to_async(WebTokens.objects.get)(user=user, name="loginExpire_5")).value
        except WebTokens.DoesNotExist:
            return {"status": "error", "message": "Tokens missing"}

    # Run Playwright
    async def run_playwright_for_refresh(token, loginExpire):
        def _sync_refresh():
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context()
                context.add_cookies([
                    {"name": "token", "value": token, "domain": "panel.5040.me", "path": "/"},
                    {"name": "loginExpire", "value": loginExpire, "domain": "panel.5040.me", "path": "/"},
                ])
                page = context.new_page()

                max_retries = 3
                delay = random.randint(2 * 60, 7 * 60)

                for attempt in range(max_retries):
                    try:
                        page.goto("https://panel.5040.me/", timeout=60000)
                        break
                    except Exception as e:
                        current_time = datetime.datetime.now().strftime("%H:%M:%S")
                        logger.error(f"Error page.goto at {current_time}: {e}")
                        if attempt < max_retries:
                            time.sleep(delay)
                        else:
                            logger.error("Max retries reached.")
                try:
                    page.goto("https://panel.5040.me/", timeout=60000)
                except Exception as e:
                    logger.error(f"Error navigating to URL: {e}")

                page.wait_for_load_state("networkidle")
                login_form = page.query_selector("form.auth-login-form.mt-2")
                cookies = context.cookies("https://panel.5040.me")
                browser.close()
                return login_form, cookies

        return await asyncio.to_thread(_sync_refresh)

    login_form, cookies = await run_playwright_for_refresh(token, loginExpire)

    # Session expired
    if login_form:
        return {"status": "expired", "message": "Session expired; please login again."}

    # Update DB tokens
    cookie_map = {"token": "token_5", "loginExpire": "loginExpire_5"}
    for c in cookies:
        key = cookie_map.get(c["name"])
        if key:
            await sync_to_async(WebTokens.objects.filter(user=user, name=key).update)(value=c["value"])

    # Reschedule job if internal

    return {"status": "ok", "message": "Refreshed successfully"}