# Quick and Dirty Headless Speedtest Scraper
This was quickly thrown together to scrape results from `www.speedtest.co.za` in a manner which could be automated.

> **⚠ Warning**
> www.speedtest.co.za will likely not enjoy abuse of this script

Only requirements are selenium, Firefox, and the Firefox webdriver, Gecko.
- `<your package manager of choice> install selenium`
- `sudo apt install firefox`
- wget the latest gecko driver here https://github.com/mozilla/geckodriver/releases
    - `tar -xzvf geckodriver-<release>.tar.gz`

Results are currently thrown in to a text file, up to you what to do with it