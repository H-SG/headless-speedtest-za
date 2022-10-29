# Quick and Dirty Headless Speedtest Scraper
This was quickly thrown together to scrape results from www.speedtest.co.za in a manner which could be automated, such as via cronjob.

By default the script writes ping, upload, and download speeds to a csv file, but can also be written to influxDB if you want to graph it on something like Grafana. Just update the relevant config line in the Python file.

There are also configurable thresholds and a probability which controls whether or not the speedtest is scored. Results will either be scored 5/5 or not at all depending on the thresholds and chance.

> **Warning**
> www.speedtest.co.za will likely not enjoy abuse of this script

Only requirements are selenium, Firefox, and the Firefox webdriver, Gecko.
- If using poetry
    - `poetry shell`
    - `poetry install`
- If using pip, create your enviroment
    - `pip install selenium influxdb-client`
- `sudo apt install firefox`
    - The snap version of firefox is not currently working, will be testing a potential workaround soonish
- wget the latest gecko driver here https://github.com/mozilla/geckodriver/releases
    - `tar -xzvf geckodriver-<release>.tar.gz`

>**Note**
> Python 3.9 or newer is required to run the script, older versions will work if you strip out type hints

## How it works
Selenium is a tool used mostly in automated testing of web applications. In this case we are using it with a headless instance of Firefox to automatically run the speedtest, wait for it to complete, give a rating, and safe the results (if so desired). Firefox is used since it's the most lightweight apt install in my opinion for a headless server.

There are three core parameters to the script which describes how the speedtest is done:
- `speedtest_url` - where is the speedtest page you want to run against
- `start_element` - what element (as identiefied by the ID parameter) on the page must be pressed to start the test
- `test_completion_element` - what element (as identified by the ID parameter) on the page becomes visible once the test is complete

While this is somewhat general, the code is made specifically for www.speedtest.co.za as of 2022/10/29.

## Example cron setup
TBD