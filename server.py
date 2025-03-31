# Standard modules
from threading import Event, Thread

# Third-party modules
from camoufox.sync_api import Camoufox
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from orjson import dumps
from uvicorn import Config as UvicornConfig
from uvicorn import Server as UvicornServer


class Server:
    def __init__(self, host: str = "127.0.0.1", port: int = 8000, log_level: str = "info") -> None:
        self._url: str | None = None
        self.host: str = host
        self.port: int = port
        self.log_level: str = log_level
        self.server: UvicornServer | None = None
        self.thread: Thread | None = None
        self.started: bool = False
        self.ready_event: Event = Event()

    @property
    def url(self) -> str | None:
        return self._url

    @url.setter
    def url(self, value: str) -> None:
        self._url = value

    def run_server(self) -> None:
        """Run the uvicorn server in the current thread."""

        config = UvicornConfig(app=app, host=self.host, port=self.port, log_level=self.log_level)

        self.server = UvicornServer(config=config)
        self.started = True
        self.server.run()

    def wait_online(self, timeout: float = 60) -> str:
        """
        Wait for the server to be online and return the URL.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            The server URL

        Raises:
            TimeoutError: If the server doesn't start within the timeout
        """

        if not self.ready_event.wait(timeout):
            raise TimeoutError(f"Server failed to start within {timeout} seconds")

        return self._url

    def start(self) -> str:
        self._url = f"http://{self.host}:{self.port}"

        def _run_and_signal() -> None:
            try:
                self.run_server()
            finally:
                self.ready_event.set()

        self.thread = Thread(target=_run_and_signal, daemon=True)
        self.thread.start()

        return self._url

    def stop(self) -> None:
        """Stop the server if it's running."""

        if self.server and self.started:
            self.server.should_exit = True

            if self.thread and self.thread.is_alive():
                self.thread.join(timeout=1)

            self.started = False
            self.ready_event.clear()


app = FastAPI()
request_endpoint = "https://httpbin.org/post"
request_details = {
    "method": "POST",
    "headers": {"Content-Type": "application/json"},
    "body": dumps("Hello, World!").decode("utf-8"),
}


@app.get("/", response_class=HTMLResponse)
async def root() -> str:
    return f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Simple POST Request</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    padding: 20px;
                }}
                button {{
                    margin-bottom: 10px;
                    cursor: pointer;
                    padding: 8px 16px;
                }}
                .status-container {{
                    margin: 10px 0;
                    display: flex;
                    align-items: center;
                }}
                .status-indicator {{
                    width: 16px;
                    height: 16px;
                    border: 1px solid #ccc;
                    margin-right: 5px;
                    display: inline-block;
                    transition: background-color 0.2s;
                }}
                .status-indicator.active {{
                    background-color: #4CAF50;
                }}
                #responseBox {{
                    width: 100%;
                    height: 200px;
                    border: 1px solid #ccc;
                    padding: 5px;
                    overflow-y: auto;
                    white-space: pre-wrap;
                    word-wrap: break-word;
                    font-family: monospace;
                    font-size: 14px;
                }}
            </style>
        </head>
        <body>
            <button id="postButton">Send POST Request</button>

            <div class="status-container">
                <div id="statusIndicator" class="status-indicator"></div>
                <span>Response received</span>
            </div>

            <div id="responseBox"></div>

            <script>
                const button = document.getElementById('postButton');
                const responseBox = document.getElementById('responseBox');
                const statusIndicator = document.getElementById('statusIndicator');

                // Disable button during fetch to prevent multiple requests
                function setButtonState(disabled) {{
                    button.disabled = disabled;
                    button.style.opacity = disabled ? '0.7' : '1';
                }}

                button.addEventListener('click', function() {{
                    responseBox.textContent = '';
                    statusIndicator.classList.remove('active');
                    setButtonState(true);

                    fetch('{request_endpoint}', {{
                        method: '{request_details["method"]}',
                        headers: {dumps(request_details["headers"]).decode("utf-8")},
                        body: {request_details["body"]}
                    }})
                    .then(response => response.text())
                    .then(data => {{
                        responseBox.textContent = data;
                        statusIndicator.classList.add('active');
                        setButtonState(false);
                    }})
                    .catch((error) => {{
                        responseBox.textContent = 'Error: ' + error;
                        statusIndicator.classList.add('active');
                        setButtonState(false);
                    }});
                }});
            </script>
        </body>
        </html>
    """


if __name__ == "__main__":
    server = Server(host="localhost", port=8542, log_level="info")
    server_url = server.start()

    with Camoufox(headless=False, humanize=False, geoip=False) as browser:
        page = browser.new_page(java_script_enabled=True)
        # server.wait_online()

        page.goto(server_url, wait_until="domcontentloaded")
        page.click("#postButton")
        page.wait_for_selector(".status-indicator.active")
        response_text = page.inner_html("#responseBox")
        print(response_text)

    server.stop()
