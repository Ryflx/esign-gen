import streamlit as st
import os
import re
import logging
from datetime import datetime
from docusign_esign import (
    ApiClient, EnvelopesApi, EnvelopeDefinition, TemplateRole, Text, Tabs, FormulaTab,
    DocGenFormField, DocGenFormFields, DocGenFormFieldRequest, DocGenFormFieldRowValue, Envelope
)
from dotenv import load_dotenv
from docusign_auth import DocuSignAuth
import webbrowser
from urllib.parse import parse_qs, urlparse
import json

# Load environment variables
load_dotenv()

# Configure logging
log_directory = "logs"
if not os.path.exists(log_directory):
    os.makedirs(log_directory)

log_filename = os.path.join(log_directory, f"api_{datetime.now().strftime('%Y%m%d')}.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def serialize_for_logging(obj):
    """Convert objects to JSON-serializable format"""
    if hasattr(obj, 'to_dict'):
        return obj.to_dict()
    elif hasattr(obj, '__dict__'):
        return obj.__dict__
    elif isinstance(obj, (list, tuple)):
        return [serialize_for_logging(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: serialize_for_logging(v) for k, v in obj.items()}
    return str(obj)

# Define products and their prices
PRODUCTS = {
    "Basic Service": 100,
    "Premium Service": 250,
    "Enterprise Solution": 500
}

# Initialize DocuSign authentication
auth_handler = DocuSignAuth()

def log_api_call(method, endpoint, request_data=None, response_data=None, error=None):
    """Log API call details"""
    try:
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "method": method,
            "endpoint": endpoint,
            "request": serialize_for_logging(request_data) if request_data else None,
            "response": serialize_for_logging(response_data) if response_data else None,
            "error": str(error) if error else None
        }
        logger.info(f"API Call: {json.dumps(log_entry, indent=2)}")
    except Exception as e:
        logger.error(f"Failed to log API call: {str(e)}")

def is_valid_email(email):
    """Check if email is valid"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def handle_callback():
    """Handle the OAuth callback"""
    if 'code' in st.query_params:
        code = st.query_params['code']
        try:
            token_data = auth_handler.get_token_from_code(code)
            st.session_state.token_data = token_data
            st.session_state.authenticated = True
            st.success("Successfully authenticated with DocuSign!")
            logger.info("Successfully authenticated with DocuSign")
            # Clear query parameters
            st.query_params.clear()
        except Exception as e:
            error_msg = f"Authentication failed: {str(e)}"
            logger.error(error_msg)
            st.error(error_msg)

def check_token():
    """Check and refresh token if necessary"""
    if 'token_data' in st.session_state:
        token_data = st.session_state.token_data
        if not auth_handler.is_token_valid(token_data):
            try:
                new_token_data = auth_handler.refresh_token(token_data['refresh_token'])
                st.session_state.token_data = new_token_data
                logger.info("Token refreshed successfully")
            except Exception as e:
                error_msg = f"Token refresh failed: {str(e)}"
                logger.error(error_msg)
                st.error(error_msg)
                st.session_state.authenticated = False
                return False
        return True
    return False

def get_envelope_documents(api_client, envelope_id):
    """Get the list of documents in an envelope"""
    try:
        endpoint = f'/v2.1/accounts/{os.getenv("DOCUSIGN_ACCOUNT_ID")}/envelopes/{envelope_id}/documents'
        log_api_call("GET", endpoint)
        
        response = api_client.call_api(
            endpoint,
            'GET',
            response_type='object'
        )
        log_api_call("GET", endpoint, response_data=response[0])
        return response[0]
    except Exception as e:
        error_msg = f"Failed to get envelope documents: {str(e)}"
        log_api_call("GET", endpoint, error=e)
        st.error(error_msg)
        return None

def get_doc_gen_fields(api_client, envelope_id):
    """Get existing document generation fields"""
    try:
        doc_gen_endpoint = f'/v2.1/accounts/{os.getenv("DOCUSIGN_ACCOUNT_ID")}/envelopes/{envelope_id}/docGenFormFields'
        log_api_call("GET", doc_gen_endpoint)
        
        response = api_client.call_api(
            doc_gen_endpoint,
            'GET',
            response_type='object'
        )
        log_api_call("GET", doc_gen_endpoint, response_data=response[0])
        return response[0]
    except Exception as e:
        error_msg = f"Failed to get doc gen fields: {str(e)}"
        log_api_call("GET", doc_gen_endpoint, error=e)
        logger.error(error_msg)
        return None

def update_doc_gen_fields(api_client, envelope_id):
    """Update document generation fields with product information"""
    try:
        # First, get existing doc gen fields
        existing_fields = get_doc_gen_fields(api_client, envelope_id)
        if not existing_fields:
            error_msg = "Failed to retrieve existing doc gen fields"
            logger.error(error_msg)
            st.error(error_msg)
            return False

        document_id_guid = existing_fields['docGenFormFields'][0]['documentId']

        # Store existing non-product fields
        existing_non_product_fields = []
        for field in existing_fields['docGenFormFields'][0].get('docGenFormFieldList', []):
            if field.get('name') != 'Product':
                existing_non_product_fields.append(field)

        # Create the doc gen form fields request with both existing and new fields
        doc_gen_form_field_request = DocGenFormFieldRequest(
            doc_gen_form_fields=[
                DocGenFormFields(
                    document_id=document_id_guid,
                    doc_gen_form_field_list=[
                        *existing_non_product_fields,  # Preserve existing non-product fields
                        DocGenFormField(
                            name="Product",
                            type="TableRow",
                            row_values=[
                                DocGenFormFieldRowValue(
                                    doc_gen_form_field_list=[
                                        DocGenFormField(
                                            name="ProductName",
                                            value=product
                                        ),
                                        DocGenFormField(
                                            name="Price",
                                            value=f"${PRODUCTS[product]}"
                                        )
                                    ]
                                ) for product in st.session_state.selected_products
                            ]
                        )
                    ]
                )
            ]
        )

        # Log the request data
        doc_gen_endpoint = f'/v2.1/accounts/{os.getenv("DOCUSIGN_ACCOUNT_ID")}/envelopes/{envelope_id}/docGenFormFields'
        log_api_call("PUT", doc_gen_endpoint, request_data=doc_gen_form_field_request)

        # Update the doc gen form fields
        response = api_client.call_api(
            doc_gen_endpoint,
            'PUT',
            header_params={'Content-Type': 'application/json'},
            body=doc_gen_form_field_request,
            response_type='object'
        )
        log_api_call("PUT", doc_gen_endpoint, response_data=response)
        return True
    except Exception as e:
        error_msg = f"Failed to update doc gen fields: {str(e)}"
        log_api_call("PUT", doc_gen_endpoint, error=e)
        st.error(error_msg)
        return False

def send_template():
    """Send template with populated fields"""
    try:
        # Validate email
        if not is_valid_email(st.session_state.email):
            logger.warning(f"Invalid email address attempted: {st.session_state.email}")
            st.error("Please enter a valid email address")
            return

        # Initialize API client
        api_client = ApiClient()
        api_client.host = "https://demo.docusign.net/restapi"
        api_client.set_default_header("Authorization", f"Bearer {st.session_state.token_data['access_token']}")

        # Create template role with tabs
        signer = TemplateRole(
            email=st.session_state.email.strip(),
            name=st.session_state.name.strip(),
            role_name="Signer",
            tabs=Tabs(
                formula_tabs=[
                    FormulaTab(
                        font="helvetica",
                        font_size="size11",
                        tab_label="TotalAmount",
                        formula=str(st.session_state.amount),
                        round_decimal_places="0",
                        required="true",
                        locked="true",
                        disable_auto_size="false"
                    )
                ],
                text_tabs=[
                    Text(
                        tab_label="prod",
                        value=", ".join(st.session_state.selected_products)
                    )
                ]
            )
        )

        # Create envelope definition (as draft)
        envelope_definition = EnvelopeDefinition(
            status="created",
            template_id="8a2d4788-2a61-4c0a-ad70-97498e0154de",
            template_roles=[signer]
        )

        # Create draft envelope
        envelopes_api = EnvelopesApi(api_client)
        
        create_envelope_endpoint = f'/v2.1/accounts/{os.getenv("DOCUSIGN_ACCOUNT_ID")}/envelopes'
        log_api_call("POST", create_envelope_endpoint, request_data=envelope_definition)
        
        envelope_summary = envelopes_api.create_envelope(
            account_id=os.getenv('DOCUSIGN_ACCOUNT_ID'),
            envelope_definition=envelope_definition
        )
        log_api_call("POST", create_envelope_endpoint, response_data=envelope_summary)

        # Update doc gen fields
        if update_doc_gen_fields(api_client, envelope_summary.envelope_id):
            # Create an Envelope instance for the update
            send_envelope = Envelope(
                status="sent",
                template_id="8a2d4788-2a61-4c0a-ad70-97498e0154de",
                template_roles=[signer]
            )
            
            update_envelope_endpoint = f'/v2.1/accounts/{os.getenv("DOCUSIGN_ACCOUNT_ID")}/envelopes/{envelope_summary.envelope_id}'
            log_api_call("PUT", update_envelope_endpoint, request_data=send_envelope)
            
            envelope_summary = envelopes_api.update(
                account_id=os.getenv('DOCUSIGN_ACCOUNT_ID'),
                envelope_id=envelope_summary.envelope_id,
                envelope=send_envelope
            )
            log_api_call("PUT", update_envelope_endpoint, response_data=envelope_summary)
            
            logger.info(f"Template sent successfully! Envelope ID: {envelope_summary.envelope_id}")
            st.success(f"Template sent successfully! Envelope ID: {envelope_summary.envelope_id}")
        else:
            error_msg = "Failed to send template due to doc gen fields update failure"
            logger.error(error_msg)
            st.error(error_msg)

    except Exception as e:
        error_msg = f"Failed to send template: {str(e)}"
        logger.error(error_msg)
        st.error(error_msg)

def main():
    st.title("DocuSign Integration")
    st.write("Welcome to the DocuSign Integration App")

    # Initialize session state
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'selected_products' not in st.session_state:
        st.session_state.selected_products = []
    if 'amount' not in st.session_state:
        st.session_state.amount = 0
    if 'product_selections' not in st.session_state:
        st.session_state.product_selections = {product: False for product in PRODUCTS}

    # Check for callback
    if not st.session_state.authenticated:
        if 'code' in st.query_params:
            handle_callback()

    # Load existing token
    if not st.session_state.authenticated:
        token_data = auth_handler.load_token()
        if token_data and auth_handler.is_token_valid(token_data):
            st.session_state.token_data = token_data
            st.session_state.authenticated = True
            logger.info("Loaded existing valid token")

    # Main application logic
    if not st.session_state.authenticated:
        st.warning("Not authenticated with DocuSign")
        if st.button("Connect to DocuSign"):
            consent_url = auth_handler.get_consent_url()
            webbrowser.open(consent_url)
            logger.info("Opening DocuSign consent URL")
            st.info("Please complete the authentication in the opened browser window.")
    else:
        if check_token():
            st.success("Connected to DocuSign")
            
            # Display token information
            token_data = st.session_state.token_data
            with st.expander("View Token Information"):
                st.json({
                    "access_token": token_data['access_token'][:20] + "...",
                    "expires_in": token_data['expires_in'],
                    "token_type": token_data['token_type']
                })

            # Template sending form
            st.subheader("Send Template")
            st.session_state.email = st.text_input("Recipient Email")
            st.session_state.name = st.text_input("Recipient Name")

            # Product selection using checkboxes
            st.subheader("Select Products/Services")
            for product, price in PRODUCTS.items():
                st.session_state.product_selections[product] = st.checkbox(
                    f"{product} (${price})",
                    value=st.session_state.product_selections.get(product, False)
                )
            
            # Update selected products and amount based on checkbox selections
            st.session_state.selected_products = [
                product for product, selected in st.session_state.product_selections.items()
                if selected
            ]
            st.session_state.amount = sum(PRODUCTS[product] for product in st.session_state.selected_products)
            
            # Display the total amount (read-only)
            st.text(f"Total Amount: ${st.session_state.amount}")

            if st.button("Send Template"):
                if not st.session_state.email or not st.session_state.name:
                    logger.warning("Attempted to send template with missing required fields")
                    st.error("Please fill in all required fields")
                elif not st.session_state.selected_products:
                    logger.warning("Attempted to send template with no products selected")
                    st.error("Please select at least one product")
                else:
                    send_template()

            if st.button("Disconnect"):
                # Delete the token file
                auth_handler.delete_token()
                # Clear session state
                st.session_state.authenticated = False
                st.session_state.token_data = None
                logger.info("User disconnected from DocuSign")
                st.rerun()

if __name__ == "__main__":
    main()
