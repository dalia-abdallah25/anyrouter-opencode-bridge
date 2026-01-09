"""
AnyRouter Proxy Server v16
支持配置文件、首次运行向导和热重载
"""

import httpx
import json
import sys
import os
import traceback
import argparse
import webbrowser
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse, JSONResponse
import uvicorn

# ================= Configuration Management =================

CONFIG_FILE = 'proxy_config.json'

DEFAULT_CONFIG = {
    "api_key": "",
    "proxy_url": "http://127.0.0.1:2080",
    "use_proxy": True,
    "debug": False,
    "target_base_url": "https://anyrouter.top/v1"
}

# Global Config Object
config = {}
CLIENT = None

def load_config():
    """Load configuration from file or use defaults"""
    global config
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)
            # Merge with default to ensure all keys exist
            config = DEFAULT_CONFIG.copy()
            config.update(loaded_config)
            print(f"[SYSTEM] Configuration loaded from {CONFIG_FILE}")
            return True
        except Exception as e:
            print(f"[SYSTEM] Error loading config: {e}")
            config = DEFAULT_CONFIG.copy()
            return False
    else:
        config = DEFAULT_CONFIG.copy()
        return False

def save_config():
    """Save current configuration to file"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)
        print(f"[SYSTEM] Configuration saved to {CONFIG_FILE}")
    except Exception as e:
        print(f"[SYSTEM] Error saving config: {e}")

def setup_wizard():
    """Interactive setup wizard"""
    print("\n" + "="*60)
    print("AnyRouter Proxy Setup Wizard")
    print("="*60)
    print("Please configure your proxy settings.\n")
    
    # API Key
    current_key = config.get('api_key', '')
    masked_key = f"{current_key[:8]}...{current_key[-4:]}" if len(current_key) > 12 else current_key
    api_key = input(f"Enter AnyRouter API Key [{masked_key}]: ").strip()
    if api_key:
        config['api_key'] = api_key
    elif not current_key:
        print("Warning: API Key is empty!")
    
    # Proxy Settings
    use_proxy_str = "y" if config.get('use_proxy', True) else "n"
    use_proxy = input(f"Use HTTP Proxy? (y/n) [{use_proxy_str}]: ").strip().lower()
    if use_proxy:
        config['use_proxy'] = (use_proxy == 'y')
        
    if config['use_proxy']:
        current_proxy = config.get('proxy_url', '')
        proxy_url = input(f"Proxy URL [{current_proxy}]: ").strip()
        if proxy_url:
            config['proxy_url'] = proxy_url

    # Debug Mode
    debug_str = "y" if config.get('debug', False) else "n"
    debug_mode = input(f"Enable Debug Mode (verbose logs)? (y/n) [{debug_str}]: ").strip().lower()
    if debug_mode:
        config['debug'] = (debug_mode == 'y')
        
    save_config()
    print("\n" + "="*60)
    print("Setup complete! You can edit 'proxy_config.json' to change these settings later.")
    print("="*60 + "\n")

# ================= FastAPI App =================

app = FastAPI()

# Claude Code 模拟 Headers
def get_claude_headers():
    return {
        "anthropic-client-name": "claude-code",
        "anthropic-client-version": "0.2.29",
        "user-agent": "claude-code/0.2.29 (win32; x64) node/v20.11.0",
        "accept": "application/json",
        "content-type": "application/json",
        "connection": "keep-alive",
        "anthropic-version": "2023-06-01",
    }

def create_async_client():
    proxy_url = config['proxy_url'] if config['use_proxy'] else None
    if config['debug']:
        print(f"[SYSTEM] Creating client with proxy: {proxy_url}")
        
    return httpx.AsyncClient(
        http2=True,
        verify=False,
        timeout=httpx.Timeout(connect=60.0, read=300.0, write=60.0, pool=300.0),
        proxy=proxy_url,
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=10)
    )

@app.on_event("startup")
async def startup():
    global CLIENT
    CLIENT = create_async_client()
    if config['debug']:
        print("[SYSTEM] Async client started")

@app.on_event("shutdown")
async def shutdown():
    global CLIENT
    if CLIENT:
        await CLIENT.aclose()

async def stream_response(resp):
    try:
        async for chunk in resp.aiter_bytes():
            yield chunk
    except Exception as e:
        print(f"[PROXY] Stream error: {e}")

# --- Management Endpoints ---

@app.get("/config")
async def get_config():
    """View current configuration"""
    safe_config = config.copy()
    # Mask API Key for display
    if len(safe_config['api_key']) > 10:
        safe_config['api_key'] = safe_config['api_key'][:8] + "..." + safe_config['api_key'][-4:]
    return safe_config

@app.post("/config/reload")
async def reload_config():
    """Hot reload configuration from file"""
    global CLIENT
    load_config()
    # Recreate client with new settings
    if CLIENT:
        await CLIENT.aclose()
    CLIENT = create_async_client()
    return {"status": "ok", "message": "Configuration reloaded", "config": config}

@app.get("/health")
async def health():
    return {"status": "ok", "version": "v16", "proxy_enabled": config['use_proxy']}

# --- Proxy Logic ---

@app.api_route("/v1/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
async def proxy(path: str, request: Request):
    global CLIENT
    target_url = f"{config['target_base_url']}/{path}"

    # Headers setup
    headers = get_claude_headers()
    # Use API Key from config, fallback to request header, fallback to empty
    req_auth = request.headers.get("Authorization")
    if config['api_key']:
        headers["x-api-key"] = config['api_key'] # Some providers need x-api-key
        headers["Authorization"] = f"Bearer {config['api_key']}"
    elif req_auth:
        headers["Authorization"] = req_auth

    if config['debug']:
        print(f"\n{'='*60}")
        print(f"[PROXY] Target: {target_url}")
    
    # Body processing
    body = await request.body()
    body_json = {}
    wants_stream = False
    
    if body:
        try:
            body_json = json.loads(body)
            # Filter body
            safe_keys = {'model', 'messages', 'max_tokens', 'metadata', 'stop_sequences', 'stream', 'system', 'temperature', 'top_k', 'top_p'}
            filtered_body = {k: v for k, v in body_json.items() if k in safe_keys}
            
            # Model fix
            model = filtered_body.get('model', '')
            if 'anyrouter/' in model:
                filtered_body['model'] = model.replace('anyrouter/', '')
            
            wants_stream = filtered_body.get('stream', False)
            if config['debug']:
                print(f"[PROXY] Model: {filtered_body.get('model')}")
                print(f"[PROXY] Stream: {wants_stream}")
            
            body_json = filtered_body
        except Exception as e:
            if config['debug']: print(f"[PROXY] Body parse error: {e}")

    # Request loop
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            if config['debug']:
                print(f"[PROXY] Attempt {attempt + 1}/{max_attempts}...")
                sys.stdout.flush()

            req = CLIENT.build_request(
                request.method,
                target_url,
                headers=headers,
                json=body_json,
                timeout=None
            )

            if wants_stream:
                resp = await CLIENT.send(req, stream=True)
                if config['debug']: print(f"[PROXY] Status: {resp.status_code}")

                if resp.status_code in [403, 500, 520, 502]:
                    await resp.aclose()
                    if config['debug']: print(f"[PROXY] Error {resp.status_code}, retrying...")
                    if attempt < max_attempts - 1:
                        CLIENT = create_async_client()
                        continue
                    
                    return Response(
                        content=json.dumps({"error": {"type": "upstream_error", "status": resp.status_code}}),
                        status_code=resp.status_code
                    )

                return StreamingResponse(
                    stream_response(resp),
                    status_code=resp.status_code,
                    media_type="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
                )
            else:
                resp = await CLIENT.send(req)
                if config['debug']: print(f"[PROXY] Status: {resp.status_code}")
                
                if resp.status_code in [403, 500, 520, 502]:
                    if attempt < max_attempts - 1:
                        CLIENT = create_async_client()
                        continue

                return Response(
                    content=resp.content,
                    status_code=resp.status_code,
                    media_type="application/json"
                )

        except Exception as e:
            if config['debug']:
                print(f"[PROXY] Error: {type(e).__name__}: {e}")
                traceback.print_exc()
            
            if attempt < max_attempts - 1:
                CLIENT = create_async_client()
            else:
                return Response(
                    content=json.dumps({"error": {"message": str(e)}}),
                    status_code=500
                )

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="AnyRouter Proxy Server")
    parser.add_argument("--setup", action="store_true", help="Run setup wizard")
    args = parser.parse_args()

    # Load config or run setup
    config_loaded = load_config()
    
    if args.setup or not config_loaded or not config.get('api_key'):
        setup_wizard()
    
    print("=" * 60)
    print("AnyRouter Proxy Server v16")
    print("=" * 60)
    print(f"Target: {config['target_base_url']}")
    print(f"Proxy:  {config['proxy_url'] if config['use_proxy'] else 'Disabled'}")
    print(f"Debug:  {'Enabled' if config['debug'] else 'Disabled'}")
    print(f"Config: {os.path.abspath(CONFIG_FILE)}")
    print("-" * 60)
    print("To change settings:")
    print("1. Edit 'proxy_config.json' directly")
    print("2. Run with --setup flag")
    print("3. Call POST http://127.0.0.1:8765/config/reload after editing file")
    print("=" * 60)
    
    # Windows Console Encoding Fix
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8')

    # Suppress uvicorn logs unless debug
    log_level = "info" if config['debug'] else "warning"
    
    try:
        uvicorn.run(app, host="127.0.0.1", port=8765, log_level=log_level)
    except KeyboardInterrupt:
        print("\nStopping server...")
