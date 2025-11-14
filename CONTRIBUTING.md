# Contributing to Basic IO Service

Thank you for your interest in contributing to the **Basic IO Service**!

> **Note**: This service is part of the larger [Waterfall](../../README.md) project. For the overall development workflow, branch strategy, and contribution guidelines, please refer to the [main CONTRIBUTING.md](../../CONTRIBUTING.md) in the root repository.

## Table of Contents

- [Service Overview](#service-overview)
- [Development Setup](#development-setup)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [API Development](#api-development)
- [Data Import/Export](#data-importexport)
- [Common Tasks](#common-tasks)

## Service Overview

The **Basic IO Service** handles core business data operations including import/export functionality:

- **Technology Stack**: Python 3.13+, Flask 3.1+, SQLAlchemy, PostgreSQL
- **Port**: 5004 (containerized) / 5000 (standalone)
- **Responsibilities**:
  - Core business entity CRUD operations
  - Data import from JSON and CSV
  - Data export to JSON and CSV
  - Batch data processing
  - Data validation and transformation
  - Integration with other services

**Key Dependencies:**
- Flask 3.1+ for REST API
- SQLAlchemy for ORM
- Pandas for data processing
- Marshmallow for validation
- PostgreSQL for data persistence

## Development Setup

### Prerequisites

- Python 3.13+
- PostgreSQL 16+ (or use Docker)
- pip and virtualenv

### Local Setup

```bash
# Navigate to service directory
cd services/basic_io_service

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Copy environment configuration
cp env.example .env.development
```

### Environment Configuration

```bash
# Flask environment
FLASK_ENV=development
LOG_LEVEL=DEBUG

# Database
DATABASE_URL=postgresql://basic_io_user:basic_io_pass@localhost:5432/basic_io_dev

# External services
STORAGE_SERVICE_URL=http://localhost:5005
INTERNAL_AUTH_TOKEN=dev-internal-secret

# Security
JWT_SECRET=dev-jwt-secret

# Data processing
MAX_UPLOAD_SIZE=10485760  # 10MB
ALLOWED_EXTENSIONS=json,csv
```

### Running the Service

```bash
# Development mode
python run.py

# Production-style
gunicorn -w 4 -b 0.0.0.0:5000 wsgi:app
```

## Coding Standards

### Python Style Guide

Follow **PEP 8** with Black formatting:

```bash
# Format code
black app/ tests/

# Check quality
pylint app/ tests/

# Sort imports
isort app/ tests/
```

### Data Processing Conventions

**CSV Handling:**
```python
import pandas as pd
from io import StringIO

def parse_csv_data(csv_content: str) -> pd.DataFrame:
    """Parse CSV content into DataFrame.
    
    Args:
        csv_content: CSV content as string
    
    Returns:
        Pandas DataFrame with parsed data
    
    Raises:
        ValueError: If CSV is malformed
    """
    try:
        df = pd.read_csv(StringIO(csv_content))
        # Validate required columns
        required_cols = ['name', 'email']
        missing = set(required_cols) - set(df.columns)
        if missing:
            raise ValueError(f"Missing columns: {missing}")
        return df
    except Exception as e:
        raise ValueError(f"Invalid CSV format: {e}")
```

**JSON Validation:**
```python
from marshmallow import Schema, fields, validate

class BulkImportSchema(Schema):
    """Schema for bulk data import."""
    
    format = fields.Str(
        required=True,
        validate=validate.OneOf(['json', 'csv'])
    )
    data = fields.Raw(required=True)
    options = fields.Dict(
        keys=fields.Str(),
        values=fields.Raw(),
        missing={}
    )
    
    @validates('data')
    def validate_data(self, value):
        """Validate data based on format."""
        format_type = self.context.get('format')
        if format_type == 'json' and not isinstance(value, (list, dict)):
            raise ValidationError("JSON data must be list or dict")
```

### Type Hints

```python
from typing import List, Dict, Any, Union
from pandas import DataFrame

def process_import_data(
    data: Union[str, List[Dict], Dict],
    format: str,
    validate_only: bool = False
) -> Dict[str, Any]:
    """Process imported data.
    
    Args:
        data: Data to import (CSV string or JSON structure)
        format: Data format ('json' or 'csv')
        validate_only: If True, only validate without importing
    
    Returns:
        Dictionary with import results including:
        - total: Total records processed
        - success: Successfully imported
        - errors: List of errors
    """
    results = {
        'total': 0,
        'success': 0,
        'errors': []
    }
    # Implementation
    return results
```

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific tests
pytest tests/test_import.py -v
pytest tests/test_export.py -v
```

### Test Structure

```python
import pytest
import pandas as pd
from app.services.import_service import ImportService

class TestDataImport:
    """Test suite for data import functionality."""
    
    @pytest.fixture
    def sample_csv(self):
        """Sample CSV data for testing."""
        return """name,email,company
John Doe,john@example.com,ACME Corp
Jane Smith,jane@example.com,TechCo"""
    
    @pytest.fixture
    def sample_json(self):
        """Sample JSON data for testing."""
        return [
            {"name": "John Doe", "email": "john@example.com", "company": "ACME Corp"},
            {"name": "Jane Smith", "email": "jane@example.com", "company": "TechCo"}
        ]
    
    def test_import_csv_success(self, client, sample_csv):
        """Test successful CSV import."""
        response = client.post('/import', json={
            'format': 'csv',
            'data': sample_csv
        })
        
        assert response.status_code == 200
        data = response.json
        assert data['total'] == 2
        assert data['success'] == 2
        assert len(data['errors']) == 0
    
    def test_import_json_validation_error(self, client):
        """Test JSON import with validation errors."""
        invalid_data = [
            {"name": "John", "email": "invalid-email"},  # Invalid email
        ]
        
        response = client.post('/import', json={
            'format': 'json',
            'data': invalid_data
        })
        
        assert response.status_code == 200
        data = response.json
        assert data['success'] == 0
        assert len(data['errors']) > 0
```

## API Development

### Import Endpoint

```python
# app/resources/import_data.py
from flask import Blueprint, request, jsonify
from app.services.import_service import ImportService
from app.logger import logger

import_bp = Blueprint('import', __name__)

@import_bp.route('/import', methods=['POST'])
def import_data():
    """Import data from JSON or CSV.
    
    Request Body:
        {
            "format": "csv",  // or "json"
            "data": "...",    // CSV string or JSON array/object
            "options": {
                "validate_only": false,
                "skip_duplicates": true,
                "batch_size": 100
            }
        }
    
    Response:
        {
            "total": 100,
            "success": 95,
            "errors": [
                {"row": 10, "error": "Invalid email"},
                {"row": 25, "error": "Duplicate entry"}
            ]
        }
    """
    try:
        data = request.get_json()
        
        service = ImportService()
        results = service.process_import(
            data=data['data'],
            format=data['format'],
            options=data.get('options', {})
        )
        
        return jsonify(results), 200
        
    except Exception as e:
        logger.error(f"Import error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 400
```

### Export Endpoint

```python
@export_bp.route('/export', methods=['POST'])
def export_data():
    """Export data to JSON or CSV.
    
    Request Body:
        {
            "format": "csv",
            "entity": "users",
            "filters": {
                "company_id": 5,
                "active": true
            },
            "fields": ["id", "name", "email"]  // optional
        }
    
    Response:
        Content-Type: text/csv or application/json
        Content-Disposition: attachment; filename="users_export.csv"
    """
    data = request.get_json()
    
    service = ExportService()
    content, content_type, filename = service.export_data(
        entity=data['entity'],
        format=data['format'],
        filters=data.get('filters', {}),
        fields=data.get('fields')
    )
    
    return Response(
        content,
        mimetype=content_type,
        headers={'Content-Disposition': f'attachment; filename="{filename}"'}
    )
```

## Data Import/Export

### CSV Export

```python
import pandas as pd
from io import StringIO

def export_to_csv(data: List[Dict], fields: Optional[List[str]] = None) -> str:
    """Export data to CSV format.
    
    Args:
        data: List of dictionaries to export
        fields: Optional list of fields to include
    
    Returns:
        CSV content as string
    """
    df = pd.DataFrame(data)
    
    if fields:
        # Select and order specified fields
        df = df[fields]
    
    # Convert to CSV
    output = StringIO()
    df.to_csv(output, index=False)
    return output.getvalue()
```

### JSON Export

```python
import json

def export_to_json(data: List[Dict], pretty: bool = True) -> str:
    """Export data to JSON format.
    
    Args:
        data: List of dictionaries to export
        pretty: If True, format with indentation
    
    Returns:
        JSON content as string
    """
    if pretty:
        return json.dumps(data, indent=2, ensure_ascii=False)
    return json.dumps(data, ensure_ascii=False)
```

### Batch Processing

```python
def batch_import(data: List[Dict], batch_size: int = 100) -> Dict:
    """Import data in batches for better performance.
    
    Args:
        data: List of records to import
        batch_size: Number of records per batch
    
    Returns:
        Import results summary
    """
    results = {'total': len(data), 'success': 0, 'errors': []}
    
    for i in range(0, len(data), batch_size):
        batch = data[i:i + batch_size]
        
        try:
            # Process batch
            imported = import_batch(batch)
            results['success'] += len(imported)
            
        except Exception as e:
            results['errors'].append({
                'batch': i // batch_size,
                'error': str(e)
            })
    
    return results
```

## Common Tasks

### Data Validation

```python
from marshmallow import Schema, fields, validates, ValidationError

class EntitySchema(Schema):
    """Schema for entity validation."""
    
    name = fields.Str(required=True)
    email = fields.Email(required=True)
    
    @validates('email')
    def validate_unique_email(self, value):
        """Check if email already exists."""
        from app.models import Entity
        if Entity.query.filter_by(email=value).first():
            raise ValidationError("Email already exists")
```

### Error Handling in Imports

```python
def safe_import_record(record: Dict, row_number: int) -> tuple:
    """Safely import a single record with error handling.
    
    Returns:
        (success: bool, error: Optional[str])
    """
    try:
        # Validate
        validated = schema.load(record)
        
        # Import
        entity = Entity(**validated)
        db.session.add(entity)
        db.session.commit()
        
        return (True, None)
        
    except ValidationError as e:
        return (False, f"Row {row_number}: Validation error - {e.messages}")
    except Exception as e:
        db.session.rollback()
        return (False, f"Row {row_number}: {str(e)}")
```

## Service-Specific Guidelines

### File Upload Limits

```python
from flask import current_app

@before_request
def check_file_size():
    """Validate upload size before processing."""
    content_length = request.content_length
    max_size = current_app.config.get('MAX_UPLOAD_SIZE', 10485760)
    
    if content_length and content_length > max_size:
        abort(413, description=f"File too large. Max size: {max_size} bytes")
```

### Data Transformation

```python
def transform_data(data: Dict, mapping: Dict[str, str]) -> Dict:
    """Transform data using field mapping.
    
    Args:
        data: Source data dictionary
        mapping: Field name mapping (source -> target)
    
    Returns:
        Transformed data dictionary
    """
    transformed = {}
    for source_field, target_field in mapping.items():
        if source_field in data:
            transformed[target_field] = data[source_field]
    return transformed
```

## Getting Help

- **Main Project**: See [root CONTRIBUTING.md](../../CONTRIBUTING.md)
- **Issues**: Use GitHub issues with `service:basic-io` label
- **Code of Conduct**: [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- **Documentation**: [README.md](README.md)

---

**Remember**: Always refer to the [main CONTRIBUTING.md](../../CONTRIBUTING.md) for branch strategy, commit conventions, and pull request process!
