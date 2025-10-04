import streamlit as st
import requests
import time
from typing import Dict, Any, List, Tuple, Optional

# ---------------------------
# Basics & Constants
# ---------------------------
BC_RESOURCE = "https://api.businesscentral.dynamics.com"  # Base for BC APIs
TOKEN_SCOPE = f"{BC_RESOURCE}/.default"
AUTH_BASE = "https://login.microsoftonline.com"

st.set_page_config(page_title="Business Central Environment Inspector", layout="wide")

st.title("Business Central Environment Inspector")
st.caption("Sign in with an Entra app (Client ID/Secret), pick an environment, and list companies, installed apps, and more.")

with st.expander("ℹ️ Quick setup notes (one-time)", expanded=False):
    st.markdown("""
- **Create an Entra app registration** (no redirect URI needed for client-credentials).
- **Add API permissions** for *Dynamics 365 Business Central*:
  - Recommended minimum (read-only): `Automation.Read.All`, `Financials.Read.All`
  - For broader access, add `Financials.ReadWrite.All` as needed.
- **Grant admin consent**.
- In **Business Central Admin Center**, ensure the app is allowed if your tenant restricts access to trusted apps.
- Use your **Directory (Tenant) ID**, **Client ID**, and **Client Secret** below.
""")

# ---------------------------
# Inputs
# ---------------------------
with st.sidebar:
    st.header("Authentication")
    tenant_id = st.text_input("Tenant (Directory) ID", placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx")
    client_id = st.text_input("Client ID", placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx")
    client_secret = st.text_input("Client Secret", type="password")
    auth_button = st.button("Get Token / Refresh", use_container_width=True)

    st.header("Target")
    bc_tenant_hint = st.text_input("Business Central Tenant ID (GUID or 'default')",
                                   help="Usually your same Directory ID (GUID). If unsure, try your Directory ID first, or 'default'.")
    environment = st.text_input("Environment name", placeholder="Production",
                                help="BC environment name, e.g., Production, Sandbox, UAT.")
    timeout_s = st.number_input("HTTP Timeout (seconds)", min_value=5, max_value=60, value=20, step=1)

# ---------------------------
# Token acquisition
# ---------------------------
@st.cache_data(show_spinner=False, ttl=60, max_entries=16)
def get_token(tenant_id: str, client_id: str, client_secret: str) -> Tuple[bool, str]:
    if not (tenant_id and client_id and client_secret):
        return False, "Missing tenant/client/secret."
    url = f"{AUTH_BASE}/{tenant_id}/oauth2/v2.0/token"
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "client_credentials",
        "scope": TOKEN_SCOPE
    }
    try:
        r = requests.post(url, data=data, timeout=30)
        if r.status_code == 200:
            return True, r.json().get("access_token", "")
        else:
            return False, f"Token error {r.status_code}: {r.text}"
    except Exception as e:
        return False, f"Token exception: {e}"

token_ok = False
access_token = ""
if auth_button:
    with st.spinner("Requesting token..."):
        token_ok, access_token = get_token(tenant_id.strip(), client_id.strip(), client_secret)
    if token_ok:
        st.success("Token acquired.")
    else:
        st.error(access_token)

# Allow silent refresh if values already there
if (tenant_id and client_id and client_secret) and not token_ok:
    token_ok, access_token = get_token(tenant_id.strip(), client_id.strip(), client_secret)

# ---------------------------
# HTTP helper
# ---------------------------
def auth_get(url: str, headers: Optional[Dict[str, str]] = None, params: Optional[Dict[str, Any]] = None) -> Tuple[int, Any, Dict[str, Any]]:
    h = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }
    if headers:
        h.update(headers)
    r = requests.get(url, headers=h, params=params, timeout=timeout_s)
    try:
        js = r.json()
    except Exception:
        js = r.text
    return r.status_code, js, dict(r.headers)

# ---------------------------
# Endpoint attempts
# ---------------------------
def try_endpoints(endpoints: List[Tuple[str, str]]) -> Dict[str, Any]:
    """Try each endpoint in order and return first success."""
    for label, url in endpoints:
        code, js, _ = auth_get(url)
        if 200 <= code < 300:
            return {"label": label, "url": url, "data": js}
