#!/usr/bin/env bash

set -euo pipefail
set -x

docker build -t deep-freeze-test:0.1 .. -f Dockerfile

docker run --rm -t deep-freeze-test:0.1
