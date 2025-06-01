#!/bin/bash
export REQUESTS_CA_BUNDLE='./ca.pem'
./venv/bin/python freebox_api.py
