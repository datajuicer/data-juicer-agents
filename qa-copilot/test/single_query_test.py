import os
import json
import time
import requests
import argparse


def single_query(query_text, url=None, session_id=None, verbose=False):
    url = url or os.environ.get("DJ_COPILOT_TEST_URL", "http://127.0.0.1:8080/process")
    session_id = session_id or f"session_{time.time()}"
    payload = {
        "input": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": query_text
                    }
                ],
            }
        ],
        "session_id": session_id,
    }
    headers = {"Content-Type": "application/json"}
    if verbose:
        print(f"Sending request to {url} ...")
        print(f"\n===== Query =====\n{query_text}\n")
    start_time = time.perf_counter()
    resp = requests.post(url, headers=headers, json=payload, stream=True)
    first_token_time = None
    complete_time = None
    texts = []
    for raw_line in resp.iter_lines():
        if not raw_line:
            continue
        line = raw_line.decode("utf-8", errors="ignore").strip()
        if not line:
            continue
        try:
            data = json.loads(line.split("data: ")[1])
            status, text = data.get("status", ""), data.get("text", "")
        except json.JSONDecodeError:
            status, text = "error", line
        if status == "in_progress" and text and first_token_time is None:
            first_token_time = time.perf_counter()
        if status == "completed" and text:
            texts.append(text)

    complete_time = time.perf_counter()
    first_token_duration = first_token_time - start_time if first_token_time is not None else None
    total_duration = complete_time - start_time
    full_text = "".join(texts)

    return {"full_text": full_text, "first_token_duration": first_token_duration, "total_duration": total_duration} 


def main():
    parser = argparse.ArgumentParser(description="Single Query Test")
    parser.add_argument("--query", type=str, default="Introduce alphanumeric_filter", help="The text query to send to the copilot.")
    args = parser.parse_args()

    response = single_query(args.query, verbose=True)
    print(f"===== Full Text =====")
    print(response['full_text'])
    print("\n===== Query Stats =====")
    if response['first_token_duration'] is not None:
        print(f"First Token Duration: {response['first_token_duration']:.3f} s")
    else:
        print("First Token Duration: N/A")
    print(f"Total Time: {response['total_duration']:.3f} s")


if __name__ == "__main__":
    main()
