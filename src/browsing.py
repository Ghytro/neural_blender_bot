from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException

import asyncio, time, threading


# Returns the url of generated picture
async def wait_until_appears(browser, xpath, timeout = 10, polling_rate = 5):
    end_time = time.monotonic() + timeout
    while time.monotonic() <= end_time:
        try:
            return browser.find_element(by=By.XPATH, value=xpath)
        except NoSuchElementException:
            await asyncio.sleep(1/polling_rate)
    raise TimeoutError()


# Returns the url of generated picture
async def get_picture(browser, title) -> str:
    title_input = browser.find_element(by=By.XPATH, value='//*[@id="root"]/div[1]/div/div[2]/section[1]/div/div/input')
    submit_button = browser.find_element(by=By.XPATH, value='//*[@id="root"]/div[1]/div/div[2]/section[2]/div[2]/button')
    title_input.send_keys(title)
    submit_button.click()
    # Waiting for the div with queue to appear
    await wait_until_appears(browser, '//*[@id="root"]/div[1]/div/div/div[3]/section/div[2]/div')
    # Waiting for the div with queue to disappear
    await wait_until_appears(browser, '//*[@id="root"]/div[1]/div/div/div[3]/section/div[2]/p')
    my_art_button = browser.find_element(by=By.XPATH, value='//*[@id="root"]/div[1]/header/div[2]/nav/a[3]')
    my_art_button.click()
    img = await wait_until_appears(browser, '//*[@id="root"]/div[1]/div/div/div[3]/section/div[2]/div/img')
    img_src = img.get_attribute("src")
    browser.quit()
    return img_src


def generate_browser_instances(amount):
    browser_instances = [None for _ in range(amount)]
    def worker(index: int):
        browser_instances[index] = webdriver.Chrome()
        browser_instances[index].get("https://neuralblender.com/create-art")
    workers = []
    for i, _ in enumerate(browser_instances):
        workers.append(threading.Thread(target=worker, args=(i,)))
        workers[-1].start()
    for i, _ in enumerate(workers):
        workers[i].join()
    return browser_instances
