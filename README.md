## StockPlayground

### Mock application for stock trading

This project is a mock of stock trading application built with Flask. It is intended for portfolio purposes and demonstrates a variety of features typical of a stock trading platform. The application use market data from Finnhub.io.


### Features

- User registration and login with hashed passwords
- Stock quote lookup
- Buying and selling stocks
- Viewing portfolio and transaction history
- Adding cash to the account
- Simple captcha verification using hCaptcha
- Data persistence using SQLAlchemy and SQLite

### Project Structure
    .
    ├── app.py                # Main application file
    ├── helpers.py            # Helper functions
    ├── templates/            # HTML templates
    ├── static/               # Static files (CSS, images)
    ├── requirements.txt      # Python dependencies
    ├── gunicorn.conf.py      # Gunicorn configuration
    ├── Dockerfile            # Docker configuration with gunicorn
    ├── docker-compose.yml    # Docker Compose configuration with nginx
    ├── nginx/
         └── nginx.conf        # Nginx configuration file

### Running Locally

1. Clone the repository:

    ```bash
    git clone https://github.com/rafalkk/StockPlayground.git
    ```

2. Install the required dependencies:

    ```bash
    pip install -r requirements.txt

3. Set the required environment variables:

    linux bash:

        export API_KEY=your-key
        export HCAPTCHA_SECRET_KEY=your-key
        export CAPTCHA_SITE_KEY=your-key
    windows powershell:

        $env:API_KEY='your-key'
        $env:HCAPTCHA_SECRET_KEY='your-key'
        $env:HCAPTCHA_SITE_KEY='your-key'

3. Run the application:

    ```bash
    flask run
    ```

The application will be available at `http://127.0.0.1:5000`.

### Running with Docker Compose and Nginx
1. Ensure you have Docker and Docker Compose installed.
2. Use the provided `docker-compose.yml` file. Do not forget to fill in the keys of the APIs in the file.

    ```bash
    docker-compose up -d
    ```

This will set up the application with Nginx as a reverse proxy, making it accessible at default http port 80 `http://127.0.0.1`.