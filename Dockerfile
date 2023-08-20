# https://hub.docker.com/_/debian
FROM python:3.11.2-slim-bullseye

# ARG firefox_ver=110.0.1
ARG geckodriver_ver=0.33.0
ARG build_rev=0

# do all the firefox and util installs
RUN apt-get update
RUN apt-get upgrade -y
RUN apt-get install -y --no-install-recommends --no-install-suggests ca-certificates 
RUN apt-get install -y git
RUN update-ca-certificates
RUN apt-get install -y --no-install-recommends --no-install-suggests curl bzip2 rsyslog
RUN apt-get install -y --no-install-recommends --no-install-suggests firefox-esr

# install python packages
RUN pip install selenium influxdb-client
WORKDIR /app

# get geckodriver
RUN curl -fL -o /tmp/geckodriver.tar.gz \
    https://github.com/mozilla/geckodriver/releases/download/v${geckodriver_ver}/geckodriver-v${geckodriver_ver}-linux64.tar.gz
RUN tar -xzf /tmp/geckodriver.tar.gz -C /app
RUN chmod +x geckodriver

# copy our script
RUN git clone https://github.com/H-SG/headless-speedtest-za.git /app/repo
RUN mv /app/repo/* /app

ENTRYPOINT [ "python", "headless-speedtest.py"]