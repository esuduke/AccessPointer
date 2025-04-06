from flask import Flask, render_template, send_file, request, jsonify
import os
import random
import string
import threading
from pyngrok import ngrok

class NgrokTunnel:
    def __init__(self):
        self.public_url = None
    
    # Starts an ngrok tunnel and returns the public URL
    def start(self, port):
        self.public_url = ngrok.connect(port, "http")
        return self.public_url

class SpeedTestApp:
    def __init__(self):
        self.app = Flask(__name__)
        self.tunnel = NgrokTunnel()
        self.setup_routes()
        self.create_test_files()
        
    def create_test_files(self):
        # Create directory for test files if it doesn't exist
        os.makedirs('test_files', exist_ok=True)
        
        # Generate test files of different sizes if they don't exist
        self.generate_test_file(1, 'test_1mb.bin')
        self.generate_test_file(5, 'test_5mb.bin')
        self.generate_test_file(10, 'test_10mb.bin')
        # Add larger test files for better bandwidth saturation
        self.generate_test_file(20, 'test_20mb.bin')
        self.generate_test_file(50, 'test_50mb.bin')
    
    def generate_test_file(self, size_mb, filename):
        filepath = os.path.join('test_files', filename)
        if not os.path.exists(filepath):
            print(f"Generating {size_mb}MB test file...")
            with open(filepath, 'wb') as f:
                f.write(os.urandom(size_mb * 1024 * 1024))
            print(f"Generated {filepath}")
    
    def setup_routes(self):
        @self.app.route('/')
        def index():
            return render_template('index.html')
        
        @self.app.route('/test-file/<size>')
        def test_file(size):
            """Serve a test file of specified size with cache control headers"""
            if size == '1mb':
                filepath = 'test_files/test_1mb.bin'
            elif size == '5mb':
                filepath = 'test_files/test_5mb.bin'
            elif size == '10mb':
                filepath = 'test_files/test_10mb.bin'
            elif size == '20mb':
                filepath = 'test_files/test_20mb.bin'
            elif size == '50mb':
                filepath = 'test_files/test_50mb.bin'
            else:
                return "Invalid file size requested", 400
            
            # Add cache control headers to prevent caching
            response = send_file(filepath)
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
            return response
        
        @self.app.route('/templates/index.html')
        def serve_template():
            return render_template('index.html')
        
        @self.app.route('/save_results', methods=['POST'])
        def save_results():
            """Save speed test results (future expansion)"""
            data = request.json
            print(f"Speed test result: {data['speed']} Mbps, Quality: {data['quality']}")
            return jsonify({"status": "success"}), 200
    
    def create_template(self):
        # Create templates directory if it doesn't exist
        os.makedirs('templates', exist_ok=True)
        
        # Create index.html template if it doesn't exist
        if not os.path.exists('templates/index.html'):
            with open('templates/index.html', 'w') as f:
                f.write('''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Internet Speed Test</title>
    <style>
        body {
            font-family: 'Arial', sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        h1 {
            color: #333;
            text-align: center;
        }
        .dashboard {
            background-color: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }
        .result-container {
            display: flex;
            justify-content: space-around;
            margin: 30px 0;
        }
        .result-box {
            text-align: center;
            padding: 15px;
            border-radius: 8px;
            background-color: #f9f9f9;
            width: 30%;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        .speed-value {
            font-size: 2.5em;
            font-weight: bold;
            margin: 10px 0;
            color: #2c3e50;
        }
        .speed-unit {
            font-size: 1em;
            color: #7f8c8d;
        }
        .connection-quality {
            font-size: 1.2em;
            font-weight: bold;
            margin-top: 10px;
        }
        .excellent {
            color: #27ae60;
        }
        .good {
            color: #2980b9;
        }
        .average {
            color: #f39c12;
        }
        .poor {
            color: #e74c3c;
        }
        button {
            background-color: #3498db;
            color: white;
            border: none;
            padding: 12px 20px;
            border-radius: 4px;
            font-size: 1em;
            cursor: pointer;
            display: block;
            margin: 20px auto;
            transition: background-color 0.3s;
        }
        button:hover {
            background-color: #2980b9;
        }
        button:disabled {
            background-color: #95a5a6;
            cursor: not-allowed;
        }
        .progress-container {
            height: 20px;
            background-color: #ecf0f1;
            border-radius: 10px;
            margin: 20px 0;
            overflow: hidden;
        }
        .progress-bar {
            height: 100%;
            background-color: #3498db;
            border-radius: 10px;
            width: 0%;
            transition: width 0.5s;
        }
        .test-info {
            text-align: center;
            margin: 10px 0;
            font-style: italic;
            color: #7f8c8d;
        }
        .history-container {
            margin-top: 30px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th, td {
            padding: 10px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        th {
            background-color: #f2f2f2;
        }
        .hidden {
            display: none;
        }
        .server-info {
            text-align: center;
            margin: 10px 0;
            font-size: 0.9em;
            color: #7f8c8d;
        }
        .mode-switch {
            display: flex;
            justify-content: center;
            gap: 15px;
            margin: 15px 0;
        }
        .test-method {
            font-size: 0.9em;
            background-color: #f2f2f2;
            padding: 8px 15px;
            border-radius: 20px;
            cursor: pointer;
        }
        .test-method.active {
            background-color: #3498db;
            color: white;
        }
    </style>
</head>
<body>
    <h1>Internet Speed Test</h1>
    
    <div class="dashboard">
        <div class="result-container">
            <div class="result-box">
                <div>Download Speed</div>
                <div class="speed-value" id="download-speed">-</div>
                <div class="speed-unit">Mbps</div>
            </div>
            <div class="result-box">
                <div>Test Progress</div>
                <div class="progress-container">
                    <div class="progress-bar" id="progress-bar"></div>
                </div>
                <div id="test-status">Ready</div>
            </div>
            <div class="result-box">
                <div>Connection Quality</div>
                <div class="connection-quality" id="connection-quality">-</div>
            </div>
        </div>
        
        <div class="mode-switch">
            <div class="test-method active" id="concurrent-mode">Concurrent Downloads</div>
            <div class="test-method" id="sequential-mode">Sequential Downloads</div>
        </div>
        
        <div class="test-info" id="test-info">Click the button below to start the test</div>
        <div class="server-info">Testing via secure HTTPS connection through ngrok</div>
        
        <button id="start-test">Start Speed Test</button>
        
        <div class="history-container hidden" id="history-container">
            <h2>Test History</h2>
            <table>
                <thead>
                    <tr>
                        <th>Time</th>
                        <th>Download (Mbps)</th>
                        <th>Quality</th>
                        <th>Method</th>
                    </tr>
                </thead>
                <tbody id="history-body">
                </tbody>
            </table>
        </div>
    </div>
    
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            const startButton = document.getElementById('start-test');
            const downloadSpeed = document.getElementById('download-speed');
            const connectionQuality = document.getElementById('connection-quality');
            const testInfo = document.getElementById('test-info');
            const progressBar = document.getElementById('progress-bar');
            const testStatus = document.getElementById('test-status');
            const historyContainer = document.getElementById('history-container');
            const historyBody = document.getElementById('history-body');
            const concurrentMode = document.getElementById('concurrent-mode');
            const sequentialMode = document.getElementById('sequential-mode');
            
            // Test mode (concurrent or sequential)
            let useConurrentMode = true;
            
            // Toggle test mode
            concurrentMode.addEventListener('click', function() {
                useConurrentMode = true;
                concurrentMode.classList.add('active');
                sequentialMode.classList.remove('active');
            });
            
            sequentialMode.addEventListener('click', function() {
                useConurrentMode = false;
                sequentialMode.classList.add('active');
                concurrentMode.classList.remove('active');
            });
            
            const testHistory = [];
            
            // Function to download a single file and measure speed
            async function downloadTest(size) {
                const sizeMap = {
                    '1mb': 1 * 1024 * 1024,
                    '5mb': 5 * 1024 * 1024,
                    '10mb': 10 * 1024 * 1024,
                    '20mb': 20 * 1024 * 1024,
                    '50mb': 50 * 1024 * 1024
                };
                
                const sizeInBytes = sizeMap[size];
                
                // Add a random parameter to prevent caching
                const cacheBuster = Math.random().toString(36).substring(2);
                const testFile = `/test-file/${size}?cb=${cacheBuster}`;
                
                const startTime = performance.now();
                
                try {
                    const response = await fetch(testFile, { 
                        method: 'GET',
                        cache: 'no-store' // Prevent caching
                    });
                    
                    const data = await response.blob();
                    const endTime = performance.now();
                    const durationInSeconds = (endTime - startTime) / 1000;
                    const bitsLoaded = sizeInBytes * 8;
                    const speedBps = bitsLoaded / durationInSeconds;
                    const speedMbps = (speedBps / 1024 / 1024);
                    
                    return speedMbps;
                } catch (error) {
                    console.error(`Error downloading ${size} file:`, error);
                    throw error;
                }
            }
            
            // Sequential download test
            async function runSequentialTest() {
                const testSizes = ['1mb', '5mb', '10mb', '20mb'];
                const results = [];
                
                for (let i = 0; i < testSizes.length; i++) {
                    const size = testSizes[i];
                    
                    testInfo.textContent = `Testing with ${size.toUpperCase()} file (${i+1}/${testSizes.length})`;
                    progressBar.style.width = `${(i / testSizes.length) * 100}%`;
                    
                    try {
                        const speed = await downloadTest(size);
                        results.push(speed);
                        
                        // Update progress
                        progressBar.style.width = `${((i+1) / testSizes.length) * 100}%`;
                    } catch (error) {
                        testInfo.textContent = `Error: ${error.message}`;
                        return null;
                    }
                    
                    // Small delay between tests
                    await new Promise(resolve => setTimeout(resolve, 300));
                }
                
                return results;
            }
            
            // Concurrent download test (more like Ookla)
            async function runConcurrentTest() {
                testInfo.textContent = "Running concurrent downloads for more accurate results...";
                progressBar.style.width = "50%";
                
                try {
                    // Start multiple downloads simultaneously (more like how Ookla works)
                    const testSizes = ['5mb', '10mb', '20mb', '50mb'];
                    const downloadPromises = testSizes.map(size => downloadTest(size));
                    
                    // Wait for all downloads to complete
                    const results = await Promise.all(downloadPromises);
                    
                    progressBar.style.width = "100%";
                    return results;
                } catch (error) {
                    testInfo.textContent = `Error: ${error.message}`;
                    return null;
                }
            }
            
            async function runSpeedTest() {
                startButton.disabled = true;
                testStatus.textContent = 'Testing...';
                progressBar.style.width = '0%';
                downloadSpeed.textContent = '-';
                connectionQuality.textContent = '-';
                connectionQuality.className = 'connection-quality';
                
                // Choose test method based on mode
                let results;
                const testMethod = useConurrentMode ? 'concurrent' : 'sequential';
                
                if (useConurrentMode) {
                    results = await runConcurrentTest();
                } else {
                    results = await runSequentialTest();
                }
                
                if (!results) {
                    startButton.disabled = false;
                    testStatus.textContent = 'Failed';
                    return;
                }
                
                // Calculate average speed (excluding outliers if we have enough samples)
                let finalSpeed;
                if (results.length >= 3) {
                    // Sort results and take the middle values (exclude min and max for stability)
                    const sortedResults = [...results].sort((a, b) => a - b);
                    // For concurrent downloads, use the higher values as they're more representative
                    // of actual maximum bandwidth
                    if (useConurrentMode) {
                        // Take the 75th percentile value for more accurate representation
                        const idx = Math.floor(sortedResults.length * 0.75);
                        finalSpeed = sortedResults[idx];
                    } else {
                        // For sequential, use middle values
                        const middleResults = sortedResults.slice(1, sortedResults.length - 1);
                        finalSpeed = middleResults.reduce((a, b) => a + b, 0) / middleResults.length;
                    }
                } else {
                    finalSpeed = results.reduce((a, b) => a + b, 0) / results.length;
                }
                
                // Update the UI with the final result
                const roundedSpeed = finalSpeed.toFixed(2);
                downloadSpeed.textContent = roundedSpeed;
                
                // Determine connection quality
                let quality;
                if (finalSpeed >= 100) {
                    quality = { text: 'Excellent', class: 'excellent' };
                } else if (finalSpeed >= 25) {
                    quality = { text: 'Good', class: 'good' };
                } else if (finalSpeed >= 5) {
                    quality = { text: 'Average', class: 'average' };
                } else {
                    quality = { text: 'Poor', class: 'poor' };
                }
                
                connectionQuality.textContent = quality.text;
                connectionQuality.classList.add(quality.class);
                
                // Add to history
                testHistory.unshift({
                    time: new Date().toLocaleTimeString(),
                    speed: roundedSpeed,
                    quality: quality.text,
                    method: testMethod
                });
                
                // Send results to server (optional)
                try {
                    await fetch('/save_results', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            speed: roundedSpeed,
                            quality: quality.text,
                            method: testMethod,
                            timestamp: new Date().toISOString()
                        }),
                    });
                } catch (error) {
                    console.error("Error saving results:", error);
                }
                
                // Update history table
                updateHistory();
                
                // Test complete
                testInfo.textContent = `Test completed successfully using ${testMethod} downloads`;
                testStatus.textContent = 'Complete';
                startButton.disabled = false;
                
                // Show history if we have results
                if (testHistory.length > 0) {
                    historyContainer.classList.remove('hidden');
                }
            }
            
            function updateHistory() {
                // Clear existing entries
                historyBody.innerHTML = '';
                
                // Add new entries
                testHistory.forEach(entry => {
                    const row = document.createElement('tr');
                    
                    const timeCell = document.createElement('td');
                    timeCell.textContent = entry.time;
                    
                    const speedCell = document.createElement('td');
                    speedCell.textContent = `${entry.speed} Mbps`;
                    
                    const qualityCell = document.createElement('td');
                    qualityCell.textContent = entry.quality;
                    
                    const methodCell = document.createElement('td');
                    methodCell.textContent = entry.method === 'concurrent' ? 'Concurrent' : 'Sequential';
                    
                    row.appendChild(timeCell);
                    row.appendChild(speedCell);
                    row.appendChild(qualityCell);
                    row.appendChild(methodCell);
                    
                    historyBody.appendChild(row);
                });
            }
            
            startButton.addEventListener('click', runSpeedTest);
        });
    </script>
</body>
</html>
                ''')
        
    def run(self):
        port = 8001
        # Create template
        self.create_template()
        
        # Start ngrok tunnel
        public_url = self.tunnel.start(port)
        print(f" * Secure ngrok tunnel available at: {public_url}")
        
        # Run flask app
        self.app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    app = SpeedTestApp()
    
    # Create a daemon thread for Flask
    flask_thread = threading.Thread(target=app.run)
    flask_thread.daemon = True
    flask_thread.start()
    
    # Simple CLI for the main thread
    print("Speed Test Server running. Press Ctrl+C to exit.")
    try:
        while True:
            cmd = input("\nCommands: 'url' to show the ngrok URL, 'exit' to quit: ")
            if cmd.lower() == 'url':
                print(f"Current ngrok URL: {app.tunnel.public_url}")
            elif cmd.lower() == 'exit':
                break
    except KeyboardInterrupt:
        print("\nShutting down...")