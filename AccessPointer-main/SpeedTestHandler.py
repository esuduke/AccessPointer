import subprocess
import json
import platform

class SpeedTestHandler:
    def __init__(self):
        # Detect OS and set the correct executable path
        if platform.system() == "Darwin":  # macOS
            self.executable_path = "./speedtest"
        elif platform.system() == "Windows":
            self.executable_path = "./speedtest.exe"
        else:
            self.executable_path = "speedtest"  # Default for Linux (if needed)

    def run_speed_test(self):
        """Runs a speed test using Speedtest CLI and returns download, upload, and ping."""
        try:
            result = subprocess.run(
                [self.executable_path, "--format=json"],  # Correct flag
                capture_output=True, text=True
            )

            # If there is an output, parse it
            if result.stdout:
                data = json.loads(result.stdout)

                # Extract relevant fields
                download_speed = (data["download"]["bandwidth"] * 8) / 1_000_000  # Convert to Mbps
                upload_speed = (data["upload"]["bandwidth"] * 8) / 1_000_000  # Convert to Mbps
                ping = data["ping"]["latency"]

                return download_speed, upload_speed, ping
            else:
                return None, None, None  # Error: no output received
        except FileNotFoundError:
            return None, None, "Error: Speedtest CLI is not installed or executable path is incorrect."
        except json.JSONDecodeError:
            return None, None, "Error decoding JSON response. Check if the CLI output format has changed."
        except Exception as e:
            return None, None, f"Unexpected error: {e}"
