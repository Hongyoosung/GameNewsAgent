🦞 OpenClaw 2026.2.26 (bc50708) — Your inbox, your infra, your rules.



Usage: openclaw [options] [command]



Options:

  --dev                Dev profile: isolate state under ~/.openclaw-dev, default gateway port 19001, and shift derived ports

                       (browser/canvas)

  -h, --help           Display help for command

  --log-level <level>  Global log level override for file + console (silent|fatal|error|warn|info|debug|trace)

  --no-color           Disable ANSI colors

  --profile <name>     Use a named profile (isolates OPENCLAW_STATE_DIR/OPENCLAW_CONFIG_PATH under ~/.openclaw-<name>)

  -V, --version        output the version number



Commands:

  Hint: commands suffixed with * have subcommands. Run <command> --help for details.

  acp *                Agent Control Protocol tools

  agent                Run one agent turn via the Gateway

  agents *             Manage isolated agents (workspaces, auth, routing)

  approvals *          Manage exec approvals (gateway or node host)

  browser *            Manage OpenClaw's dedicated browser (Chrome/Chromium)

  channels *           Manage connected chat channels (Telegram, Discord, etc.)

  clawbot *            Legacy clawbot command aliases

  completion           Generate shell completion script

  config *             Non-interactive config helpers (get/set/unset). Default: starts setup wizard.

  configure            Interactive setup wizard for credentials, channels, gateway, and agent defaults

  cron *               Manage cron jobs via the Gateway scheduler

  daemon *             Gateway service (legacy alias)

  dashboard            Open the Control UI with your current token

  devices *            Device pairing + token management

  directory *          Lookup contact and group IDs (self, peers, groups) for supported chat channels

  dns *                DNS helpers for wide-area discovery (Tailscale + CoreDNS)

  docs                 Search the live OpenClaw docs

  doctor               Health checks + quick fixes for the gateway and channels

  gateway *            Run, inspect, and query the WebSocket Gateway

  health               Fetch health from the running gateway

  help                 Display help for command

  hooks *              Manage internal agent hooks

  logs                 Tail gateway file logs via RPC

  memory *             Search and reindex memory files

  message *            Send, read, and manage messages

  models *             Discover, scan, and configure models

  node *               Run and manage the headless node host service

  nodes *              Manage gateway-owned node pairing and node commands

  onboard              Interactive onboarding wizard for gateway, workspace, and skills

  pairing *            Secure DM pairing (approve inbound requests)

  plugins *            Manage OpenClaw plugins and extensions

  qr                   Generate iOS pairing QR/setup code

  reset                Reset local config/state (keeps the CLI installed)

  sandbox *            Manage sandbox containers for agent isolation

  secrets *            Secrets runtime reload controls

  security *           Security tools and local config audits

  sessions *           List stored conversation sessions

  setup                Initialize local config and agent workspace

  skills *             List and inspect available skills

  status               Show channel health and recent session recipients

  system *             System events, heartbeat, and presence

  tui                  Open a terminal UI connected to the Gateway

  uninstall            Uninstall the gateway service + local data (CLI remains)

  update *             Update OpenClaw and inspect update channel status

  webhooks *           Webhook helpers and integrations



Examples:

  openclaw models --help

    Show detailed help for the models command.

  openclaw channels login --verbose

    Link personal WhatsApp Web and show QR + connection logs.

  openclaw message send --target +15555550123 --message "Hi" --json

    Send via your web session and print JSON result.

  openclaw gateway --port 18789

    Run the WebSocket Gateway locally.

  openclaw --dev gateway

    Run a dev Gateway (isolated state/config) on ws://127.0.0.1:19001.

  openclaw gateway --force

    Kill anything bound to the default gateway port, then start it.

  openclaw gateway ...

    Gateway control via WebSocket.

  openclaw agent --to +15555550123 --message "Run summary" --deliver

    Talk directly to the agent using the Gateway; optionally send the WhatsApp reply.

  openclaw message send --channel telegram --target @mychat --message "Hi"

    Send via your Telegram bot.



🦞 OpenClaw 2026.2.26 (bc50708) — I keep secrets like a vault... unless you print them in debug logs again.



Usage: openclaw agent [options]



Run an agent turn via the Gateway (use --local for embedded)



Options:

  --agent <id>               Agent id (overrides routing bindings)

  --channel <channel>        Delivery channel: last|telegram|whatsapp|discord|irc|googlechat|slack|signal|imessage (omit to use the  

                             main session channel)

  --deliver                  Send the agent's reply back to the selected channel (default: false)

  -h, --help                 Display help for command

  --json                     Output result as JSON (default: false)

  --local                    Run the embedded agent locally (requires model provider API keys in your shell) (default: false)        

  -m, --message <text>       Message body for the agent

  --reply-account <id>       Delivery account id override

  --reply-channel <channel>  Delivery channel override (separate from routing)

  --reply-to <target>        Delivery target override (separate from session routing)

  --session-id <id>          Use an explicit session id

  -t, --to <number>          Recipient number in E.164 used to derive the session key

  --thinking <level>         Thinking level: off | minimal | low | medium | high

  --timeout <seconds>        Override agent command timeout (seconds, default 600 or config value)

  --verbose <on|off>         Persist agent verbose level for the session



Examples:

  openclaw agent --to +15555550123 --message "status update"

    Start a new session.

  openclaw agent --agent ops --message "Summarize logs"

    Use a specific agent.

  openclaw agent --session-id 1234 --message "Summarize inbox" --thinking medium

    Target a session with explicit thinking level.

  openclaw agent --to +15555550123 --message "Trace logs" --verbose on --json

    Enable verbose logging and JSON output.

  openclaw agent --to +15555550123 --message "Summon reply" --deliver

    Deliver reply.

  openclaw agent --agent ops --message "Generate report" --deliver --reply-channel slack --reply-to "#reports"

    Send reply to a different channel/target.



Docs: docs.openclaw.ai/cli/agent

hys@DESKTOP-ROGPH03:/mnt/c/Users/Foryoucom/Documents/GitHub/GameNewsAgent$ 

hys@DESKTOP-ROGPH03:/mnt/c/Users/Foryoucom/Documents/GitHub/GameNewsAgent$ openclaw models --help



🦞 OpenClaw 2026.2.26 (bc50708) — Claws out, commit in—let's ship something mildly responsible.



Usage: openclaw models [options] [command]



Model discovery, scanning, and configuration



Options:

  --agent <id>     Agent id to inspect (overrides OPENCLAW_AGENT_DIR/PI_CODING_AGENT_DIR)

  -h, --help       Display help for command

  --status-json    Output JSON (alias for `models status --json`) (default: false)

  --status-plain   Plain output (alias for `models status --plain`) (default: false)



Commands:

  aliases          Manage model aliases

  auth             Manage model auth profiles

  fallbacks        Manage model fallback list

  image-fallbacks  Manage image model fallback list

  list             List models (configured by default)

  scan             Scan OpenRouter free models for tools + images

  set              Set the default model

  set-image        Set the image model

  status           Show configured model state



Docs: docs.openclaw.ai/cli/models