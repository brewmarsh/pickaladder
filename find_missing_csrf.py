import os
import re

def find_forms_without_csrf(directory):
    csrf_pattern = re.compile(r'csrf_token|hidden_tag', re.IGNORECASE)

    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.html'):
                filepath = os.path.join(root, file)
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Find all forms
                forms = list(re.finditer(r'<form.*?</form>', content, re.DOTALL | re.IGNORECASE))
                for form in forms:
                    form_text = form.group(0)
                    if 'method="post"' in form_text.lower() or "method='post'" in form_text.lower():
                        if not csrf_pattern.search(form_text):
                            print(f"File: {filepath}")
                            # print(form_text)
                            # print("-" * 20)

if __name__ == "__main__":
    find_forms_without_csrf('pickaladder/templates')
