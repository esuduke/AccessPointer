import os
import json
import requests
from flask import Blueprint, request, jsonify, Response, make_response

backend_bp = Blueprint("backend_bp", __name__)

# Pre-generate a buffer of random data (1 MB of random bytes).
PREGENERATED_DATA = os.urandom(1024 * 1024)

def get_client_ip():
    return (
        request.headers.get("HTTP_CLIENT_IP") or
        request.headers.get("HTTP_X_REAL_IP") or
        request.headers.get("HTTP_X_FORWARDED_FOR", "").split(",")[0] or
        request.remote_addr or "0.0.0.0"
    ).replace("::ffff:", "")

@backend_bp.route("/backend/getIP", methods=["GET"])
def get_ip():
    ip = get_client_ip()
    isp_info = None
    raw_info = ""

    # Check for ISP detection
    if "isp" in request.args:
        # Local IP cases
        if ip.startswith("127.") or ip.startswith("192.168.") or ip == "::1":
            isp_info = "localhost IPv4 access"
        else:
            # Try ipinfo.io API (token optional via env var or config)
            token = os.getenv("IPINFO_APIKEY")
            if token:
                try:
                    res = requests.get(f"https://ipinfo.io/{ip}/json?token={token}", timeout=2)
                    if res.ok:
                        data = res.json()
                        raw_info = data
                        if "org" in data:
                            isp_info = data["org"].replace("AS", "").strip()
                        elif "asn" in data and "name" in data["asn"]:
                            isp_info = data["asn"]["name"]
                except:
                    pass  # Fallback if API fails

    processed_string = ip
    if isp_info:
        processed_string += f" - {isp_info}"

    response = jsonify({
        "processedString": processed_string,
        "yourIp": ip,
        "query": ip,
        "ISP": isp_info,
        "rawIspInfo": raw_info or "",
    })

    # Headers
    response.headers["Content-Type"] = "application/json; charset=utf-8"
    if "cors" in request.args:
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST"
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0, s-maxage=0"
    response.headers["Pragma"] = "no-cache"

    return response

@backend_bp.route("/backend/empty", methods=["GET", "POST"])
def empty():
    response = make_response("", 200)
    if "cors" in request.args:
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST"
        response.headers["Access-Control-Allow-Headers"] = "Content-Encoding, Content-Type"

    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0, s-maxage=0"
    response.headers.add("Cache-Control", "post-check=0, pre-check=0")
    response.headers["Pragma"] = "no-cache"
    response.headers["Connection"] = "keep-alive"
    return response

@backend_bp.route("/backend/garbage", methods=["GET"])
def garbage():
    # Mimic PHP default to 4 if invalid, and max 1024
    try:
        ckSize = int(request.args.get("ckSize", "4"))
        ckSize = max(1, min(ckSize, 1024))
    except:
        ckSize = 4

    chunk = PREGENERATED_DATA  # 1 MB
    payload = chunk * ckSize
    headers = {
        "Content-Description": "File Transfer",
        "Content-Type": "application/octet-stream",
        "Content-Disposition": "attachment; filename=random.dat",
        "Content-Transfer-Encoding": "binary",
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0, s-maxage=0",
        "Pragma": "no-cache",
        "Content-Length": str(len(payload))
    }

    if "cors" in request.args:
        headers["Access-Control-Allow-Origin"] = "*"
        headers["Access-Control-Allow-Methods"] = "GET, POST"

    return Response(payload, headers=headers)

@backend_bp.route("/results/telemetry", methods=["POST"])
def save_telemetry():
    data = request.get_json(force=True)

    try:
        download = float(data.get("download"))
        upload = float(data.get("upload"))
        ping = float(data.get("ping"))
        jitter = float(data.get("jitter"))
        # Save to DB or log here
        return jsonify({"status": "success"}), 200
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid data format"}), 400