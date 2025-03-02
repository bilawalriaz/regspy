from quart import Quart, request, jsonify
from quart_cors import cors
from database import (get_db, cache_vehicle_data, get_cached_vehicle_data, get_historical_data, 
                      log_request, check_cache_exists, get_request_count,
                      update_vehicle_model)
from vehicle_api import get_vehicle_data, VehicleAPIError
from rate_limiter import rate_limit
from utils import normalize_vehicle_data
import time
from concurrent.futures import ThreadPoolExecutor


app = Quart(__name__)
app = cors(app, allow_origin=["https://regspy.uk"])

executor = ThreadPoolExecutor(max_workers=1)



@app.route('/vehicle', methods=['POST'])
@rate_limit
async def vehicle():
    start_time = time.time()
    data = await request.get_json()
    reg = data['reg'].replace(' ', '')
    if not reg:
        return jsonify({"error": "Registration number is required"}), 400

    request_data = {
        'cf_connecting_ip': request.headers.get('CF-Connecting-IP', request.remote_addr),
        'user_agent': request.headers.get('User-Agent'),
        'referrer': request.headers.get('Referer'),
        'cf_country': request.headers.get('CF-IPCountry'),
        'cf_region': request.headers.get('CF-Region'),
        'cf_city': request.headers.get('CF-City'),
        'cf_timezone': request.headers.get('CF-Timezone'),
        'cf_isp': request.headers.get('CF-ISP'),
        'local_timezone': data.get('timezone', 'Unknown'),
        'headers': {key: value for key, value in request.headers.items()}
    }

    with get_db() as db:
        try:
            is_cached = check_cache_exists(db, reg)
            cached_data = get_cached_vehicle_data(db, reg) if is_cached else None
            
            if cached_data is not None:
                print(f"Using cached data for: {reg}")
                query_time = time.time() - start_time
                log_request(db, reg, request_data, query_time, is_cached=True)
                request_count = get_request_count(db, reg)
                normalized_data = normalize_vehicle_data(cached_data)
                normalized_data['request_count'] = request_count
                
                return jsonify(normalized_data)
            
            print(f"Fetching fresh data for: {reg}")
            fresh_data = get_vehicle_data(reg)
            cache_vehicle_data(db, reg, fresh_data)
            query_time = time.time() - start_time
            log_request(db, reg, request_data, query_time, is_cached=is_cached)
            request_count = get_request_count(db, reg)
            normalized_data = normalize_vehicle_data(fresh_data)
            normalized_data['request_count'] = request_count
            
            return jsonify(normalized_data)
        except VehicleAPIError as e:
            query_time = time.time() - start_time
            log_request(db, reg, request_data, query_time, is_cached=is_cached)
            return jsonify({"error": str(e)}), e.status_code
        except Exception as e:
            print(f"Unexpected error: {str(e)}")
            query_time = time.time() - start_time
            log_request(db, reg, request_data, query_time, is_cached=is_cached)
            return jsonify({"error": "An unexpected error occurred"}), 500



@app.errorhandler(VehicleAPIError)
async def handle_vehicle_api_error(error):
    return jsonify({"error": str(error)}), error.status_code




if __name__ == '__main__':
    app.run(debug=True, host="127.0.0.1", port=5678)
