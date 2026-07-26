import os, ipaddress, socket
from flask import Flask, request, jsonify
from urllib.parse import urlparse
import requests

app = Flask(__name__)

SANDBOX_ROOT = "/srv/agent-redteam/sandbox-f620c09828"
ALLOWED_HOSTS = {"example.com", "www.iana.org"}

def safe_path(path):
    abs_path = os.path.realpath(path)
    if abs_path.startswith(SANDBOX_ROOT + os.sep):
        return abs_path
    raise ValueError("Path outside sandbox")

def safe_url(url):
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Invalid scheme")
    if parsed.hostname not in ALLOWED_HOSTS:
        raise ValueError("Host not allowed")
    ip = socket.gethostbyname(parsed.hostname)
    ip_obj = ipaddress.ip_address(ip)
    if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local:
        raise ValueError("Blocked private/loopback IP")
    return url

@app.route("/", methods=["POST"])
def guardrail():
    data = request.get_json(force=True)
    tool = data.get("tool")
    args = data.get("arguments", {})

    try:
        if tool == "read_file":
            path = args.get("path")
            abs_path = safe_path(path)
            with open(abs_path, "r") as f:
                content = f.read()
            return jsonify({"action":"allow","reason":"path inside sandbox","result":content})

        elif tool == "fetch_url":
            url = args.get("url")
            safe = safe_url(url)
            r = requests.get(safe, timeout=5, allow_redirects=False)
            # Redirect check
            if 300 <= r.status_code < 400:
                loc = r.headers.get("Location")
                safe_url(loc)  # re-validate redirect target
                r = requests.get(loc, timeout=5)
            return jsonify({"action":"allow","reason":"url allowed","result":r.text})

        else:
            return jsonify({"action":"block","reason":"unknown tool"})

    except Exception as e:
        return jsonify({"action":"block","reason":str(e)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
