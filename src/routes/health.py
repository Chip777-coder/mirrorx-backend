from flask import send_from_directory
import os

@health_bp.route("/openapi.json", methods=["GET"])
def openapi_spec():
    """Serve the OpenAPI spec for GPT Actions"""
    return send_from_directory(os.getcwd(), "openapi.json")
