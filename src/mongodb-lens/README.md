# MongoDB Lens

[![License](https://img.shields.io/github/license/furey/mongodb-lens)](./LICENSE)
[![Docker Hub Version](https://img.shields.io/docker/v/furey/mongodb-lens)](https://hub.docker.com/r/furey/mongodb-lens)
[![NPM Version](https://img.shields.io/npm/v/mongodb-lens)](https://www.npmjs.com/package/mongodb-lens)
[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-donate-orange.svg)](https://www.buymeacoffee.com/furey)

**MongoDB Lens** is a local Model Context Protocol (MCP) server with full featured access to MongoDB databases using natural language via LLMs to perform queries, run aggregations, optimize performance, and more.

## Contents

- [Quick Start](#quick-start)
- [Features](#features)
- [Installation](#installation)
- [Configuration](#configuration)
- [Client Setup](#client-setup)
- [Data Protection](#data-protection)
- [Tutorial](#tutorial)
- [Disclaimer](#disclaimer)
- [Support](#support)

## Quick Start

- [Install](#installation) MongoDB Lens
- [Configure](#configuration) MongoDB Lens
- [Set up](#client-setup) your MCP Client (e.g. [Claude Desktop](#client-setup-claude-desktop))
- Explore your MongoDB databases with [natural language queries](#tutorial-4-example-queries)

## Features

- [Tools](#tools)
- [Resources](#resources)
- [Prompts](#prompts)
- [Other](#other-features)

### Tools

- `aggregate-data`: Execute aggregation pipelines (with streaming support for large result sets)
- `analyze-query-patterns`: Analyze queries and suggest optimizations
- `analyze-schema`: Automatically infer collection schemas
- `bulk-operations`: Perform multiple operations efficiently
- `collation-query`: Find documents with language-specific collation rules
- `compare-schemas`: Compare schemas between two collections
- `count-documents`: Count documents matching specified criteria
- `create-collection`: Create new collections with custom options
- `create-index`: Create new indexes for performance optimization
- `create-timeseries`: Create time series collections for temporal data
- `current-database`: Show the current database context
- `distinct-values`: Extract unique values for any field
- `drop-collection`: Remove collections from the database
- `explain-query`: Analyze query execution plans
- `export-data`: Export query results in JSON or CSV format
- `find-documents`: Run queries with filters, projections, and sorting (with streaming for large result sets)
- `generate-schema-validator`: Generate JSON Schema validators
- `geo-query`: Perform geospatial queries with various operators
- `get-stats`: Retrieve database or collection statistics
- `gridfs-operation`: Manage large files with GridFS buckets
- `list-collections`: Explore collections in the current database
- `list-databases`: View all accessible MongoDB databases
- `map-reduce`: Run MapReduce operations for complex data processing
- `modify-document`: Insert, update, or delete specific documents
- `rename-collection`: Rename existing collections
- `shard-status`: View sharding configuration for databases and collections
- `text-search`: Perform full-text search across text-indexed fields
- `transaction`: Execute multiple operations in a single ACID transaction
- `use-database`: Switch to a specific database context
- `validate-collection`: Check for data inconsistencies
- `watch-changes`: Monitor real-time changes to collections

### Resources

- `collection-indexes`: Index information for a collection
- `collection-schema`: Schema information for a collection
- `collection-stats`: Performance statistics for a collection
- `collection-validation`: Validation rules for a collection
- `collections`: List of collections in the current database
- `database-triggers`: Database change streams and event triggers configuration
- `database-users`: Database users and roles in the current database
- `databases`: List of all accessible databases
- `performance-metrics`: Real-time performance metrics and profiling data
- `replica-status`: Replica set status and configuration
- `server-status`: Server status information
- `stored-functions`: Stored JavaScript functions in the current database

### Prompts

- `aggregation-builder`: Step-by-step creation of aggregation pipelines
- `backup-strategy`: Customized backup and recovery recommendations
- `data-modeling`: Expert advice on MongoDB schema design for specific use cases
- `database-health-check`: Comprehensive database health assessment and recommendations
- `index-recommendation`: Get personalized index suggestions based on query patterns
- `inspector-guide`: Get help using MongoDB Lens with MCP Inspector
- `migration-guide`: Step-by-step MongoDB version migration plans
- `mongo-shell`: Generate MongoDB shell commands with explanations
- `multi-tenant-design`: Design MongoDB multi-tenant database architecture
- `query-builder`: Interactive guidance for constructing MongoDB queries
- `query-optimizer`: Optimization recommendations for slow queries
- `schema-analysis`: Detailed collection schema analysis with recommendations
- `schema-versioning`: Manage schema evolution in MongoDB applications
- `security-audit`: Database security analysis and improvement recommendations
- `sql-to-mongodb`: Convert SQL queries to MongoDB aggregation pipelines

### Other Features

- **Sanitized Inputs**: Security enhancements for query processing
- **Configuration File**: Custom configuration via `~/.mongodb-lens.json`
- **Connection Resilience**: Automatic reconnection with exponential backoff
- **Smart Caching**: Enhanced caching for schemas, collection lists, and server status
- **JSONRPC Error Handling**: Comprehensive error handling with proper error codes
- **Memory Management**: Automatic memory monitoring and cleanup for large operations
- **Streaming Support**: Stream large result sets for `find-documents` and `aggregate-data` operations

## Installation

MongoDB Lens can be installed and run in several ways:

- [NPX](#installation-npx) (Easiest)
- [Docker Hub](#installation-docker-hub)
- [Node.js from Source](#installation-nodejs-from-source)
- [Docker from Source](#installation-docker-from-source)
- [Installation Verification](#installation-verification)

### Installation: NPX

> [!NOTE]<br>
> NPX requires [Node.js](https://nodejs.org/en/download) installed and running on your system (suggestion: use [Volta](https://volta.sh)).

The easiest way to run MongoDB Lens is using `npx`:

```console
# Using default connection string mongodb://localhost:27017
npx -y mongodb-lens

# Using custom connection string
npx -y mongodb-lens mongodb://your-connection-string
```

> [!TIP]<br>
> If you encounter permissions errors with `npx`, try running `npx clear-npx-cache` prior to running `npx -y mongodb-lens` (this clears the cache and re-downloads the package).

### Installation: Docker Hub

> [!NOTE]<br>
> Docker Hub requires [Docker](https://docs.docker.com/get-started/get-docker) installed and running on your system.

Run MongoDB Lens via Docker Hub:

```console
# Using default connection string mongodb://localhost:27017
docker run --rm -i --network=host furey/mongodb-lens

# Using custom connection string
docker run --rm -i --network=host furey/mongodb-lens mongodb://your-connection-string

# Using "--pull" to keep the Docker image up-to-date
docker run --rm -i --network=host --pull=always furey/mongodb-lens
```

### Installation: Node.js from Source

> [!NOTE]<br>
> Node.js from source requires [Node.js](https://nodejs.org/en/download) installed and running on your system (suggestion: use [Volta](https://volta.sh)).

1. Clone the MongoDB Lens repository:<br>
    ```console
    git clone https://github.com/furey/mongodb-lens.git
    ```
1. Navigate to the cloned repository directory:<br>
    ```console
    cd /path/to/mongodb-lens
    ```
1. Install Node.js dependencies:<br>
    ```console
    node --version # …ideally >= v22.*.*
    npm ci
    ```
1. Start the server:<br>
    ```console
    # Using default connection string mongodb://localhost:27017
    node mongodb-lens.js

    # Using custom connection string
    node mongodb-lens.js mongodb://your-connection-string
    ```

### Installation: Docker from Source

> [!NOTE]<br>
> Docker from source requires [Docker](https://docs.docker.com/get-started/get-docker) installed and running on your system.

1. Clone the MongoDB Lens repository:<br>
    ```console
    git clone https://github.com/furey/mongodb-lens.git
    ```
1. Navigate to the cloned repository directory:<br>
    ```console
    cd /path/to/mongodb-lens
    ```
1. Build the Docker image:<br>
    ```console
    docker build -t mongodb-lens .
    ```
1. Run the container:<br>
    ```console
    # Using default connection string mongodb://localhost:27017
    docker run --rm -i --network=host mongodb-lens

    # Using custom connection string
    docker run --rm -i --network=host mongodb-lens mongodb://your-connection-string
    ```

### Installation Verification

To verify the installation, paste and run the following jsonrpc message into the server's stdio:
    
```json
{"method":"resources/read","params":{"uri":"mongodb://databases"},"jsonrpc":"2.0","id":1}
```

The server should respond with a list of databases in your MongoDB instance, for example:

```json
{"result":{"contents":[{"uri":"mongodb://databases","text":"Databases (12):\n- admin (180.00 KB)\n- config (108.00 KB)\n- local (40.00 KB)\n- sample_airbnb (51.88 MB)\n- sample_analytics (9.46 MB)\n- sample_geospatial (980.00 KB)\n- sample_guides (40.00 KB)\n- sample_mflix (108.90 MB)\n- sample_restaurants (7.73 MB)\n- sample_supplies (968.00 KB)\n- sample_training (40.85 MB)\n- sample_weatherdata (2.69 MB)"}]},"jsonrpc":"2.0","id":1}
```

MongoDB Lens is now installed and ready to accept MCP requests.

## Configuration

- [MongoDB Connection String](#configuration-mongodb-connection-string)
- [Verbose Logging](#configuration-verbose-logging)
- [Config File](#configuration-config-file)

### Configuration: MongoDB Connection String

The server accepts a MongoDB connection string as its only argument.

Example NPX usage:

```console
npx -y mongodb-lens mongodb://your-connection-string
```

MongoDB connection strings have the following format:

```txt
mongodb://[username:password@]host[:port][/database][?options]
```

Example connection strings:

- Local connection:<br>
  `mongodb://localhost:27017`
- Connection to `mydatabase` with credentials from `admin` database:<br>
  `mongodb://username:password@hostname:27017/mydatabase?authSource=admin`
- Connection to `mydatabase` with various other options:<br>
  `mongodb://hostname:27017/mydatabase?retryWrites=true&w=majority`

If no connection string is provided, the server will attempt to connect via local connection.

### Configuration: Verbose Logging

With verbose logging enabled, the server will output additional information to the console.

To enable verbose logging, set environment variable `VERBOSE_LOGGING` to `true`.

Example NPX usage:

```console
VERBOSE_LOGGING=true npx -y mongodb-lens mongodb://your-connection-string
```

Example Docker Hub usage:

```console
docker run --rm -i --network=host -e VERBOSE_LOGGING='true' furey/mongodb-lens mongodb://your-connection-string
```

### Configuration: Config File

MongoDB Lens can also be configured via JSON config file: `~/.mongodb-lens.json`

Alternatively, set environment variable `CONFIG_PATH` to the path of your custom config file.

Example NPX usage:

```console
CONFIG_PATH='/path/to/config.json' npx -y mongodb-lens
```

Example Docker Hub usage:

```console
docker run --rm -i --network=host -v /path/to/config.json:/root/.mongodb-lens.json furey/mongodb-lens
```

Example configuration file contents:

```json
{
  "mongoUri": "mongodb://username:password@hostname:27017/mydatabase?authSource=admin",
  "connectionOptions": {
    "maxPoolSize": 20,
    "connectTimeoutMS": 30000
  }
}
```

## Client Setup

- [Claude Desktop](#client-setup-claude-desktop)
- [MCP Inspector](#client-setup-mcp-inspector)
- [Other MCP Clients](#client-setup-other-mcp-clients)

### Client Setup: Claude Desktop

To use MongoDB Lens with Claude Desktop:

1. Install [Claude Desktop](https://claude.ai/download)
1. Open `claude_desktop_config.json` (create it if it doesn't exist):
    - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
    - Windows: `%APPDATA%\Claude\claude_desktop_config.json`
1. Add the MongoDB Lens server configuration as per [configuration options](#claude-desktop-configuration-options)
1. Restart Claude Desktop
1. Start a conversation with Claude about your MongoDB data

#### Claude Desktop Configuration Options

- [Option 1: NPX (Recommended)](#option-1-npx-recommended)
- [Option 2: Docker Hub Image](#option-2-docker-hub-image)
- [Option 3: Local Node.js Installation](#option-3-local-nodejs-installation)
- [Option 4: Local Docker Image](#option-4-local-docker-image)

For each option:

- Replace `mongodb://your-connection-string` with your MongoDB connection string or omit it to use the default `mongodb://localhost:27017`.
- Set `VERBOSE_LOGGING` to `true` or `false`.
- To use a custom config file, see [Configuration: Config File](#configuration-config-file) and adapt option accordingly.

##### Option 1: NPX (Recommended)

```json
{
  "mcpServers": {
    "mongodb-lens": {
      "command": "/path/to/npx",
      "args": [
        "-y",
        "mongodb-lens",
        "mongodb://your-connection-string"
      ],
      "env": {
        "VERBOSE_LOGGING": "[true|false]"
      }
    }
  }
}
```

##### Option 2: Docker Hub Image

```json
{
  "mcpServers": {
    "mongodb-lens": {
      "command": "docker",
      "args": [
        "run",
        "--rm",
        "-i",
        "--network=host",
        "--pull=always",
        "-e",
        "VERBOSE_LOGGING=[true|false]",
        "furey/mongodb-lens",
        "mongodb://your-connection-string"
      ]
    }
  }
}
```

##### Option 3: Local Node.js Installation

```json
{
  "mcpServers": {
    "mongodb-lens": {
      "command": "/path/to/node",
      "args": [
        "/path/to/mongodb-lens.js",
        "mongodb://your-connection-string"
      ],
      "env": {
        "VERBOSE_LOGGING": "[true|false]"
      }
    }
  }
}
```

##### Option 4: Local Docker Image

```json
{
  "mcpServers": {
    "mongodb-lens": {
      "command": "docker",
      "args": [
        "run",
        "--rm",
        "-i",
        "--network=host",
        "-e",
        "VERBOSE_LOGGING=[true|false]",
        "mongodb-lens",
        "mongodb://your-connection-string"
      ]
    }
  }
}
```

### Client Setup: MCP Inspector

[MCP Inspector](https://github.com/modelcontextprotocol/inspector) is a tool designed for testing and debugging MCP servers.

Example NPX usage:

1. Run Inspector:<br>
    ```console
    # Using default connection string mongodb://localhost:27017
    npx -y @modelcontextprotocol/inspector npx -y mongodb-lens

    # Using custom connection string
    npx -y @modelcontextprotocol/inspector npx -y mongodb-lens mongodb://your-connection-string

    # Using verbose logging
    npx -y @modelcontextprotocol/inspector -e VERBOSE_LOGGING=true npx -y mongodb-lens
    ```
1. Inspector starts a proxy server (default port: 3000) and web app (default port: 5173). To optionally change the default ports:<br>
    ```console
    CLIENT_PORT=1234 SERVER_PORT=5678 npx -y @modelcontextprotocol/inspector npx -y mongodb-lens
    ```
1. Open Inspector: http://localhost:5173

Inspector should support the full range of MongoDB Lens capabilities, including autocompletion for collection names and query fields.

For more, see: [MCP Inspector](https://modelcontextprotocol.io/docs/tools/inspector)

### Client Setup: Other MCP Clients

MongoDB Lens should be usable with any MCP-compatible client.

For more, see: [MCP Documentation: Example Clients](https://modelcontextprotocol.io/clients)

## Data Protection

To protect your data while using MongoDB Lens, consider the following:

- [Read-Only User Accounts](#data-protection-read-only-user-accounts)
- [Working with Database Backups](#data-protection-working-with-database-backups)

### Data Protection: Read-Only User Accounts

When connecting MongoDB Lens to your database, the permissions granted to the user in your connection string dictate what actions can be performed. For exploration and analysis, a read-only user can prevent unintended writes or deletes, ensuring MongoDB Lens can query data but not alter it.

To set this up, create a user with the `'read'` role scoped to the database(s) you're targeting. In MongoDB shell, you'd run something like:

```js
use admin

db.createUser({
  user: 'readonly',
  pwd: 'eXaMpLePaSsWoRd',
  roles: [{ role: 'read', db: 'mydatabase' }]
})
```

Then, plug those credentials into your MongoDB Lens connection string (e.g. `mongodb://readonly:eXaMpLePaSsWoRd@localhost:27017/mydatabase`). This restricts MongoDB Lens to read-only operations, safeguarding your data during development or testing. It's a simple yet effective way to enforce security boundaries, especially when you're poking around schemas or running ad-hoc queries.

### Data Protection: Working with Database Backups

To keep your production data unmodified while leveraging MongoDB Lens for analysis, its suggested to use a backup copy hosted on a separate MongoDB instance. This setup isolates your live environment, letting you experiment with queries or aggregations without risking accidental corruption.

Start by generating a backup with `mongodump`. Next, spin up a fresh MongoDB instance (e.g. on a different port like `27018`) and restore the backup there using `mongorestore`. Once it's running, point MongoDB Lens to the backup instance's connection string (e.g. `mongodb://localhost:27018/mydatabase`).

This approach gives you a sandbox to test complex operations—like pipeline-heavy aggregations or schema tweaks—without touching your production data. It's a practical choice when you need to dig into your dataset safely, especially in scenarios where live modifications aren't an option.

## Tutorial

This following tutorial guides you through setting up a MongoDB container with sample data, then using MongoDB Lens to interact with it through natural language queries:

1. [Start Sample Data Container](#tutorial-1-start-sample-data-container)
2. [Import Sample Data](#tutorial-2-import-sample-data)
3. [Connect MongoDB Lens](#tutorial-3-connect-mongodb-lens)
4. [Example Queries](#tutorial-4-example-queries)

### Tutorial: 1. Start Sample Data Container

> [!NOTE]<br>
> This tutorial assumes you have [Docker](https://docs.docker.com/get-started/get-docker/) installed and running on your system.

> [!IMPORTANT]<br>
> If Docker is already running a container on port 27017, stop it before proceeding.

1. Initialise sample data container:<br>
    ```console
    docker run --name mongodb-sampledata -d -p 27017:27017 mongo:6
    ```
1. Verify the container is running without issue:<br>
    ```console
    docker ps | grep mongodb-sampledata
    ```

### Tutorial: 2. Import Sample Data

MongoDB provides several [sample datasets](https://www.mongodb.com/docs/atlas/sample-data/#available-sample-datasets), which we'll use to explore MongoDB Lens.

1. Download the sample datasets:
    ```console<br>
    curl -LO https://atlas-education.s3.amazonaws.com/sampledata.archive
    ```
2. Copy the sample datasets into your sample data container:<br>
    ```console
    docker cp sampledata.archive mongodb-sampledata:/tmp/
    ```
3. Restore the sample data into MongoDB:<br>
    ```console
    docker exec -it mongodb-sampledata mongorestore --archive=/tmp/sampledata.archive
    ```

This will import several databases:

- `sample_airbnb`: Airbnb listings and reviews
- `sample_analytics`: Customer and account data
- `sample_geospatial`: Geographic data
- `sample_mflix`: Movie data
- `sample_restaurants`: Restaurant data
- `sample_supplies`: Supply chain data
- `sample_training`: Training data for various applications
- `sample_weatherdata`: Weather measurements

### Tutorial: 3. Connect MongoDB Lens

Download and [install](#installation) MongoDB Lens as per the [Quick Start](#quick-start) instructions.

Set your [MCP Client](#client-setup) to connect to MongoDB Lens via: `mongodb://localhost:27017`

> [!TIP]<br>
> Omitting the connection string from your MCP Client configuration will default the connection string to `mongodb://localhost:27017`.

Example [Claude Desktop configuration](#client-setup-claude-desktop):

```json
{
  "mcpServers": {
    "mongodb-lens": {
      "command": "/path/to/npx",
      "args": [
        "-y",
        "mongodb-lens"
      ]
    }
  }
}
```

### Tutorial: 4. Example Queries

With your MCP Client running and connected to MongoDB Lens, try these example queries that demonstrate the capabilities of the various tools, resources, and prompts available through MongoDB Lens:

- [Example Queries: Basic Database Operations](#example-queries-basic-database-operations)
- [Example Queries: Movie Data Analysis](#example-queries-movie-data-analysis)
- [Example Queries: Airbnb Data Exploration](#example-queries-airbnb-data-exploration)
- [Example Queries: Weather Data Operations](#example-queries-weather-data-operations)
- [Example Queries: Geospatial Operations](#example-queries-geospatial-operations)
- [Example Queries: Time Series & Change Streams](#example-queries-time-series--change-streams)
- [Example Queries: Bulk Operations & Data Modeling](#example-queries-bulk-operations--data-modeling)
- [Example Queries: Administrative Operations](#example-queries-administrative-operations)
- [Example Queries: Advanced Features](#example-queries-advanced-features)

#### Example Queries: Basic Database Operations

- _"List all available databases"_<br>
  <sup>➥ Uses `list-databases` tool</sup>
- _"What's the current database I'm connected to?"_<br>
  <sup>➥ Uses `current-database` tool</sup>
- _"Switch to the sample_mflix database"_<br>
  <sup>➥ Uses `use-database` tool</sup>
- _"What collections are available in this database?"_<br>
  <sup>➥ Uses `list-collections` tool</sup>
- _"Get statistics for the sample_mflix database"_<br>
  <sup>➥ Uses `get-stats` tool with database target</sup>
- _"Create the temp_collection collection, then drop it"_<br>
  <sup>➥ Uses `create-collection` & `drop-collection` tool</sup>

#### Example Queries: Movie Data Analysis

- _"Count how many movies are in the movies collection"_<br>
  <sup>➥ Uses `count-documents` tool</sup>
- _"Find the top 5 movies by IMDB rating with a runtime over 120 minutes"_<br>
  <sup>➥ Uses `find-documents` tool with sort and filter</sup>
- _"What's the schema of the movies collection?"_<br>
  <sup>➥ Uses `analyze-schema` tool</sup>
- _"Find distinct countries where movies were produced"_<br>
  <sup>➥ Uses `distinct-values` tool</sup>
- _"Create an index on the title field in the movies collection"_<br>
  <sup>➥ Uses `create-index` tool</sup>
- _"Why is my query for movies with over 1000 votes slow? Help me optimize it"_<br>
  <sup>➥ Uses `query-optimizer` prompt</sup>
- _"Run an explain on the query {year: 1995}"_<br>
  <sup>➥ Uses `explain-query` tool</sup>
- _"Build an aggregation pipeline to show the count of movies by decade and genre"_<br>
  <sup>➥ Uses `aggregation-builder` prompt</sup>
- _"Execute this aggregation pipeline: [{$group: {\_id: {$floor: {$divide: ['$year', 10]}}, count: {$sum: 1}}}]"_<br>
  <sup>➥ Uses `aggregate-data` tool</sup>
- _"Update all movies from 1994 to add a 'classic' field set to true"_<br>
  <sup>➥ Uses `modify-document` tool with update operation</sup>

#### Example Queries: Airbnb Data Exploration

- _"Switch to sample_airbnb database"_<br>
  <sup>➥ Uses `use-database` tool</sup>
- _"Get collection statistics for the listingsAndReviews collection"_<br>
  <sup>➥ Uses `get-stats` tool with collection target</sup>
- _"What's the validation rules for the listingsAndReviews collection?"_<br>
  <sup>➥ Uses `collection-validation` resource</sup>
- _"Show me the indexes on the listingsAndReviews collection"_<br>
  <sup>➥ Uses `collection-indexes` resource</sup>
- _"Find listings with more than 5 bedrooms in Manhattan, limited to 10 results"_<br>
  <sup>➥ Uses `find-documents` tool</sup>
- _"Get distinct property types in the listings"_<br>
  <sup>➥ Uses `distinct-values` tool</sup>
- _"Help me create a query filter to find superhosts with pool amenities"_<br>
  <sup>➥ Uses `query-builder` prompt</sup>
- _"Export the top 20 highest-rated listings in Brooklyn as CSV with name, price, and rating"_<br>
  <sup>➥ Uses `export-data` tool</sup>
- _"Is my schema optimized for querying by neighborhood? Analyze and give recommendations"_<br>
  <sup>➥ Uses `schema-analysis` prompt</sup>
- _"Rename the reviews collection to guest_reviews"_<br>
  <sup>➥ Uses `rename-collection` tool</sup>

#### Example Queries: Weather Data Operations

- _"Switch to sample_weatherdata database"_<br>
  <sup>➥ Uses `use-database` tool</sup>
- _"What's in the schema of the data collection?"_<br>
  <sup>➥ Uses `collection-schema` resource</sup>
- _"Find the highest recorded temperatures with a callLetters of 'SHIP'"_<br>
  <sup>➥ Uses `find-documents` tool</sup>
- _"Validate the data collection for inconsistencies"_<br>
  <sup>➥ Uses `validate-collection` tool</sup>
- _"Insert a new weather record for today"_<br>
  <sup>➥ Uses `modify-document` tool with insert operation</sup>
- _"Create a new collection called weather_summary"_<br>
  <sup>➥ Uses `create-collection` tool</sup>
- _"Create index recommendation for queries that filter by callLetters and sort by date"_<br>
  <sup>➥ Uses `index-recommendation` prompt</sup>
- _"Show me how to write a MapReduce operation to get average temperatures by day"_<br>
  <sup>➥ Uses `mongo-shell` prompt</sup>
- _"Run this MapReduce to calculate average pressure by location"_<br>
  <sup>➥ Uses `map-reduce` tool</sup>
- _"Delete all weather readings below -50 degrees"_<br>
  <sup>➥ Uses `modify-document` tool with delete operation</sup>

#### Example Queries: Geospatial Operations

- _"Switch to sample_geospatial database"_<br>
  <sup>➥ Uses `use-database` tool</sup>
- _"Find all shipwrecks within 5km of the coast of Florida"_<br>
  <sup>➥ Uses `geo-query` tool with near operator</sup>
- _"Show me restaurants that fall within the downtown Manhattan polygon"_<br>
  <sup>➥ Uses `geo-query` tool with geoWithin operator</sup>
- _"Which bike routes intersect with Central Park?"_<br>
  <sup>➥ Uses `geo-query` tool with geoIntersects operator</sup>
- _"Create a geospatial index on the location field of the neighborhoods collection"_<br>
  <sup>➥ Uses `create-index` tool with 2dsphere index type</sup>
- _"Analyze the schema of the shipwrecks collection to understand its geospatial data structure"_<br>
  <sup>➥ Uses `analyze-schema` tool</sup>

#### Example Queries: Time Series & Change Streams

- _"Create a new time series collection for sensor readings with 'timestamp' as the time field"_<br>
  <sup>➥ Uses `create-timeseries` tool</sup>
- _"Watch for changes in the orders collection for the next 30 seconds"_<br>
  <sup>➥ Uses `watch-changes` tool</sup>
- _"Monitor all insert operations on the users collection for 15 seconds"_<br>
  <sup>➥ Uses `watch-changes` tool with specific operations</sup>
- _"Create a time series collection for IoT device data with hourly granularity"_<br>
  <sup>➥ Uses `create-timeseries` tool with granularity option</sup>
- _"Create a time series collection that automatically deletes data older than 30 days"_<br>
  <sup>➥ Uses `create-timeseries` tool with expireAfterSeconds option</sup>

#### Example Queries: Bulk Operations & Data Modeling

- _"Switch to sample_training database"_<br>
  <sup>➥ Uses `use-database` tool</sup>
- _"Execute a bulk operation to update multiple post documents to add 'edited' flags"_<br>
  <sup>➥ Uses `bulk-operations` tool</sup>
- _"How should I model a social media application in MongoDB?"_<br>
  <sup>➥ Uses `data-modeling` prompt</sup>
- _"Perform a bulk insertion of new product records in the supplies database"_<br>
  <sup>➥ Uses `bulk-operations` tool</sup>
- _"Show me how to use MongoDB Lens with the MCP Inspector"_<br>
  <sup>➥ Uses `inspector-guide` prompt</sup>
- _"What's the optimal data model for a multi-tenant SaaS application with heavy analytical queries?"_<br>
  <sup>➥ Uses `data-modeling` prompt</sup>

#### Example Queries: Administrative Operations

- _"Switch to the admin database"_<br>
  <sup>➥ Uses `use-database` tool</sup>
- _"Show me the server status"_<br>
  <sup>➥ Uses `server-status` resource</sup>
- _"Display the replica set configuration"_<br>
  <sup>➥ Uses `replica-status` resource</sup>
- _"List all users in the database"_<br>
  <sup>➥ Uses `database-users` resource</sup>
- _"Get any stored JavaScript functions"_<br>
  <sup>➥ Uses `stored-functions` resource</sup>
- _"Perform a security audit on my MongoDB deployment"_<br>
  <sup>➥ Uses `security-audit` prompt</sup>
- _"What's a good backup strategy for my MongoDB instance?"_<br>
  <sup>➥ Uses `backup-strategy` prompt</sup>
- _"How would I migrate from MongoDB 4.4 to 6.0?"_<br>
  <sup>➥ Uses `migration-guide` prompt</sup>

#### Example Queries: Schema Management & Analysis

- _"Compare schemas between the users and customers collections"_<br>
  <sup>➥ Uses new `compare-schemas` tool to identify differences</sup>
- _"Generate a JSON Schema validator for the profiles collection with moderate strictness"_<br>
  <sup>➥ Uses new `generate-schema-validator` tool</sup>
- _"Analyze query patterns for the orders collection"_<br>
  <sup>➥ Uses new `analyze-query-patterns` tool</sup>
- _"What fields are missing in the new customers collection compared to the old one?"_<br>
  <sup>➥ Uses `compare-schemas` to analyze migration gaps</sup>
- _"Are my indexes being used effectively for my queries?"_<br>
  <sup>➥ Uses `analyze-query-patterns` to identify optimization opportunities</sup>

#### Example Queries: Advanced Features

- _"Switch to sample_mflix database"_<br>
  <sup>➥ Uses `use-database` tool</sup>
- _"Search for movies containing the phrase 'space odyssey' using text search"_<br>
  <sup>➥ Uses `text-search` tool</sup>
- _"Find users named 'müller' using German collation rules"_<br>
  <sup>➥ Uses `collation-query` tool</sup>
- _"List all files in the images GridFS bucket"_<br>
  <sup>➥ Uses `gridfs-operation` tool with list operation</sup>
- _"Get detailed information about the 'profile.jpg' file in GridFS"_<br>
  <sup>➥ Uses `gridfs-operation` tool with info operation</sup>
- _"Delete the 'old_backup.zip' file from the files GridFS bucket"_<br>
  <sup>➥ Uses `gridfs-operation` tool with delete operation</sup>
- _"Check the sharding status of the sample_analytics database"_<br>
  <sup>➥ Uses `shard-status` tool with database target</sup>
- _"View the sharding distribution for the customers collection"_<br>
  <sup>➥ Uses `shard-status` tool with collection target</sup>
- _"Execute a transaction that transfers $100 from account A to account B"_<br>
  <sup>➥ Uses `transaction` tool</sup>
- _"Get real-time performance metrics for my MongoDB server"_<br>
  <sup>➥ Uses `performance-metrics` resource</sup>
- _"Show me the current event triggers in my database"_<br>
  <sup>➥ Uses `database-triggers` resource</sup>
- _"Convert this SQL query to MongoDB: SELECT * FROM users WHERE age > 30 ORDER BY name"_<br>
  <sup>➥ Uses `sql-to-mongodb` prompt</sup>
- _"Perform a comprehensive health check on my database"_<br>
  <sup>➥ Uses `database-health-check` prompt</sup>
- _"Help me design a multi-tenant architecture for my SaaS application"_<br>
  <sup>➥ Uses `multi-tenant-design` prompt</sup>
- _"I need to add user address fields to my schema. How should I version and migrate?"_<br>
  <sup>➥ Uses `schema-versioning` prompt</sup>

## Disclaimer

MongoDB Lens:

- is licensed under the [MIT License](./LICENSE).
- is not affiliated with or endorsed by MongoDB, Inc.
- is written with the assistance of AI and may contain errors.
- is intended for educational and experimental purposes only.
- is provided as-is with no warranty—please use at your own risk.

## Support

If you've found MongoDB Lens helpful consider supporting my work through:

[Buy Me a Coffee](https://www.buymeacoffee.com/furey) | [GitHub Sponsorship](https://github.com/sponsors/furey)

Contributions help me continue developing and improving this tool, allowing me to dedicate more time to add new features and ensuring it remains a valuable resource for the community.