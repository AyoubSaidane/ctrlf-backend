# Google Drive Connector

This project provides a connector to interact with Google Drive, allowing you to list, download, and retrieve metadata for files.

## Getting Started

### Prerequisites

- Python 3.6 or higher
- `google-auth`, `google-auth-oauthlib`, `google-auth-httplib2`, `google-api-python-client`

You can install the required packages using pip:

```sh
pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client
```

### Setting Up Google Drive API

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project or select an existing project.
3. Navigate to the **OAuth consent screen** tab and configure the consent screen if you haven't already.
4. Go to the **Credentials** tab and click on **Create Credentials**.
5. Select **OAuth 2.0 Client IDs**.
6. Configure the OAuth consent screen and set the application type to **Desktop app**.
7. Download the JSON file containing your credentials and save it as `credentials.json` in the `connector` directory.

### Running the Connector

You can run the connector using the following command:

```sh
python connector.py
```

This will list the files in your Google Drive based on the specified extensions and print their metadata.

### Example Usage

```python
if __name__ == '__main__':
    connector = GoogleDriveConnector(['pdf', 'pptx', 'docx'])
    files = connector.list_files()
    if not files:
        print('No files found.')
    else:    
        for file in files:
            print(connector.get_file(files, file))
```

This example initializes the connector to filter files with extensions `pdf`, `pptx`, and `docx`, lists the files, and prints their metadata.
