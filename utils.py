import os
import requests
from dotenv import load_dotenv

load_dotenv()

def generate_mot_access_token(client_id, client_secret, token_url):
    """Centralized function to get MOT API access token"""
    data = {
        'grant_type': 'client_credentials',
        'client_id': client_id,
        'client_secret': client_secret,
        'scope': 'https://tapi.dvsa.gov.uk/.default'
    }
    response = requests.post(token_url, data=data)
    response.raise_for_status()
    return response.json()['access_token']

def normalize_vehicle_data(data):
    """Centralized function to normalize vehicle data"""
    return {
        'co2_emissions': data.get('co2Emissions') or data.get('co2_emissions'),
        'engine_size': data.get('engineCapacity') or data.get('engine_size'),
        'first_used_date': data.get('firstUsedDate') or data.get('first_used_date'),
        'fuel_type': data.get('fuelType') or data.get('fuel_type'),
        'make': data.get('make'),
        'manufacture_date': data.get('manufactureDate') or data.get('manufacture_date'),
        'model': data.get('model'),
        'mot_expiry_date': data.get('motExpiryDate') or data.get('mot_expiry_date'),
        'mot_status': data.get('motStatus') or data.get('mot_status'),
        'primary_colour': data.get('primaryColour') or data.get('primary_colour'),
        'registration_date': data.get('registrationDate') or data.get('registration_date'),
        'registration_number': data.get('registration_number'),
        'tax_due_date': data.get('taxDueDate') or data.get('tax_due_date'),
        'tax_status': data.get('taxStatus') or data.get('tax_status'),
        'year_of_manufacture': data.get('yearOfManufacture') or data.get('year_of_manufacture'),
        'motTests': data.get('motTests'),
        'request_count': data.get('request_count')
    }
