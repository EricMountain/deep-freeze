FROM ubuntu:22.04

# systemd provides systemd-detect-virt
RUN apt update && \
    apt install -y python3 gnupg sqlite3 systemd

WORKDIR /deep-freeze/test
ENV PYTHONPATH=/deep-freeze
ENTRYPOINT ["/deep-freeze/test/run_tests.sh"]
COPY test/mock/aws /usr/local/bin/aws
COPY . /deep-freeze
