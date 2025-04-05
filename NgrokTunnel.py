from pyngrok import ngrok

class NgrokTunnel:
    def __init__(self):
        self.public_url = None
    
    # Starts an ngrok tunnel and returns the public URL
    def start(self, port):
        self.public_url = ngrok.connect(port, "http")
        return self.public_url