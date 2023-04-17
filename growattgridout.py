
import datetime
from enum import IntEnum
import hashlib
import json
import requests
import warnings
import os
import time
import pandas
from random import randint
import numpy as np
from scipy.optimize import curve_fit
import tinytuya
import time
import json
import argparse



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


def hash_password(password):
    """
    Normal MD5, except add c if a byte of the digest is less than 10.
    """
    password_md5 = hashlib.md5(password.encode('utf-8')).hexdigest()
    for i in range(0, len(password_md5), 2):
        if password_md5[i] == '0':
            password_md5 = password_md5[0:i] + 'c' + password_md5[i + 1:]
    return password_md5

class Timespan(IntEnum):
    hour = 0
    day = 1
    month = 2

class GrowattApi:
    server_url = 'https://server.growatt.com/'
    agent_identifier = "Dalvik/2.1.0 (Linux; U; Android 12; https://github.com/indykoning/PyPi_GrowattServer)"

    def __init__(self, add_random_user_id=False, agent_identifier=None):
        if (agent_identifier != None):
          self.agent_identifier = agent_identifier

        #If a random user id is required, generate a 5 digit number and add it to the user agent
        if (add_random_user_id):
          random_number = ''.join(["{}".format(randint(0,9)) for num in range(0,5)])
          self.agent_identifier += " - " + random_number

        self.session = requests.Session()
        self.session.hooks = {
            'response': lambda response, *args, **kwargs: response.raise_for_status()
        }

        headers = {'User-Agent': self.agent_identifier}
        self.session.headers.update(headers)

    def __get_date_string(self, timespan=None, date=None):
        if timespan is not None:
         assert timespan in Timespan

        if date is None:
          date = datetime.datetime.now()

        date_str=""
        if timespan == Timespan.month:
            date_str = date.strftime('%Y-%m')
        else:
            date_str = date.strftime('%Y-%m-%d')

        return date_str

    def get_url(self, page):
        """
        Simple helper function to get the page url/
        """
        return self.server_url + page

    def login(self, username, password, is_password_hashed=False):
        """
        Log the user in.

        Returns
        'data' -- A List containing Objects containing the folowing
            'plantName' -- Friendly name of the plant
            'plantId'   -- The ID of the plant
        'service'
        'quality'
        'isOpenSmartFamily'
        'totalData' -- An Object
        'success'   -- True or False
        'msg'
        'app_code'
        'user' -- An Object containing a lot of user information
            'uid'
            'userLanguage'
            'inverterGroup' -- A List
            'timeZone' -- A Number
            'lat'
            'lng'
            'dataAcqList' -- A List
            'type'
            'accountName' -- The username
            'password' -- The password hash of the user
            'isValiPhone'
            'kind'
            'mailNotice' -- True or False
            'id'
            'lasLoginIp'
            'lastLoginTime'
            'userDeviceType'
            'phoneNum'
            'approved' -- True or False
            'area' -- Continent of the user
            'smsNotice' -- True or False
            'isAgent'
            'token'
            'nickName'
            'parentUserId'
            'customerCode'
            'country'
            'isPhoneNumReg'
            'createDate'
            'rightlevel'
            'appType'
            'serverUrl'
            'roleId'
            'enabled' -- True or False
            'agentCode'
            'inverterList' -- A list
            'email'
            'company'
            'activeName'
            'codeIndex'
            'appAlias'
            'isBigCustomer'
            'noticeType'
        """
        if not is_password_hashed:
            password = hash_password(password)

        response = self.session.post(self.get_url('newTwoLoginAPI.do'), data={
            'userName': username,
            'password': password
        })
        data = json.loads(response.content.decode('utf-8'))['back']
        if data['success']:
            data.update({
                'userId': data['user']['id'],
                'userLevel': data['user']['rightlevel']
            })
        return data

    def plant_list(self, user_id):
        """
        Get a list of plants connected to this account.
        """
        response = self.session.get(self.get_url('PlantListAPI.do'),
                                    params={'userId': user_id},
                                    allow_redirects=False)

        data = json.loads(response.content.decode('utf-8'))
        return data['back']

    def plant_detail(self, plant_id, timespan, date=None):
        """
        Get plant details for specified timespan.
        """
        date_str = self.__get_date_string(timespan, date)

        response = self.session.get(self.get_url('PlantDetailAPI.do'), params={
            'plantId': plant_id,
            'type': timespan.value,
            'date': date_str
        })
        data = json.loads(response.content.decode('utf-8'))
        return data['back']

    def inverter_data(self, inverter_id, date=None):
        """
        Get inverter data for specified date or today.
        """
        date_str = self.__get_date_string(date=date)
        response = self.session.get(self.get_url('newInverterAPI.do'), params={
            'op': 'getInverterData',
            'id': inverter_id,
            'type': 1,
            'date': date_str
        })
        data = json.loads(response.content.decode('utf-8'))
        return data

    def inverter_detail(self, inverter_id):
        """
        Get "All parameters" from PV inverter.
        """
        response = self.session.get(self.get_url('newInverterAPI.do'), params={
            'op': 'getInverterDetailData',
            'inverterId': inverter_id
        })

        data = json.loads(response.content.decode('utf-8'))
        return data

    def inverter_detail_two(self, inverter_id):
        """
        Get "All parameters" from PV inverter.
        """
        response = self.session.get(self.get_url('newInverterAPI.do'), params={
            'op': 'getInverterDetailData_two',
            'inverterId': inverter_id
        })

        data = json.loads(response.content.decode('utf-8'))
        return data

    def tlx_data(self, tlx_id, date=None):
        """
        Get inverter data for specified date or today.
        """
        date_str = self.__get_date_string(date=date)
        response = self.session.get(self.get_url('newTlxApi.do'), params={
            'op': 'getTlxData',
            'id': tlx_id,
            'type': 1,
            'date': date_str
        })
        data = json.loads(response.content.decode('utf-8'))
        return data

    def tlx_detail(self, tlx_id):
        """
        Get "All parameters" from PV inverter.
        """
        response = self.session.get(self.get_url('newTlxApi.do'), params={
            'op': 'getTlxDetailData',
            'id': tlx_id
        })

        data = json.loads(response.content.decode('utf-8'))
        return data

    def mix_info(self, mix_id, plant_id = None):
        """
        Returns high level values from Mix device

        Keyword arguments:
        mix_id -- The serial number (device_sn) of the inverter
        plant_id -- The ID of the plant (the mobile app uses this but it does not appear to be necessary) (default None)

        Returns:
        'acChargeEnergyToday' -- ??? 2.7
        'acChargeEnergyTotal' -- ??? 25.3
        'acChargePower' -- ??? 0
        'capacity': '45' -- The current remaining capacity of the batteries (same as soc but without the % sign)
        'eBatChargeToday' -- Battery charged today in kWh
        'eBatChargeTotal' -- Battery charged total (all time) in kWh
        'eBatDisChargeToday' -- Battery discharged today in kWh
        'eBatDisChargeTotal' -- Battery discharged total (all time) in kWh
        'epvToday' -- Energy generated from PVs today in kWh
        'epvTotal' -- Energy generated from PVs total (all time) in kWh
        'isCharge'-- ??? 0 - Possible a 0/1 based on whether or not the battery is charging
        'pCharge1' -- ??? 0
        'pDischarge1' -- Battery discharging rate in W
        'soc' -- Statement of charge including % symbol
        'upsPac1' -- ??? 0
        'upsPac2' -- ??? 0
        'upsPac3' -- ??? 0
        'vbat' -- Battery Voltage
        'vbatdsp' -- ??? 51.8
        'vpv1' -- Voltage PV1
        'vpv2' -- Voltage PV2
        """
        request_params={
            'op': 'getMixInfo',
            'mixId': mix_id
        }

        if (plant_id):
          request_params['plantId'] = plant_id

        response = self.session.get(self.get_url('newMixApi.do'), params=request_params)

        data = json.loads(response.content.decode('utf-8'))
        return data['obj']

    def mix_totals(self, mix_id, plant_id):
        """
        Returns "Totals" values from Mix device

        Keyword arguments:
        mix_id -- The serial number (device_sn) of the inverter
        plant_id -- The ID of the plant

        Returns:
        'echargetoday' -- Battery charged today in kWh (same as eBatChargeToday from mix_info)
        'echargetotal' -- Battery charged total (all time) in kWh (same as eBatChargeTotal from mix_info)
        'edischarge1Today' -- Battery discharged today in kWh (same as eBatDisChargeToday from mix_info)
        'edischarge1Total' -- Battery discharged total (all time) in kWh (same as eBatDisChargeTotal from mix_info)
        'elocalLoadToday' -- Load consumption today in kWh
        'elocalLoadTotal' -- Load consumption total (all time) in kWh
        'epvToday' -- Energy generated from PVs today in kWh (same as epvToday from mix_info)
        'epvTotal' -- Energy generated from PVs total (all time) in kWh (same as epvTotal from mix_info)
        'etoGridToday' -- Energy exported to the grid today in kWh
        'etogridTotal' -- Energy exported to the grid total (all time) in kWh
        'photovoltaicRevenueToday' -- Revenue earned from PV today in 'unit' currency
        'photovoltaicRevenueTotal' -- Revenue earned from PV total (all time) in 'unit' currency
        'unit' -- Unit of currency for 'Revenue'
        """
        response = self.session.post(self.get_url('newMixApi.do'), params={
            'op': 'getEnergyOverview',
            'mixId': mix_id,
            'plantId': plant_id
        })

        data = json.loads(response.content.decode('utf-8'))
        return data['obj']

    def mix_system_status(self, mix_id, plant_id):
        """
        Returns current "Status" from Mix device

        Keyword arguments:
        mix_id -- The serial number (device_sn) of the inverter
        plant_id -- The ID of the plant

        Returns:
        'SOC' -- Statement of charge (remaining battery %)
        'chargePower' -- Battery charging rate in kw
        'fAc' -- Frequency (Hz)
        'lost' -- System status e.g. 'mix.status.normal'
        'pLocalLoad' -- Load conumption in kW
        'pPv1' -- PV1 Wattage in W
        'pPv2' -- PV2 Wattage in W
        'pactogrid' -- Export to grid rate in kW
        'pactouser' -- Import from grid rate in kW
        'pdisCharge1' -- Discharging batteries rate in kW
        'pmax' -- ??? 6 ??? PV Maximum kW ??
        'ppv' -- PV combined Wattage in kW
        'priorityChoose' -- Priority setting - 0=Local load
        'status' -- System statue - ENUM - Unknown values
        'unit' -- Unit of measurement e.g. 'kW'
        'upsFac' -- ??? 0
        'upsVac1' -- ??? 0
        'uwSysWorkMode' -- ??? 6
        'vAc1' -- Grid voltage in V
        'vBat' -- Battery voltage in V
        'vPv1' -- PV1 voltage in V
        'vPv2' -- PV2 voltage in V
        'vac1' -- Grid voltage in V (same as vAc1)
        'wBatteryType' -- ??? 1
        """
        response = self.session.post(self.get_url('newMixApi.do'), params={
            'op': 'getSystemStatus_KW',
            'mixId': mix_id,
            'plantId': plant_id
        })

        data = json.loads(response.content.decode('utf-8'))
        return data['obj']

    def mix_detail(self, mix_id, plant_id, timespan=Timespan.hour, date=None):
        """
        Get Mix details for specified timespan

        Keyword arguments:
        mix_id -- The serial number (device_sn) of the inverter
        plant_id -- The ID of the plant
        timespan -- The ENUM value conforming to the time window you want e.g. hours from today, days, or months (Default Timespan.hour)
        date -- The date you are interested in (Default datetime.datetime.now())

        Returns:
        A chartData object where each entry is for a specific 5 minute window e.g. 00:05 and 00:10 respectively (below)
        'chartData': {   '00:05': {   'pacToGrid' -- Export rate to grid in kW
                                      'pacToUser' -- Import rate from grid in kW
                                      'pdischarge' -- Battery discharge in kW
                                      'ppv' -- Solar generation in kW
                                      'sysOut' -- Load consumption in kW
                                  },
                         '00:10': {   'pacToGrid': '0',
                                      'pacToUser': '0.93',
                                      'pdischarge': '0',
                                      'ppv': '0',
                                      'sysOut': '0.93'},
                          ......
                     }
        'eAcCharge' -- Exported to grid in kWh
        'eCharge' -- System production in kWh = Self-consumption + Exported to Grid
        'eChargeToday' -- Load consumption from solar in kWh
        'eChargeToday1' -- Self-consumption in kWh
        'eChargeToday2' -- Self-consumption in kWh (eChargeToday + echarge1)
        'echarge1' -- Load consumption from battery in kWh
        'echargeToat' -- Total battery discharged (all time) in kWh
        'elocalLoad' -- Load consumption in kW (battery + solar + imported)
        'etouser' -- Load consumption imported from grid in kWh
        'photovoltaic' -- Load consumption from solar in kWh (same as eChargeToday)
        'ratio1' -- % of system production that is self-consumed
        'ratio2' -- % of system production that is exported
        'ratio3' -- % of Load consumption that is "self consumption"
        'ratio4' -- % of Load consumption that is "imported from grid"
        'ratio5' -- % of Self consumption that is directly from Solar
        'ratio6' -- % of Self consumption that is from batteries
        'unit' -- Unit of measurement e.g kWh
        'unit2' -- Unit of measurement e.g kW


        NOTE - It is possible to calculate the PV generation that went into charging the batteries by performing the following calculation:
        Solar to Battery = Solar Generation - Export to Grid - Load consumption from solar
                           epvToday (from mix_info) - eAcCharge - eChargeToday
        """
        date_str = self.__get_date_string(timespan, date)

        response = self.session.post(self.get_url('newMixApi.do'), params={
            'op': 'getEnergyProdAndCons_KW',
            'plantId': plant_id,
            'mixId': mix_id,
            'type': timespan.value,
            'date': date_str
        })
        data = json.loads(response.content.decode('utf-8'))

        return data['obj']

    def dashboard_data(self, plant_id, timespan=Timespan.hour, date=None):
        """
        Get 'dashboard' data for specified timespan
        NOTE - All numerical values returned by this api call include units e.g. kWh or %
             - Many of the 'total' values that are returned for a Mix system are inaccurate on the system this was tested against.
               However, the statistics that are correct are not available on any other interface, plus these values may be accurate for
               non-mix types of system. Where the values have been proven to be inaccurate they are commented below.

        Keyword arguments:
        plant_id -- The ID of the plant
        timespan -- The ENUM value conforming to the time window you want e.g. hours from today, days, or months (Default Timespan.hour)
        date -- The date you are interested in (Default datetime.datetime.now())

        Returns:
        A chartData object where each entry is for a specific 5 minute window e.g. 00:05 and 00:10 respectively (below)
        NOTE: The keys are interpreted differently, the examples below describe what they are used for in a 'Mix' system
        'chartData': {   '00:05': {   'pacToUser' -- Power from battery in kW
                                      'ppv' -- Solar generation in kW
                                      'sysOut' -- Load consumption in kW
                                      'userLoad' -- Export in kW
                                  },
                         '00:10': {   'pacToUser': '0',
                                      'ppv': '0',
                                      'sysOut': '0.7',
                                      'userLoad': '0'},
                          ......
                     }
        'chartDataUnit' -- Unit of measurement e.g. 'kW',
        'eAcCharge' -- Energy exported to the grid in kWh e.g. '20.5kWh' (not accurate for Mix systems)
        'eCharge' -- System production in kWh = Self-consumption + Exported to Grid e.g '23.1kWh' (not accurate for Mix systems - actually showing the total 'load consumption'
        'eChargeToday1' -- Self-consumption of PPV (possibly including excess diverted to batteries) in kWh e.g. '2.6kWh' (not accurate for Mix systems)
        'eChargeToday2' -- Total self-consumption (PPV consumption(eChargeToday2Echarge1) + Battery Consumption(echarge1)) e.g. '10.1kWh' (not accurate for Mix systems)
        'eChargeToday2Echarge1' -- Self-consumption of PPV only e.g. '0.8kWh' (not accurate for Mix systems)
        'echarge1' -- Self-consumption from Battery only e.g. '9.3kWh'
        'echargeToat' -- Not used on Dashboard view, likely to be total battery discharged e.g. '152.1kWh'
        'elocalLoad' -- Total load consumption (etouser + eChargeToday2) e.g. '20.3kWh', (not accurate for Mix systems)
        'etouser'-- Energy imported from grid today (includes both directly used by load and AC battery charging e.g. '10.2kWh'
        'keyNames' -- Keys to be used for the graph data e.g. ['Solar', 'Load Consumption', 'Export To Grid', 'From Battery']
        'photovoltaic' -- Same as eChargeToday2Echarge1 e.g. '0.8kWh'
        'ratio1' -- % of 'Solar production' that is self-consumed e.g. '11.3%' (not accurate for Mix systems)
        'ratio2' -- % of 'Solar production' that is exported e.g. '88.7%' (not accurate for Mix systems)
        'ratio3' -- % of 'Load consumption' that is self consumption e.g. '49.8%' (not accurate for Mix systems)
        'ratio4' -- % of 'Load consumption' that is imported from the grid e.g '50.2%' (not accurate for Mix systems)
        'ratio5' -- % of Self consumption that is from batteries e.g. '92.1%' (not accurate for Mix systems)
        'ratio6' -- % of Self consumption that is directly from Solar e.g. '7.9%' (not accurate for Mix systems)
        """
        date_str = self.__get_date_string(timespan, date)

        response = self.session.post(self.get_url('newPlantAPI.do'), params={
            'action': "getEnergyStorageData",
            'date': date_str,
            'type': timespan.value,
            'plantId': plant_id
        })

        data = json.loads(response.content.decode('utf-8'))
        return data

    def storage_detail(self, storage_id):
        """
        Get "All parameters" from battery storage.
        """
        response = self.session.get(self.get_url('newStorageAPI.do'), params={
            'op': 'getStorageInfo_sacolar',
            'storageId': storage_id
        })

        data = json.loads(response.content.decode('utf-8'))
        return data

    def storage_params(self, storage_id):
        """
        Get much more detail from battery storage.
        """
        response = self.session.get(self.get_url('newStorageAPI.do'), params={
            'op': 'getStorageParams_sacolar',
            'storageId': storage_id
        })

        data = json.loads(response.content.decode('utf-8'))
        return data

    def storage_energy_overview(self, plant_id, storage_id):
        """
        Get some energy/generation overview data.
        """
        response = self.session.post(self.get_url('newStorageAPI.do?op=getEnergyOverviewData_sacolar'), params={
            'plantId': plant_id,
            'storageSn': storage_id
        })

        data = json.loads(response.content.decode('utf-8'))
        return data['obj']

    def inverter_list(self, plant_id):
        """
        Use device_list, it's more descriptive since the list contains more than inverters.
        """
        warnings.warn("This function may be deprecated in the future because naming is not correct, use device_list instead", DeprecationWarning)
        return self.device_list(plant_id)

    def device_list(self, plant_id):
        """
        Get a list of all devices connected to plant.
        """
        return self.plant_info(plant_id)['deviceList']

    def plant_info(self, plant_id):
        """
        Get basic plant information with device list.
        """
        response = self.session.get(self.get_url('newTwoPlantAPI.do'), params={
            'op': 'getAllDeviceList',
            'plantId': plant_id,
            'pageNum': 1,
            'pageSize': 1
        })

        data = json.loads(response.content.decode('utf-8'))
        return data

    def get_plant_settings(self, plant_id):
        """
        Returns a dictionary containing the settings for the specified plant

        Keyword arguments:
        plant_id -- The id of the plant you want the settings of

        Returns:
        A python dictionary containing the settings for the specified plant
        """
        response = self.session.get(self.get_url('newPlantAPI.do'), params={
            'op': 'getPlant',
            'plantId': plant_id
        })
        data = json.loads(response.content.decode('utf-8'))
        return data




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
power_values = [0, 0]

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
        power_values.append(overproduction)

        # Predict the next value using power_values
        predicted = predict_next_value_sin(power_values)

        # Remove the oldest value from power_values if there are more than 14 values
        if len(power_values) > 14:
            power_values.pop(0)

        # If predicted overproduction or overproduction is high, turn on the device and set performance settings
        if predicted > 0.35 or overproduction > 0.5 and not overproduction < 0.2:
            os.system('undervolt --gpu -20 --core -15 --cache -15 --uncore -15 --analogio -15 --temp 95')
            os.system('cpupower frequency-set --governor performance > /dev/null')

            if predicted > 0.5 and not turned_on:
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

            if (predicted < 0.2 or overproduction < 0.2) and turned_on:
                # Turn off the device and handle any errors
                ret = device.turn_off()
                if "Error" in ret:
                    device = tinytuya.OutletDevice(device_id, ip_address, local_key)
                    device.set_version(3.3)
                    device.turn_off()
                    print("     ERROR", ret)
                turned_on = False

        # Print the current time, overproduction, predicted value, power_values, and any device status messages
        print(datetime.datetime.now(), mixinfo["pactogrid"], predicted, power_values, ret)

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
    time.sleep(5*60)

