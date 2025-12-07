import os
from dotenv import load_dotenv

# Try to load .env file if it exists, but don't fail if it doesn't
load_dotenv()

# Required environment variables with error handling
def get_required_env_var(var_name):
    value = os.getenv(var_name)
    if value is None:
        raise ValueError(f"Required environment variable {var_name} is not set")
    return value

# Optional environment variables with defaults
def get_optional_env_var(var_name, default_value=None):
    return os.getenv(var_name, default_value)

# API Keys
GEMINI_API_KEY = get_required_env_var("GEMINI_API_KEY")
BLOGGER_API_KEY = get_required_env_var("BLOGGER_API_KEY")

# Blogger Configuration
BLOG_ID = get_required_env_var("BLOG_ID")
BLOG_BASE_URL = get_required_env_var("BLOG_BASE_URL")

# OAuth Configuration
CLIENT_SECRETS_FILE = get_optional_env_var("CLIENT_SECRETS_FILE", "client_secrets.json")

# Publishing Configuration
PUBLISH = get_optional_env_var("PUBLISH", "false").lower() == "true"

# NWS Configuration
NWS_USER_AGENT = get_required_env_var("NWS_USER_AGENT")