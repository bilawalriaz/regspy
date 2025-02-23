import requests
import os
from dotenv import load_dotenv
from utils import generate_mot_access_token

load_dotenv()

VES_API_URL = 'https://driver-vehicle-licensing.api.gov.uk/vehicle-enquiry/v1/vehicles'
VES_API_KEY = os.getenv('VES_API_KEY')
MOT_API_URL = os.getenv('MOT_API_URL')
MOT_CLIENT_ID = os.getenv('MOT_CLIENT_ID')
MOT_CLIENT_SECRET = os.getenv('MOT_CLIENT_SECRET')
MOT_API_KEY = os.getenv('MOT_API_TOKEN')

class VehicleAPIError(Exception):
    def __init__(self, message, status_code):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

def get_mot_access_token():
    token_url = os.getenv('MOT_TOKEN_URL')
    return generate_mot_access_token(MOT_CLIENT_ID, MOT_CLIENT_SECRET, token_url)

def get_vehicle_data(registration_number):
    # VES API Call
    ves_headers = {
        'x-api-key': VES_API_KEY,
        'Content-Type': 'application/json'
    }
    ves_data = {'registrationNumber': registration_number}
    
    ves_response = requests.post(VES_API_URL, headers=ves_headers, json=ves_data)
    
    if ves_response.status_code != 200:
        if ves_response.status_code == 404:
            raise VehicleAPIError("Vehicle not found", 404)
        elif ves_response.status_code == 400:
            raise VehicleAPIError("Invalid registration number", 400)
        else:
            raise VehicleAPIError(f"Error fetching vehicle data from VES API: {ves_response.status_code}", ves_response.status_code)
    
    ves_data = ves_response.json()

    # MOT API Call
    mot_access_token = get_mot_access_token()
    mot_headers = {
        'Authorization': f'Bearer {mot_access_token}',
        'X-API-Key': MOT_API_KEY
    }
    mot_response = requests.get(f'{MOT_API_URL}/v1/trade/vehicles/registration/{registration_number}', headers=mot_headers)
    
    if mot_response.status_code != 200:
        print(f"Warning: Failed to fetch MOT data. Status code: {mot_response.status_code}")
        mot_data = {}
    else:
        mot_data = mot_response.json()

    # Merge VES and MOT data
    combined_data = {**ves_data, **mot_data}
    
    # Ensure 'motTests' key exists
    if 'motTests' not in combined_data:
        combined_data['motTests'] = []

    return combined_data
