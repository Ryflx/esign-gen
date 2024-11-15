# DocuSign Integration Application

A Streamlit-based application that handles DocuSign authentication and token management.

## Setup

1. Create a Python virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up DocuSign Developer Account:
   - Go to [DocuSign Developer Center](https://developers.docusign.com/)
   - Create a new application
   - Note down the Integration Key (Client ID) and Secret Key
   - Add `http://localhost:8501/callback` to the allowed redirect URIs

4. Configure environment variables:
   - Copy `.env.example` to `.env`
   - Fill in your DocuSign credentials:
     - DOCUSIGN_CLIENT_ID
     - DOCUSIGN_CLIENT_SECRET
     - DOCUSIGN_ACCOUNT_ID
     - Other configuration values can remain as default for development

## Running the Application

1. Ensure your virtual environment is activated
2. Run the Streamlit application:
```bash
streamlit run src/app.py
```

3. The application will open in your default web browser at `http://localhost:8501`

## Features

- DocuSign OAuth authentication
- Automatic token refresh
- Secure token storage
- Token information display

## Project Structure

```
├── docs/
│   └── blueprint.md         # Project blueprint and documentation
├── src/
│   ├── app.py              # Main Streamlit application
│   └── docusign_auth.py    # DocuSign authentication handler
├── .env.example            # Example environment variables
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

## Token Storage

Tokens are stored locally in a `.tokens` directory (created automatically) in JSON format. The storage location can be configured in the `.env` file.

## Security Notes

- Never commit your `.env` file or tokens to version control
- Keep your DocuSign credentials secure
- The application stores tokens locally in an encrypted format
