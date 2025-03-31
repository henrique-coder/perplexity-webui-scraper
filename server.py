# Standard modules
from threading import Event, Thread
from time import sleep

# Third-party modules
from camoufox.sync_api import Camoufox
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
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
request_endpoint = "https://www.perplexity.ai/rest/uploads/create_upload_url?version=2.18&source=default"


@app.get("/", response_class=HTMLResponse)
async def root() -> str:
    return """
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

                function setButtonState(disabled) {{
                    button.disabled = disabled;
                    button.style.opacity = disabled ? '0.7' : '1';
                }}

                button.addEventListener('click', function() {{
                    responseBox.textContent = '';
                    statusIndicator.classList.remove('active');
                    setButtonState(true);
                    fetch("https://www.perplexity.ai/rest/uploads/create_upload_url?version=2.18&source=default", {
                        "method": "POST",
                        "headers": {
                            "accept": "*/*",
                            "accept-language": "pt-BR,pt;q=0.9,en;q=0.8",
                            "content-type": "application/json",
                            "priority": "u=1, i",
                            "sec-ch-ua": "'Google Chrome';v='135', 'Not-A.Brand';v='8', 'Chromium';v='135'",
                            "sec-ch-ua-mobile": "?0",
                            "sec-ch-ua-platform": "'Linux'",
                            "sec-fetch-dest": "empty",
                            "sec-fetch-site": "same-origin",
                            "x-app-apiclient": "default",
                            "x-app-apiversion": "2.18",
                            "x-perplexity-request-endpoint": "https://www.perplexity.ai/rest/uploads/create_upload_url?version=2.18&source=default",
                            "x-perplexity-request-try-number": "1",
                            "x-perplexity-url-template": "/rest/uploads/create_upload_url"
                        },
                        "body": JSON.stringify({
                            filename: "Henrique (IA).png",
                            content_type: "image/png",
                            source: "default",
                            file_size: 1143480,
                            force_image: false
                        }),
                        "credentials": "include",
                        "referrer": "https://www.perplexity.ai/",
                        "referrerPolicy": "strict-origin-when-cross-origin"
                    })
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

        page.goto(server_url, wait_until="networkidle", referer="https://www.perplexity.ai/")
        page.click("#postButton")
        page.wait_for_selector(".status-indicator.active")
        response_text = page.inner_html("#responseBox")
        print(response_text)

        # sleep(10)

    server.stop()
