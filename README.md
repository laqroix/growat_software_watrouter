# growatt software watrouter
This script uses the tinytuya library to turn off a device, retrieves current overproduction from a Growatt inverter and predicts the next power value. The prediction is made by fitting a sine curve to the input values and evaluating the sine curve at the next point. If there are less than two input values, a ValueError will be raised.
Prerequisites

- To run this script, you need to have the following libraries installed:
```
    numpy
    scipy
    pandas
    tinytuya
    requests
    argparse
```
- You also need to have a valid account on the Growatt server, and have obtained your username, password, mixsn, device_id, local_key, and ip_address.
Usage

- Run the script in a Python environment, passing a path to a configuration file using the -c or --config argument.


python3 growattgridout.py -c ./config.json

The configuration file should contain the following fields:

```json

{
    "username": "your Growatt username",
    "password": "your Growatt password",
    "mixsn": "your Mixinverter serial number",
    "device_id": "your Tuya device ID",
    "local_key": "your Tuya device local key",
    "ip_address": "your Tuya device IP address"
}
```
License

This project is licensed under the MIT License - see the LICENSE file for details.
