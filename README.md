# Flask API Template

![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)
![Flask](https://img.shields.io/badge/flask-%3E=2.0-green.svg)
![License](https://img.shields.io/badge/license-AGPLv3-blue.svg)
![CI](https://img.shields.io/github/actions/workflow/status/<your-username>/flask_api_template/ci.yml?branch=main)
![Coverage](https://img.shields.io/badge/coverage-pytest-yellow.svg)
![Docker](https://img.shields.io/badge/docker-ready-blue.svg)

A minimalist, production-ready template to quickly build a RESTful API using Flask.  
This repository provides a solid foundation for your next API project, with environment-based configuration, Docker support, migrations, and a full OpenAPI 3.0 specification.

---

## Features

- **Environment-based configuration**: Easily switch between development, testing, staging, and production using the `FLASK_ENV` environment variable.
- **RESTful API**: CRUD endpoints for a sample resource (`Dummy`), plus endpoints for version, configuration, import/export.
- **OpenAPI 3.0 documentation**: See [`openapi.yml`](openapi.yml).
- **Docker-ready**: Includes a `Dockerfile` and healthcheck script.
- **Database migrations**: Managed with Alembic/Flask-Migrate.
- **Testing**: Pytest-based test suite.
- **Logging**: Colored logging for better readability.

---

## Environments

The application behavior is controlled by the `FLASK_ENV` environment variable.  
Depending on its value, different configuration classes and `.env` files are loaded:

- **development** (default):  
  Loads `.env.development` and uses `app.config.DevelopmentConfig`.  
  Debug mode is enabled.

- **testing**:  
  Loads `.env.test` and uses `app.config.TestingConfig`.  
  Testing mode is enabled.

- **staging**:  
  Loads `.env.staging` and uses `app.config.StagingConfig`.  
  Debug mode is enabled.

- **production**:  
  Loads `.env.production` and uses `app.config.ProductionConfig`.  
  Debug mode is disabled.

See `app/config.py` for details.  
You can use `env.example` as a template for your environment files.

---

## API Endpoints

The main endpoints are:

| Method | Path             | Description                         |
|--------|------------------|-------------------------------------|
| GET    | /version         | Get API version                     |
| GET    | /config          | Get current app configuration       |
| GET    | /dummies         | List all dummy items                |
| POST   | /dummies         | Create a new dummy item             |
| GET    | /dummies/{id}    | Get a dummy item by ID              |
| PUT    | /dummies/{id}    | Replace a dummy item by ID          |
| PATCH  | /dummies/{id}    | Partially update a dummy by ID      |
| DELETE | /dummies/{id}    | Delete a dummy item by ID           |
| GET    | /export/csv      | Export all dummies as CSV           |
| POST   | /import/csv      | Import dummies from a CSV file      |
| POST   | /import/json     | Import dummies from a JSON file     |

See [`openapi.yml`](openapi.yml) for full documentation and schema details.

---

## Project Structure

```
.
├── app
│   ├── config.py
│   ├── __init__.py
│   ├── logger.py
│   ├── models.py
│   ├── resources
│   │   ├── config.py
│   │   ├── dummy.py
│   │   ├── export_to.py
│   │   ├── import_from.py
│   │   ├── __init__.py
│   │   └── version.py
│   ├── routes.py
│   └── schemas.py
├── CODE_OF_CONDUCT.md
├── Dockerfile
├── env.example
├── LICENSE
├── migrations
│   ├── alembic.ini
│   ├── env.py
│   ├── README
│   └── script.py.mako
├── openapi.yml
├── pytest.ini
├── README.md
├── requirements-dev.txt
├── requirements.txt
├── run.py
├── tests
│   ├── conftest.py
│   ├── __init__.py
│   ├── test_api.py
│   ├── test_init.py
│   ├── test_run.py
│   └── test_wsgi.py
├── TODO
├── wait-for-it.sh
└── wsgi.py
```

---

## Usage

### Local Development

1. Copy `env.example` to `.env.development` and set your variables.
2. Install dependencies:
   ```
   pip install -r requirements-dev.txt
   ```
3. Run database migrations:
   ```
   flask db upgrade
   ```
4. Start the server:
   ```
   FLASK_ENV=development python run.py
   ```

### Docker

Build and run the container:
```
docker build -t flask-api-template .
docker run --env-file .env.development -p 5000:5000 flask-api-template
```

### Testing

Run all tests with:
```
pytest
```

---

## License

This project is licensed under the GNU AGPLv3.

---

## Code of Conduct

See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
