import google.generativeai as genai
import PIL.Image
import io
import tempfile
import os
import fitz
from dotenv import load_dotenv
load_dotenv()

class GeminiParser:
    def __init__(self):
        """
        Initializes the ConsultingDocumentOCR class.

        Args:
            api_key: Your Gemini API key.
        """
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        self.model = genai.GenerativeModel('gemini-2.0-flash-001')

    def parse(self, data):
        """
        Performs OCR on a consulting document from file content.

        Args:
            file_content: A BytesIO object containing the file content.
            mime_type: The MIME type of the file.

        Returns:
            The extracted text as a string, or None if an error occurs.
        """
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
                        image = PIL.Image.open(io.BytesIO(img_bytes))
                        images.append(image)
                finally:
                    doc.close()
                    os.unlink(temp_pdf_path) # delete temp pdf
            else:
                # Handle image files directly
                image = PIL.Image.open(file_content)
                images = [image]
            chunks = []
            all_extracted_text = ""
            ocr_prompt = """
                        You are an advanced Optical Character Recognition (OCR) system specialized in extracting text from documents commonly used by consulting firms. Your primary goal is to provide clean, error-free text output, paying close attention to the specific formats and terminology found in these documents.

                        **Instructions:**

                        1.  **Input:** You will receive an image of a document from a consulting firm. This may include:
                            * Project proposals
                            * Client reports
                            * Financial statements
                            * Contracts
                            * Presentations
                            * Meeting minutes
                            * Spreadsheets
                            * Internal memos
                        2.  **Output:** Provide the extracted text in plain text format.
                        3.  **Accuracy:** Prioritize accuracy, especially with numerical data, technical terms, and client names. Consulting documents often contain precise information that must be captured correctly.
                        4.  **Formatting:**
                            * Maintain the original line breaks and paragraph structure.
                            * Pay close attention to tables and lists, which are common in consulting documents. Represent them in a readable plain text format (e.g., using tabs or spaces for alignment).
                            * If the document contains headers, bolded text, or other formatting elements, represent them as best as possible in plain text. For example, add asterisks around bolded text.
                            * Specifically, if the document contains spreadsheet like data, attempt to represent it in a CSV like format, separating columns with commas.
                        5.  **Language:** Identify the language of the text in the image and output the text in that language.
                        6.  **Terminology:** Be aware that consulting documents often contain industry-specific terminology and acronyms. Attempt to recognize and accurately transcribe these terms.
                        7.  **Numerical Data:** Pay extra attention to the accuracy of numerical data, including financial figures, percentages, and dates.
                        8.  **Client Information:** Treat client names and sensitive information with care. Ensure accurate transcription.
                        9.  **Clarity:** If the image quality is poor or the text is unclear, attempt to decipher the text based on context and common consulting practices. If uncertain, add a note within brackets, e.g., "[uncertain word]".
                        10. **Conciseness:** Provide only the extracted text. Do not add any introductory or explanatory text.
                    """
            description_prompt = """
                you are parsing this slide to later be used in a RAG system. It will be used by consultants, so adapt to their language, tone, and needs. You need to give me a high level overview of the slides content and layout.
                give me an exhaustive description of the slide provided. Start by describing it at a high level: what the main topic is, what the layout looks like, what elements are there, where each element is located, and the relationships between these elements.
            """
            page_number = 1
            for image in images:
                text = self.model.generate_content([ocr_prompt, image])
                description = self.model.generate_content([description_prompt, image])
                all_extracted_text += text.text + "\n"
                chunk = {
                    "text": text.text,
                    "description":description.text,
                    "summary": "",
                    "metadata": {
                        **data['metadata'],
                        "page_number":page_number,
                    }
                }
                chunks.append(chunk)
                page_number += 1

            resume_prompt = f"""
                write a breif summary of the document {all_extracted_text}
            """
            resume = self.model.generate_content(resume_prompt)
            for chunk in chunks:
                chunk["summary"] = resume.text

            return chunks

        except Exception as e:
            print(f"An error occurred: {e}")
            return None

if __name__ == "__main__":
    from connecter.connecter import GoogleDriveConnecter
    connecter = GoogleDriveConnecter(service_account_file = 'connecter/service-account.json', extensions = ['pdf', 'pptx', 'docx','gdoc','gslides'])
    parser = GeminiParser()
    files = connecter.list_files()
    for file in files:
        data = connecter.fetch_file_data(files, file)
        print(parser.parse(data))
        break
