# slack-mcp-server
MCP Server for the Slack API, enabling Claude to interact with Slack workspaces.

### Build and run
```
docker build -t slack-mcp-server .

docker run --rm -p 8000:8000 -e SLACK_BOT_TOKEN="your-bot-token" -e SLACK_TEAM_ID="your-team-id" slack-mcp-server
```