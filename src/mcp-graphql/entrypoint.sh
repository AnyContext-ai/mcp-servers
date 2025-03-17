#!/bin/sh
set -e

# Move into the correct directory
cd /app

# Start constructing the command inside --stdio
CMD="npx supergateway --stdio 'dist/index.js --endpoint \"$ENDPOINT\""

# Append headers inside the --stdio argument
if [ -n "$BEARER_TOKEN" ]; then
    CMD="$CMD --headers \"{\\\"Authorization\\\": \\\"Bearer $BEARER_TOKEN\\\"}\""
fi

# Append --enable-mutations flag if set to true
if [ "$ENABLE_MUTATIONS" = "true" ]; then
    CMD="$CMD --enable-mutations"
fi

# Close the quoted --stdio argument
CMD="$CMD'"

# Debugging: Show final command before execution
echo "Executing: $CMD"

# Execute the command correctly
exec sh -c "$CMD"
