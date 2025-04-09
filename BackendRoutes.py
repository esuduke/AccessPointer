import os
from flask import Blueprint, request, jsonify, Response

backend_bp = Blueprint("backend_bp", __name__)

# Pre-generate a buffer of random data (1 MB of random bytes).
# This will prevent the server from having to re-generate random data on every request.
PREGENERATED_DATA = os.urandom(1024 * 1024)  # 1 MB

@backend_bp.route("/backend/getIP", methods=["GET"])
def get_ip():
    """
    This endpoint is called by LibreSpeed to get the client IP.
    Return a minimal JSON response with the client's IP address.
    """
    ip_addr = request.remote_addr or "0.0.0.0"
    return jsonify({
        "processedString": ip_addr,
        "yourIp": ip_addr,
        "query": ip_addr,
        "ISP": None,
        "overrideIsp": None
    })

@backend_bp.route("/backend/empty", methods=["GET", "POST"])
def empty():
    """
    This endpoint is used for the upload and ping tests.
    It simply returns a 200 OK with an empty body.
    """
    return ("", 200)

@backend_bp.route("/backend/garbage", methods=["GET"])
def garbage():
    """
    This endpoint is used for the download test.
    It returns a non-compressible payload of size ckSize (in KB).
    """
    # Get size in kilobytes; default to 500 KB if not provided.
    ckSize = request.args.get("ckSize", 500, type=int)
    size_bytes = ckSize * 1024
    
    # Build a payload using pre-generated random data.
    # If the requested size is more than 1 MB, repeat the data as needed.
    if size_bytes <= len(PREGENERATED_DATA):
        data = PREGENERATED_DATA[:size_bytes]
    else:
        # Calculate how many times to repeat the buffer
        times = (size_bytes // len(PREGENERATED_DATA)) + 1
        data = (PREGENERATED_DATA * times)[:size_bytes]
    
    headers = {
        "Content-Type": "application/octet-stream",
        "Content-Length": str(len(data)),
        "Cache-Control": "no-cache"  # Ensure no caching interferes
    }
    return Response(data, headers=headers)
