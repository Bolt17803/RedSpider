
import fitz  # PyMuPDF

def extract_text_from_pdf(pdf_path):
    """
    Extracts text from a PDF file using PyMuPDF.

    Args:
        pdf_path (str): The path to the PDF file.

    Returns:
        str: The extracted text from the PDF.
    """
    text = ""
    try:
        doc = fitz.open(pdf_path)
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text += page.get_text()
        doc.close()
    except Exception as e:
        print(f"Error extracting text from {pdf_path}: {e}")
    return text

if __name__ == '__main__':
    # Example usage:
    # Create a dummy PDF for testing
    try:
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "This is the first page.")
        page = doc.new_page()
        page.insert_text((72, 72), "This is the second page.")
        doc.save("dummy.pdf")
        doc.close()

        extracted_text = extract_text_from_pdf("dummy.pdf")
        print("Extracted Text:\n", extracted_text)
    except Exception as e:
        print(f"Error creating or processing dummy PDF: {e}")
