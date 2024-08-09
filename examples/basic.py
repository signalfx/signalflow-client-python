#!/usr/bin/env python

# Copyright (C) 2017 SignalFx, Inc. All rights reserved.
#
# A simple example showing how to execute a SignalFx SignalFlow computation
# from Python and dump its data, metadata and event output to the console.

import argparse

from signalfx.signalflow import SignalFlowClient


def main():
    parser = argparse.ArgumentParser(
        description="SignalFx SignalFlow streaming analytics demo"
    )
    parser.add_argument(
        "--stream-endpoint",
        help="SignalFx SignalFlow stream API endpoint",
        default="https://stream.signalfx.com",
    )
    parser.add_argument("token", help="Your SignalFx API access token")
    parser.add_argument("program", help="SignalFlow program to execute")
    options = parser.parse_args()
    client = SignalFlowClient(
        token=options.token,
        endpoint=options.stream_endpoint,
    )
    try:
        # Execute the computation and iterate over the message stream
        print("Requesting computation: {0}".format(options.program))
        c = client.execute(options.program)
        print("Waiting for data...")
        for msg in c.stream():
            print(f"Message: {msg}")
    except KeyboardInterrupt:
        print("Detaching from computation...")
    finally:
        client.close()
    print("Done.")


if __name__ == "__main__":
    main()
