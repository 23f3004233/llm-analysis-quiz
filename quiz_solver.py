import anthropic
import json
import re
from typing import Dict, Any, List, Optional

class QuizSolver:
    """Advanced quiz solving with Claude"""
    
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
    
    def solve_quiz(self, quiz_content: Dict[str, Any], files_data: Optional[Dict] = None) -> Dict[str, Any]:
        """Main method to solve a quiz"""
        
        # Build comprehensive prompt
        prompt = self._build_prompt(quiz_content, files_data)
        
        # Get Claude's response
        response = self._call_claude(prompt)
        
        # Parse and validate response
        solution = self._parse_response(response)
        
        return solution
    
    def _build_prompt(self, quiz_content: Dict, files_data: Optional[Dict] = None) -> str:
        """Build a comprehensive prompt for Claude"""
        
        prompt_parts = [
            "You are an expert data analyst solving a quiz. Analyze carefully and provide accurate answers.",
            "",
            "=== QUIZ CONTENT ===",
            quiz_content.get('text', ''),
            "",
            "=== QUIZ HTML ===",
            quiz_content.get('html', '')[:3000],  # Truncate to avoid token limits
        ]
        
        if files_data:
            prompt_parts.extend([
                "",
                "=== DOWNLOADED FILES ===",
                f"Available files: {list(files_data.keys())}",
            ])
        
        prompt_parts.extend([
            "",
            "=== YOUR TASK ===",
            "1. Identify what the question is asking",
            "2. Extract the submission URL from the quiz page",
            "3. If files are mentioned, list their URLs in 'files_needed'",
            "4. If you have file data, analyze it to answer the question",
            "5. Calculate/derive the answer",
            "6. Format your response as JSON",
            "",
            "=== RESPONSE FORMAT ===",
            "You MUST respond with ONLY a valid JSON object (no other text):",
            "{",
            '  "reasoning": "brief explanation of your approach",',
            '  "submit_url": "URL where answer should be posted",',
            '  "answer": <the answer - could be number, string, boolean, or object>,',
            '  "files_needed": ["list of file URLs if any are needed"]',
            "}",
            "",
            "CRITICAL RULES:",
            "- answer must match the expected data type (number for sums, string for text, etc.)",
            "- extract submit_url exactly as shown in the quiz page",
            "- if files are needed but not yet provided, list them in files_needed",
            "- if files are provided, analyze them and give the final answer",
            "- return ONLY valid JSON, no markdown formatting or extra text"
        ])
        
        return "\n".join(prompt_parts)
    
    def _call_claude(self, prompt: str, max_retries: int = 2) -> str:
        """Call Claude API with retry logic"""
        
        for attempt in range(max_retries):
            try:
                message = self.client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=4096,
                    temperature=0.1,  # Lower temperature for more consistent answers
                    messages=[{
                        "role": "user",
                        "content": prompt
                    }]
                )
                
                return message.content[0].text
            
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                print(f"Claude API error (attempt {attempt + 1}): {e}")
                continue
    
    def _parse_response(self, response: str) -> Dict[str, Any]:
        """Parse Claude's response into structured format"""
        
        # Remove markdown code blocks if present
        response = re.sub(r'```json\s*', '', response)
        response = re.sub(r'```\s*', '', response)
        
        # Try to find JSON object
        try:
            # Find first { and last }
            start = response.find('{')
            end = response.rfind('}') + 1
            
            if start == -1 or end == 0:
                return {
                    "error": "No JSON found in response",
                    "raw_response": response
                }
            
            json_str = response[start:end]
            result = json.loads(json_str)
            
            # Validate required fields
            if 'submit_url' not in result:
                result['error'] = "Missing submit_url"
            
            if 'answer' not in result and 'files_needed' not in result:
                result['error'] = "Missing both answer and files_needed"
            
            return result
        
        except json.JSONDecodeError as e:
            return {
                "error": f"JSON parse error: {str(e)}",
                "raw_response": response
            }
    
    def analyze_files(self, quiz_content: Dict, files_data: Dict) -> Dict[str, Any]:
        """Analyze downloaded files to answer the quiz"""
        
        prompt_parts = [
            "You are analyzing files to answer a data quiz.",
            "",
            "=== ORIGINAL QUESTION ===",
            quiz_content.get('text', ''),
            "",
            "=== FILES PROVIDED ===",
        ]
        
        for file_url, file_info in files_data.items():
            prompt_parts.extend([
                f"",
                f"File: {file_url}",
                f"Type: {file_info.get('type', 'unknown')}",
                f"Content preview: {str(file_info.get('content', ''))[:1000]}",
            ])
        
        prompt_parts.extend([
            "",
            "=== YOUR TASK ===",
            "Analyze the file(s) and answer the question precisely.",
            "If the question asks for a sum, calculate the exact sum.",
            "If it asks for a count, count accurately.",
            "If it asks for specific data, extract it correctly.",
            "",
            "Respond with ONLY valid JSON:",
            "{",
            '  "reasoning": "how you analyzed the data",',
            '  "submit_url": "submission URL from original quiz",',
            '  "answer": <precise answer>',
            "}"
        ])
        
        response = self._call_claude("\n".join(prompt_parts))
        return self._parse_response(response)
    
    def handle_visualization(self, data: Any, viz_type: str) -> str:
        """Generate visualization if needed"""
        
        prompt = f"""Generate a {viz_type} visualization for this data:

{json.dumps(data, indent=2)}

Return a JSON object with:
{{
  "chart_type": "{viz_type}",
  "data_for_chart": {{"x": [...], "y": [...]}},
  "base64_image": "data:image/png;base64,..." 
}}

If you cannot generate the image, describe what the chart should show.
"""
        
        response = self._call_claude(prompt)
        return self._parse_response(response)
    
    def validate_answer(self, answer: Any, expected_type: str) -> bool:
        """Validate answer matches expected type"""
        
        type_mapping = {
            'number': (int, float),
            'string': str,
            'boolean': bool,
            'object': dict,
            'array': list
        }
        
        expected = type_mapping.get(expected_type)
        if expected is None:
            return True  # Unknown type, allow it
        
        return isinstance(answer, expected)
