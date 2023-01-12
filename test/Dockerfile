FROM ubuntu:22.04

RUN apt update && \
    apt install -y python3 gnupg

COPY .. /deep-freeze

WORKDIR /deep-freeze/test
ENV PYTHONPATH=/deep-freeze
ENTRYPOINT ["/deep-freeze/test/run_tests.sh"]
