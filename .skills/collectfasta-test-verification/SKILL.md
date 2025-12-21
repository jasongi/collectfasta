---
name: collectfasta-test-verification
description: Verify Collectfasta changes by running the project test commands defined in the Makefile. Use when asked to run or verify tests, or just generally when making changes.
---

# Collectfasta Test Verification

## Choose the right test target

- Read `Makefile` to find the appropriate test target.
- Since you don't have credentials, only use the docker tests
- Default to `make test-docker` for a standard run.
- If you want to test performance, run `make test-speed` - otherwise, avoid this, it is slower
- If you want to investigate an error, run `make test-docker-ff` - it is fast-fail and verbose logging 

## Run and report

- Run the selected `make` target.
- If a command times out or fails, report the partial output and the exit status.
- Suggest a narrower target if the default run is too slow.
