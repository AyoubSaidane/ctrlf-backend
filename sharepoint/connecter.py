import requests
import msal
import os
import json
import io


class SharePointConnecter:
    def __init__(self, credentials_file, extensions=None):
        self.credentials = self._load_json(credentials_file)
        self.extensions = extensions
        self.access_token = self._get_access_token()
        self.site_id = self._get_site_id()
        self.drive_id = self._get_drive_id()

    def _load_json(self, config_file):
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

    def _get_access_token(self):
        # App registration details
        CLIENT_ID = self.credentials["CLIENT_ID"]
        CLIENT_SECRET = self.credentials["CLIENT_SECRET"]
        TENANT_ID = self.credentials["TENANT_ID"]

        # Check if environment variables are set
        if not CLIENT_ID or not CLIENT_SECRET or not TENANT_ID:
            raise ValueError("Missing required environment variables. Ensure CLIENT_ID, CLIENT_SECRET, and TENANT_ID are set.")

        # Create a confidential client application
        app = msal.ConfidentialClientApplication(
            CLIENT_ID, 
            authority=f"https://login.microsoftonline.com/{TENANT_ID}",
            client_credential=CLIENT_SECRET
        )

        # Acquire token for application
        result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])

        # Check if token acquisition was successful
        if "access_token" not in result:
            print(f"Error acquiring token: {result.get('error')}")
            print(f"Error description: {result.get('error_description')}")
            exit(1)

        access_token = result['access_token']
        print("Token acquired successfully")
        return access_token
    
    def _get_site_id(self):
        TENANT_NAME = self.credentials["TENANT_NAME"]
        SITE_NAME = self.credentials["SITE_NAME"]

        site_response = requests.get(
            f"https://graph.microsoft.com/v1.0/sites/{TENANT_NAME}.sharepoint.com:/sites/{SITE_NAME}",
            headers={
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
        )

        if site_response.status_code != 200:
            print(f"Error getting specific site: {site_response.status_code}")
            print(f"Response: {site_response.text}")
            exit(1)

        site_data = site_response.json()
        site_id = site_data.get('id')

        if not site_id:
            print("Could not retrieve site ID")
            exit(1)
        return site_id

    def _get_drive_id(self):  
        # Get document libraries in the site
        drive_url = f"https://graph.microsoft.com/v1.0/sites/{self.site_id}/drives"
        drives_response = requests.get(
            drive_url,
            headers={
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
        )

        if drives_response.status_code != 200:
            print(f"Error getting drives: {drives_response.status_code}")
            print(f"Response: {drives_response.text}")
            exit(1)

        drives_data = drives_response.json()
        if drives_data.get('value'):
            drive_id = drives_data['value'][0]['id']
        return drive_id
    
    def list_files(self, folder_id="root", all_files=None):
        if all_files is None:
            all_files = []
            
        # Get items in the current folder
        response = requests.get(
            f"https://graph.microsoft.com/v1.0/drives/{self.drive_id}/items/{folder_id}/children", 
            headers={
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
        )

        if response.status_code != 200:
            print(f"Error listing files in folder {folder_id}: {response.status_code}")
            print(f"Response: {response.text}")
            return all_files

        items = response.json().get('value', [])
        for item in items:
            if "folder" in item:
                # Recursively process subfolders
                self.list_files(item["id"], all_files)
            else:
                # Check if file matches the extension filter (if provided)
                file_name = item.get("name", "")
                if not self.extensions or any(file_name.lower().endswith(f".{ext.lower()}") for ext in self.extensions):
                    all_files.append(item)
        
        return all_files

    def fetch_file_data(self, files, file):
        print('Processing file:', file.get("name"))
        return {
            'content': self.get_file_content(file.get("id")),
            'metadata': {
                'file_id': file.get("id"),
                'file_type': file.get("file", {}).get("mimeType", "unknown"),
                'file_name': file.get("name"),
                'file_path': self.get_file_path(files, file),
                'file_size': file.get("size", 0),
                'creation_date': file.get("createdDateTime", "Unknown"),
                'last_modified_date': file.get("lastModifiedDateTime", "Unknown"),
                'experts': self.get_experts(file),
                'url': file.get("webUrl", "Unknown")
            }
        }

    def get_file_content(self, file_id):
        """
        Downloads a file from OneDrive/SharePoint. Handles different file types appropriately.

        :param file_id: The ID of the file in OneDrive/SharePoint.
        :param drive_id: The ID of the drive containing the file.
        :param mime_type: The MIME type of the file.
        :return: File content in bytes.
        """
        # Use the correct URL format for SharePoint site drives
        file_url = f"https://graph.microsoft.com/v1.0/drives/{self.drive_id}/items/{file_id}/content"
        
        # Set specific headers for content download - remove Content-Type
        download_headers = {
            'Authorization': f'Bearer {self.access_token}'
        }
        
        response = requests.get(file_url, headers=download_headers, stream=True)

        if response.status_code != 200:
            print(f"Error downloading file {file_id}: {response.status_code}")
            print(f"Response: {response.text}")
            return None

        # Use a larger chunk size for better performance (1MB)
        file_content = io.BytesIO()
        for chunk in response.iter_content(chunk_size=1024*1024):
            if chunk:  # Filter out keep-alive chunks
                file_content.write(chunk)

        file_content.seek(0)
        return file_content

    def get_experts(self, file_metadata):
        """
        Retrieves the last modifying user of a file.

        :param file_metadata: Metadata of the file (from Microsoft Graph API).
        :return: List containing the name and profile picture of the last modifying user.
        """
        last_modifier = file_metadata.get("lastModifiedBy", {}).get("user", {})
        
        return [{
            'name': last_modifier.get("displayName", ""),
            'mail': last_modifier.get("email", ""),
            'image': last_modifier.get("@odata.id", "")  # No direct image API, needs a workaround
        }]
    
    def get_file_path(self, files, file):
        # Extract the relative path from parentReference.path
        parent_path = file.get('parentReference', {}).get('path', '')
        
        # The path is typically in the format: /drives/{driveId}/root:/path/to/folder
        # We want to extract just the "/path/to/folder" part
        if ':' in parent_path:
            relative_path = parent_path.split(':')[-1]
        else:
            relative_path = ''
        
        # Combine the relative path with the filename
        file_name = file.get('name', '')
        if relative_path:
            return f"{relative_path}/{file_name}"
        else:
            return file_name

if __name__ == '__main__':
    """Example usage of the GoogleDriveConnecter."""
    connecter = SharePointConnecter(credentials_file = 'credentials.json', extensions = ['pdf', 'docx', 'pptx'])
    files = connecter.list_files()
    if not files:
        print('No files found.')
    else:    
        for file in files:
            print(connecter.fetch_file_data(files, file))