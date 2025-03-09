from connecter.connecter import GoogleDriveConnecter
from rag.parser import Parser
from rag.indexer import Indexer
from llama_index.llms.gemini import Gemini
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import nest_asyncio
from fastapi.middleware.cors import CORSMiddleware

# Apply nest_asyncio to allow nested async event loops
nest_asyncio.apply()

class Query(BaseModel):
    message: str
counter = 0  
print(counter)
app = FastAPI(title="CtrlF API")

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
    global counter
    counter = 0
    try:
        # connect to Google Drive and parse files
        connecter = GoogleDriveConnecter(service_account_file = 'connecter/service-account.json', extensions = ['pdf', 'pptx', 'docx','gdoc','gslides'])
        files = connecter.list_files()
        parser = Parser()
        global all_data
        all_data = []
        for file in files:
            data = connecter.fetch_file_data(files, file)
            file_chunks = parser.parse_bytes_io(data)
            all_data.extend(file_chunks)
        global index
        indexer = Indexer()
        index = indexer.index_document(all_data)
        if not files:
            return {"message": "No files found."}
        else:
            return {"message": "Successfully connected to Google Drive."}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

  
@app.post("/query", status_code=200)
async def query_endpoint(query: Query):
    try:
        # retrieve the index and run the query
        global index
        indexer = Indexer()
        index = indexer.retrieve_index()
        
        # Step 1: Retrieve relevant documents using the retriever
        retriever = index.as_retriever(similarity_top_k=20)
        retrieved_nodes = retriever.retrieve(query.message)
       
        # Step 2: Format retrieved documents for the LLM
        doc_texts = []
        documents = []
        experts_map = {} 
        for retrieved_node in retrieved_nodes:
            node = retrieved_node.node
            score = retrieved_node.score
            metadata = node.metadata
            print(f"Retrieved document {metadata.get("file_name")}:{metadata.get("page_number")}, with score {score}")
            text = node.text
            doc_texts.append(text)
            
            doc = {
                "title": metadata.get("file_name", "Untitled"),
                "url": metadata.get("url", ""),
                "page": metadata.get("page_number", "")
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
        
        context = "\n\n".join(doc_texts)
        
        # Step 3: Set up the LLM to generate a structured response
        
        llm = Gemini(model="models/gemini-2.0-flash")
        
        # Step 4: Create prompt for the LLM
        prompt = f"""
            You are a helpful assistant that provides accurate information based on provided documents.
            
            USER QUERY: {query.message}
            
            RETRIEVED DOCUMENTS:
            {context}
            
            Using ONLY the information from the retrieved documents, provide a comprehensive answer to the query.
            If the documents don't contain relevant information to answer the query, admit that you don't have enough information.
            
            Format your response as follows:
            
            [Your detailed answer to the query]
        """
        
        # Step 5: Generate structured response
        structured_response = llm.complete(prompt).text
        print(f"Structured response: {structured_response}")
        # Return formatted response
        message = {
            "response":{
                "text": structured_response,
                "documents": documents
            }
        }     
        
        return message
    
    except Exception as e:
        print(f"Error in query_endpoint: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="localhost", port=8000, reload=True)