import datetime
from enum import IntEnum
import hashlib
import json
import requests
import warnings
import os
import time
from random import randint
import numpy as np
from scipy.optimize import curve_fit
import tinytuya
import time
import json
import argparse

from growattlib import *



def sin_fit(x, a, b, c, d):
    return a * np.sin(b * x + c) + d

def predict_next_value_sin(values):
    try:
        # Normalize the input values
        y = (values - np.min(values)) / (np.max(values) - np.min(values))

        # Generate x values
        x = np.linspace(0, 1, len(values))

        # Fit a sine curve to the normalized data
        popt, _ = curve_fit(sin_fit, x, y, p0=[1, 2 * np.pi, 0, 0.5])

        # Evaluate the sine curve at the next x value
        x_next = (len(values) + 1) / len(values)
        y_next = sin_fit(x_next, *popt)

        # Rescale the predicted value to the range of the input data
        y_next = y_next * (np.max(values) - np.min(values)) + np.min(values)
    except:
        y_next = values[-1]
    return y_next

def predict_next_value(input_values):
    # Check if there are at least two input values
    if len(input_values) < 2:
        raise ValueError('At least two input values are required')
    # Create a numpy array of the input values
    x = np.array(input_values)
    # Create a numpy array of the indices
    t = np.arange(len(input_values))
    # Fit a polynomial function to the input data
    coeffs = np.polyfit(t, x, deg=len(input_values)-1)
    # Predict the next value using the polynomial function
    return np.polyval(coeffs, len(input_values))




parser = argparse.ArgumentParser()
parser.add_argument("-c", "--config", help="path to config file")
args = parser.parse_args()
name = "growattServer"

if args.config:
    with open(args.config) as f:
        config = json.load(f)
        username = config['username']
        password = config['password']
        mixsn = config['mixsn']
        device_id = config['device_id']
        local_key = config['local_key']
        ip_address = config['ip_address']

# Initialize power values
power_values = []

# Create a Growatt API instance and log in
api = GrowattApi()
login_response = api.login(username, password)
print(login_response)

# Turn off the device
turned_on = False
device = tinytuya.OutletDevice(device_id, ip_address, local_key)
device.set_version(3.3)
print(device.turn_off())

# Continuously loop
while True:
    try:
        ret = ''

        # Get plant information and ID
        plant_info = api.plant_list(login_response['user']['id'])
        plant_id = plant_info["data"][0]["plantId"]

        # Get mix system status
        mixinfo = api.mix_system_status(mixsn, plant_id)

        # Get current overproduction and add it to power_values
        overproduction = float(mixinfo["pactogrid"])
        chargepower = float(mixinfo["chargePower"])
        chargelevel = float(mixinfo["SOC"])

        power_values.append(overproduction)

        # Predict the next value using power_values
        predicted = predict_next_value_sin(power_values) if len(power_values) > 5 else 0

        # Remove the oldest value from power_values if there are more than 14 values
        if len(power_values) > 14:
            power_values.pop(0)

        # If predicted overproduction or overproduction is high, turn on the device and set performance settings
        if (predicted > 0.5 or overproduction > 0.5 or (chargelevel > 65 and chargepower > .5)):
            os.system('undervolt --gpu -20 --core -15 --cache -15 --uncore -15 --analogio -15 --temp 95')
            os.system('cpupower frequency-set --governor performance > /dev/null')

            if not turned_on and (predicted > 0.5 or chargepower > 3.5 or (chargelevel > 85 and chargepower > .75)):
                # Turn on the device and handle any errors
                ret = device.turn_on()
                if "Error" in ret:
                    device = tinytuya.OutletDevice(device_id, ip_address, local_key)
                    device.set_version(3.3)
                    device.turn_on()
                    print("     ERROR", ret)
                turned_on = True

        # If predicted overproduction or overproduction is low, turn off the device and set power saving settings
        else:
            os.system('undervolt --gpu -20 --core -15 --cache -15 --uncore -15 --analogio -15 --temp 70')
            os.system('cpupower frequency-set --governor powersave > /dev/null')

            if turned_on and (predicted < 0.3 or overproduction < 0.4 or (chargelevel < 90 and chargepower < 1.75)):
                # Turn off the device and handle any errors
                ret = device.turn_off()
                if "Error" in ret:
                    device = tinytuya.OutletDevice(device_id, ip_address, local_key)
                    device.set_version(3.3)
                    device.turn_off()
                    print("     ERROR", ret)
                turned_on = False

        # Print the current time, overproduction, predicted value, power_values, and any device status messages
        print(datetime.datetime.now(), "to grid:", overproduction, "charging power:", chargepower, "predicted:", round(predicted, 3), "battery level:", chargelevel, "power history:", power_values, ret)

    # If an error occurs, wait 5 minutes and try again
    except Exception as e:
        print(datetime.datetime.now(), "Error", e)
        time.sleep(5*60)
        try:
            api = GrowattApi()
            login_response = api.login(username, password)
            print(login_response)
        except Exception as e:
            pass
        pass

    # Wait 5 minutes before the next iteration
    time.sleep(5*60 -1)

