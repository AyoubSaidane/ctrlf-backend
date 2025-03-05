from llama_cloud_services import LlamaParse
from llama_index.core import SimpleDirectoryReader
from dotenv import load_dotenv
import os
import time
import tempfile

class Parser:
    def __init__(self):
        load_dotenv()
        self.llama_cloud_api_key = os.getenv("LLAMA_CLOUD_API_KEY")
        self.parser = self._initialize_parser()
        
    def _initialize_parser(self):
        return LlamaParse(
            api_key=self.llama_cloud_api_key,
            use_vendor_multimodal_model=True,
            vendor_multimodal_model_name="gemini-2.0-flash-001",
            system_prompt_append="give me an exhaustive description of every chart. Include everything: layout, text, images, graphs, etc. You also need to give me an explanation of the slide: what is the overall message that is conveyed.",
            result_type="markdown",
            
        )
    
    def parse_document(self, file_path):
        file_extractor = {os.path.splitext(file_path)[1]: self.parser}
        chunks = SimpleDirectoryReader(
            input_files=[file_path],
            file_extractor=file_extractor
        ).load_data()
        
        # Extraire et incrémenter le numéro de page à partir du doc_id
        for chunk in chunks:
            try:
                page_str = chunk.doc_id.split('_')[-1]
                chunk.metadata['page_number'] = int(page_str) + 1
            except (ValueError, IndexError):
                print(f"Warning: Could not extract page number from doc_id: {chunk.doc_id}")
                chunk.metadata['page_number'] = 0
        
        print(f"Parsed {len(chunks)} chunks for document {file_path}")
        
        return chunks
    
    def list_all_files(self, directory):
        all_files = []
        for root, _, files in os.walk(directory):
            for file in files:
                all_files.append(os.path.join(root, file))
        return all_files

    def parse_directory(self, directory):
        file_paths = self.list_all_files(directory)
        documents = []
        
        start_time = time.time()  # Start timer
        
        for file_path in file_paths:
            documents += self.parse_document(file_path)
        
        end_time = time.time()  # End timer
        elapsed_time = end_time - start_time
        print(f"Parsing the directory took {elapsed_time:.2f} seconds.")
        
        return documents

    def preview_text(self, documents, preview_length=500):
        return documents[0].text[:preview_length]
    
    def parse_bytes_io(self, data):
        """
        Parse a document from a BytesIO object
        
        Args:
            data (dict): Dictionary containing 'content' (BytesIO) and 'metadata'
        
        Returns:
            List of chunks from the parsed document
        """
        # Extract content and metadata
        bytes_io_content = data['content']
        cloud_metadata = data['metadata']
        file_name = cloud_metadata['file_name']
        file_type = cloud_metadata['file_type']
        
        # Determine appropriate file extension
        if file_type.startswith('application/vnd.google-apps.'):
            # For Google Workspace files, use .pdf since they're exported as PDF
            file_extension = '.pdf'
            temp_file_name = f"{os.path.splitext(file_name)[0]}.pdf"
        else:
            # For regular files, use the original extension
            file_extension = os.path.splitext(file_name)[1]
            temp_file_name = file_name
            
            # If extension is unusual or not supported, default to PDF
            supported_extensions = ['.pdf', '.doc', '.docx', '.ppt', '.pptx', '.txt', '.html', '.xlsx', '.xls', '.csv']
            if not file_extension or file_extension not in supported_extensions:
                print(f"Warning: Unusual file extension '{file_extension}' for file '{file_name}'. Treating as PDF.")
                file_extension = '.pdf'
                temp_file_name = f"{os.path.splitext(file_name)[0]}.pdf"
        
        temp_dir = tempfile.gettempdir()
        temp_file_path = os.path.join(temp_dir, temp_file_name)
        
        try:
            # Write content to the temporary file
            with open(temp_file_path, 'wb') as temp_file:
                bytes_io_content.seek(0)  # Ensure we're at the start of the BytesIO
                temp_file.write(bytes_io_content.read())
            
            # Parse the temporary file
            file_extractor = {file_extension: self.parser}

            chunks = SimpleDirectoryReader(
                input_files=[temp_file_path],
                file_extractor=file_extractor,
                filename_as_id=True
            ).load_data()
            
            # Extract and increment page number from doc_id
            for chunk in chunks:
                try:
                    page_str = chunk.doc_id.split('_')[-1]
                    chunk.metadata = cloud_metadata
                    chunk.metadata['page_number'] = int(page_str) + 1
                except (ValueError, IndexError):
                    print(f"Warning: Could not extract page number from doc_id: {chunk.doc_id}")
                    chunk.metadata['page_number'] = 0
            
            print(f"Parsed {len(chunks)} chunks for document {file_name}")
            
            return chunks
        except Exception as e:
            print(f"Error parsing file '{file_name}' with type '{file_type}': {e}")
            # Return an empty list instead of failing completely
            return []
        finally:
            # Clean up the temporary file
            if os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                except Exception as e:
                    print(f"Warning: Could not remove temporary file {temp_file_path}: {e}")


if __name__ == "__main__":
    from connector.connector import GoogleDriveConnector
    connector = GoogleDriveConnector(['pdf', 'pptx', 'docx'])
    parser = Parser()
    files = connector.list_files()
    if not files:
        print('No files found.')
    else:    
        for file in files:
            data = connector.get_file(files, file)
            chunks = parser.parse_bytes_io(data)
            print(chunks[0].text[:500])