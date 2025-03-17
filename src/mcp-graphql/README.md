# mcp-graphql

A Model Context Protocol server that enables LLMs to interact with GraphQL APIs. This implementation provides schema introspection and query execution capabilities, allowing models to discover and use GraphQL APIs dynamically.

### Build and run
```
docker build -t mcp-graphql .

docker run --rm -p 8000:8000 -e ENDPOINT="https://countries.trevorblades.com/" -e BEARER_TOKEN="my-super-secret-token" -e ENABLE_MUTATIONS=true mcp-graphql
```