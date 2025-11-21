import pandas as pd
import PyPDF2
import io
import base64
import json
from PIL import Image
import requests

class DataProcessor:
    """Handle various data processing tasks"""
    
    @staticmethod
    def process_pdf(pdf_content_base64, page_number=None):
        """Extract text and tables from PDF"""
        try:
            pdf_bytes = base64.b64decode(pdf_content_base64)
            pdf_file = io.BytesIO(pdf_bytes)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            
            if page_number is not None:
                # Extract specific page (1-indexed)
                page = pdf_reader.pages[page_number - 1]
                text = page.extract_text()
                return {"page": page_number, "text": text}
            else:
                # Extract all pages
                all_text = []
                for i, page in enumerate(pdf_reader.pages):
                    all_text.append({
                        "page": i + 1,
                        "text": page.extract_text()
                    })
                return all_text
        except Exception as e:
            return {"error": str(e)}
    
    @staticmethod
    def process_csv(csv_content, encoding='utf-8'):
        """Process CSV data"""
        try:
            if isinstance(csv_content, bytes):
                csv_content = csv_content.decode(encoding)
            
            df = pd.read_csv(io.StringIO(csv_content))
            return {
                "columns": df.columns.tolist(),
                "shape": df.shape,
                "data": df.to_dict('records'),
                "summary": df.describe().to_dict()
            }
        except Exception as e:
            return {"error": str(e)}
    
    @staticmethod
    def process_excel(excel_content_base64):
        """Process Excel files"""
        try:
            excel_bytes = base64.b64decode(excel_content_base64)
            excel_file = io.BytesIO(excel_bytes)
            
            # Read all sheets
            sheets = pd.read_excel(excel_file, sheet_name=None)
            
            result = {}
            for sheet_name, df in sheets.items():
                result[sheet_name] = {
                    "columns": df.columns.tolist(),
                    "shape": df.shape,
                    "data": df.to_dict('records')
                }
            return result
        except Exception as e:
            return {"error": str(e)}
    
    @staticmethod
    def analyze_dataframe(df, operation):
        """Perform analysis on dataframe"""
        try:
            if operation['type'] == 'sum':
                column = operation['column']
                return df[column].sum()
            elif operation['type'] == 'mean':
                column = operation['column']
                return df[column].mean()
            elif operation['type'] == 'count':
                return len(df)
            elif operation['type'] == 'groupby':
                group_col = operation['group_column']
                agg_col = operation['agg_column']
                agg_func = operation['agg_function']
                return df.groupby(group_col)[agg_col].agg(agg_func).to_dict()
            elif operation['type'] == 'filter':
                condition = operation['condition']
                return len(df.query(condition))
            else:
                return {"error": "Unknown operation"}
        except Exception as e:
            return {"error": str(e)}
    
    @staticmethod
    def extract_tables_from_text(text):
        """Extract potential tables from text"""
        lines = text.split('\n')
        tables = []
        current_table = []
        
        for line in lines:
            # Simple heuristic: lines with multiple spaces or tabs might be tables
            if '  ' in line or '\t' in line:
                current_table.append(line)
            elif current_table:
                tables.append('\n'.join(current_table))
                current_table = []
        
        if current_table:
            tables.append('\n'.join(current_table))
        
        return tables
    
    @staticmethod
    def scrape_data_from_html(html_content, selector=None):
        """Extract data from HTML"""
        from bs4 import BeautifulSoup
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            if selector:
                elements = soup.select(selector)
                return [elem.get_text(strip=True) for elem in elements]
            else:
                # Extract all text
                return soup.get_text(strip=True)
        except Exception as e:
            return {"error": str(e)}
    
    @staticmethod
    def create_visualization(data, chart_type='bar'):
        """Create visualization and return as base64 image"""
        import matplotlib.pyplot as plt
        import matplotlib
        matplotlib.use('Agg')
        
        try:
            fig, ax = plt.subplots(figsize=(10, 6))
            
            if chart_type == 'bar':
                ax.bar(data.keys(), data.values())
            elif chart_type == 'line':
                ax.plot(list(data.keys()), list(data.values()))
            elif chart_type == 'pie':
                ax.pie(data.values(), labels=data.keys(), autopct='%1.1f%%')
            
            # Save to bytes
            buf = io.BytesIO()
            plt.savefig(buf, format='png', bbox_inches='tight')
            buf.seek(0)
            img_base64 = base64.b64encode(buf.read()).decode('utf-8')
            plt.close()
            
            return f"data:image/png;base64,{img_base64}"
        except Exception as e:
            return {"error": str(e)}
