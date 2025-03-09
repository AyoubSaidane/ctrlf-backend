from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from dotenv import load_dotenv
import os

class Indexer:
    def __init__(self):
        load_dotenv()
        
        self.QDRANT_URL = os.getenv("QDRANT_URL")
        self.QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
        self.COLLECTION_NAME = os.getenv("COLLECTION_NAME", "base_demo")
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

        # Initialize Qdrant client
        self.qdrant_client = QdrantClient(
            url=self.QDRANT_URL,
            api_key=self.QDRANT_API_KEY,
        )
        
        self.embed_model = OpenAIEmbedding(model="text-embedding-ada-002", api_key=self.OPENAI_API_KEY)
        self.vector_store = QdrantVectorStore(
            client=self.qdrant_client,
            collection_name=self.COLLECTION_NAME,
        )
        
        self.storage_context = StorageContext.from_defaults(vector_store=self.vector_store)

    def index_document(self, documents):
        index = VectorStoreIndex.from_documents(
            documents,
            storage_context=self.storage_context, 
            embed_model=self.embed_model,
            include_metadata=True
        )
        print("✅ Documents successfully indexed and stored in Qdrant!")
        return index
    
    def retrieve_index(self):
        # Retrieve the index from the storage context
        index = VectorStoreIndex.from_vector_store(
            vector_store=self.vector_store,
            embed_model=self.embed_model
        )
        print("✅ Index successfully retrieved from Qdrant!")
        return index

# Example usage:
if __name__ == "__main__":
    from rag.parser import Parser
    parser = Parser()
    indexer = Indexer()
    docs = parser.parse_document('PDF_002_Media_in_NYC_2012.pdf')
    index = indexer.index_document(docs)