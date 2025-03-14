import requests
import msal
import os
import json

def _load_config(config_file):
    """Load configuration from a JSON file"""
    try:
        file_path = os.path.join(os.path.dirname(__file__), config_file)
        with open(file_path, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        print(f"Error: Config file not found at {file_path}")
        return None
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON format in {file_path}")
        return None
    
# Usage example
config_path = "credentials.json"
config = _load_config(config_path)

# App registration details
APP_NAME = config["APP_NAME"]
CLIENT_ID = config["CLIENT_ID"]
SITE_NAME = config["SITE_NAME"]
TENANT_NAME = config["TENANT_NAME"]

ADMIN_CLIENT_ID = config["ADMIN_CLIENT_ID"]
ADMIN_CLIENT_SECRET = config["ADMIN_CLIENT_SECRET"]
ADMIN_TENANT_ID = config["ADMIN_TENANT_ID"]


# Check if environment variables are set
if not ADMIN_CLIENT_ID or not ADMIN_CLIENT_SECRET or not ADMIN_TENANT_ID:
    raise ValueError("Missing required environment variables. Ensure CLIENT_ID, CLIENT_SECRET, and TENANT_ID are set.")

# Azure AD authority URL
authority = f"https://login.microsoftonline.com/{ADMIN_TENANT_ID}"

# Create a confidential client application
app = msal.ConfidentialClientApplication(
    ADMIN_CLIENT_ID, 
    authority=authority,
    client_credential=ADMIN_CLIENT_SECRET
)

# Acquire token for application
scopes = ["https://graph.microsoft.com/.default"]
result = app.acquire_token_for_client(scopes=scopes)

# Check if token acquisition was successful
if "access_token" not in result:
    print(f"Error acquiring token: {result.get('error')}")
    print(f"Error description: {result.get('error_description')}")
    exit(1)

access_token = result['access_token']
print("Token acquired successfully")

headers = {
    'Authorization': f'Bearer {access_token}',
    'Content-Type': 'application/json'
}


# Get site ID
site_url = f"https://graph.microsoft.com/v1.0/sites/{TENANT_NAME}.sharepoint.com:/sites/{SITE_NAME}"
site_response = requests.get(site_url, headers=headers)

if site_response.status_code == 200:
    site_data = site_response.json()
    site_id = site_data["id"]
    print(f"Site ID retrieved: {site_id}")
else:
    print(f"Error retrieving site ID: {site_response.status_code}")
    print(f"Response: {site_response.text}")
    exit(1)




# Ask for permission to access the site
permissions_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/permissions"
permissions_payload = {
    "roles": ["read"],
    "grantedToIdentities": [{
        "application": {
            "id": CLIENT_ID,
            "displayName": APP_NAME
        }
    }]
}

print(f"Requesting permissions for application {APP_NAME} with ID {CLIENT_ID}...")
permissions_response = requests.post(permissions_url, headers=headers, json=permissions_payload)

if permissions_response.status_code == 201:
    print("Permissions granted successfully")
elif permissions_response.status_code == 403:
    print("Warning: Not authorized to grant permissions. You may need admin consent.")
else:
    print(f"Error requesting permissions: {permissions_response.status_code}")
    print(f"Response: {permissions_response.text}")
    # Continue execution even if permissions request failed