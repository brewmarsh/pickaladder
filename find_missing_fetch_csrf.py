import os
import re

def find_fetch_without_csrf(directory):
    fetch_pattern = re.compile(r'fetch\((.*?)\)', re.DOTALL)
    method_post_pattern = re.compile(r'method\s*:\s*["\'](POST|PUT|DELETE)["\']', re.IGNORECASE)
    csrf_header_pattern = re.compile(r'X-CSRFToken', re.IGNORECASE)

    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(('.html', '.js')):
                filepath = os.path.join(root, file)
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()

                for match in fetch_pattern.finditer(content):
                    fetch_body = match.group(1)
                    if method_post_pattern.search(fetch_body):
                        if not csrf_header_pattern.search(fetch_body):
                            print(f"File: {filepath}")
                            print(f"Fetch call: fetch({fetch_body})")
                            print("-" * 20)

if __name__ == "__main__":
    find_fetch_without_csrf('pickaladder/')
