import os
import google.generativeai as genai
from pathlib import Path
import sys
current_dir = Path(__file__).resolve().parent
sys.path.append(str(current_dir / '..'))
import io
import base64
from PIL import Image
from dotenv import load_dotenv
load_dotenv()
import fitz
import tempfile
from mistralai import Mistral
from googledrive.connecter import GoogleDriveConnecter
from tqdm import tqdm 

class MistralParser:
    def __init__(self):
        self.ocr_model = Mistral(api_key=os.getenv("MISTRAL_API_KEY"))
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        self.vision_model = genai.GenerativeModel('gemini-2.0-flash-001')

    def parse(self, data):
        try:
            file_content, mime_type = data['content'], data['metadata']['file_type']
            if mime_type == 'application/pdf' or mime_type.startswith('application/vnd.google-apps.'):
                # Handle PDF files
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
                    temp_pdf.write(file_content.getvalue())
                    temp_pdf_path = temp_pdf.name

                try:
                    doc = fitz.open(temp_pdf_path)
                    images = []
                    for page in doc:
                        pix = page.get_pixmap()
                        img_bytes = pix.tobytes("png")
                        image = Image.open(io.BytesIO(img_bytes))
                        images.append(image)
                finally:
                    doc.close()
                    os.unlink(temp_pdf_path) # delete temp pdf
            else:
                # Handle image files directly
                image = Image.open(file_content)
                images = [image]

            image_prompt = """

                You are a document analysis assistant helping me understand content from images I upload.

                Start by giving me a high-level description of the image. Provide a factual description of the visible elements in the image, focusing on:

                For text content:
                - Transcribe the visible text only, formatted in markdown
                - For tables, maintain the structure using markdown table format

                For visual elements:
                - Describe any charts/graphs by type (bar, line, pie, etc.) and key data points shown
                - Note visible logos without making assumptions about brand ownership
                - Describe diagrams, illustrations, or other visual elements objectively

                Guidelines:
                - Only describe what is clearly visible in the image
                - Do not interpret, analyze, or draw conclusions beyond what's explicitly shown
                - Avoid making claims about copyright, ownership, or authorship
                - Provide factual transcription without judgment or commentary
                - If text is partially visible or unclear, indicate this with [unclear] or similar notation

                Here is the image:
            """

            chunks = []
            all_extracted_text = ""
            page_number = 1
            for image in tqdm(images, desc="Processing pages", unit="page"):
                buffered = io.BytesIO()
                image.save(buffered, format="JPEG")
                base64_image = base64.b64encode(buffered.getvalue()).decode('utf-8')

                ocr_response = self.ocr_model.ocr.process(
                    model="mistral-ocr-latest",
                    document={
                        "type": "image_url",
                        "image_url": f"data:image/jpeg;base64,{base64_image}" 
                    },
                    include_image_base64=True
                )

                page = ocr_response.pages[0]
                extracted_text = page.markdown
                all_extracted_text += extracted_text + "\n"
                
                page_images = page.images
                transcribed_images = []
                if len(page_images) > 0:
                    for page_image in page_images:
                        image_base64 = page_image.image_base64
                        filtered_base64 = image_base64.replace('data:image/jpeg;base64,', '')
                        image_content = Image.open(io.BytesIO(base64.b64decode(filtered_base64)))
                        image_description = self.vision_model.generate_content([image_prompt, image_content])
                        transcribed_images.append(image_description.text)
                        all_extracted_text += image_description.text + "\n"
                
                chunk = {
                    "text": extracted_text,
                    "images": transcribed_images,
                    "summary": "",
                    "metadata": {
                        **data['metadata'],
                        "page_number": page_number
                    }
                }
                chunks.append(chunk)
                page_number += 1
                

            resume_prompt = f"""
                You are an expert consultant analysing a slide deck. 
                Give me a high-level summary of this deck: a fact-based description of its content and a quick overview of the message it conveys. 
                Only use information from the deck: do not hallucinate, do not infer anything, do not generate conclusions not clearly stated in the deck.
                here is the content of the slide deck:
                {all_extracted_text}
            """
            resume = self.vision_model.generate_content(resume_prompt)    
            for chunk in chunks:
                chunk["summary"] = resume.text

            return chunks
        except Exception as e:
            print(f"An error occurred: {e}")
            return None    
        


if __name__ == "__main__":
    # from googledrive.connecter import GoogleDriveConnecter
    # from rag.indexer import Indexer
    # indexer = Indexer()
    # connecter = GoogleDriveConnecter(credentials_file = 'service-account.json', extensions = ['pdf', 'pptx', 'docx','gdoc','gslides'])
    # parser = MistralParser()
    # files = connecter.list_files()
    # for file in files:
    #     data = connecter.fetch_file_data(files, file)
    #     chunks = parser.parse(data)
    #     indexer.index_from_chunks(chunks)

    from sharepoint.connecter import SharePointConnecter
    from rag.indexer import Indexer
    indexer = Indexer()
    connecter = SharePointConnecter(credentials_file = 'credentials.json', extensions = ['pdf', 'pptx', 'docx'])
    parser = MistralParser()
    files = connecter.list_files()
    for file in files:
        data = connecter.fetch_file_data(files, file)
        chunks = parser.parse(data)
        print(chunks)
        break


# {
#   "pages": [
#     {
#       "index": 0,
#       "markdown": "string",
#       "images": [
#         {
#           "id": "string",
#           "top_left_x": 0,
#           "top_left_y": 0,
#           "bottom_right_x": 0,
#           "bottom_right_y": 0,
#           "image_base64": "string"
#         }
#       ],
#       "dimensions": {
#         "dpi": 0,
#         "height": 0,
#         "width": 0
#       }
#     }
#   ],
#   "model": "string",
#   "usage_info": {
#     "pages_processed": 0,
#     "doc_size_bytes": 0
#   }
# }
