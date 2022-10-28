from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By
from pathlib import Path
import time
from datetime import datetime as dt

ROOT = Path.cwd()
GECKO_DRIVER_PATH = ROOT / 'geckodriver'
RESULTS_PATH = ROOT / 'speedtest-results.txt'

def get_speedtest_result(speedtest_url: str, 
                         start_element: str, 
                         result_elements: list[str],
                         wait_element: str) -> dict[str, float]:
    # setup the webdriver
    options = Options()
    options.headless = True
    service = Service(GECKO_DRIVER_PATH)
    driver = webdriver.Firefox(options=options, service=service)

    # get the page    
    driver.get(speedtest_url)

    test_complete_element = driver.find_element(By.ID, wait_element)

    # start the test
    start_button = driver.find_element(By.ID, start_element)
    # lazy wait for some page loading
    time.sleep(5)
    start_button.click()

    # wait for the test to complete
    while not test_complete_element.is_displayed():
        time.sleep(1)

    # get the results
    results_dict = {}    
    for result_element in result_elements:
        result = driver.find_element(By.ID, result_element)
        results_dict[result_element] =  result.text
    
    driver.close()
    return results_dict


if __name__ == '__main__':
    page_url = 'http://speedtest.co.za/'
    start_button_id = 'start-btn'
    ping_result_id = 'ping-result'
    download_result_id = 'download-result'
    upload_result_id = 'upload-result'
    wait_element_id = 'starRating'
    result_ids = [ping_result_id, download_result_id, upload_result_id]
    results = get_speedtest_result(page_url, 
                                   start_button_id, 
                                   result_ids,
                                   wait_element_id)

    # write our results out with a timestamp
    with open(RESULTS_PATH, 'a') as rf:
        rf.write(f"{dt.now().isoformat()} - p:{results[ping_result_id]} - d:{results[download_result_id]} - u:{results[upload_result_id]}\n")