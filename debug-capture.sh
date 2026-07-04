#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PARENT_DIR="$(dirname "$SCRIPT_DIR")"
FIRMWARE_DIR="$SCRIPT_DIR/velxio-deployer-firmware"
IDF_PATH="$PARENT_DIR/esp-idf-v6"
WS_URL_FILE="/tmp/opencode/cdp-ws-url"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${CYAN}[INFO]${NC} $1"; }
ok()    { echo -e "${GREEN}[OK]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
err()   { echo -e "${RED}[ERR]${NC} $1" >&2; }

usage() {
  cat <<'EOF'
Usage: debug-capture.sh <command> [options]

Commands:
  setup              Detect ADB device, setup forward, find Chrome tab
  cdp [ws_url]       Stream Chrome console.log via CDP (inline Node.js)
  firmware           Source IDF + run idf.py monitor on /dev/ttyACM0
  all [ws_url]       Run CDP + firmware simultaneously
  sw-clear [ws_url]  Unregister SW + clear caches + reload page on device
  eval '<js>'        Evaluate JS expression on device, print result
  status             Check connection status (ADB, CDP, Chrome)
  help               Show this help
EOF
}

detect_adb() {
  local devices
  devices=$(adb devices 2>/dev/null | grep -v "List of devices attached" | grep -v "^$" | awk '{print $1}')
  if [ -z "$devices" ]; then
    err "No ADB device detected. Check USB/WiFi connection."
    return 1
  fi
  local count; count=$(echo "$devices" | wc -l)
  [ "$count" -gt 1 ] && warn "Multiple ADB devices. Using first."
  echo "$devices" | head -1
}

setup_forward() {
  adb forward tcp:9222 localabstract:chrome_devtools_remote >/dev/null 2>&1
  local fwd; fwd=$(adb forward --list | grep tcp:9222)
  [ -z "$fwd" ] && { err "ADB forward tcp:9222 failed"; return 1; }
  ok "ADB forward: $fwd"
}

detect_tab() {
  local filter="${1:-sinau-c-dev}"
  local resp; resp=$(curl -s http://localhost:9222/json/list 2>/dev/null)
  [ -z "$resp" ] && { err "CDP not responding at http://localhost:9222"; return 1; }
  local ws_url
  ws_url=$(echo "$resp" | python3 -c "
import sys, json
tabs = json.load(sys.stdin)
term = '$filter'
for t in tabs:
    if t.get('type') == 'page' and term in t.get('url', ''):
        print(t.get('webSocketDebuggerUrl', ''))
        sys.exit(0)
# fallback: first page tab
for t in tabs:
    if t.get('type') == 'page':
        print(t.get('webSocketDebuggerUrl', ''))
        sys.exit(0)
sys.exit(1)
" 2>/dev/null)
  if [ -z "$ws_url" ]; then
    err "No page tab found. Listing available tabs:"
    echo "$resp" | python3 -c "
import sys, json
for t in json.load(sys.stdin):
    if t.get('type') == 'page':
        print(f\"  {t.get('title','?')[:50]:50s} {t.get('url','?')[:80]}\")
" 2>/dev/null
    return 1
  fi
  echo "$ws_url"
}

source_idf() {
  [ ! -f "$IDF_PATH/export.sh" ] && { err "IDF not found at $IDF_PATH"; return 1; }
  . "$IDF_PATH/export.sh" >/dev/null 2>&1
}

get_ws_url() {
  local url="$1"
  [ -n "$url" ] && { echo "$url"; return 0; }
  [ -f "$WS_URL_FILE" ] && { cat "$WS_URL_FILE"; return 0; }
  setup_forward 2>/dev/null
  detect_tab
}

CDP_NODE_SCRIPT='
const wsUrl = process.env.WS_URL;
const ws = new WebSocket(wsUrl);
let msgId = 0;
function cmd(m, p = {}) { return JSON.stringify({ id: ++msgId, method: m, params: p }); }
ws.addEventListener("open", () => {
  ws.send(cmd("Runtime.enable"));
  ws.send(cmd("Console.enable"));
  ws.send(cmd("Runtime.runIfWaitingForDebugger"));
});
ws.addEventListener("message", (ev) => {
  let msg;
  try { msg = JSON.parse(ev.data); } catch { return; }
  if (msg.method === "Runtime.consoleAPICalled") {
    const text = msg.params.args.map(a => a.type === "string" ? a.value : JSON.stringify(a.value ?? a)).join(" ");
    console.log(text);
  } else if (msg.method === "Console.messageAdded") {
    console.log("[CONSOLE]", msg.params.message.text);
  } else if (msg.method === "Runtime.exceptionThrown") {
    const d = msg.params.exceptionDetails;
    console.error("[EXCEPTION]", d.text, "at", d.url + ":" + d.lineNumber);
  }
});
ws.addEventListener("error", () => process.exit(1));
ws.addEventListener("close", () => process.exit(0));
'

case "$1" in
setup)
  echo "=== Setup CDP Connection ==="
  detect_adb || exit 1
  setup_forward || exit 1
  info "Waking up device..."
  adb shell input keyevent 82 2>/dev/null; sleep 0.5
  adb shell input keyevent 82 2>/dev/null
  info "Waiting for Chrome devtools..."
  for i in $(seq 1 10); do
    curl -s -o /dev/null -w "%{http_code}" http://localhost:9222/json/list 2>/dev/null | grep -q 200 && break
    [ "$i" -eq 10 ] && { err "Chrome devtools not responding."; exit 1; }
    sleep 1
  done
  ok "Chrome devtools ready"
  ws_url=$(detect_tab "${2:-sinau-c-dev}") || exit 1
  ok "Tab found"
  echo "$ws_url" > "$WS_URL_FILE"
  ok "WS URL saved to $WS_URL_FILE"
  echo ""
  echo "Next:  ./debug-capture.sh cdp     # Stream console.log"
  echo "       ./debug-capture.sh firmware # Firmware log"
  echo "       ./debug-capture.sh all      # Both at once"
  ;;

cdp)
  ws_url=$(get_ws_url "$2") || { err "No CDP WS URL. Run 'setup' first."; exit 1; }
  ok "Connecting to CDP"
  info "Streaming console.log... Ctrl+C to stop."
  echo "---"
  WS_URL="$ws_url" node -e "$CDP_NODE_SCRIPT"
  ;;

firmware)
  source_idf || exit 1
  info "Starting firmware monitor on /dev/ttyACM0... Ctrl+C to stop."
  echo "---"
  cd "$FIRMWARE_DIR" || exit 1
  idf.py -p /dev/ttyACM0 monitor
  ;;

all)
  ws_url=$(get_ws_url "$2") || { err "No CDP WS URL. Run 'setup' first."; exit 1; }
  source_idf || exit 1
  info "Starting CDP monitor (background) + firmware monitor (foreground)..."
  echo "---"
  WS_URL="$ws_url" node -e "$CDP_NODE_SCRIPT" &
  CDP_PID=$!
  info "CDP PID: $CDP_PID"
  cd "$FIRMWARE_DIR" || exit 1
  idf.py -p /dev/ttyACM0 monitor
  kill "$CDP_PID" 2>/dev/null
  wait "$CDP_PID" 2>/dev/null
  ;;

sw-clear)
  ws_url=$(get_ws_url "$2") || { err "No CDP WS URL. Run 'setup' first."; exit 1; }
  info "Clearing Service Worker cache on device..."
  WS_URL="$ws_url" node -e '
const wsUrl = process.env.WS_URL;
const ws = new WebSocket(wsUrl);
let msgId = 0;
function cmd(m, p = {}) { return JSON.stringify({ id: ++msgId, method: m, params: p }); }
ws.addEventListener("open", () => {
  ws.send(cmd("Runtime.enable"));
  ws.send(cmd("Runtime.runIfWaitingForDebugger"));
  setTimeout(() => {
    ws.send(cmd("Runtime.evaluate", {
      expression: `(async () => {
        const regs = await navigator.serviceWorker.getRegistrations();
        for (const r of regs) {
          await r.unregister();
          console.log("SW unregistered:", r.active?.scriptURL || "unknown");
        }
        const keys = await caches.keys();
        for (const k of keys) {
          await caches.delete(k);
          console.log("Cache deleted:", k);
        }
        return { unregistered: regs.length, cachesCleared: keys.length };
      })()`,
      awaitPromise: true
    }));
  }, 1000);
});
ws.addEventListener("message", (ev) => {
  let msg;
  try { msg = JSON.parse(ev.data); } catch { return; }
  if (msg.method === "Runtime.consoleAPICalled") {
    const text = msg.params.args.map(a => a.value || JSON.stringify(a)).join(" ");
    console.log(text);
  }
  if (msg.id && msg.result) {
    if (msg.result.result?.value) {
      console.log("Result:", JSON.stringify(msg.result.result.value));
    }
    setTimeout(() => {
      ws.send(cmd("Page.enable"));
      setTimeout(() => {
        ws.send(cmd("Page.reload", { ignoreCache: true }));
        console.error("[CDP] Page reloaded");
        setTimeout(() => { ws.close(); process.exit(0); }, 2000);
      }, 300);
    }, 500);
  }
});
ws.addEventListener("error", () => process.exit(1));
setTimeout(() => { console.error("Timeout"); process.exit(1); }, 20000);
'
  ;;

eval)
  [ -z "$2" ] && { err "Usage: $(basename "$0") eval '\''<js_expression>'\''"; exit 1; }
  ws_url=$(get_ws_url "$3") || { err "No CDP WS URL. Run 'setup' first."; exit 1; }
  info "Evaluating: $2"
  WS_URL="$ws_url" JS_EXPR="$2" node -e '
const wsUrl = process.env.WS_URL;
const expr = process.env.JS_EXPR;
const ws = new WebSocket(wsUrl);
let msgId = 0;
function cmd(m, p = {}) { return JSON.stringify({ id: ++msgId, method: m, params: p }); }
ws.addEventListener("open", () => {
  ws.send(cmd("Runtime.enable"));
  ws.send(cmd("Runtime.runIfWaitingForDebugger"));
  setTimeout(() => {
    ws.send(cmd("Runtime.evaluate", {
      expression: "(async () => { try { return await (" + expr + "); } catch(e) { return {error: e?.message || String(e)}; } })()",
      awaitPromise: true
    }));
  }, 500);
});
ws.addEventListener("message", (ev) => {
  let msg;
  try { msg = JSON.parse(ev.data); } catch { return; }
  if (msg.id && msg.result) {
    const r = msg.result.result;
    if (r) {
      if (r.type === "string") console.log(r.value);
      else console.log(JSON.stringify(r.value ?? r.description ?? r, null, 2));
    }
    ws.close();
    process.exit(0);
  }
});
ws.addEventListener("error", () => process.exit(1));
setTimeout(() => { console.error("Timeout"); process.exit(1); }, 15000);
'
  ;;

status)
  echo "=== Debug Connection Status ==="
  if adb_devices=$(adb devices 2>/dev/null | grep -v "List of devices attached" | grep -v "^$") && [ -n "$adb_devices" ]; then
    echo "$adb_devices" | while IFS= read -r line; do ok "ADB: $line"; done
  else
    err "ADB: No device"
  fi
  if fwd=$(adb forward --list 2>/dev/null | grep tcp:9222) && [ -n "$fwd" ]; then
    ok "Forward: $fwd"
  else
    err "Forward: No tcp:9222"
  fi
  cdp_code=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:9222/json/version 2>/dev/null)
  if [ "$cdp_code" = "200" ]; then
    browser=$(curl -s http://localhost:9222/json/version 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('Browser','?'))" 2>/dev/null)
    ok "CDP: OK ($browser)"
    tab=$(detect_tab 2>/dev/null)
    [ -n "$tab" ] && ok "Tab: Found" || warn "Tab: No lesson tab"
  else
    err "CDP: Not responding"
  fi
  [ -c /dev/ttyACM0 ] && ok "ACM0: Present" || err "ACM0: Missing"
  [ -f "$IDF_PATH/export.sh" ] && ok "IDF: $IDF_PATH" || err "IDF: Not found"
  [ -f "$WS_URL_FILE" ] && ok "WS URL file: Exists" || warn "WS URL file: Missing"
  nv=$(node --version 2>/dev/null)
  [ -n "$nv" ] && ok "Node: $nv" || err "Node: Not found"
  ;;

--help|-h|help|"")
  usage
  ;;

*)
  err "Unknown command: $1"
  usage
  exit 1
  ;;
esac
