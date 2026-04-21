# ---------------------------------------------------------------------------
# Dockerfile for the AlgoVoi MCP Server
#
# Used by Glama.ai's automated inspector to build, run, and introspect the
# server's tools list. For end users, the preferred install is still:
#   npx -y @algovoi/mcp-server
# or:
#   uvx algovoi-mcp
#
# Build:  docker build -f mcp-server/Dockerfile -t algovoi-mcp-server .
# Run:    docker run -i --rm                                            \
#           -e ALGOVOI_API_KEY=algv_...                                 \
#           -e ALGOVOI_API_BASE=https://cloud.algovoi.co.uk             \
#           algovoi-mcp-server
#
# The server speaks MCP over stdio. Keep `-i` so stdin stays attached;
# Glama's inspector sends a JSON-RPC `initialize` + `tools/list` over stdin
# and reads the response from stdout.
# ---------------------------------------------------------------------------

FROM node:22-alpine

# Install the published npm package globally. We pin a specific version so
# Glama's build output is reproducible and doesn't silently update on rebuild.
RUN npm install -g @algovoi/mcp-server@1.2.1

# Run as an unprivileged user.
RUN addgroup -S mcp && adduser -S mcp -G mcp
WORKDIR /home/mcp
USER mcp

# The MCP server uses stdio transport. Env vars configure auth / routing;
# see the README for the full list. ALGOVOI_API_KEY is required; the others
# have sensible defaults.
ENV ALGOVOI_API_BASE=https://cloud.algovoi.co.uk

# No exposed port — stdio only. ENTRYPOINT uses the bin shim installed by npm.
ENTRYPOINT ["algovoi-mcp-server"]
