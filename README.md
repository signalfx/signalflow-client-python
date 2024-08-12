# signalflow-client-python

[![PyPI - Version](https://img.shields.io/pypi/v/signalflow-client-python.svg)](https://pypi.org/project/signalflow-client-python)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/signalflow-client-python.svg)](https://pypi.org/project/signalflow-client-python)

-----

**Table of Contents**

- [Installation](#installation)
- [Run a SignalFlow computation](#run-a-signalflow-computation)
- [License](#license)

## Installation

To install the SignalFlow Python client library, open a terminal and run the
following command:

```console
pip install signalflow-client-python
```

## Run a SignalFlow computation

The following example allows you run a SignalFlow computation from the command
line. For additional examples, see the [examples](./examples) directory.

1. Install the `signalflow-client-python` package:

   ```console
   pip install signalflow-client-python
   ```

2. Create a `.py` file that includes the following content:

```python
#!/usr/bin/env python

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
```

3. Run the Python script, specifying values for the streaming endpoint (optional), the API access token, and the SignalFlow program.

   For example:

   ```console
   python <file-name>.py --stream-endpoint https://stream.us0.signalfx.com <api-token> "data('sf.org.num.orguser').publish()"
   ```

## License

`signalflow-client-python` is distributed under the terms of the [Apache-2.0](https://spdx.org/licenses/Apache-2.0.html) license.
