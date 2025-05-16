#!/usr/bin/env python3
"""
Python script to perform a search request on wk.lordfilm12.ru and save the result HTML to a file.
"""
import requests
import argparse
import sys

def perform_search(query, output_file, session=None):
    """
    Perform search with the given query and save HTML results.
    """
    # Create a session if not provided
    sess = session or requests.Session()

    url = 'https://wk.lordfilm12.ru/search-result/'

    # Payload parameters for DataLife Engine search
    data = {
        'do': 'search',
        'subaction': 'search',
        'story': query
    }

    # Headers to mimic a real browser and include referer/origin
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/90.0.4430.93 Safari/537.36',
        'Referer': 'https://wk.lordfilm12.ru/',
        'Origin': 'https://wk.lordfilm12.ru'
    }

    # Send POST request
    response = sess.post(url, data=data, headers=headers)
    response.raise_for_status()

    # Write the raw HTML to file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(response.text)

    print(f"Search results saved to '{output_file}'")


def main():
    parser = argparse.ArgumentParser(
        description='Search wk.lordfilm12.ru and save HTML output'
    )
    parser.add_argument('query', help='Search query (film title)')
    parser.add_argument('-o', '--output', default='results.html',
                        help='Output HTML file name (default: results.html)')
    args = parser.parse_args()

    try:
        perform_search(args.query, args.output)
    except requests.HTTPError as e:
        print(f"HTTP error occurred: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
