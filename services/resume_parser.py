import os
import re

class ResumeParser:
    @staticmethod
    def extract_text(file_path):
        """
        Extracts clean text from PDF, DOCX, or TXT file.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        ext = os.path.splitext(file_path)[1].lower()

        if ext == '.pdf':
            return ResumeParser._extract_from_pdf(file_path)
        elif ext in ['.docx', '.doc']:
            return ResumeParser._extract_from_docx(file_path)
        elif ext == '.txt':
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return ResumeParser._clean_text(f.read())
        else:
            raise ValueError(f"Unsupported file format: {ext}")

    @staticmethod
    def _extract_from_pdf(file_path):
        text_parts = []
        try:
            import pypdf
            reader = pypdf.PdfReader(file_path)
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
        except Exception as e:
            # Fallback to pdfplumber if installed
            try:
                import pdfplumber
                with pdfplumber.open(file_path) as pdf:
                    for page in pdf.pages:
                        txt = page.extract_text()
                        if txt:
                            text_parts.append(txt)
            except Exception:
                raise RuntimeError(f"Failed to extract PDF text: {str(e)}")

        raw_text = "\n".join(text_parts)
        return ResumeParser._clean_text(raw_text)

    @staticmethod
    def _extract_from_docx(file_path):
        try:
            import docx
            doc = docx.Document(file_path)
            text_parts = []
            for p in doc.paragraphs:
                if p.text.strip():
                    text_parts.append(p.text)
            for table in doc.tables:
                for row in table.rows:
                    row_txt = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                    if row_txt:
                        text_parts.append(row_txt)
            return ResumeParser._clean_text("\n".join(text_parts))
        except Exception as e:
            raise RuntimeError(f"Failed to extract DOCX text: {str(e)}")

    @staticmethod
    def _clean_text(text):
        if not text:
            return ""
        # Normalize Unicode spaces and linebreaks
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        # Replace multiple spaces with a single space
        text = re.sub(r'[ \t]+', ' ', text)
        # Collapse excessive newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()
