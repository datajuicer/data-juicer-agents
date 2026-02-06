# -*- coding: utf-8 -*-
"""
URL verification tool for QA Agent.
Validates that reference URLs are accessible before including them in responses.
"""

import asyncio
from re import I
from typing import Any
from concurrent.futures import ThreadPoolExecutor

import requests
from agentscope.tool import ToolResponse
from agentscope.message import TextBlock

# Trusted domains that bypass verification (e.g., sites with anti-bot protection)
TRUSTED_DOMAINS = [
    "bilibili.com",
    "b23.tv",  # Bilibili short link
]


def _is_trusted_domain(url: str) -> bool:
    """Check if URL belongs to a trusted domain."""
    for domain in TRUSTED_DOMAINS:
        if domain in url:
            return True
    return False


def _check_single_url(url: str, timeout: int = 5) -> dict[str, Any]:
    """
    Check if a single URL is accessible.
    
    Args:
        url: The URL to check
        timeout: Request timeout in seconds
        
    Returns:
        Dict with url, is_valid, status_code, and error (if any)
    """
    result = {
        "url": url,
        "is_valid": False,
        "status_code": None,
        "error": None,
    }
    
    # Skip verification for trusted domains (e.g., Bilibili has anti-bot protection)
    if _is_trusted_domain(url):
        result["is_valid"] = True
        result["status_code"] = 200
        return result
    
    try:
        # Use HEAD request first (faster), fallback to GET if HEAD fails
        response = requests.head(
            url,
            timeout=timeout,
            allow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; URLValidator/1.0)"
            },
        )
        
        # Some servers don't support HEAD, try GET for 405 errors
        if response.status_code == 405:
            response = requests.get(
                url,
                timeout=timeout,
                allow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; URLValidator/1.0)"
                },
                stream=True,  # Don't download the body
            )
            response.close()
        
        result["status_code"] = response.status_code
        result["is_valid"] = response.status_code < 400
        
    except requests.exceptions.Timeout:
        result["error"] = "Connection timeout"
    except requests.exceptions.ConnectionError:
        result["error"] = "Connection failed"
    except requests.exceptions.TooManyRedirects:
        result["error"] = "Too many redirects"
    except requests.exceptions.RequestException as e:
        result["error"] = str(e)
    
    return result


async def verify_urls(
    urls: list[str],
    timeout: int = 5,
) -> ToolResponse:
    """
    Verify whether a list of URLs are accessible and valid.
    Use this tool to check reference links BEFORE including them in your response.
    
    Args:
        urls: A list of URLs to verify (e.g., ["https://example.com", "https://github.com/..."])
        timeout: Request timeout in seconds for each URL (default: 5)
    
    Returns:
        Verification results for each URL, including:
        - url: The checked URL
        - is_valid: Whether the URL is accessible (True/False)
        - status_code: HTTP status code (if available)
        - error: Error message (if any)
    """
    if not urls:
        return ToolResponse(
            metadata={"success": True, "total": 0, "valid": 0, "invalid": 0},
            content=[
                TextBlock(
                    type="text",
                    text="No URLs provided to verify.",
                ),
            ],
        )
    
    # Remove duplicates while preserving order
    unique_urls = list(dict.fromkeys(urls))
    
    # Run URL checks in parallel using thread pool
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=min(10, len(unique_urls))) as executor:
        tasks = [
            loop.run_in_executor(executor, _check_single_url, url, timeout)
            for url in unique_urls
        ]
        results = await asyncio.gather(*tasks)
    
    # Summarize results
    valid_count = sum(1 for r in results if r["is_valid"])
    invalid_count = len(results) - valid_count
    
    # Format output
    output_lines = [
        f"URL Verification Results ({valid_count} valid, {invalid_count} invalid):",
        "",
    ]
    
    for result in results:
        status = "✓ VALID" if result["is_valid"] else "✗ INVALID"
        status_info = f"(HTTP {result['status_code']})" if result["status_code"] else ""
        error_info = f" - {result['error']}" if result["error"] else ""
        output_lines.append(f"  {status} {status_info}{error_info}")
        output_lines.append(f"    {result['url']}")
        output_lines.append("")
    
    # Add recommendations
    if invalid_count > 0:
        output_lines.append("Recommendation: Do NOT include invalid URLs in your response.")
        output_lines.append("Use only valid URLs as references, or provide general documentation links instead.")
    
    return ToolResponse(
        metadata={
            "success": True,
            "total": len(results),
            "valid": valid_count,
            "invalid": invalid_count,
            "results": results,
        },
        content=[
            TextBlock(
                type="text",
                text="\n".join(output_lines),
            ),
        ],
    )


if __name__ == "__main__":
    urls = [
        "https://github.com/datajuicer/data-juicer-agents", # valid url
        "https://github.com/datajuicer/data-juicy-agents", # fake url
    ]
    response = asyncio.run(verify_urls(urls))
    print(response.content[0]["text"])