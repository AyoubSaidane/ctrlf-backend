from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import os, json, io


class GoogleDriveConnecter:
    def __init__(self, credentials_file,extensions=None):
        """Initialize the Google Drive connecter with read-only scope."""
        self.SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(__file__), credentials_file)
        self.creds = service_account.Credentials.from_service_account_file(
            self.SERVICE_ACCOUNT_FILE, scopes= ['https://www.googleapis.com/auth/drive.readonly']
        )
        self.service = build('drive', 'v3', credentials=self.creds)
        self.config = self._load_json("config.json")
        self.extensions = self._extension_map(extensions)
        self.fields = ",".join(self.config['drive_api']['fields']) 

    def _load_json(self, config_file):
        config_path = os.path.join(os.path.dirname(__file__), config_file)
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

        files = []
        page_token = None

        try:
            while True:
                results = self.service.files().list(
                    q=query,
                    fields=f"nextPageToken, files({self.fields})",
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                    pageToken=page_token
                ).execute()

                files.extend(results.get('files', []))
                page_token = results.get('nextPageToken')

                if not page_token:  # No more pages
                    break

            print(len(files), 'files found')
            return files

        except Exception as e:
            print(f"Error listing files: {e}")
            return []

        
    def fetch_file_data(self, files, file):
        print('Processing file:', file['name'])
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

    # def get_file_content(self, file_id, mime_type):  # 50MB chunks
    #     import time
    #     start_time = time.time()
        
    #     try:
    #         # Check if file is cached
    #         cache_path = os.path.join('cache', file_id)
    #         os.makedirs('cache', exist_ok=True)
            
    #         # Check if we have a recent cached version
    #         if os.path.exists(cache_path):
    #             file_stat = os.stat(cache_path)
    #             # Use cache if file is less than 1 hour old
    #             if (time.time() - file_stat.st_mtime) < 3600:  
    #                 with open(cache_path, 'rb') as f:
    #                     content = io.BytesIO(f.read())
    #                     print(f"File loaded from cache in {time.time() - start_time:.2f} seconds")
    #                     return content
        
    #         # Check if it's a Google native format
    #         if mime_type.startswith('application/vnd.google-apps.'):
    #             request = self.service.files().export(fileId=file_id, mimeType='application/pdf')
    #         else:
    #             request = self.service.files().get_media(fileId=file_id)
            
    #         file_content = io.BytesIO()
    #         downloader = MediaIoBaseDownload(file_content, request)
            
    #         done = False
    #         while not done:
    #             _, done = downloader.next_chunk()
                
    #         file_content.seek(0)
            
    #         # Cache the downloaded file
    #         with open(cache_path, 'wb') as f:
    #             f.write(file_content.getvalue())
                
    #         print(f"File downloaded in {time.time() - start_time:.2f} seconds")
    #         return file_content
            
    #     except Exception as e:
    #         print(f"Error downloading file {file_id}: {str(e)}")
    #         raise

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
    connecter = GoogleDriveConnecter(credentials_file = 'service-account.json', extensions = ['pdf', 'pptx', 'docx','gdoc','gslides'])
    files = connecter.list_files()
    if not files:
        print('No files found.')
    else:    
        for file in files:
            print(connecter.fetch_file_data(files, file))
            break