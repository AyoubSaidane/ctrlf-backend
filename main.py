from googledrive.connecter import GoogleDriveConnecter
from rag.mistral_parser import MistralParser
from rag.indexer import Indexer
from llama_index.llms.gemini import Gemini
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import nest_asyncio
from fastapi.middleware.cors import CORSMiddleware
from llama_index.postprocessor.cohere_rerank import CohereRerank
from llama_index.core.response.pprint_utils import pprint_response
from dotenv import load_dotenv
import base64
import os
import time
load_dotenv()


cohere_api_key = os.getenv("COHERE_API_KEY")

# Apply nest_asyncio to allow nested async event loops
nest_asyncio.apply()

class Query(BaseModel):
    message: str

app = FastAPI(title="Probe API")

# Add this near the top of your file after creating the FastAPI app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)



@app.get("/connect", status_code=200)
async def connection_endpoint():
    try:
        # Set up database connection
        import sqlite3
        from datetime import datetime
        
        # Create or connect to SQLite database
        conn = sqlite3.connect(f"{os.getenv("COLLECTION_NAME")}.db")
        cursor = conn.cursor()
        
        # Create table if it doesn't exist
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS processed_documents (
            document_id TEXT PRIMARY KEY,
            file_name TEXT,
            last_modified_date TEXT,
            processed_date TEXT
        )
        ''')
        conn.commit()
        
        # connect to Google Drive and parse files
        connecter = GoogleDriveConnecter(credentials_file = 'googledrive/service-account.json', extensions = ['pdf', 'pptx', 'docx','gdoc','gslides'])
        files = connecter.list_files()
        parser = MistralParser()
        indexer = Indexer()
        
        files_processed = 0
        files_skipped = 0
        
        for file in files:
            file_id = file.get('id')
            file_name = file.get('name')
            last_modified = file.get('modifiedTime', '')
            
            # Check if file exists in database and is unchanged
            cursor.execute(
                "SELECT last_modified_date FROM processed_documents WHERE document_id = ?", 
                (file_id,)
            )
            result = cursor.fetchone()
            
            # Process file if it's new or modified
            if not result or result[0] != last_modified:
                print(f"Processing file: {file_name} (new or modified)")
                data = connecter.fetch_file_data(files, file)
                file_chunks = parser.parse(data)
                indexer.index_from_chunks(file_chunks)
                
                # Update or insert record in database
                now = datetime.now().isoformat()
                cursor.execute(
                    '''INSERT OR REPLACE INTO processed_documents 
                    (document_id, file_name, last_modified_date, processed_date) 
                    VALUES (?, ?, ?, ?)''',
                    (file_id, file_name, last_modified, now)
                )
                conn.commit()
                files_processed += 1
            else:
                print(f"Skipping file: {file_name} (unchanged)")
                files_skipped += 1
        
        # Commit database changes
        conn.commit()
        conn.close()
        
        
        if not files:
            return {"message": "No files found."}
        else:
            print(f"Processed {files_processed} new/modified files, skipped {files_skipped} unchanged files.")
            return {
                "message": f"Successfully connected to Google Drive. Processed {files_processed} new/modified files, skipped {files_skipped} unchanged files."
            }
        
    except Exception as e:
        print(f"Error in connection_endpoint: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

  
@app.post("/query", status_code=200)
async def query_endpoint(query: Query):
    try:
        # Step 0: Connect to Google Drive and retrieve index
        connect_start_time = time.time()
        connecter = GoogleDriveConnecter(credentials_file = 'googledrive/service-account.json', extensions = ['pdf', 'pptx', 'docx','gdoc','gslides'])
        global index
        indexer = Indexer()
        index = indexer.retrieve_index()
        connect_end_time = time.time()
        print(f"Index retrieval took {connect_end_time - connect_start_time:.2f} seconds")
        
        # Step 1: Retrieve relevant documents using the retriever with Cohere postprocessor
        query_start_time = time.time()
        cohere_rerank = CohereRerank(api_key=cohere_api_key, top_n=3)
        query_engine = index.as_query_engine(
            similarity_top_k=10,
            node_postprocessors=[cohere_rerank],
        )
        response = query_engine.query(query.message)
        query_end_time = time.time()
        print(f"Query execution took {query_end_time - query_start_time:.2f} seconds")
    
        # Step 2: Format retrieved documents for the LLM
        format_start_time = time.time()
        retrieved_nodes = response.source_nodes
        documents = []
        experts_map = {} 
        for retrieved_node in retrieved_nodes:
            node = retrieved_node.node
            score = retrieved_node.score
            metadata = node.metadata
            print(f"Retrieved document {metadata.get("file_name")} page number:{metadata.get("page_number")}, with similarity {score}")
            
            doc = {
                "title": metadata.get("file_name", "Untitled"),
                "url": metadata.get("url", ""),
                "page": metadata.get("page_number", ""),
                "array_buffer": base64.b64encode(connecter.get_file_content(metadata.get("file_id"), metadata.get("file_type")).getvalue()).decode('ascii'),
            }
            documents.append(doc)
            
            # Process experts and associate them with documents
            expert_list = metadata.get("experts", [])
            for expert in expert_list:
                name = expert.get("name")
                if name not in experts_map:
                    # Create new expert entry with documents list
                    experts_map[name] = {
                        "name": name,
                        "email": expert.get("email", ""),
                        "image": expert.get("image", ""),
                        "documents": [doc["title"]]
                    }
                else:
                    # Add document to existing expert if not already there
                    if doc["title"] not in experts_map[name]["documents"]:
                        experts_map[name]["documents"].append(doc["title"])

        # Convert experts map to list
        experts = list(experts_map.values())       
        # Return formatted response
        print(response.response)
        message = {
            "response":{
                "text": response.response,
                "documents": documents,
                "experts": experts
            }
        }  
        format_end_time = time.time()
        print(f"Format response took {format_end_time - format_start_time:.2f} seconds")   
        return message
    
    except Exception as e:
        print(f"Error in query_endpoint: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="localhost", port=8000, reload=True)