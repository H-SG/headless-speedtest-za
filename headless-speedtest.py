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


def load_config(args: argparse.Namespace) -> dict:
    # check if the config file exists
    config_path: Path
    if isinstance(args.CONFIG_PATH, Path):
        config_path = args.CONFIG_PATH
    else:
        config_path = Path(args.CONFIG_PATH)
    if not config_path.is_file():
        raise FileNotFoundError(f"The specified config path '{config_path}' is invalid")

    # load raw config
    with open(config_path, "rb") as f:
        config: dict = tomllib.load(f)

    # setup paths in config
    root_path: Path
    if config["files"]["custom_root"]:
        root_path = Path(config["files"]["custom_root"])
        if not root_path.is_dir():
            raise FileNotFoundError(f"The specifid root path '{root_path}' is invalid.")
    else:
        root_path = Path.cwd()

    config["files"]["geckodriver_name"] = (
        root_path / config["files"]["geckodriver_name"]
    )
    config["test_load"]["screenshot_name"] = (
        root_path / config["test_load"]["screenshot_name"]
    )
    config["csv_results"]["csv_name"] = root_path / config["csv_results"]["csv_name"]
    config["logging"]["log_name"] = root_path / config["logging"]["log_name"]

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
                    # TODO: refactor out "fa" into config
                    stars = scoring_parent.find_elements(By.CLASS_NAME, "fa")
                    stars[-1].click()

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
    DEFAULT_CONFIG_PATH: Path = Path.cwd() / "config.toml"
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Run speedtest on headless server"
    )
    parser.add_argument(
        "-c",
        "--configpath",
        default=DEFAULT_CONFIG_PATH,
        help="Specify alternative config location",
        dest="CONFIG_PATH",
    )

    parser.add_argument(
        "-r",
        "--repeat-time",
        default=0,
        help="Specify time in minutes between test repeats",
        dest="repeat_time",
        type=float
    )
    args: argparse.Namespace = parser.parse_args()

    # load parsed config
    config: dict = load_config(args)

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

    # run the test and return the completed test instance
    if args.repeat_time == 0:
        main(config)
    else:
        logger.info(f"Starting recurring testing at {args.repeat_time} minute intervals.")
        while True:
            main(config)
            logger.info(f"Sleeping for {args.repeat_time} minutes...")
            time.sleep(args.repeat_time * 60)

    logger.info("Headless speedtest script complete.")
    
