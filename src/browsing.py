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


async def generate_browser_instances(amount):
    class AtomicCounter:
        def __init__(self):
            self.__value = 0
            self.__mutex = threading.Lock()
        
        def inc(self):
            with self.__mutex:
                self.__value += 1
                return self.__value

        def postfix_inc(self):
            with self.__mutex:
                old_value = self.__value
                self.__value += 1
                return old_value

        def value(self):
            with self.__mutex:
                return self.__value
    
    async def async_range(n):
        for i in range(n):
            yield i
            await asyncio.sleep(0.0)
    
    async def async_enumerate(iterable):
        for idx, val in enumerate(iterable):
            yield idx, val
            await asyncio.sleep(0.0)

    browser_instances = [None for _ in range(amount)]
    launched_browsers = AtomicCounter()

    def worker(idx):
        browser_instances[idx] = webdriver.Chrome()
        browser_instances[idx].get("https://neuralblender.com/create-art")
        launched_browsers.inc()

    workers = []
    async for i in async_range(amount):
        workers.append(threading.Thread(target=worker, args=(i,)))
        workers[-1].start()
    while launched_browsers.value() != amount:
        await asyncio.sleep(.1)
    async for i, _ in async_enumerate(workers):
        workers[i].join()
    return browser_instances
