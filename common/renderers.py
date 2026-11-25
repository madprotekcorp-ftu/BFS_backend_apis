from rest_framework.renderers import JSONRenderer


class EnvelopeJSONRenderer(JSONRenderer):
    """Wraps any response that is not already enveloped in {"success": ..., "data": ...}."""

    def render(self, data, accepted_media_type=None, renderer_context=None):
        response = (renderer_context or {}).get("response")
        if response is not None and response.status_code == 204:
            return b""
        if not (isinstance(data, dict) and "success" in data):
            ok = response is None or response.status_code < 400
            data = {"success": ok, "data": data}
        return super().render(data, accepted_media_type, renderer_context)
