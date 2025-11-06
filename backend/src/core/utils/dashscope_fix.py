"""
Fix for DashScope API error handling in langchain_community.

When DashScope returns an error response (403, 429, etc.), langchain_community's
check_response() function crashes with KeyError: 'request' when trying to raise HTTPError.

This module monkey-patches the check_response function to handle DashScope errors properly.
"""

from typing import Any


def patch_tongyi_check_response() -> None:
    """
    Monkey-patch langchain_community check_response to handle DashScope errors.

    The original function tries to raise requests.HTTPError with a DashScope response,
    but HTTPError.__init__ tries to access response.request which doesn't exist on
    DashScope response objects, causing KeyError.
    """
    try:
        from langchain_community import llms as llms_module
        from langchain_community import chat_models as chat_models_module

        def patched_check_response(resp: Any) -> Any:
            """Check DashScope API response and raise appropriate errors."""
            # DashScope responses are dict-like with status_code
            if hasattr(resp, 'status_code') or (isinstance(resp, dict) and 'status_code' in resp):
                status_code = resp.get('status_code') if isinstance(resp, dict) else resp.status_code

                # Success status codes (200-299)
                if 200 <= status_code < 300:
                    return resp

                # Error response - extract details
                code = resp.get('code', 'Unknown') if isinstance(resp, dict) else getattr(resp, 'code', 'Unknown')
                message = resp.get('message', 'Unknown error') if isinstance(resp, dict) else getattr(resp, 'message', 'Unknown error')
                request_id = resp.get('request_id', '') if isinstance(resp, dict) else getattr(resp, 'request_id', '')

                # Raise a clear error instead of HTTPError
                error_msg = f"DashScope API Error [{status_code}]: {code} - {message}"
                if request_id:
                    error_msg += f" (request_id: {request_id})"

                # Special handling for quota errors
                if code == "AllocationQuota.FreeTierOnly":
                    error_msg += "\n\nFree tier quota exhausted. Please disable 'free tier only' mode in DashScope console."

                raise ValueError(error_msg)

            # Not a DashScope response - just return it (success case)
            return resp

        # Apply the patch to BOTH modules
        llms_module.tongyi.check_response = patched_check_response
        chat_models_module.tongyi.check_response = patched_check_response

    except ImportError:
        # langchain_community not installed or tongyi module not available
        pass
