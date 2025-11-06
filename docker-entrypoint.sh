#!/bin/bash
set -e

# Mark that we're running in a container
export IN_DOCKER_CONTAINER=true

# Wait for database if needed
if [ "$WAIT_FOR_DB" = "true" ]; then
    /wait-for-it.sh db_service:5432 -t 120 --strict
fi

# Run database migrations if needed
if [ "$RUN_MIGRATIONS" = "true" ]; then
    echo "Running database migrations..."
    flask db upgrade
fi

# Determine how to run the application
case "$APP_MODE" in
    "production")
        echo "Starting application with Gunicorn..."
        exec gunicorn --bind 0.0.0.0:5000 --workers 4 --timeout 60 wsgi:app
        ;;
    "staging"|"development")
        echo "Starting application with Python development server..."
        exec python run.py
        ;;
    *)
        echo "Unknown APP_MODE: $APP_MODE. Defaulting to development mode."
        exec python run.py
        ;;
esac