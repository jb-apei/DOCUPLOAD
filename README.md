# DocUpload Project

A simple document upload service with an embeddable widget.

## Setup

1.  **Create a virtual environment:**
    ```bash
    python -m venv venv
    ```

2.  **Activate variable environment:**
    -   Windows: `venv\Scripts\activate`
    -   Mac/Linux: `source venv/bin/activate`

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Run the application:**
    ```bash
    python app.py
    ```

5.  **View the demo:**
    Open [http://localhost:5000](http://localhost:5000) in your browser.

## Embed Instructions

To embed the upload widget on another site:

1.  Include the script:
    ```html
    <script src="http://your-server-url/static/widget.js"></script>
    ```

2.  Add the container div where you want the widget to appear:
    ```html
    <div id="docupload-widget"></div>
    ```
