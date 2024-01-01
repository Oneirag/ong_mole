"""
Module to get jwt token from selenium
"""
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC


from ong_utils import Chrome
from selenium.webdriver.support.ui import WebDriverWait
from ong_mole import server, logger


def get_token() -> str:
    """Gets jwt token from user authentication"""
    chrome = Chrome(undetected=True)
    url = server + "/gobook/mainmonitor"
    driver = chrome.get_driver()

    driver.get(url)
    # Wait for windows icon to be shown
    elem = WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.PARTIAL_LINK_TEXT, 'Windows'))  # This is a dummy element
    )
    elem.click()
    token = None
    try:
        request_url = "wns/negotiate"
        # request_url = "/connect/userinfo"
        req = chrome.wait_for_request(url=None, request_url=request_url, timeout=60 * 10)
        # req = driver.wait_for_request("/connect/userinfo", timeout=60 * 10)
        # req = driver.wait_for_request("wns/negotiate", timeout=60 * 10)
        token = req.headers['Authorization'].split(" ")[-1]
    except:
        pass
    # sleep(.1)
    chrome.close_driver()
    # driver.quit()
    return token


if __name__ == '__main__':
    token = get_token()
    print(token)
