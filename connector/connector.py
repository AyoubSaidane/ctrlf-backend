from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io
import os
import pickle
import json

class GoogleDriveConnector:
    def __init__(self, extensions=None):
        """Initialize the Google Drive connector with read-only scope."""
        self.SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
        self.creds = None
        # Required for local OAuth testing
        os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
        self.config = self._load_config()
        self.extensions = self._get_mime_types(extensions)
        self.service = build('drive', 'v3', credentials=self._authenticate())

    def _load_config(self):
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        with open(config_path, 'r') as f:
            return json.load(f)
        
    def _get_mime_types(self, extensions):
        if extensions is None:
            return None
        extension_map = self.config["drive_api"]["extension"]
        return [extension_map[ext] for ext in extensions if ext in extension_map]

    def _authenticate(self):
        """
        Handle the OAuth2 flow for Google Drive authentication.
        This will:
        1. Load existing credentials from token.pickle if available
        2. Refresh expired credentials if possible
        3. Create new credentials via OAuth2 flow if needed
        """
        # Try to load existing credentials
        if os.path.exists('connector/token.pickle'):
            with open('connector/token.pickle', 'rb') as token:
                self.creds = pickle.load(token)

        # If no valid credentials available, authenticate user
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'connector/credentials.json', 
                    self.SCOPES
                )
                self.creds = flow.run_local_server(port=8080)
                
                # Save credentials for future use
                with open('connector/token.pickle', 'wb') as token:
                    pickle.dump(self.creds, token)

        return self.creds

    def list_files(self):
        """
        List files in Google Drive, optionally filtered by type.
        Args:
            file_types: List of MIME types to filter by (e.g., ['application/pdf'])
        Returns:
            List of file metadata dictionaries
        """
        
        query = None
        if self.extensions:
            query = " or ".join(f"mimeType='{mime}'" for mime in self.extensions)
            
        try:
            fields = ",".join(self.config['drive_api']['fields'])
            results = self.service.files().list(
                q=query,
                fields=f"files({fields})"
            ).execute()
            return results.get('files', [])
        
        except Exception as e:
            print(f"Error listing files: {e}")
            return []
        
    def download_file(self, file_id):
        """
        Download a file from Google Drive and return its content as bytes.
        Args:
            file_id: The ID of the file in Google Drive
        Returns:
            BytesIO object containing the file content
        """
       
        request = self.service.files().get_media(fileId=file_id)
        
        file_content = io.BytesIO()
        downloader = MediaIoBaseDownload(file_content, request)
        
        done = False
        while not done:
            _, done = downloader.next_chunk()
            
        file_content.seek(0)
        return file_content

    def get_experts(self, file):
        result = []
        for owner in file['owners']:
            result.append({
                'name':owner['displayName'],
                'email':owner['emailAddress'],
                'image':owner['photoLink']
            })
        return result
    
    def get_file_path(self, files, file_id, current_path=None):
        """
        Find the path of a file based on its ID.
        
        Args:
            files (list): List of file objects with their metadata
            file_id (str): ID of the file to find
            current_path (list, optional): Current path being explored. Defaults to None.
        
        Returns:
            str: Full path of the file if found, None otherwise
        """
        if current_path is None:
            current_path = []
        
        # Search for the file in the current level
        for file in files:
            if file['id'] == file_id:
                # Found the file, return its path
                path_elements = current_path + [file['name']]
                return '/'.join(path_elements)
            
            # If this is a folder, search inside it
            if file['mimeType'] == 'application/vnd.google-apps.folder':
                # Create a list of files that are children of this folder
                folder_id = file['id']
                folder_children = [f for f in files if 'parents' in f and folder_id in f['parents']]
                
                # Recursively search in this folder
                nested_path = self.get_file_path(
                    folder_children, 
                    file_id, 
                    current_path + [file['name']]
                )
                
                if nested_path:
                    return nested_path
        
        # File not found
        return None

    def get_file(self, files, file):
        return {
            'content':self.download_file(file['id']),
            'metadata':{
                'file_id':file['id'],
                'file_type':file['mimeType'],
                'file_name':file['name'],
                'file_path':self.get_file_path(files, file['id']),
                'file_size':file['size'],
                'creation_date':file['createdTime'],
                'last_modified_date':file['modifiedTime'],
                'experts':self.get_experts(file),
                'url' : file['webViewLink']
            }
        }
    

if __name__ == '__main__':
    """Example usage of the GoogleDriveConnector."""
    connector = GoogleDriveConnector(['pdf', 'pptx', 'docx'])
    files = connector.list_files()
    if not files:
        print('No files found.')
    else:    
        for file in files:
            print(connector.get_file(files, file))
        