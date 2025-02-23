import os
import json
import sqlite3
import requests
import gzip
import zipfile
import shutil
from datetime import datetime
from dotenv import load_dotenv
from tqdm import tqdm
from utils import generate_mot_access_token

# Load environment variables
load_dotenv()

class MOTAPIClient:
    def __init__(self, client_id, client_secret, api_key, token_url, api_url):
        self.client_id = client_id
        self.client_secret = client_secret
        self.api_key = api_key
        self.token_url = token_url
        self.api_url = api_url
        self.access_token = None

    def get_access_token(self):
        try:
            self.access_token = generate_mot_access_token(self.client_id, self.client_secret, self.token_url)
        except requests.exceptions.RequestException as e:
            print(f"Error obtaining access token: {e}")
            raise


    def get_vehicle_info(self, registration):
        if not self.access_token:
            self.get_access_token()

        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'X-API-Key': self.api_key
        }
        response = requests.get(f'{self.api_url}/v1/trade/vehicles/registration/{registration}', headers=headers)
        response.raise_for_status()
        return response.json()

    def download_bulk_data(self):
        if not self.access_token:
            self.get_access_token()

        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'X-API-Key': self.api_key
        }
        response = requests.get(f'{self.api_url}/v1/trade/vehicles/bulk-download', headers=headers)
        response.raise_for_status()
        return response.json()



def normalize_registration(registration):
    return registration.replace(' ', '').upper()

class MOTDatabase:
    def __init__(self, db_name):
        self.conn = sqlite3.connect(db_name)
        self.create_tables()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def create_tables(self):
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS vehicles (
                registration TEXT PRIMARY KEY,
                make TEXT,
                model TEXT,
                first_used_date TEXT,
                fuel_type TEXT,
                primary_colour TEXT,
                registration_date TEXT,
                manufacture_date TEXT,
                engine_size INTEGER,
                mot_data TEXT,
                last_updated TEXT,
                last_checked TEXT,
                has_changes INTEGER
            )
        ''')
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS file_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                registration TEXT,
                file_type TEXT,
                download_url TEXT,
                file_path TEXT
            )
        ''')
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS processed_files (
                file_name TEXT PRIMARY KEY,
                processed_date TEXT
            )
        ''')
        self.conn.commit()

    def save_vehicle_info(self, vehicle_info):
        normalized_reg = normalize_registration(vehicle_info['registration'])
        existing_info = self.get_vehicle_info(normalized_reg)
        has_changes = 1

        if existing_info:
            existing_mot_data = json.loads(existing_info['mot_data'])
            new_mot_data = vehicle_info.get('motTests', [])
            if existing_mot_data == new_mot_data:
                has_changes = 0
                vehicle_info = existing_info  # Keep existing data if no changes

        self.conn.execute('''
            INSERT OR REPLACE INTO vehicles 
            (registration, make, model, first_used_date, fuel_type, primary_colour, 
             registration_date, manufacture_date, engine_size, mot_data, last_updated, last_checked, has_changes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            normalized_reg,
            vehicle_info.get('make'),
            vehicle_info.get('model'),
            vehicle_info.get('firstUsedDate'),
            vehicle_info.get('fuelType'),
            vehicle_info.get('primaryColour'),
            vehicle_info.get('registrationDate'),
            vehicle_info.get('manufactureDate'),
            vehicle_info.get('engineSize'),
            json.dumps(vehicle_info.get('motTests', [])),
            datetime.now().isoformat() if has_changes else existing_info.get('last_updated') if existing_info else None,
            datetime.now().isoformat(),
            has_changes
        ))
        self.conn.commit()
        return has_changes

    def get_vehicle_info(self, registration):
        normalized_reg = normalize_registration(registration)
        cursor = self.conn.execute('''
            SELECT * FROM vehicles WHERE registration = ?
        ''', (normalized_reg,))
        result = cursor.fetchone()
        if result:
            return dict(zip([column[0] for column in cursor.description], result))
        return None

    def save_file_link(self, registration, file_type, download_url, file_path):
        self.conn.execute('''
            INSERT INTO file_links (registration, file_type, download_url, file_path)
            VALUES (?, ?, ?, ?)
        ''', (registration, file_type, download_url, file_path))
        self.conn.commit()

    def mark_file_processed(self, file_name):
        self.conn.execute('''
            INSERT OR REPLACE INTO processed_files (file_name, processed_date)
            VALUES (?, ?)
        ''', (file_name, datetime.now().isoformat()))
        self.conn.commit()

    def is_file_processed(self, file_name):
        cursor = self.conn.execute('''
            SELECT * FROM processed_files WHERE file_name = ?
        ''', (file_name,))
        return cursor.fetchone() is not None

    def close(self):
        self.conn.close()


def extract_zip(zip_path, extract_to):
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)

def process_delta_file(file_path, db):
    with gzip.open(file_path, 'rt') as f:
        for line in f:
            vehicle_info = json.loads(line)
            db.save_vehicle_info(vehicle_info)
    db.mark_file_processed(os.path.basename(file_path))

def download_file(url, file_path, resume=True):
    headers = {}
    mode = 'ab' if resume else 'wb'
    existing_size = 0

    if resume and os.path.exists(file_path):
        existing_size = os.path.getsize(file_path)
        headers['Range'] = f'bytes={existing_size}-'

    response = requests.get(url, headers=headers, stream=True)
    
    if resume and response.status_code == 206:  # Partial Content
        total_size = int(response.headers.get('content-length', 0)) + existing_size
    elif response.status_code == 200:  # OK
        total_size = int(response.headers.get('content-length', 0))
        existing_size = 0  # Reset if server doesn't support resume
    else:
        response.raise_for_status()

    with open(file_path, mode) as file, tqdm(
        desc=file_path,
        initial=existing_size,
        total=total_size,
        unit='iB',
        unit_scale=True,
        unit_divisor=1024,
    ) as progress_bar:
        for data in response.iter_content(chunk_size=8192):
            size = file.write(data)
            progress_bar.update(size)



def print_mot_history(vehicle_info):
    if not vehicle_info:
        print("No vehicle information available.")
        return
    
    print(f"MOT History for {vehicle_info['registration']}:")
    print(f"Make: {vehicle_info['make']}")
    print(f"Model: {vehicle_info['model']}")
    print(f"First used date: {vehicle_info['first_used_date']}")
    print(f"Fuel type: {vehicle_info['fuel_type']}")
    print(f"Color: {vehicle_info['primary_colour']}")
    print("\nMOT Tests:")
    mot_tests = json.loads(vehicle_info['mot_data'])
    for test in mot_tests:
        print(f"  Date: {test['completedDate']}")
        print(f"  Result: {test['testResult']}")
        print(f"  Mileage: {test['odometerValue']} {test['odometerUnit']}")
        print(f"  Expiry Date: {test.get('expiryDate', 'N/A')}")
        if test.get('defects'):
            print("  Defects:")
            for defect in test['defects']:
                print(f"    - {defect['text']}")
        print()


def save_bulk_data(bulk_data, registration, db, bulk_folder_path):
    searches_folder = os.path.join(bulk_folder_path, 'searches')
    os.makedirs(searches_folder, exist_ok=True)
    normalized_reg = normalize_registration(registration)
    reg_folder_path = os.path.join(searches_folder, normalized_reg)
    os.makedirs(reg_folder_path, exist_ok=True)

    # Download bulk file if it doesn't exist or is incomplete
    bulk_file = bulk_data.get('bulk', [{}])[0]
    bulk_filename = bulk_file.get('filename', '').split('/')[-1]
    bulk_file_path = os.path.join(bulk_folder_path, bulk_filename)

    if not os.path.exists(bulk_file_path) or os.path.getsize(bulk_file_path) < bulk_file.get('fileSize', 0):
        print("Downloading or resuming bulk file download...")
        download_file(bulk_file['downloadUrl'], bulk_file_path, resume=True)
        db.save_file_link(normalized_reg, 'bulk', bulk_file['downloadUrl'], bulk_file_path)
    else:
        print("Bulk file already downloaded completely.")

    # Process delta files
    print("Processing delta files...")
    for delta_file in bulk_data.get('delta', []):
        filename = delta_file['filename'].split('/')[-1]
        zip_path = os.path.join(reg_folder_path, filename)
        
        if not db.is_file_processed(filename):
            if not os.path.exists(zip_path) or os.path.getsize(zip_path) < delta_file.get('fileSize', 0):
                download_file(delta_file['downloadUrl'], zip_path, resume=True)
                db.save_file_link(normalized_reg, 'delta', delta_file['downloadUrl'], zip_path)
            
            # Extract the ZIP file
            extract_folder = os.path.join(reg_folder_path, 'temp_extract')
            os.makedirs(extract_folder, exist_ok=True)
            extract_zip(zip_path, extract_folder)
            
            # Process extracted .json.gz files
            for root, dirs, files in os.walk(extract_folder):
                for file in files:
                    if file.endswith('.json.gz'):
                        file_path = os.path.join(root, file)
                        process_delta_file(file_path, db)
            
            # Clean up: remove extracted files
            shutil.rmtree(extract_folder)
            
            db.mark_file_processed(filename)
            print(f"Processed delta file: {filename}")
        else:
            print(f"Delta file {filename} already processed.")

def main(registration, bulk_folder_path):
    try:
        with MOTDatabase('mot_database.sqlite') as db:
            # Initialize API client
            client = MOTAPIClient(
                client_id=os.getenv('MOT_CLIENT_ID'),
                client_secret=os.getenv('MOT_CLIENT_SECRET'),
                api_key=os.getenv('MOT_API_TOKEN'),
                token_url=os.getenv('MOT_TOKEN_URL'),
                api_url=os.getenv('MOT_API_URL')
            )

            # Get vehicle info from API and save/update in database
            api_vehicle_info = client.get_vehicle_info(registration)
            has_changes = db.save_vehicle_info(api_vehicle_info)

            # Download and process bulk data
            print("Fetching bulk data information...")
            bulk_data = client.download_bulk_data()
            save_bulk_data(bulk_data, registration, db, bulk_folder_path)

            # Fetch updated vehicle info from database
            vehicle_info = db.get_vehicle_info(registration)
            if not vehicle_info:
                print(f"Error: Vehicle information not found for registration {registration}")
                print("Normalized registration:", normalize_registration(registration))
                # Debug: print all registrations in the database
                cursor = db.conn.execute("SELECT registration FROM vehicles")
                print("Registrations in database:", [row[0] for row in cursor.fetchall()])
            else:
                if has_changes:
                    print("Vehicle information has been updated.")
                else:
                    print("No changes in vehicle information.")
                print_mot_history(vehicle_info)
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    registration = input("Enter the vehicle registration number: ")
    bulk_folder_path = input("Enter the path for bulk data storage (default: ./data): ") or "./data"
    main(registration, bulk_folder_path)