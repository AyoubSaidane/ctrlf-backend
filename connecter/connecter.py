from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import os, json, io


class GoogleDriveConnecter:
    def __init__(self, service_account_file,extensions=None):
        """Initialize the Google Drive connecter with read-only scope."""
        self.SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
        self.SERVICE_ACCOUNT_FILE = service_account_file
        self.creds = service_account.Credentials.from_service_account_file(
            self.SERVICE_ACCOUNT_FILE, scopes=self.SCOPES
        )
        self.service = build('drive', 'v3', credentials=self.creds)
        self.config = self._load_config()
        self.extensions = self._extension_map(extensions)
        self.fields = ",".join(self.config['drive_api']['fields']) 

    def _load_config(self):
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        with open(config_path, 'r') as f:
            return json.load(f)
    
    def _extension_map(self, extensions):
        if extensions is None:
            return None
        extension_map = self.config["drive_api"]["extension"]
        return [extension_map[ext] for ext in extensions if ext in extension_map]

    def list_files(self):
        query = None
        if self.extensions:
            query = " or ".join(f"mimeType='{mime}'" for mime in self.extensions)
            
        try:
            results = self.service.files().list(
                q=query,
                fields=f"files({self.fields})",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True
            ).execute()
            return results.get('files', [])
        
        except Exception as e:
            print(f"Error listing files: {e}")
            return []
        
    def fetch_file_data(self, files, file):
        return {
            'content':self.get_file_content(file['id'],file['mimeType']),
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

    def get_file_content(self, file_id, mime_type):
        # Check if it's a Google native format
        if mime_type.startswith('application/vnd.google-apps.'):
            # Export the file instead of direct download
            request = self.service.files().export(fileId=file_id, mimeType='application/pdf')
        else:
            # Regular file, use standard get_media
            request = self.service.files().get_media(fileId=file_id)
        
        file_content = io.BytesIO()
        downloader = MediaIoBaseDownload(file_content, request)
        
        done = False
        while not done:
            _, done = downloader.next_chunk()
            
        file_content.seek(0)
        return file_content
    
    def get_experts(self, file):
        return [{
                'name':file['lastModifyingUser']['displayName'],
                'image':file['lastModifyingUser']['photoLink']
            }]
    
    def get_file_path(self, files, file_id, current_path=None):
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



if __name__ == '__main__':
    """Example usage of the GoogleDriveConnecter."""
    connecter = GoogleDriveConnecter(service_account_file = 'connecter/service-account.json', extensions = ['pdf', 'pptx', 'docx','gdoc','gslides'])
    files = connecter.list_files()
    if not files:
        print('No files found.')
    else:    
        for file in files:
            print(connecter.fetch_file_data(files, file))