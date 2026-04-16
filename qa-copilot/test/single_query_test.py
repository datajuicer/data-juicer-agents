import os
import json
import time
import requests
import argparse


def _normalize_error(error):
    if not error:
        return None
    if isinstance(error, dict):
        error_type = error.get("code") or error.get("type") or "StreamError"
        error_message = error.get("message") or json.dumps(error, ensure_ascii=False)
        return {
            "type": error_type,
            "message": error_message,
        }
    return {
        "type": type(error).__name__,
        "message": str(error),
    }


def _iter_sse_events(resp):
    for raw_line in resp.iter_lines():
        if not raw_line:
            continue
        line = raw_line.decode("utf-8", errors="ignore").strip()
        if not line:
            continue
        if line.startswith("data: "):
            line = line[6:]
        elif line.startswith("data:"):
            line = line[5:].lstrip()
        else:
            continue
        if line == "[DONE]":
            break
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            yield {
                "object": "parse_error",
                "status": "error",
                "error": {"message": f"Failed to parse SSE line: {line[:200]}"},
            }


def _extract_completed_message_text(data):
    if data.get("object") != "message" or data.get("status") != "completed":
        return ""

    content = data.get("content")
    if not isinstance(content, list):
        return ""

    text_parts = []
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "text" or item.get("delta"):
            continue
        text = item.get("text")
        if text:
            text_parts.append(text)
    return "".join(text_parts)


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
    headers = {
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }
    if verbose:
        print(f"Sending request to {url} ...")
        print(f"\n===== Query =====\n{query_text}\n")
    start_time = time.perf_counter()
    first_token_time = None
    text_order = []
    text_buffers = {}
    stream_error = None
    response_completed = False
    response_status = None
    try:
        resp = requests.post(
            url, headers=headers, json=payload, stream=True, timeout=600
        )
        resp.raise_for_status()
        for data in _iter_sse_events(resp):
            status = data.get("status", "")
            text = data.get("text", "")
            msg_id = data.get("msg_id")

            if data.get("object") == "response":
                response_status = status or response_status
                if status == "completed" and not data.get("error"):
                    response_completed = True

            if data.get("error") and stream_error is None:
                stream_error = _normalize_error(data["error"])

            if data.get("object") == "content" and data.get("type") == "text" and msg_id:
                if msg_id not in text_order:
                    text_order.append(msg_id)
                if text and first_token_time is None:
                    first_token_time = time.perf_counter()
                if status == "completed" and text:
                    text_buffers[msg_id] = text
                elif text:
                    text_buffers[msg_id] = text_buffers.get(msg_id, "") + text

            completed_message_text = _extract_completed_message_text(data)
            if completed_message_text:
                message_key = msg_id or f"completed_message_{len(text_order)}"
                if message_key not in text_order:
                    text_order.append(message_key)
                if first_token_time is None:
                    first_token_time = time.perf_counter()
                # Prefer streamed content when available; use completed message
                # payload only as a fallback for non-delta responses.
                if not text_buffers.get(message_key):
                    text_buffers[message_key] = completed_message_text
    except requests.RequestException as exc:
        stream_error = _normalize_error(exc)
    except Exception as exc:
        stream_error = _normalize_error(exc)

    complete_time = time.perf_counter()
    first_token_duration = first_token_time - start_time if first_token_time is not None else None
    total_duration = complete_time - start_time
    full_text = "".join(text_buffers.get(msg_id, "") for msg_id in text_order)
    if stream_error:
        error_type = stream_error["type"]
        error_message = stream_error["message"]
        error_prefix = f"[ERROR:{error_type}]"
        full_text = f"{error_prefix} {error_message}\n{full_text}".strip() if full_text else f"{error_prefix} {error_message}"

    if response_completed and not stream_error:
        completion_status = "completed"
    elif stream_error:
        completion_status = "error"
    elif response_status:
        completion_status = response_status
    else:
        completion_status = "incomplete"

    return {
        "full_text": full_text,
        "first_token_duration": first_token_duration,
        "total_duration": total_duration,
        "error": stream_error,
        "error_type": stream_error["type"] if stream_error else None,
        "is_completed": response_completed and stream_error is None,
        "completion_status": completion_status,
    }


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
    print(f"Completed: {response['is_completed']}")
    print(f"Completion Status: {response['completion_status']}")
    if response.get("error"):
        print("\n===== Stream Error =====")
        print(response["error"])


if __name__ == "__main__":
    main()
