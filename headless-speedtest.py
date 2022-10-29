from selenium.webdriver import Firefox
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By
from pathlib import Path
import time
from datetime import datetime as dt
import logging
import random
from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS
import platform

# some general params
ROOT_PATH = Path.cwd()
GECKO_DRIVER_PATH = ROOT_PATH / 'geckodriver'
PAGE_LOAD_DELAY = 5
SAVE_SCREENSHOT = False # enable to save a screenshot of the completed test
SCREENSHOT_PATH = ROOT_PATH / 'last_test.png'

# scoring parameters
MAX_PING = 10 # ms - 10 is a reasonable number for fibre
MIN_DOWNLOAD = 400 # mbps - set this to about 80% of your specified download
MIN_UPLOAD = 400 # mbps - set this to about 80% of your specified upload
SCORE_CHANCE = 0.5 # assuming above thresholds are met, what is the chance of actually scoring

# influx db parameters
INFLUX_TOKEN = None
INFLUX_ORG = None
INFLUX_BUCKET = None
INFLUX_URL = None

# plaintext parameters
CSV_RESULTS_PATH = ROOT_PATH / 'headless-speedtest-results.csv'

# logging config
LOG_FILE_PATH = ROOT_PATH / 'headless-speedtest.log'
LOG_LEVEL = logging.INFO
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# functions
def run_speedtest(speedtest_url: str, 
                  start_element: str, 
                  test_completion_element: str,
                  timeout=60) -> Firefox:
    # setup the webdriver
    options = Options()
    options.headless = True
    service = Service(GECKO_DRIVER_PATH)
    driver = Firefox(options=options, service=service)

    # get the page
    logging.info("Initialising web driver")
    driver.get(speedtest_url)

    # lazy wait for some page loading
    logging.info(f"Waiting for page {speedtest_url} to load...")
    time.sleep(PAGE_LOAD_DELAY)

    # getting key elements
    start_button = driver.find_element(By.ID, start_element)
    test_complete_element = driver.find_element(By.ID, test_completion_element) 
    
    # start the test
    logging.info("Starting speedtest")
    start_button.click()
    test_start = time.time()

    # wait for the test to complete by checking visibility of completion element
    logging.info("Waiting for speedtest to complete...")
    while not test_complete_element.is_displayed():
        time.sleep(1)
        if (time.time() - test_start) > timeout:
            logging.ERROR("Speedtest timed out")
            return None
    
    # return the completed test for results extraction and misc further actions
    logging.info("Speedtest complete")
    return driver


if __name__ == '__main__':
    logging.basicConfig(filename=LOG_FILE_PATH, level=LOG_LEVEL, format=LOG_FORMAT, filemode='a')
    logging.info("Starting headless speedtest")

    # this config is specific to speedtest.co.za
    speedtest_url = 'http://speedtest.co.za/'
    start_element_id = 'start-btn'
    test_completion_element_id = 'starRating'

    # run the test and return the completed test instance
    try:
        driver = run_speedtest(speedtest_url, start_element_id, test_completion_element_id)
    except:
        logging.exception("An uncaught error occured while trying to the run the speedtest")
    else:
        # extract the results, most of this code is specific to speedtest.co.za
        ping_result_id = 'ping-result'
        download_result_id = 'download-result'
        upload_result_id = 'upload-result'
        result_ids = [ping_result_id, download_result_id, upload_result_id]

        results = {}    
        for result_id in result_ids:
            result = driver.find_element(By.ID, result_id)
            results[result_id] =  float(result.text)

        # score the results
        score_test = True
        if results[ping_result_id] > MAX_PING:
            score_test = False
            logging.warning("Ping results above threshold")

        if results[download_result_id] < MIN_DOWNLOAD:
            score_test = False
            logging.warning("Download results below threshold")

        if results[upload_result_id] < MIN_UPLOAD:
            score_test = False
            logging.warning("Upload results below threshold")

        if not random.choices([True, False], [SCORE_CHANCE, 1 - SCORE_CHANCE]):
            score_test = False

        if score_test:
            logging.info("Giving 5/5 test score")
            scoring_parent = driver.find_element(By.ID, test_completion_element_id)
            stars = scoring_parent.find_elements(By.CLASS_NAME, "fa")
            stars[-1].click()

        # write our results out with a timestamp
        if CSV_RESULTS_PATH is not None:
            logging.info("Writing results to CSV")
            with open(CSV_RESULTS_PATH, 'a') as rf:
                rf.write(f"{dt.now().isoformat()},{results[ping_result_id]},{results[download_result_id]},{results[upload_result_id]}\n")

        # write our results to influxDB
        if INFLUX_URL is not None:
            logging.info("Writing results to influxDB")
            with InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG) as client:
                write_api = client.write_api(write_options=SYNCHRONOUS)

                data = [f"speedtest,host={platform.node()} ping_ms={results[ping_result_id]}",
                        f"speedtest,host={platform.node()} download_mbps={results[download_result_id]}",
                        f"speedtest,host={platform.node()} upload_mbps={results[upload_result_id]}"]

                write_api.write(INFLUX_BUCKET, INFLUX_ORG, data)

        # save screenshot of last speedtest
        if SAVE_SCREENSHOT:
            driver.save_screenshot(SCREENSHOT_PATH)

        # close the webdriver instance
        driver.close()
        logging.info("Headless speedtest script complete")
