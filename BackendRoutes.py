# BackendRoutes.py
# Handles backend API routes for IP information, data transfer, and telemetry.

import os
import json
import requests
from flask import Blueprint, request, jsonify, Response, make_response

# Define blueprint for backend routes
backend_bp = Blueprint("backend_bp", __name__)

# Pre-generate a buffer of random data (1 MB of random bytes) for garbage endpoint.
PREGENERATED_DATA = os.urandom(1024 * 1024)
# Define timeout duration in seconds for external API calls.
API_TIMEOUT_SECONDS = 2

# --- Helper Functions ---

def get_client_ip():
    """
    Retrieves the client's IP address from request headers.
    Prioritizes specific headers to handle proxies.
    Returns the IP address string or a default value.
    """
    # Prioritize 'HTTP_CLIENT_IP' header.
    # Prioritize 'HTTP_X_REAL_IP' header.
    # Check 'HTTP_X_FORWARDED_FOR' header, taking the first IP if multiple.
    # Fallback to 'remote_addr'.
    # Default to '0.0.0.0' if none found.
    ip_address = (
        request.headers.get("HTTP_CLIENT_IP") or
        request.headers.get("HTTP_X_REAL_IP") or
        request.headers.get("HTTP_X_FORWARDED_FOR", "").split(",")[0] or
        request.remote_addr or "0.0.0.0"
    )
    # Remove IPv6 mapping prefix if present.
    return ip_address.replace("::ffff:", "")

# --- Route Definitions ---

@backend_bp.route("/backend/getIP", methods=["GET"])
def get_ip():
    """
    GET /backend/getIP
    Returns the client's IP address.
    Optionally includes ISP information if 'isp' query parameter is present.
    Supports CORS if 'cors' query parameter is present.
    """
    # Get the client's IP address.
    ip_address = get_client_ip()
    isp_info = None
    raw_info = ""

    # Check if ISP detection is requested via query parameter.
    if "isp" in request.args:
        # Handle local IP addresses.
        if ip_address.startswith("127.") or ip_address.startswith("192.168.") or ip_address == "::1":
            isp_info = "localhost IPv4 access"
        else:
            # Attempt to get ISP info from ipinfo.io API.
            api_key = os.getenv("IPINFO_APIKEY")
            # Use API key if available for higher rate limits.
            if api_key:
                try:
                    # Construct the API URL.
                    api_url = f"https://ipinfo.io/{ip_address}/json?token={api_key}"
                    # Make the request with a timeout.
                    res = requests.get(api_url, timeout=API_TIMEOUT_SECONDS)
                    # Check if the request was successful.
                    if res.ok:
                        data = res.json()
                        raw_info = data # Store the raw JSON response.
                        # Extract ISP organization name, preferring 'org' field.
                        if "org" in data:
                            # Clean up the organization name.
                            isp_info = data["org"].replace("AS", "").strip()
                        # Fallback to ASN name if 'org' is not present.
                        elif "asn" in data and "name" in data["asn"]:
                            isp_info = data["asn"]["name"]
                except requests.exceptions.RequestException as e:
                    # Log API call failure, but continue.
                    print(f"ipinfo.io API call failed: {e}")
                    pass # Fallback if API call fails or times out.

    # Construct the processed string including IP and ISP if available.
    processed_string = ip_address
    if isp_info:
        processed_string += f" - {isp_info}"

    # Create the JSON response payload.
    response_data = {
        "processedString": processed_string,
        "yourIp": ip_address,
        "query": ip_address, # Keep 'query' field for potential compatibility.
        "ISP": isp_info,
        "rawIspInfo": raw_info or "", # Ensure raw info is always a string.
    }
    # Convert the dictionary to a JSON response.
    response = jsonify(response_data)

    # Set response headers.
    # Set content type to JSON with UTF-8 encoding.
    response.headers["Content-Type"] = "application/json; charset=utf-8"
    # Enable CORS if requested via query parameter.
    if "cors" in request.args:
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST"
    # Prevent caching of this dynamic response.
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0, s-maxage=0"
    response.headers["Pragma"] = "no-cache" # For older HTTP/1.0 caches.

    return response

@backend_bp.route("/backend/empty", methods=["GET", "POST"])
def empty():
    """
    GET, POST /backend/empty
    Returns an empty response (200 OK).
    Used by the speed test for ping and upload measurements.
    Supports CORS if 'cors' query parameter is present.
    Disables caching.
    """
    # Create an empty response with status code 200.
    response = make_response("", 200)
    # Enable CORS if requested via query parameter.
    if "cors" in request.args:
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST"
        # Allow specific headers needed by speedtest.js.
        response.headers["Access-Control-Allow-Headers"] = "Content-Encoding, Content-Type"

    # Set headers to prevent caching thoroughly.
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0, s-maxage=0"
    # Additional cache control headers for older proxies/clients.
    response.headers.add("Cache-Control", "post-check=0, pre-check=0")
    response.headers["Pragma"] = "no-cache"
    # Keep the connection alive if possible.
    response.headers["Connection"] = "keep-alive"
    return response

@backend_bp.route("/backend/garbage", methods=["GET"])
def garbage():
    """
    GET /backend/garbage
    Returns a stream of random data.
    Used by the speed test for download measurements.
    The size of the data stream is controlled by the 'ckSize' query parameter.
    Supports CORS if 'cors' query parameter is present.
    """
    # Get chunk size multiplier from query parameter, default to 4.
    try:
        # Ensure ckSize is an integer between 1 and 1024.
        chunk_size_multiplier = int(request.args.get("ckSize", "4"))
        chunk_size_multiplier = max(1, min(chunk_size_multiplier, 1024))
    except ValueError:
        # Default to 4 if conversion fails.
        chunk_size_multiplier = 4

    # Generate payload by repeating the pre-generated 1MB chunk.
    payload = PREGENERATED_DATA * chunk_size_multiplier
    # Define response headers for file transfer.
    headers = {
        "Content-Description": "File Transfer",
        "Content-Type": "application/octet-stream", # Indicate binary data.
        "Content-Disposition": "attachment; filename=random.dat", # Suggest filename.
        "Content-Transfer-Encoding": "binary",
        # Prevent caching of the random data.
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0, s-maxage=0",
        "Pragma": "no-cache",
        # Set the correct content length.
        "Content-Length": str(len(payload))
    }

    # Enable CORS if requested via query parameter.
    if "cors" in request.args:
        headers["Access-Control-Allow-Origin"] = "*"
        headers["Access-Control-Allow-Methods"] = "GET, POST"

    # Return the random data payload with appropriate headers.
    return Response(payload, headers=headers)

@backend_bp.route("/results/telemetry", methods=["POST"])
def save_telemetry():
    """
    POST /results/telemetry
    Receives speed test results (telemetry data) as JSON.
    Validates the data and potentially saves it (currently just logs).
    Returns a success or error JSON response.
    """
    # Get JSON data from the request body. Force parsing even if content-type is wrong.
    data = request.get_json(force=True, silent=True) # Use silent=True to handle bad JSON

    # Validate if JSON data was received.
    if data is None:
        return jsonify({"error": "Invalid or missing JSON payload"}), 400

    # Validate and extract required fields, converting to float.
    try:
        # Extract speed test metrics.
        download_speed = float(data.get("download"))
        upload_speed = float(data.get("upload"))
        ping_time = float(data.get("ping"))
        jitter_time = float(data.get("jitter"))

        # Placeholder: Add logic here to save the validated data to a database or log file.
        print(f"Received Telemetry: DL={download_speed}, UL={upload_speed}, Ping={ping_time}, Jitter={jitter_time}")

        # Return success response.
        return jsonify({"status": "success"}), 200
    # Handle potential errors during data extraction or conversion.
    except (TypeError, ValueError, AttributeError):
        # Return error response for invalid data format.
        return jsonify({"error": "Invalid or missing numeric data fields (download, upload, ping, jitter)"}), 400