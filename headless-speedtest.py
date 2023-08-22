import os
import datetime
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
import argparse
import tomllib
from typing import Optional

# logger initialisation
logger = logging.getLogger("headless-speedtest")
logger.setLevel(logging.DEBUG)


# functions
def run_speedtest(
    speedtest_url: str,
    start_element: str,
    test_completion_element: str,
    config: dict,
    timeout=60,
) -> Optional[Firefox]:
    # setup the webdriver
    options = Options()
    options.add_argument('-headless')
    service = Service(config["files"]["geckodriver_name"])
    driver = Firefox(options=options, service=service)

    # get the page
    logger.info("Initialising web driver")
    driver.get(speedtest_url)

    # lazy wait for some page loading
    logger.info(f"Waiting for page {speedtest_url} to load...")
    time.sleep(config["test_load"]["page_load_delay"])

    # getting key elements
    start_button = driver.find_element(By.ID, start_element)
    test_complete_element = driver.find_element(By.ID, test_completion_element)

    # start the test
    logger.info("Starting speedtest")
    start_button.click()
    test_start = time.time()

    # wait for the test to complete by checking visibility of completion element
    logger.info("Waiting for speedtest to complete...")
    while not test_complete_element.is_displayed():
        time.sleep(1)
        if (time.time() - test_start) > timeout:
            logger.error("Speedtest timed out")
            return None

    # return the completed test for results extraction and misc further actions
    logger.info("Speedtest complete")
    return driver


def load_config(config_path: Path) -> dict:
    # check if the config file exists
    if not config_path.is_file():
        raise FileNotFoundError(f"The specified config path '{config_path}' is invalid")

    # load raw config
    with open(config_path, "rb") as f:
        config: dict = tomllib.load(f)

    config["files"]["geckodriver_name"] = Path(config["files"]["geckodriver_name"])
    config["test_load"]["screenshot_name"] = Path(config["test_load"]["screenshot_name"])
    config["csv_results"]["csv_name"] = Path(config["csv_results"]["csv_name"])
    config["logging"]["log_name"] = Path(config["logging"]["log_name"])

    if not config["files"]["geckodriver_name"].is_file():
        raise FileNotFoundError(
            f"Firefox webdriver could not be found at {config['files']['geckodriver_name']}"
        )

    return config

def main(config: dict) -> None:
    try:
        driver = run_speedtest(
            speedtest_url, start_element_id, test_completion_element_id, config
        )
    except:
        logger.exception(
            "An uncaught error occured while trying to the run the speedtest"
        )
    else:
        if driver is not None:
            # extract the results, most of this code is specific to speedtest.co.za
            ping_result_id = config["test_run"]["ping_result"]
            download_result_id = config["test_run"]["download_result"]
            upload_result_id = config["test_run"]["upload_result"]
            result_ids = [ping_result_id, download_result_id, upload_result_id]

            results = {}
            for result_id in result_ids:
                result = driver.find_element(By.ID, result_id)
                results[result_id] = float(result.text)

            # score the results
            score_test = True
            if results[ping_result_id] > config["test_scoring"]["max_ping"]:
                score_test = False
                logger.warning("Ping results above threshold")

            if results[download_result_id] < config["test_scoring"]["min_download"]:
                score_test = False
                logger.warning("Download results below threshold")

            if results[upload_result_id] < config["test_scoring"]["min_upload"]:
                score_test = False
                logger.warning("Upload results below threshold")

            # TODO: add random scoring again in conf
            # if random.random() > SCORE_CHANCE:
            #     score_test = False

            if config["test_run"]["score"]:
                if score_test:
                    logger.info("Giving 5/5 test score")
                    scoring_parent = driver.find_element(
                        By.ID, test_completion_element_id
                    )
                    # TODO: refactor out into config
                    stars = scoring_parent.find_elements(By.XPATH, "//*[contains(@class, 'star')]")
                    try:
                        stars[-1].click()
                    except IndexError:
                        logger.warning("Could not find star to rate, site might be modified!")

            # write our results out with a timestamp
            if config["csv_results"]["save_csv"]:
                logger.info("Writing results to CSV")
                with open(config["csv_results"]["csv_name"], "a") as rf:
                    rf.write(
                        f"{dt.now().isoformat()},{results[ping_result_id]},{results[download_result_id]},{results[upload_result_id]},{score_test}\n"
                    )

            # write our results to influxDB
            if config["influx_db"]["save_influx"]:
                logger.info("Writing results to influxDB")
                with InfluxDBClient(
                    url=config["influx_db"]["influx_url"],
                    token=config["influx_db"]["influx_token"],
                    org=config["influx_db"]["influx_org"],
                ) as client:
                    write_api = client.write_api(write_options=SYNCHRONOUS)

                    data = [
                        f"speedtest,host={platform.node()} ping_ms={results[ping_result_id]}",
                        f"speedtest,host={platform.node()} download_mbps={results[download_result_id]}",
                        f"speedtest,host={platform.node()} upload_mbps={results[upload_result_id]}",
                        f"speedtest,host={platform.node()} test_scored={score_test}",
                    ]
                    # TODO: check if host identifier remains valid

                    write_api.write(
                        config["influx_db"]["influx_bucket"],
                        config["influx_db"]["influx_org"],
                        data,
                    )

            # save screenshot of last speedtest
            if config["test_load"]["save_test_screenshot"]:
                driver.save_screenshot(config["test_load"]["screenshot_name"])

            # close the webdriver instance
            driver.close()
            logger.info("Speedtest complete.")
        else:
            logger.error("An error occurred while running the speedtest.")


if __name__ == "__main__":
    # parse non-default config and check if valid file
    DEFAULT_CONFIG_PATH: Path = Path("/app/config/config.toml")

    # load parsed config
    config: dict = load_config(DEFAULT_CONFIG_PATH)

    # configure file logger
    fl: logging.FileHandler = logging.FileHandler(config["logging"]["log_name"])
    match (config["logging"]["log_level"]):
        # TODO: put in cases for other log levels
        case "debug" | "DEBUG":
            fl.setLevel(logging.DEBUG)
        case _:
            fl.setLevel(logging.INFO)
    fl.setFormatter(logging.Formatter(config["logging"]["log_format"]))
    logger.addHandler(fl)

    logger.debug("Config loaded and logger configured")
    logger.info("Starting headless speedtest")

    # this config is specific to speedtest.co.za
    speedtest_url = config["test_run"]["test_url"]
    start_element_id = config["test_run"]["test_trigger"]
    test_completion_element_id = config["test_run"]["score_trigger"]

    # get repeat properties
    test_repeat = bool(os.getenv("TEST_REPEAT", config["test_run"]["test_repeat"]))
    repeat_test_interval = float(os.getenv("REPEAT_TEST_INTERVAL", config["test_run"]["repeat_test_interval"]))
    repeat_test_time_align = int(os.getenv("REPEAT_TEST_ALIGNMENT_TIME", config["test_run"]["repeat_test_time_align"]))

    # run the test and return the completed test instance
    if not test_repeat:
        main(config)
    else:
        logger.info(f"Starting recurring testing at {repeat_test_interval} minute intervals, starting at the next {repeat_test_time_align} minute of the hour")
        current_time = datetime.datetime.now()
        minute_delta = repeat_test_time_align - current_time.minute
        if minute_delta < 0:
            time.sleep((60 + minute_delta) * 60)
        else:
            time.sleep(minute_delta * 60)
        next_test_time = datetime.datetime.now()
        while True:
            current_time = datetime.datetime.now()
            if current_time >= next_test_time:
                next_test_time += datetime.timedelta(minutes=repeat_test_interval)
                main(config)
                logger.info(f"Sleeping until next test...")

            # 1 minute sleep to stop this loop from chowing resources
            time.sleep(60)

    logger.info("Headless speedtest script complete.")
    
