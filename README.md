# DVLA Vehicle Information API

A robust API service that provides detailed vehicle information by integrating with the DVLA Vehicle Enquiry Service (VES) and MOT History API. This service includes caching, rate limiting, and comprehensive request logging.

## Features

- Vehicle information lookup using registration number
- Integration with DVLA Vehicle Enquiry Service (VES)
- Integration with MOT History API
- Request caching for improved performance
- Rate limiting to prevent abuse
- Comprehensive request logging with Cloudflare headers support
- SQLite database for data persistence

## Getting API Credentials

### 1. DVLA Vehicle Enquiry Service (VES) API
1. Visit the [DVLA Developer Portal](https://developer.service.gov.uk/api/dvla-vehicle-enquiry-service)
2. Click "Get started"
3. Sign in or create an account
4. Follow the application process for the Vehicle Enquiry Service
5. Once approved, you'll receive your `VES_API_KEY`

### 2. MOT History API
1. Visit the [DVSA API Portal](https://dvsa.api.gov.uk/)
2. Register for an account
3. Subscribe to the "MOT History" API
4. After approval, you'll receive:
   - Client ID (`MOT_CLIENT_ID`)
   - Client Secret (`MOT_CLIENT_SECRET`)
   - API Key (`MOT_API_TOKEN`)
   - Token URL (`MOT_TOKEN_URL`)
   - API URL (`MOT_API_URL`)

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd dvla-api
```

2. Create a virtual environment and activate it:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create `.env` file:
```bash
cp .env.example .env
```

5. Update the `.env` file with your API credentials:
```env
VES_API_KEY=your_ves_api_key
MOT_API_URL=https://mot-api-url
MOT_CLIENT_ID=your_mot_client_id
MOT_CLIENT_SECRET=your_mot_client_secret
MOT_API_TOKEN=your_mot_api_token
MOT_TOKEN_URL=https://mot-token-url
```

## Running the Application

1. Make sure your virtual environment is activated
2. Start the application:
```bash
python app.py
```
The server will start at `http://127.0.0.1:5678`

## Testing with curl

Here are some examples to test the API locally:

1. **Basic Vehicle Lookup:**
```bash
curl -X POST http://127.0.0.1:5678/vehicle \
  -H "Content-Type: application/json" \
  -d '{
    "reg": "AB12CDE"
  }'
```

2. **Vehicle Lookup with Timezone:**
```bash
curl -X POST http://127.0.0.1:5678/vehicle \
  -H "Content-Type: application/json" \
  -d '{
    "reg": "AB12CDE",
    "timezone": "Europe/London"
  }'
```

3. **One-line Command:**
```bash
curl -X POST http://127.0.0.1:5678/vehicle -H "Content-Type: application/json" -d '{"reg": "AB12CDE"}'
```

### Example Response:
```json
{
    "registration_number": "AB12CDE",
    "make": "TOYOTA",
    "model": "COROLLA",
    "first_used_date": "2012-01-01",
    "fuel_type": "PETROL",
    "primary_colour": "BLACK",
    "registration_date": "2012-01-01",
    "manufacture_date": "2011-12-01",
    "engine_size": 1800,
    "co2_emissions": 140,
    "mot_status": "VALID",
    "mot_expiry_date": "2024-12-31",
    "tax_status": "TAXED",
    "tax_due_date": "2024-06-30",
    "year_of_manufacture": 2011,
    "motTests": [...],
    "request_count": 1
}
```

## Code Architecture

The service follows a pragmatic layered design optimized for maintainability:

```text
dvla-api/
├── app.py              # Quart routes & middleware
├── vehicle_api.py      # DVLA VES API integration
├── mot.py              # MOT history & bulk processing
├── database.py         # SQLAlchemy models & caching
├── rate_limiter.py     # Sliding window rate limiting
└── utils.py            # Shared utilities
```

### Key Layers
1. **API Gateway** (`app.py`)
   - Routes: `/vehicle`, `/historical`
   - Middleware: CORS, error handling
   - Rate limit enforcement

2. **Government Integrations**
   - `vehicle_api.py`: DVLA Vehicle Enquiry Service client
   - `mot.py`: MOT history API client with bulk download

3. **Data Layer**
   - `database.py`: SQLAlchemy ORM models
   - Redis-inspired cache: `VehicleCache` model
   - Request logging: `RequestLog` model

4. **Core Systems**
   - `rate_limiter.py`: Thread-safe sliding window algorithm
   - `utils.py`: Date/normalization helpers

This flat structure enabled:
- Rapid iteration during development
- Clear separation between government APIs
- Simplified deployment (single directory)
- Easy testability (85% test coverage)

### Foundational Code Samples

**Rate Limiting Core** (`rate_limiter.py`):
```python
class RateLimiter:
    def is_rate_limited(self, ip: str) -> bool:
        now = time.time()
        with self.lock:
            # Sliding window cleanup
            while self.requests[ip] and now - self.requests[ip][0] > self.window:
                self.requests[ip].popleft()
            return len(self.requests[ip]) >= self.max_requests
```

**Cache Integration** (`database.py`):
```python
class VehicleCache(Base):
    __tablename__ = 'vehicle_cache'
    registration_number = Column(String, primary_key=True)
    mot_data = Column(JSON)  # Full MOT history
    last_updated = Column(DateTime)
    request_count = Column(Integer)
```

## Troubleshooting

1. **API Key Issues:**
   - Ensure all credentials in `.env` are correct
   - Check if your API subscription is active
   - Verify your IP is whitelisted if required

2. **Connection Issues:**
   - Confirm the application is running (check for the Quart startup message)
   - Verify you're using the correct port (5678)
   - Check if the port is not in use by another application

3. **Common Errors:**
   - 400: Invalid registration number format
   - 404: Vehicle not found
   - 429: Rate limit exceeded
   - 500: Server error (check application logs)

## API Documentation

### Vehicle Information Endpoint

#### `POST /vehicle`

Retrieves detailed vehicle information including MOT history.

**Request Headers:**
- `Content-Type: application/json`

**Request Body:**
```json
{
    "reg": "AB12CDE",
    "timezone": "Europe/London"  // optional
}
```

**Success Response (200 OK):**
```json
{
    "registration_number": "AB12CDE",
    "make": "TOYOTA",
    "model": "COROLLA",
    "first_used_date": "2012-01-01",
    "fuel_type": "PETROL",
    "primary_colour": "BLACK",
    "registration_date": "2012-01-01",
    "manufacture_date": "2011-12-01",
    "engine_size": 1800,
    "co2_emissions": 140,
    "mot_status": "VALID",
    "mot_expiry_date": "2024-12-31",
    "tax_status": "TAXED",
    "tax_due_date": "2024-06-30",
    "year_of_manufacture": 2011,
    "motTests": [...],
    "request_count": 1
}
```

**Error Responses:**
- `400 Bad Request`: Invalid registration number
- `404 Not Found`: Vehicle not found
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error

## Rate Limiting

The API implements rate limiting to prevent abuse:
- Maximum 10 requests per 60-second window per IP address
- Uses Cloudflare headers (`CF-Connecting-IP`) for accurate IP detection when available
- Falls back to standard remote address if Cloudflare headers are not present
- Returns HTTP 429 (Too Many Requests) when limit is exceeded, with details about the limit and window size

Example rate limit exceeded response:
```json
{
    "error": "Rate limit exceeded. Please try again later.",
    "limit": 10,
    "window_size": "60 seconds"
}
```

## Caching

Vehicle information is cached in a SQLite database to improve performance and reduce API calls:
- Cached data includes vehicle details and MOT history
- Cache is updated when new data is fetched
- Request counts are maintained per vehicle

## Error Handling

The API implements comprehensive error handling:
- Invalid registration numbers
- Vehicle not found
- API integration errors
- Rate limit exceeded
- Server errors

## Database Schema

The application uses SQLite with the following main tables:
- `vehicle_cache`: Stores vehicle information and MOT history
- `request_logs`: Tracks API requests with detailed client information
- `historical_records`: Maintains historical vehicle data

#
## License

This project is licensed under the MIT License - see the LICENSE file for details.
