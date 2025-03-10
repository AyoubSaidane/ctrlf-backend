from qdrant_client import QdrantClient

# Connect to your Qdrant Cloud instance
client = QdrantClient(
    url="https://a0430371-9648-47de-a9d7-4ff7d044ec77.europe-west3-0.gcp.cloud.qdrant.io",  # Replace with your cloud URL
    api_key="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.rOBVNZL7Lj7Dj-7D7_iLAjyBJ8idmP6ZQE6NkZxqMPI",            # Replace with your API key
)

file_names = set()
offset = None

while True:
    records, next_offset = client.scroll(
        collection_name="base_demo",  # replace with your collection name
        offset=offset,
        limit=100,
        with_payload=True,
        with_vectors=False
    )
    
    for record in records:
        file_name = record.payload.get("file_name")  # Replace with your payload key
        if file_name:
            file_names.add(file_name)
    
    if not next_offset:
        break
    offset = next_offset

print("Unique source files in your Qdrant Cloud instance:")
for file in file_names:
    print(file)