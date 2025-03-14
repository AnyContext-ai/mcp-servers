#!/usr/bin/env node

import { McpServer, ResourceTemplate } from '@modelcontextprotocol/sdk/server/mcp.js'
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js'
import { dirname, join } from 'path'
import { fileURLToPath } from 'url'
import { readFileSync, existsSync } from 'fs'
import mongodb from 'mongodb'
import { z } from 'zod'
import { Transform } from 'stream'

const { MongoClient, ObjectId, GridFSBucket } = mongodb

const CACHE_TTL = {
  SCHEMAS: 60 * 1000,
  COLLECTIONS: 30 * 1000,
  STATS: 15 * 1000,
  INDEXES: 120 * 1000,
  SERVER_STATUS: 20 * 1000
}

const memoryCache = {
  schemas: new Map(),
  collections: new Map(),
  stats: new Map(),
  indexes: new Map(),
  serverStatus: new Map(),
  fields: new Map()
}

const connectionOptions = {
  useUnifiedTopology: true, 
  maxPoolSize: 20,
  connectTimeoutMS: 30000,
  socketTimeoutMS: 360000,
  serverSelectionTimeoutMS: 30000,
  heartbeatFrequencyMS: 10000,
  retryWrites: false,
  useNewUrlParser: true
}

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)
const packageJson = JSON.parse(readFileSync(join(__dirname, 'package.json'), 'utf8'))
const PACKAGE_VERSION = packageJson.version
const VERBOSE_LOGGING = process.env.VERBOSE_LOGGING === 'true'
const CONFIG_PATH = process.env.CONFIG_PATH || join(process.env.HOME || __dirname, '.mongodb-lens.json')

let server = null
let watchdog = null
let transport = null
let currentDb = null
let configFile = null
let mongoClient = null
let currentDbName = null
let connectionRetries = 0

if (existsSync(CONFIG_PATH)) {
  try {
    configFile = JSON.parse(readFileSync(CONFIG_PATH, 'utf8'))
  } catch (error) {
    log(`Error loading config file: ${error.message}`, true)
  }
}

const instructions = `
MongoDB Lens is an MCP server that lets you interact with MongoDB databases through natural language.

Core capabilities include:

- Database exploration: List databases, view collections, analyze schemas
- Querying: Find documents, count, aggregate data, full-text search, geospatial queries
- Data management: Insert, update, delete documents, bulk operations, transactions
- Performance tools: Create indexes, explain queries, analyze patterns, view metrics
- Administration: Monitor server status, users, replication, sharding

Use tools like \`list-databases\`, \`find-documents\`, \`aggregate-data\`, \`create-index\`, and \`modify-document\` to interact with your data.

For complex tasks, use prompts like \`query-builder\`, \`schema-analysis\`, \`data-modeling\`, and \`sql-to-mongodb\` to get expert assistance.

Stream large result sets with \`streaming: true\` parameter and monitor real-time database changes with \`watch-changes\`.

For full documentation and examples, see: https://github.com/furey/mongodb-lens
`

const startWatchdog = () => {
  if (watchdog) clearInterval(watchdog)
  
  watchdog = setInterval(() => {
    const memoryUsage = process.memoryUsage()
    const heapUsedMB = Math.round(memoryUsage.heapUsed / 1024 / 1024)
    const heapTotalMB = Math.round(memoryUsage.heapTotal / 1024 / 1024)
    
    if (heapUsedMB > 1500) {
      log(`High memory usage: ${heapUsedMB}MB used of ${heapTotalMB}MB heap`, true)
      
      if (heapUsedMB > 2000) {
        log('Critical memory pressure. Clearing caches…', true)
        memoryCache.schemas.clear()
        memoryCache.collections.clear()
        memoryCache.stats.clear()
        memoryCache.indexes.clear()
        memoryCache.serverStatus.clear()
        memoryCache.fields.clear()
        global.gc && global.gc()
      }
    }

    const isClientConnected = mongoClient && mongoClient.topology && mongoClient.topology.isConnected()
    if (!isClientConnected) {
      log('Detected MongoDB disconnection. Attempting reconnect…', true)
      reconnect()
    }
    
  }, 30000)
}

const reconnect = async () => {
  if (connectionRetries > 10) {
    log('Maximum reconnection attempts reached. Giving up.', true)
    return false
  }
  
  connectionRetries++
  log(`Reconnection attempt ${connectionRetries}…`, true)
  
  try {
    await mongoClient.connect()
    log('Reconnected to MongoDB successfully', true)
    connectionRetries = 0
    return true
  } catch (error) {
    log(`Reconnection failed: ${error.message}`, true)
    return false
  }
}

const createTransport = async () => {
  log('Starting stdio transport…', true)
  transport = new StdioServerTransport()
  
  return transport
}

const main = async (mongoUri) => {
  log(`MongoDB Lens v${PACKAGE_VERSION} starting…`, true)
  
  const connected = await connect(mongoUri)
  if (!connected) {
    log('Failed to connect to MongoDB database.', true)
    return false
  }
  
  startWatchdog()
  
  log('Initializing MCP server…')
  server = new McpServer({
    name: 'MongoDB Lens',
    version: PACKAGE_VERSION,
    description: 'MongoDB MCP server for natural language database interaction',
    homepage: 'https://github.com/furey/mongodb-lens',
    license: 'MIT',
    vendor: {
      name: 'James Furey',
      url: 'https://about.me/jamesfurey'
    }
  }, {
    instructions
  })

  const JSONRPC_ERROR_CODES = {
    PARSE_ERROR: -32700,
    INVALID_REQUEST: -32600,
    METHOD_NOT_FOUND: -32601,
    INVALID_PARAMS: -32602,
    INTERNAL_ERROR: -32603,
    SERVER_ERROR_START: -32000,
    SERVER_ERROR_END: -32099,
    MONGODB_CONNECTION_ERROR: -32050,
    MONGODB_QUERY_ERROR: -32051,
    MONGODB_SCHEMA_ERROR: -32052,
    RESOURCE_NOT_FOUND: -32040,
    RESOURCE_ACCESS_DENIED: -32041
  }

  server.fallbackRequestHandler = async (request) => {
    log(`Received request for undefined method: ${request.method}`, true)
    const error = new Error(`Method '${request.method}' not found`)
    error.code = JSONRPC_ERROR_CODES.METHOD_NOT_FOUND
    throw error
  }
  
  log('Registering MCP resources…')
  registerResources(server)
  
  log('Registering MCP tools…')
  registerTools(server)
  
  log('Registering MCP prompts…')
  registerPrompts(server)
  
  log('Creating transport…')
  transport = await createTransport()
  
  log('Connecting MCP server transport…')
  await server.connect(transport)
  
  log('MongoDB Lens server running.', true)
  return true
}

const connect = async (uri = 'mongodb://localhost:27017') => {
  try {
    log(`Connecting to MongoDB at: ${uri}`)
    
    const finalUri = configFile?.mongoUri || uri
    const finalOptions = {
      ...connectionOptions,
      ...(configFile?.connectionOptions || {})
    }
    
    mongoClient = new MongoClient(finalUri, finalOptions)
    
    let retryCount = 0
    const maxRetries = 5
    
    while (retryCount < maxRetries) {
      try {
        await mongoClient.connect()
        break
      } catch (connectionError) {
        retryCount++
        if (retryCount >= maxRetries) {
          throw connectionError
        }
        const delay = Math.min(1000 * Math.pow(2, retryCount), 30000)
        log(`Connection attempt ${retryCount} failed, retrying in ${delay/1000} seconds…`)
        await new Promise(resolve => setTimeout(resolve, delay))
      }
    }
    
    const adminDb = mongoClient.db('admin')
    let serverInfo
    
    try {
      serverInfo = await adminDb.command({ buildInfo: 1 })
      log(`Connected to MongoDB server version: ${serverInfo.version}`)
      
      const cacheKey = 'server_info'
      memoryCache.serverStatus.set(cacheKey, {
        data: serverInfo,
        timestamp: Date.now()
      })
    } catch (infoError) {
      log(`Warning: Unable to get server info: ${infoError.message}`)
    }
    
    currentDbName = extractDbNameFromConnectionString(finalUri)
    currentDb = mongoClient.db(currentDbName)
    
    try {
      await currentDb.stats()
    } catch (statsError) {
      log(`Warning: Unable to get database stats: ${statsError.message}`)
    }
    
    mongoClient.on('error', (err) => {
      log(`MongoDB connection error: ${err.message}. Will attempt to reconnect.`, true)
    })
    
    mongoClient.on('close', () => {
      log('MongoDB connection closed. Will attempt to reconnect.', true)
    })
    
    log(`Connected to MongoDB successfully, using database: ${currentDbName}`)
    return true
  } catch (error) {
    log(`MongoDB connection error: ${error.message}`, true)
    return false
  }
}

const extractDbNameFromConnectionString = (uri) => {
  const pathParts = uri.split('/').filter(part => part)
  const lastPart = pathParts[pathParts.length - 1]?.split('?')[0]
  currentDbName = (lastPart && !lastPart.includes(':')) ? lastPart : 'admin'
  return currentDbName
}

const registerResources = (server) => {
  server.resource(
    'databases',
    'mongodb://databases',
    { description: 'List of all accessible MongoDB databases' },
    async () => {
      log('Resource: Retrieving list of databases…')
      const dbs = await listDatabases()
      log(`Resource: Found ${dbs.length} databases.`)
      return {
        contents: [{
          uri: 'mongodb://databases',
          text: formatDatabasesList(dbs)
        }]
      }
    }
  )
  
  server.resource(
    'collections',
    'mongodb://collections',
    { description: 'List of collections in the current database' },
    async () => {
      log(`Resource: Retrieving collections from database '${currentDbName}'…`)
      const collections = await listCollections()
      log(`Resource: Found ${collections.length} collections.`)
      return {
        contents: [{
          uri: 'mongodb://collections',
          text: formatCollectionsList(collections)
        }]
      }
    }
  )
  
  server.resource(
    'collection-schema',
    new ResourceTemplate('mongodb://collection/{name}/schema', { 
      list: async () => {
        try {
          log('Resource: Listing collection schemas…')
          const collections = await listCollections()
          log(`Resource: Preparing schema resources for ${collections.length} collections.`)
          return {
            resources: collections.map(coll => ({
              uri: `mongodb://collection/${coll.name}/schema`,
              name: `${coll.name} Schema`,
              description: `Schema for ${coll.name} collection`
            }))
          }
        } catch (error) {
          log(`Error listing collection schemas: ${error.message}`, true)
          return { resources: [] }
        }
      },
      complete: {
        name: async (value) => {
          try {
            log(`Resource: Autocompleting collection name with prefix '${value}'…`)
            const collections = await listCollections()
            const matches = collections
              .map(coll => coll.name)
              .filter(name => name.toLowerCase().includes(value.toLowerCase()))
            log(`Resource: Found ${matches.length} matching collections.`)
            return matches
          } catch (error) {
            log(`Error completing collection names: ${error.message}`, true)
            return []
          }
        }
      }
    }),
    { description: 'Schema information for a MongoDB collection' },
    async (uri, { name }) => {
      log(`Resource: Inferring schema for collection '${name}'…`)
      const schema = await inferSchema(name)
      log(`Resource: Schema inference complete for '${name}', identified ${Object.keys(schema.fields).length} fields.`)
      return {
        contents: [{
          uri: uri.href,
          text: formatSchema(schema)
        }]
      }
    }
  )
  
  server.resource(
    'collection-stats',
    new ResourceTemplate('mongodb://collection/{name}/stats', { 
      list: async () => {
        try {
          log('Resource: Listing collection stats resources…')
          const collections = await listCollections()
          log(`Resource: Preparing stats resources for ${collections.length} collections.`)
          return {
            resources: collections.map(coll => ({
              uri: `mongodb://collection/${coll.name}/stats`,
              name: `${coll.name} Stats`,
              description: `Statistics for ${coll.name} collection`
            }))
          }
        } catch (error) {
          log(`Error listing collections for stats: ${error.message}`, true)
          return { resources: [] }
        }
      },
      complete: {
        name: async (value) => {
          try {
            log(`Resource: Autocompleting collection name for stats with prefix '${value}'…`)
            const collections = await listCollections()
            const matches = collections
              .map(coll => coll.name)
              .filter(name => name.toLowerCase().includes(value.toLowerCase()))
            log(`Resource: Found ${matches.length} matching collections for stats.`)
            return matches
          } catch (error) {
            log(`Error completing collection names: ${error.message}`, true)
            return []
          }
        }
      }
    }),
    { description: 'Performance statistics for a MongoDB collection' },
    async (uri, { name }) => {
      log(`Resource: Retrieving stats for collection '${name}'…`)
      const stats = await getCollectionStats(name)
      log(`Resource: Retrieved stats for collection '${name}'.`)
      return {
        contents: [{
          uri: uri.href,
          text: formatStats(stats)
        }]
      }
    }
  )
  
  server.resource(
    'collection-indexes',
    new ResourceTemplate('mongodb://collection/{name}/indexes', { 
      list: async () => {
        try {
          log('Resource: Listing collection indexes resources…')
          const collections = await listCollections()
          log(`Resource: Preparing index resources for ${collections.length} collections.`)
          return {
            resources: collections.map(coll => ({
              uri: `mongodb://collection/${coll.name}/indexes`,
              name: `${coll.name} Indexes`,
              description: `Indexes for ${coll.name} collection`
            }))
          }
        } catch (error) {
          log(`Error listing collections for indexes: ${error.message}`, true)
          return { resources: [] }
        }
      },
      complete: {
        name: async (value) => {
          try {
            log(`Resource: Autocompleting collection name for indexes with prefix '${value}'…`)
            const collections = await listCollections()
            const matches = collections
              .map(coll => coll.name)
              .filter(name => name.toLowerCase().includes(value.toLowerCase()))
            log(`Resource: Found ${matches.length} matching collections for indexes.`)
            return matches
          } catch (error) {
            log(`Error completing collection names: ${error.message}`, true)
            return []
          }
        }
      }
    }),
    { description: 'Index information for a MongoDB collection' },
    async (uri, { name }) => {
      log(`Resource: Retrieving indexes for collection '${name}'…`)
      const indexes = await getCollectionIndexes(name)
      log(`Resource: Retrieved ${indexes.length} indexes for collection '${name}'.`)
      return {
        contents: [{
          uri: uri.href,
          text: formatIndexes(indexes)
        }]
      }
    }
  )

  server.resource(
    'server-status',
    'mongodb://server/status',
    { description: 'MongoDB server status information' },
    async () => {
      log('Resource: Retrieving server status…')
      const status = await getServerStatus()
      log('Resource: Retrieved server status information.')
      return {
        contents: [{
          uri: 'mongodb://server/status',
          text: formatServerStatus(status)
        }]
      }
    }
  )

  server.resource(
    'replica-status',
    'mongodb://server/replica',
    { description: 'MongoDB replica set status and configuration' },
    async () => {
      log('Resource: Retrieving replica set status…')
      const status = await getReplicaSetStatus()
      log('Resource: Retrieved replica set status information.')
      return {
        contents: [{
          uri: 'mongodb://server/replica',
          text: formatReplicaSetStatus(status)
        }]
      }
    }
  )

  server.resource(
    'collection-validation',
    new ResourceTemplate('mongodb://collection/{name}/validation', {
      list: async () => {
        try {
          log('Resource: Listing collection validation resources…')
          const collections = await listCollections()
          log(`Resource: Preparing validation resources for ${collections.length} collections.`)
          return {
            resources: collections.map(coll => ({
              uri: `mongodb://collection/${coll.name}/validation`,
              name: `${coll.name} Validation`,
              description: `Validation rules for ${coll.name} collection`
            }))
          }
        } catch (error) {
          log(`Error listing collections for validation: ${error.message}`, true)
          return { resources: [] }
        }
      },
      complete: {
        name: async (value) => {
          try {
            log(`Resource: Autocompleting collection name for validation with prefix '${value}'…`)
            const collections = await listCollections()
            const matches = collections
              .map(coll => coll.name)
              .filter(name => name.toLowerCase().includes(value.toLowerCase()))
            return matches
          } catch (error) {
            log(`Error completing collection names: ${error.message}`, true)
            return []
          }
        }
      }
    }),
    { description: 'Validation rules for a MongoDB collection' },
    async (uri, { name }) => {
      log(`Resource: Retrieving validation rules for collection '${name}'…`)
      const validation = await getCollectionValidation(name)
      log(`Resource: Retrieved validation rules for collection '${name}'.`)
      return {
        contents: [{
          uri: uri.href,
          text: formatValidationRules(validation)
        }]
      }
    }
  )

  server.resource(
    'database-users',
    'mongodb://database/users',
    { description: 'MongoDB database users and roles' },
    async () => {
      log('Resource: Retrieving database users…')
      const users = await getDatabaseUsers()
      log(`Resource: Retrieved user information.`)
      return {
        contents: [{
          uri: 'mongodb://database/users',
          text: formatDatabaseUsers(users)
        }]
      }
    }
  )

  server.resource(
    'stored-functions',
    'mongodb://database/functions',
    { description: 'MongoDB stored JavaScript functions' },
    async () => {
      log('Resource: Retrieving stored JavaScript functions…')
      const functions = await getStoredFunctions()
      log(`Resource: Retrieved stored functions.`)
      return {
        contents: [{
          uri: 'mongodb://database/functions',
          text: formatStoredFunctions(functions)
        }]
      }
    }
  )

  server.resource(
    'performance-metrics',
    'mongodb://server/metrics',
    { description: 'Real-time MongoDB performance metrics and profiling data' },
    async () => {
      log('Resource: Retrieving performance metrics…')
      const metrics = await getPerformanceMetrics()
      return {
        contents: [{
          uri: 'mongodb://server/metrics',
          text: formatPerformanceMetrics(metrics)
        }]
      }
    }
  )

  server.resource(
    'database-triggers',
    'mongodb://database/triggers',
    { description: 'Database change streams and event triggers configuration' },
    async () => {
      log('Resource: Retrieving database triggers and event configuration…')
      const triggers = await getDatabaseTriggers()
      return {
        contents: [{
          uri: 'mongodb://database/triggers',
          text: formatTriggerConfiguration(triggers)
        }]
      }
    }
  )
}

const registerPrompts = (server) => {
  server.prompt(
    'query-builder',
    'Help construct MongoDB query filters',
    {
      collection: z.string().min(1).describe('Collection name to query'),
      condition: z.string().describe('Describe the condition in natural language (e.g. "users older than 30")')
    },
    ({ collection, condition }) => {
      log(`Prompt: Initializing queryBuilder for collection '${collection}' with condition: "${condition}".`)
      return {
        description: `MongoDB Query Builder for ${collection}`,
        messages: [
          {
            role: 'user',
            content: {
              type: 'text',
              text: `Please help me create a MongoDB query for the '${collection}' collection based on this condition: "${condition}".

I need both the filter object and a complete example showing how to use it with the findDocuments tool.

Guidelines:
1. Create a valid MongoDB query filter as a JSON object
2. Show me how special MongoDB operators work if needed (like $gt, $in, etc.)
3. Provide a complete example of using this with the findDocuments tool
4. Suggest any relevant projections or sort options

Remember: I'm working with the ${currentDbName} database and the ${collection} collection.`
            }
          }
        ]
      }
    }
  )
  
  server.prompt(
    'aggregation-builder',
    'Help construct MongoDB aggregation pipelines',
    {
      collection: z.string().min(1).describe('Collection name for aggregation'),
      goal: z.string().describe('What you want to calculate or analyze')
    },
    ({ collection, goal }) => {
      log(`Prompt: Initializing aggregationBuilder for collection '${collection}' with goal: "${goal}".`)
      return {
        description: `MongoDB Aggregation Pipeline Builder for ${collection}`,
        messages: [
          {
            role: 'user',
            content: {
              type: 'text',
              text: `I need to create a MongoDB aggregation pipeline for the '${collection}' collection to ${goal}.

Please help me create:
1. A complete aggregation pipeline as a JSON array
2. An explanation of each stage in the pipeline
3. How to execute this with the aggregateData tool

Remember: I'm working with the ${currentDbName} database and the ${collection} collection.`
            }
          }
        ]
      }
    }
  )
  
  server.prompt(
    'schema-analysis',
    'Analyze collection schema and recommend improvements',
    {
      collection: z.string().min(1).describe('Collection name to analyze')
    },
    async ({ collection }) => {
      log(`Prompt: Initializing schemaAnalysis for collection '${collection}'…`)
      const schema = await inferSchema(collection)
      log(`Prompt: Retrieved schema for '${collection}' with ${Object.keys(schema.fields).length} fields.`)
      return {
        description: `MongoDB Schema Analysis for ${collection}`,
        messages: [
          {
            role: 'user',
            content: {
              type: 'text',
              text: `Please analyze the schema of the '${collection}' collection and provide recommendations:

Here's the current schema:
${formatSchema(schema)}

Could you help with:
1. Identifying any schema design issues or inconsistencies
2. Suggesting schema improvements for better performance
3. Recommending appropriate indexes based on the data structure
4. Best practices for this type of data model
5. Any potential MongoDB-specific optimizations`
            }
          }
        ]
      }
    }
  )
  
  server.prompt(
    'index-recommendation',
    'Get index recommendations for query patterns',
    {
      collection: z.string().min(1).describe('Collection name'),
      queryPattern: z.string().describe('Common query pattern or operation')
    },
    ({ collection, queryPattern }) => {
      log(`Prompt: Initializing indexRecommendation for collection '${collection}' with query pattern: "${queryPattern}".`)
      return {
        description: `MongoDB Index Recommendations for ${collection}`,
        messages: [
          {
            role: 'user',
            content: {
              type: 'text',
              text: `I need index recommendations for the '${collection}' collection to optimize this query pattern: "${queryPattern}".

Please provide:
1. Recommended index(es) with proper key specification
2. Explanation of why this index would help
3. The exact command to create this index using the createIndex tool
4. How to verify the index is being used
5. Any potential trade-offs or considerations for this index

Remember: I'm working with the ${currentDbName} database and the ${collection} collection.`
            }
          }
        ]
      }
    }
  )
  
  server.prompt(
    'mongo-shell',
    'Generate MongoDB shell commands',
    {
      operation: z.string().describe('Operation you want to perform'),
      details: z.string().optional().describe('Additional details about the operation')
    },
    ({ operation, details }) => {
      log(`Prompt: Initializing mongoShell for operation: "${operation}" with${details ? ' details: "' + details + '"' : 'out details'}.`)
      return {
        description: 'MongoDB Shell Command Generator',
        messages: [
          {
            role: 'user',
            content: {
              type: 'text',
              text: `Please generate MongoDB shell commands to ${operation}${details ? ` with these details: ${details}` : ''}.

I need:
1. The exact MongoDB shell command(s)
2. Explanation of each part of the command
3. How this translates to using MongoDB Lens tools
4. Any important considerations or variations

Current database: ${currentDbName}`
            }
          }
        ]
      }
    }
  )
  
  server.prompt(
    'inspector-guide',
    'Get help using MongoDB Lens with MCP Inspector',
    {},
    () => {
      log('Prompt: Initializing inspectorGuide.')
      return {
        description: 'MongoDB Lens Inspector Guide',
        messages: [
          {
            role: 'user',
            content: {
              type: 'text',
              text: `I'm using the MCP Inspector with MongoDB Lens. How can I best use these tools together?

Please provide:
1. An overview of the most useful Inspector features for MongoDB
2. Tips for debugging MongoDB queries
3. Common workflows for exploring a database
4. How to use the Inspector features with MongoDB Lens resources and tools`
            }
          }
        ]
      }
    }
  )

  server.prompt(
    'data-modeling',
    'Get MongoDB data modeling advice for specific use cases',
    {
      useCase: z.string().describe('Describe your application or data use case'),
      requirements: z.string().describe('Key requirements (performance, access patterns, etc.)'),
      existingData: z.string().optional().describe('Optional: describe any existing data structure')
    },
    ({ useCase, requirements, existingData }) => {
      log(`Prompt: Initializing dataModeling for use case: "${useCase}".`)
      return {
        description: 'MongoDB Data Modeling Guide',
        messages: [
          {
            role: 'user',
            content: {
              type: 'text',
              text: `I need help designing a MongoDB data model for this use case: "${useCase}".

Key requirements:
${requirements}

${existingData ? `Existing data structure:\n${existingData}\n\n` : ''}
Please provide:
1. Recommended data model with collection structures
2. Sample document structures in JSON format
3. Explanation of design decisions and trade-offs
4. Appropriate indexing strategy
5. Any MongoDB-specific features or patterns I should consider
6. How this model addresses the stated requirements`
            }
          }
        ]
      }
    }
  )

  server.prompt(
    'query-optimizer',
    'Get optimization advice for slow queries',
    {
      collection: z.string().min(1).describe('Collection name'),
      query: z.string().describe('The slow query (as a JSON filter)'),
      performance: z.string().optional().describe('Optional: current performance metrics')
    },
    async ({ collection, query, performance }) => {
      log(`Prompt: Initializing queryOptimizer for collection '${collection}' with query: ${query}.`)
      const stats = await getCollectionStats(collection)
      const indexes = await getCollectionIndexes(collection)
      return {
        description: 'MongoDB Query Optimization Advisor',
        messages: [
          {
            role: 'user',
            content: {
              type: 'text',
              text: `I have a slow MongoDB query on the '${collection}' collection and need help optimizing it.

Query filter: ${query}

${performance ? `Current performance: ${performance}\n\n` : ''}
Collection stats:
${formatStats(stats)}

Current indexes:
${formatIndexes(indexes)}

Please provide:
1. Analysis of why this query might be slow
2. Recommend index changes (additions or modifications)
3. Suggest query structure improvements
4. Explain how to verify performance improvements
5. Other optimization techniques I should consider`
            }
          }
        ]
      }
    }
  )

  server.prompt(
    'security-audit',
    'Get MongoDB security recommendations',
    {},
    async () => {
      log('Prompt: Initializing securityAudit.')
      const serverStatus = await getServerStatus()
      const users = await getDatabaseUsers()
      return {
        description: 'MongoDB Security Audit',
        messages: [
          {
            role: 'user',
            content: {
              type: 'text',
              text: `Please help me perform a security audit on my MongoDB deployment.

Server information:
${formatServerStatus(serverStatus)}

User information:
${formatDatabaseUsers(users)}

Please provide:
1. Potential security vulnerabilities in my current setup
2. Recommendations for improving security
3. Authentication and authorization best practices
4. Network security considerations
5. Data encryption options
6. Audit logging recommendations
7. Backup security considerations`
            }
          }
        ]
      }
    }
  )

  server.prompt(
    'backup-strategy',
    'Get advice on MongoDB backup and recovery approaches',
    {
      databaseSize: z.string().optional().describe('Optional: database size information'),
      uptime: z.string().optional().describe('Optional: uptime requirements (e.g. "99.9%")'),
      rpo: z.string().optional().describe('Optional: recovery point objective'),
      rto: z.string().optional().describe('Optional: recovery time objective')
    },
    ({ databaseSize, uptime, rpo, rto }) => {
      log('Prompt: Initializing backupStrategy.')
      return {
        description: 'MongoDB Backup & Recovery Strategy',
        messages: [
          {
            role: 'user',
            content: {
              type: 'text',
              text: `I need recommendations for a MongoDB backup and recovery strategy.

${databaseSize ? `Database size: ${databaseSize}\n` : ''}${uptime ? `Uptime requirement: ${uptime}\n` : ''}${rpo ? `Recovery Point Objective (RPO): ${rpo}\n` : ''}${rto ? `Recovery Time Objective (RTO): ${rto}\n` : ''}
Current database: ${currentDbName}

Please provide:
1. Recommended backup methods for my scenario
2. Backup frequency and retention recommendations
3. Storage considerations and best practices
4. Restoration procedures and testing strategy
5. Monitoring and validation approaches
6. High availability considerations
7. Tools and commands for implementing the strategy`
            }
          }
        ]
      }
    }
  )

  server.prompt(
    'migration-guide',
    'Generate MongoDB migration steps between versions',
    {
      sourceVersion: z.string().describe('Source MongoDB version'),
      targetVersion: z.string().describe('Target MongoDB version'),
      features: z.string().optional().describe('Optional: specific features you use')
    },
    ({ sourceVersion, targetVersion, features }) => {
      log(`Prompt: Initializing migrationGuide from ${sourceVersion} to ${targetVersion}.`)
      return {
        description: 'MongoDB Version Migration Guide',
        messages: [
          {
            role: 'user',
            content: {
              type: 'text',
              text: `I need to migrate my MongoDB deployment from version ${sourceVersion} to ${targetVersion}.

${features ? `Key features I'm using: ${features}\n\n` : ''}
Please provide:
1. Step-by-step migration plan
2. Pre-migration checks and preparations
3. Breaking changes and deprecated features to be aware of
4. New features or improvements I can leverage
5. Common pitfalls and how to avoid them
6. Performance considerations
7. Rollback strategy in case of issues`
            }
          }
        ]
      }
    }
  )

  server.prompt(
    'sql-to-mongodb',
    'Convert SQL queries to MongoDB aggregation pipelines',
    {
      sqlQuery: z.string().min(1).describe('SQL query to convert'),
      targetCollection: z.string().optional().describe('Target MongoDB collection name')
    },
    ({ sqlQuery, targetCollection }) => {
      log(`Prompt: Initializing sqlToMongodb for query: "${sqlQuery}".`)
      return {
        description: 'SQL to MongoDB Query Translator',
        messages: [
          {
            role: 'user',
            content: {
              type: 'text',
              text: `Please convert this SQL query to MongoDB syntax:\n\n\`\`\`sql\n${sqlQuery}\n\`\`\`\n\n${targetCollection ? `Target collection: ${targetCollection}` : ''}\n\nI need:
  1. The equivalent MongoDB query/aggregation pipeline with proper MongoDB operators
  2. Explanation of how each part of the SQL query maps to MongoDB
  3. How to execute this using MongoDB Lens tools
  4. Any important considerations or MongoDB-specific optimizations
  
  Please provide both the find() query format (if applicable) and the aggregation pipeline format.`
            }
          }
        ]
      }
    }
  )

  server.prompt(
    'database-health-check',
    'Comprehensive database health assessment',
    {
      includePerformance: z.string().default('true').describe('Include performance metrics'),
      includeSchema: z.string().default('true').describe('Include schema analysis'),  
      includeSecurity: z.string().default('true').describe('Include security assessment')
    },
    async ({ includePerformance, includeSchema, includeSecurity }) => {
      const includePerformanceBool = includePerformance.toLowerCase() === 'true'
      const includeSchemaBool = includeSchema.toLowerCase() === 'true'
      const includeSecurityBool = includeSecurity.toLowerCase() === 'true'
      
      log('Prompt: Initializing comprehensive database health check')
   
      const dbStats = await getDatabaseStats()
      const collections = await listCollections()
      
      let serverStatus = null
      let indexes = {}
      let schemaAnalysis = {}
      
      if (includePerformanceBool) {
        serverStatus = await getServerStatus()
        const collectionsToAnalyze = collections.slice(0, 5)
        for (const coll of collectionsToAnalyze) {
          indexes[coll.name] = await getCollectionIndexes(coll.name)
        }
      }
      
      if (includeSchemaBool) {
        const collectionsToAnalyze = collections.slice(0, 3)
        for (const coll of collectionsToAnalyze) {
          schemaAnalysis[coll.name] = await inferSchema(coll.name, 10)
        }
      }
      
      let securityInfo = null
      if (includeSecurityBool) {
        const users = await getDatabaseUsers()
        securityInfo = {
          users,
          auth: serverStatus ? serverStatus.security : null
        }
      }
      
      return {
        description: `MongoDB Health Check: ${currentDbName}`,
        messages: [
          {
            role: 'user',
            content: {
              type: 'text',
              text: `Please perform a comprehensive health check on my MongoDB database "${currentDbName}" and provide recommendations for improvements.
    
    Database Statistics:
    ${JSON.stringify(dbStats, null, 2)}
    
    Collections (${collections.length}):
    ${collections.map(c => `- ${c.name}`).join('\n')}
    
    ${includePerformanceBool ? `\nPerformance Metrics:
    ${JSON.stringify(serverStatus ? {
      connections: serverStatus.connections,
      opcounters: serverStatus.opcounters,
      mem: serverStatus.mem
    } : {}, null, 2)}
    
    Indexes:
    ${Object.entries(indexes).map(([coll, idxs]) => 
      `- ${coll}: ${idxs.length} indexes`
    ).join('\n')}` : ''}
    
    ${includeSchemaBool ? `\nSchema Samples:
    ${Object.keys(schemaAnalysis).join(', ')}` : ''}
    
    ${includeSecurityBool ? `\nSecurity Information:
    - Users: ${securityInfo.users.users ? securityInfo.users.users.length : 'N/A'}
    - Authentication: ${securityInfo.auth && securityInfo.auth.authentication ? 
    JSON.stringify(securityInfo.auth.authentication.mechanisms || securityInfo.auth.authentication) : 'N/A'}` : ''}
    
    Please provide:
    1. Overall health assessment
    2. Urgent issues that need addressing
    3. Performance optimization recommendations
    4. Schema design suggestions and improvements
    5. Security best practices and concerns
    6. Monitoring and maintenance recommendations
    7. Specific MongoDB Lens tools to use for implementing your recommendations`
            }
          }
        ]
      }
    }
   )

  server.prompt(
    'multi-tenant-design',
    'Design MongoDB multi-tenant database architecture',
    {
      tenantIsolation: z.enum(['database', 'collection', 'field']).describe('Level of tenant isolation required'),
      estimatedTenants: z.string().describe('Estimated number of tenants'),
      sharedFeatures: z.string().describe('Features/data that will be shared across tenants'),
      tenantSpecificFeatures: z.string().describe('Features/data unique to each tenant'),
      scalingPriorities: z.string().optional().describe('Primary scaling concerns (e.g., read-heavy, write-heavy)')
    },
    ({ tenantIsolation, estimatedTenants, sharedFeatures, tenantSpecificFeatures, scalingPriorities }) => {
      const estimatedTenantsNum = parseInt(estimatedTenants, 10) || 1
      log(`Prompt: Initializing multiTenantDesign with ${tenantIsolation} isolation level for ${estimatedTenantsNum} tenants.`)
      return {
        description: 'MongoDB Multi-Tenant Architecture Design',
        messages: [
          {
            role: 'user',
            content: {
              type: 'text',
              text: `I need to design a multi-tenant MongoDB architecture with the following requirements:
  
  - Tenant isolation level: ${tenantIsolation}
  - Estimated number of tenants: ${estimatedTenants}
  - Shared features/data: ${sharedFeatures}
  - Tenant-specific features/data: ${tenantSpecificFeatures}
  ${scalingPriorities ? `- Scaling priorities: ${scalingPriorities}` : ''}
  
  Please provide:
  1. Recommended multi-tenant architecture for MongoDB
  2. Data model with collection structures and relationships
  3. Schema examples (in JSON) for each collection
  4. Indexing strategy for optimal tenant isolation and performance
  5. Security considerations and access control patterns
  6. Scaling approach as tenant count and data volume grow
  7. Query patterns to efficiently retrieve tenant-specific data
  8. Specific MongoDB features to leverage for multi-tenancy
  9. Potential challenges and mitigation strategies
  
  For context, I'm using MongoDB version ${mongoClient.topology?.lastIsMaster?.version || 'recent'} and want to ensure my architecture follows best practices.`
            }
          }
        ]
      }
    }
  )

  server.prompt(
    'schema-versioning',
    'Manage schema evolution in MongoDB applications',
    {
      collection: z.string().min(1).describe('Collection name to version'),
      currentSchema: z.string().describe('Current schema structure (brief description)'),
      plannedChanges: z.string().describe('Planned schema changes'),
      migrationConstraints: z.string().optional().describe('Migration constraints (e.g., zero downtime)')
    },
    async ({ collection, currentSchema, plannedChanges, migrationConstraints }) => {
      log(`Prompt: Initializing schemaVersioning for collection '${collection}'…`)

      const schema = await inferSchema(collection)
      
      return {
        description: 'MongoDB Schema Versioning Strategy',
        messages: [
          {
            role: 'user',
            content: {
              type: 'text',
              text: `I need to implement schema versioning/evolution for the '${collection}' collection in MongoDB. Please help me design a strategy.
  
  Current Schema Information:
  ${formatSchema(schema)}
  
  Current Schema Description: 
  ${currentSchema}
  
  Planned Schema Changes:
  ${plannedChanges}
  
  ${migrationConstraints ? `Migration Constraints: ${migrationConstraints}` : ''}
  
  Please provide:
  1. Recommended approach to schema versioning in MongoDB
  2. Step-by-step migration plan for these specific changes
  3. Code examples showing how to handle both old and new schema versions
  4. Schema validation rules to enforce the new schema
  5. Performance considerations during migration
  6. Rollback strategy if needed
  7. Testing approach to validate the migration
  8. MongoDB Lens tools and commands to use for the migration process
  
  I want to ensure backward compatibility during this transition.`
            }
          }
        ]
      }
    }
  )


}

async function generateExampleFilter(collectionName) {
  try {
    log(`Generating example filter for collection '${collectionName}'…`)
    const schema = await inferSchema(collectionName, 5)
    const fields = Object.entries(schema.fields)
    
    if (fields.length === 0) return '{}'
    
    const fieldEntry = fields.find(([name, info]) => 
      info.types.includes('string') || 
      info.types.includes('number') || 
      info.types.includes('boolean')
    )
    
    if (!fieldEntry) return '{}'
    
    const [fieldName, info] = fieldEntry
    log(`Found suitable field for example filter: ${fieldName} (${info.types.join(', ')}).`)
    
    if (info.types.includes('string')) {
      return JSON.stringify({ [fieldName]: { $regex: "example" } })
    } else if (info.types.includes('number')) {
      return JSON.stringify({ [fieldName]: { $gt: 0 } })
    } else if (info.types.includes('boolean')) {
      return JSON.stringify({ [fieldName]: true })
    }
    
    return '{}'
  } catch (error) {
    log(`Error generating example filter: ${error.message}`, true)
    return '{}'
  }
}

async function getFieldsForCollection(collectionName) {
  try {
    log(`Retrieving fields for collection '${collectionName}'…`)
    const schema = await inferSchema(collectionName, 5)
    const fields = Object.keys(schema.fields)
    log(`Retrieved ${fields.length} fields from collection '${collectionName}'.`)
    return fields
  } catch (error) {
    console.error(`Error getting fields for ${collectionName}:`, error)
    return []
  }
}

function isValidFieldName(field) {
  return typeof field === 'string' && field.length > 0 && !field.startsWith('$')
}

const registerTools = (server) => {
  const withErrorHandling = async (operation, errorMessage, defaultValue = null) => {
    try {
      return await operation()
    } catch (error) {
      const formattedError = `${errorMessage}: ${error.message}`
      log(formattedError, true)
      
      let errorCode = JSONRPC_ERROR_CODES.SERVER_ERROR_START
      
      if (error.name === 'MongoError' || error.name === 'MongoServerError') {
        if (error.code === 13) errorCode = JSONRPC_ERROR_CODES.RESOURCE_ACCESS_DENIED
        else if (error.code === 59 || error.code === 61) errorCode = JSONRPC_ERROR_CODES.MONGODB_CONNECTION_ERROR
        else if (error.code === 121) errorCode = JSONRPC_ERROR_CODES.MONGODB_SCHEMA_ERROR
        else errorCode = JSONRPC_ERROR_CODES.MONGODB_QUERY_ERROR
      } else if (error.message.includes('not found') || error.message.includes('does not exist')) {
        errorCode = JSONRPC_ERROR_CODES.RESOURCE_NOT_FOUND
      }
      
      const errorResponse = {
        content: [{
          type: 'text',
          text: formattedError
        }],
        isError: true,
        error: {
          code: errorCode,
          message: error.message,
          data: { type: error.name }
        }
      }
      
      return errorResponse
    }
  }

  server.tool(
    'list-databases',
    'List all accessible MongoDB databases',
    async () => {
      return withErrorHandling(async () => {
        log('Tool: Listing databases…')
        const dbs = await listDatabases()
        log(`Tool: Found ${dbs.length} databases.`)
        return {
          content: [{
            type: 'text',
            text: formatDatabasesList(dbs)
          }]
        }
      }, 'Error listing databases')
    }
  )

  server.tool(
    'current-database',
    'Get the name of the current database',
    async () => {
      return withErrorHandling(async () => {
        log('Tool: Getting current database name…')
        return {
          content: [{
            type: 'text',
            text: `Current database: ${currentDbName}`
          }]
        }
      }, 'Error getting current database')
    }
  )
  
  server.tool(
    'use-database',
    'Switch to a specific database',
    {
      database: z.string().min(1).describe('Database name to use')
    },
    async ({ database }) => {
      try {
        log(`Tool: Switching to database '${database}'…`)
        await switchDatabase(database)
        log(`Tool: Successfully switched to database '${database}'.`)
        return {
          content: [{
            type: 'text',
            text: `Switched to database: ${database}`
          }]
        }
      } catch (error) {
        log(`Error switching database: ${error.message}`, true)
        return {
          content: [{
            type: 'text',
            text: `Error switching database: ${error.message}`
          }],
          isError: true
        }
      }
    }
  )

  server.tool(
    'create-user',
    'Create a new database user',
    {
      username: z.string().min(1).describe('Username'),
      password: z.string().min(1).describe('Password'),
      roles: z.string().describe('Roles as JSON array, e.g. [{"role": "readWrite", "db": "mydb"}]')
    },
    async ({ username, password, roles }) => {
      try {
        log(`Tool: Creating user '${username}'…`)
        const parsedRoles = JSON.parse(roles)
        await createUser(username, password, parsedRoles)
        log(`Tool: User created successfully.`)
        return {
          content: [{
            type: 'text',
            text: `User '${username}' created with roles: ${JSON.stringify(parsedRoles)}`
          }]
        }
      } catch (error) {
        log(`Error creating user: ${error.message}`, true)
        return {
          content: [{
            type: 'text',
            text: `Error creating user: ${error.message}`
          }],
          isError: true
        }
      }
    }
  )

  server.tool(
    'drop-user',
    'Drop an existing database user',
    {
      username: z.string().min(1).describe('Username to drop')
    },
    async ({ username }) => {
      try {
        log(`Tool: Dropping user '${username}'…`)
        await dropUser(username)
        log(`Tool: User dropped successfully.`)
        return {
          content: [{
            type: 'text',
            text: `User '${username}' dropped successfully`
          }]
        }
      } catch (error) {
        log(`Error dropping user: ${error.message}`, true)
        return {
          content: [{
            type: 'text',
            text: `Error dropping user: ${error.message}`
          }],
          isError: true
        }
      }
    }
  )
  
  server.tool(
    'list-collections',
    'List collections in the current database',
    async () => {
      try {
        log(`Tool: Listing collections in database '${currentDbName}'…`)
        const collections = await listCollections()
        log(`Tool: Found ${collections.length} collections in database '${currentDbName}'.`)
        return {
          content: [{
            type: 'text',
            text: formatCollectionsList(collections)
          }]
        }
      } catch (error) {
        log(`Error listing collections: ${error.message}`, true)
        return {
          content: [{
            type: 'text',
            text: `Error listing collections: ${error.message}`
          }],
          isError: true
        }
      }
    }
  )
  
  server.tool(
    'find-documents',
    'Run queries with filters and projections',
    {
      collection: z.string().min(1).describe('Collection name'),
      filter: z.string().default('{}').describe('MongoDB query filter (JSON string)'),
      projection: z.string().optional().describe('Fields to include/exclude (JSON string)'),
      limit: z.number().int().min(1).default(10).describe('Maximum number of documents to return'),
      skip: z.number().int().min(0).default(0).describe('Number of documents to skip'),
      sort: z.string().optional().describe('Sort specification (JSON string)'),
      streaming: z.boolean().default(false).describe('Enable streaming for large result sets')
    },
    async ({ collection, filter, projection, limit, skip, sort, streaming }) => {
      try {
        log(`Tool: Finding documents in collection '${collection}'…`)
        log(`Tool: Using filter: ${filter}`)
        if (projection) log(`Tool: Using projection: ${projection}`)
        if (sort) log(`Tool: Using sort: ${sort}`)
        log(`Tool: Using limit: ${limit}, skip: ${skip}, streaming: ${streaming}`)
        
        const parsedFilter = filter ? JSON.parse(filter) : {}
        const parsedProjection = projection ? JSON.parse(projection) : null
        const parsedSort = sort ? JSON.parse(sort) : null
        
        if (streaming) {
          await throwIfCollectionNotExists(collection)
          const coll = currentDb.collection(collection)
          
          let query = coll.find(parsedFilter)
          if (parsedProjection) query = query.project(parsedProjection)
          if (skip) query = query.skip(skip)
          if (parsedSort) query = query.sort(parsedSort)
          query = query.limit(limit).batchSize(20)
          
          const resourceUri = `mongodb://find/${collection}`
          const count = await streamResultsToMcp(
            query, 
            doc => JSON.stringify(serializeDocument(doc), null, 2),
            resourceUri,
            limit
          )
          
          return {
            content: [{
              type: 'text',
              text: `Streaming ${count} document${count === 1 ? '' : 's'} from collection '${collection}'.`
            }]
          }
        } else {
          const documents = await findDocuments(collection, parsedFilter, parsedProjection, limit, skip, parsedSort)
          log(`Tool: Found ${documents.length} documents in collection '${collection}'.`)
          return {
            content: [{
              type: 'text',
              text: formatDocuments(documents, limit)
            }]
          }
        }
      } catch (error) {
        log(`Error finding documents: ${error.message}`, true)
        return {
          content: [{
            type: 'text',
            text: `Error finding documents: ${error.message}`
          }],
          isError: true,
          error: {
            code: JSONRPC_ERROR_CODES.MONGODB_QUERY_ERROR,
            message: error.message,
            data: { type: error.name }
          }
        }
      }
    }
  )
  
  server.tool(
    'count-documents',
    'Count documents with optional filter',
    {
      collection: z.string().min(1).describe('Collection name'),
      filter: z.string().default('{}').describe('MongoDB query filter (JSON string)')
    },
    async ({ collection, filter }) => {
      try {
        log(`Tool: Counting documents in collection '${collection}'…`)
        log(`Tool: Using filter: ${filter}`)
        
        const parsedFilter = filter ? JSON.parse(filter) : {}
        const count = await countDocuments(collection, parsedFilter)
        log(`Tool: Count result: ${count} documents.`)
        return {
          content: [{
            type: 'text',
            text: `Count: ${count} document(s)`
          }]
        }
      } catch (error) {
        log(`Error counting documents: ${error.message}`, true)
        return {
          content: [{
            type: 'text',
            text: `Error counting documents: ${error.message}`
          }],
          isError: true
        }
      }
    }
  )
  
  server.tool(
    'aggregate-data',
    'Run aggregation pipelines',
    {
      collection: z.string().min(1).describe('Collection name'),
      pipeline: z.string().describe('Aggregation pipeline as JSON string array'),
      streaming: z.boolean().default(false).describe('Enable streaming results for large datasets'),
      limit: z.number().int().min(1).default(1000).describe('Maximum number of results to return when streaming')
    },
    async ({ collection, pipeline, streaming, limit }) => {
      try {
        log(`Tool: Running aggregation on collection '${collection}'…`)
        log(`Tool: Using pipeline: ${pipeline}`)
        log(`Tool: Streaming: ${streaming}, Limit: ${limit}`)
        
        const parsedPipeline = JSON.parse(pipeline)
        const processedPipeline = processAggregationPipeline(parsedPipeline)
        
        if (streaming) {
          await throwIfCollectionNotExists(collection)
          const coll = currentDb.collection(collection)
          const cursor = coll.aggregate(processedPipeline, { 
            allowDiskUse: true,
            cursor: { batchSize: 20 }
          })
          
          const resourceUri = `mongodb://aggregation/${collection}`
          const count = await streamResultsToMcp(
            cursor, 
            doc => JSON.stringify(serializeDocument(doc), null, 2),
            resourceUri,
            limit
          )
          
          return {
            content: [{
              type: 'text',
              text: `Streaming ${count} aggregation results from collection '${collection}'.${count === limit ? " Results limited to first " + limit + " documents." : ""}`
            }]
          }
        } else {
          const results = await aggregateData(collection, processedPipeline)
          log(`Tool: Aggregation returned ${results.length} results.`)
          return {
            content: [{
              type: 'text',
              text: formatDocuments(results, 100)
            }]
          }
        }
      } catch (error) {
        log(`Error running aggregation: ${error.message}`, true)
        return {
          content: [{
            type: 'text',
            text: `Error running aggregation: ${error.message}`
          }],
          isError: true,
          error: {
            code: JSONRPC_ERROR_CODES.MONGODB_QUERY_ERROR,
            message: error.message,
            data: { type: error.name }
          }
        }
      }
    }
  )
  
  server.tool(
    'get-stats',
    'Get database or collection statistics',
    {
      target: z.enum(['database', 'collection']).describe('Target type'),
      name: z.string().optional().describe('Collection name (for collection stats)')
    },
    async ({ target, name }) => {
      try {
        let stats
        if (target === 'database') {
          log(`Tool: Getting statistics for database '${currentDbName}'…`)
          stats = await getDatabaseStats()
          log(`Tool: Retrieved database statistics.`)
        } else if (target === 'collection') {
          if (!name) throw new Error('Collection name is required for collection stats')
          log(`Tool: Getting statistics for collection '${name}'…`)
          stats = await getCollectionStats(name)
          log(`Tool: Retrieved collection statistics.`)
        }
        
        return {
          content: [{
            type: 'text',
            text: formatStats(stats)
          }]
        }
      } catch (error) {
        log(`Error getting stats: ${error.message}`, true)
        return {
          content: [{
            type: 'text',
            text: `Error getting stats: ${error.message}`
          }],
          isError: true
        }
      }
    }
  )
  
  server.tool(
    'analyze-schema',
    'Automatically infer schema from collection',
    {
      collection: z.string().min(1).describe('Collection name'),
      sampleSize: z.number().int().min(1).default(100).describe('Number of documents to sample')
    },
    async ({ collection, sampleSize }) => {
      try {
        log(`Tool: Analyzing schema for collection '${collection}' with sample size ${sampleSize}…`)
        const schema = await inferSchema(collection, sampleSize)
        log(`Tool: Schema analysis complete for '${collection}', found ${Object.keys(schema.fields).length} fields.`)
        return {
          content: [{
            type: 'text',
            text: formatSchema(schema)
          }]
        }
      } catch (error) {
        log(`Error inferring schema: ${error.message}`, true)
        return {
          content: [{
            type: 'text',
            text: `Error inferring schema: ${error.message}`
          }],
          isError: true
        }
      }
    }
  )
  
  server.tool(
    'create-index',
    'Create new index on collection',
    {
      collection: z.string().min(1).describe('Collection name'),
      keys: z.string().describe('Index keys as JSON object'),
      options: z.string().optional().describe('Index options as JSON object')
    },
    async ({ collection, keys, options }) => {
      try {
        log(`Tool: Creating index on collection '${collection}'…`)
        log(`Tool: Index keys: ${keys}`)
        if (options) log(`Tool: Index options: ${options}`)
        
        const parsedKeys = JSON.parse(keys)
        const parsedOptions = options ? JSON.parse(options) : {}
        
        const result = await createIndex(collection, parsedKeys, parsedOptions)
        log(`Tool: Index created successfully: ${result}`)
        return {
          content: [{
            type: 'text',
            text: `Index created: ${result}`
          }]
        }
      } catch (error) {
        log(`Error creating index: ${error.message}`, true)
        return {
          content: [{
            type: 'text',
            text: `Error creating index: ${error.message}`
          }],
          isError: true
        }
      }
    }
  )

  server.tool(
    'drop-index',
    'Drop an existing index from a collection',
    {
      collection: z.string().min(1).describe('Collection name'),
      indexName: z.string().min(1).describe('Name of the index to drop')
    },
    async ({ collection, indexName }) => {
      try {
        log(`Tool: Dropping index '${indexName}' from collection '${collection}'…`)
        await dropIndex(collection, indexName)
        log(`Tool: Index dropped successfully.`)
        return {
          content: [{
            type: 'text',
            text: `Index '${indexName}' dropped from collection '${collection}'`
          }]
        }
      } catch (error) {
        log(`Error dropping index: ${error.message}`, true)
        return {
          content: [{
            type: 'text',
            text: `Error dropping index: ${error.message}`
          }],
          isError: true
        }
      }
    }
  )
  
  server.tool(
    'explain-query',
    'Analyze query performance',
    {
      collection: z.string().min(1).describe('Collection name'),
      filter: z.string().describe('MongoDB query filter (JSON string)'),
      verbosity: z.enum(['queryPlanner', 'executionStats', 'allPlansExecution']).default('executionStats').describe('Explain verbosity level')
    },
    async ({ collection, filter, verbosity }) => {
      try {
        log(`Tool: Explaining query on collection '${collection}'…`)
        log(`Tool: Filter: ${filter}`)
        log(`Tool: Verbosity level: ${verbosity}`)
        
        const parsedFilter = JSON.parse(filter)
        const explanation = await explainQuery(collection, parsedFilter, verbosity)
        log(`Tool: Query explanation generated.`)
        return {
          content: [{
            type: 'text',
            text: formatExplanation(explanation)
          }]
        }
      } catch (error) {
        log(`Error explaining query: ${error.message}`, true)
        return {
          content: [{
            type: 'text',
            text: `Error explaining query: ${error.message}`
          }],
          isError: true
        }
      }
    }
  )

  server.tool(
    'distinct-values',
    'Get unique values for a field',
    {
      collection: z.string().min(1).describe('Collection name'),
      field: z.string().min(1).describe('Field name to get distinct values for'),
      filter: z.string().default('{}').describe('Optional filter as JSON string')
    },
    async ({ collection, field, filter }) => {
      try {
        log(`Tool: Getting distinct values for field '${field}' in collection '${collection}'…`)
        log(`Tool: Using filter: ${filter}`)
        
        const parsedFilter = filter ? JSON.parse(filter) : {}
        const values = await getDistinctValues(collection, field, parsedFilter)
        log(`Tool: Found ${values.length} distinct values.`)
        return {
          content: [{
            type: 'text',
            text: formatDistinctValues(field, values)
          }]
        }
      } catch (error) {
        log(`Error getting distinct values: ${error.message}`, true)
        return {
          content: [{
            type: 'text',
            text: `Error getting distinct values: ${error.message}`
          }],
          isError: true
        }
      }
    }
  )

  server.tool(
    'validate-collection',
    'Run validation on a collection to check for inconsistencies',
    {
      collection: z.string().min(1).describe('Collection name'),
      full: z.boolean().default(false).describe('Perform full validation (slower but more thorough)')
    },
    async ({ collection, full }) => {
      try {
        log(`Tool: Validating collection '${collection}'…`)
        log(`Tool: Full validation: ${full}`)
        
        const results = await validateCollection(collection, full)
        log(`Tool: Validation complete.`)
        return {
          content: [{
            type: 'text',
            text: formatValidationResults(results)
          }]
        }
      } catch (error) {
        log(`Error validating collection: ${error.message}`, true)
        return {
          content: [{
            type: 'text',
            text: `Error validating collection: ${error.message}`
          }],
          isError: true
        }
      }
    }
  )

  server.tool(
    'create-collection',
    'Create a new collection with options',
    {
      name: z.string().min(1).describe('Collection name'),
      options: z.string().default('{}').describe('Collection options as JSON string (capped, size, etc.)')
    },
    async ({ name, options }) => {
      try {
        log(`Tool: Creating collection '${name}'…`)
        log(`Tool: Using options: ${options}`)
        
        const parsedOptions = options ? JSON.parse(options) : {}
        const result = await createCollection(name, parsedOptions)
        log(`Tool: Collection created successfully.`)
        return {
          content: [{
            type: 'text',
            text: `Collection '${name}' created successfully.`
          }]
        }
      } catch (error) {
        log(`Error creating collection: ${error.message}`, true)
        return {
          content: [{
            type: 'text',
            text: `Error creating collection: ${error.message}`
          }],
          isError: true
        }
      }
    }
  )

  server.tool(
    'drop-collection',
    'Remove a collection',
    {
      name: z.string().min(1).describe('Collection name')
    },
    async ({ name }) => {
      try {
        log(`Tool: Dropping collection '${name}'…`)
        
        const result = await dropCollection(name)
        log(`Tool: Collection dropped successfully.`)
        return {
          content: [{
            type: 'text',
            text: `Collection '${name}' dropped successfully.`
          }]
        }
      } catch (error) {
        log(`Error dropping collection: ${error.message}`, true)
        return {
          content: [{
            type: 'text',
            text: `Error dropping collection: ${error.message}`
          }],
          isError: true
        }
      }
    }
  )

  server.tool(
    'rename-collection',
    'Rename an existing collection',
    {
      oldName: z.string().min(1).describe('Current collection name'),
      newName: z.string().min(1).describe('New collection name'),
      dropTarget: z.boolean().default(false).describe('Whether to drop target collection if it exists')
    },
    async ({ oldName, newName, dropTarget }) => {
      try {
        log(`Tool: Renaming collection from '${oldName}' to '${newName}'…`)
        log(`Tool: Drop target if exists: ${dropTarget}`)
        
        const result = await renameCollection(oldName, newName, dropTarget)
        log(`Tool: Collection renamed successfully.`)
        return {
          content: [{
            type: 'text',
            text: `Collection '${oldName}' renamed to '${newName}' successfully.`
          }]
        }
      } catch (error) {
        log(`Error renaming collection: ${error.message}`, true)
        return {
          content: [{
            type: 'text',
            text: `Error renaming collection: ${error.message}`
          }],
          isError: true
        }
      }
    }
  )

  server.tool(
    'modify-document',
    'Insert, update, or delete specific documents',
    {
      collection: z.string().min(1).describe('Collection name'),
      operation: z.enum(['insert', 'update', 'delete']).describe('Operation type'),
      document: z.string().describe('Document as JSON string (for insert)'),
      filter: z.string().optional().describe('Filter as JSON string (for update/delete)'),
      update: z.string().optional().describe('Update operations as JSON string (for update)'),
      options: z.string().optional().describe('Options as JSON string')
    },
    async ({ collection, operation, document, filter, update, options }) => {
      try {
        log(`Tool: Modifying documents in collection '${collection}' with operation '${operation}'…`)
        
        let result
        const parsedOptions = options ? JSON.parse(options) : {}
        
        if (operation === 'insert') {
          if (!document) throw new Error('Document is required for insert operation')
          const parsedDocument = JSON.parse(document)
          result = await insertDocument(collection, parsedDocument, parsedOptions)
          log(`Tool: Document inserted successfully.`)
        } else if (operation === 'update') {
          if (!filter) throw new Error('Filter is required for update operation')
          if (!update) throw new Error('Update is required for update operation')
          const parsedFilter = JSON.parse(filter)
          const parsedUpdate = JSON.parse(update)
          result = await updateDocument(collection, parsedFilter, parsedUpdate, parsedOptions)
          log(`Tool: Document(s) updated successfully.`)
        } else if (operation === 'delete') {
          if (!filter) throw new Error('Filter is required for delete operation')
          const parsedFilter = JSON.parse(filter)
          result = await deleteDocument(collection, parsedFilter, parsedOptions)
          log(`Tool: Document(s) deleted successfully.`)
        }
        
        return {
          content: [{
            type: 'text',
            text: formatModifyResult(operation, result)
          }]
        }
      } catch (error) {
        console.error(`Error in ${operation} operation:`, error)
        return {
          content: [{
            type: 'text',
            text: `Error in ${operation} operation: ${error.message}`
          }],
          isError: true
        }
      }
    }
  )

  server.tool(
    'export-data',
    'Export query results to formatted JSON or CSV',
    {
      collection: z.string().min(1).describe('Collection name'),
      filter: z.string().default('{}').describe('Filter as JSON string'),
      format: z.enum(['json', 'csv']).default('json').describe('Export format'),
      fields: z.string().optional().describe('Comma-separated list of fields to include (for CSV)'),
      limit: z.number().int().min(1).default(1000).describe('Maximum documents to export'),
      sort: z.string().optional().describe('Sort specification as JSON string (e.g. {"date": -1} for descending)')
    },
    async ({ collection, filter, format, fields, limit, sort }) => {
      try {
        log(`Tool: Exporting data from collection '${collection}' in ${format} format…`)
        log(`Tool: Using filter: ${filter}`)
        if (sort) log(`Tool: Using sort: ${sort}`)
        log(`Tool: Max documents: ${limit}`)
        
        const parsedFilter = filter ? JSON.parse(filter) : {}
        const parsedSort = sort ? JSON.parse(sort) : null
        let fieldsArray = fields ? fields.split(',').map(f => f.trim()) : null
        
        const documents = await findDocuments(collection, parsedFilter, null, limit, 0, parsedSort)
        log(`Tool: Found ${documents.length} documents to export.`)
        
        const exportData = await formatExport(documents, format, fieldsArray)
        log(`Tool: Data exported successfully in ${format} format.`)
        
        return {
          content: [{
            type: 'text',
            text: exportData
          }]
        }
      } catch (error) {
        log(`Error exporting data: ${error.message}`, true)
        return {
          content: [{
            type: 'text',
            text: `Error exporting data: ${error.message}`
          }],
          isError: true
        }
      }
    }
  )

  server.tool(
    'map-reduce',
    'Run MapReduce operations',
    {
      collection: z.string().min(1).describe('Collection name'),
      map: z.string().describe('Map function as string'),
      reduce: z.string().describe('Reduce function as string'),
      options: z.string().optional().describe('Options as JSON string (query, limit, etc.)')
    },
    async ({ collection, map, reduce, options }) => {
      try {
        log(`Tool: Running MapReduce on collection '${collection}'…`)
        
        const mapFunction = new Function('function() {' + map + '}')()
        const reduceFunction = new Function('function(key, values) {' + reduce + '}')()
        const parsedOptions = options ? JSON.parse(options) : {}
        
        const results = await runMapReduce(collection, mapFunction, reduceFunction, parsedOptions)
        log(`Tool: MapReduce operation complete.`)
        
        return {
          content: [{
            type: 'text',
            text: formatMapReduceResults(results)
          }]
        }
      } catch (error) {
        log(`Error running MapReduce: ${error.message}`, true)
        return {
          content: [{
            type: 'text',
            text: `Error running MapReduce: ${error.message}`
          }],
          isError: true
        }
      }
    }
  )

  server.tool(
    'bulk-operations',
    'Perform bulk inserts, updates, or deletes',
    {
      collection: z.string().min(1).describe('Collection name'),
      operations: z.string().describe('Array of operations as JSON string'),
      ordered: z.boolean().default(true).describe('Whether operations should be performed in order')
    },
    async ({ collection, operations, ordered }) => {
      try {
        log(`Tool: Performing bulk operations on collection '${collection}'…`)
        log(`Tool: Ordered: ${ordered}`)
        
        const parsedOperations = JSON.parse(operations)
        const result = await bulkOperations(collection, parsedOperations, ordered)
        log(`Tool: Bulk operations complete.`)
        
        return {
          content: [{
            type: 'text',
            text: formatBulkResult(result)
          }]
        }
      } catch (error) {
        log(`Error in bulk operations: ${error.message}`, true)
        return {
          content: [{
            type: 'text',
            text: `Error in bulk operations: ${error.message}`
          }],
          isError: true
        }
      }
    }
  )

  server.tool(
    'geo-query',
    'Run geospatial queries with various operators',
    {
      collection: z.string().min(1).describe('Collection name'),
      operator: z.enum(['near', 'geoWithin', 'geoIntersects']).describe('Geospatial operator type'),
      field: z.string().min(1).describe('Geospatial field name'),
      geometry: z.string().describe('GeoJSON geometry as JSON string'),
      maxDistance: z.number().optional().describe('Maximum distance in meters (for near queries)'),
      limit: z.number().int().min(1).default(10).describe('Maximum number of documents to return')
    },
    async ({ collection, operator, field, geometry, maxDistance, limit }) => {
      try {
        log(`Tool: Running geospatial query on collection '${collection}'…`)
        
        let indexMessage = ''
        try {
          const coll = currentDb.collection(collection)
          const indexes = await coll.listIndexes().toArray()
          
          const hasGeoIndex = indexes.some(idx => {
            if (!idx.key[field]) return false
            const indexType = idx.key[field]
            return indexType === '2dsphere' || indexType === '2d'
          })
          
          if (!hasGeoIndex) {
            log(`Warning: No geospatial index found for field '${field}' in collection '${collection}'`, true)
            indexMessage = "\n\nNote: This query would be more efficient with a geospatial index. " +
              `Consider creating a 2dsphere index with: create-index {"collection": "${collection}", "keys": "{\\"${field}\\": \\"2dsphere\\"}"}`
          }
        } catch (indexError) {
          log(`Warning: Unable to check for geospatial indexes: ${indexError.message}`, true)
        }
        
        const geoJson = JSON.parse(geometry)
        let query = {}
        
        if (operator === 'near') {
          query[field] = { $near: { $geometry: geoJson } }
          if (maxDistance) query[field].$near.$maxDistance = maxDistance
        } else if (operator === 'geoWithin') {
          query[field] = { $geoWithin: { $geometry: geoJson } }
        } else if (operator === 'geoIntersects') {
          query[field] = { $geoIntersects: { $geometry: geoJson } }
        }
        
        const results = await findDocuments(collection, query, null, limit, 0)
        const resultText = formatDocuments(results, limit) + indexMessage
        
        return {
          content: [{
            type: 'text',
            text: resultText
          }]
        }
      } catch (error) {
        return {
          content: [{
            type: 'text',
            text: `Error running geospatial query: ${error.message}`
          }],
          isError: true
        }
      }
    }
  )
  
  server.tool(
    'create-timeseries',
    'Create a time series collection for temporal data',
    {
      name: z.string().min(1).describe('Collection name'),
      timeField: z.string().min(1).describe('Field that contains the time value'),
      metaField: z.string().optional().describe('Field that contains metadata for grouping'),
      granularity: z.enum(['seconds', 'minutes', 'hours']).default('seconds').describe('Time series granularity'),
      expireAfterSeconds: z.number().int().optional().describe('Optional TTL in seconds')
    },
    async ({ name, timeField, metaField, granularity, expireAfterSeconds }) => {
      try {
        log(`Tool: Creating time series collection '${name}'…`)

        const adminDb = mongoClient.db('admin')
        const serverInfo = await adminDb.command({ buildInfo: 1 })
        const versionParts = serverInfo.version.split('.').map(Number)
        if (versionParts[0] < 5) {
          return { content: [{ type: 'text', text: `Time series collections require MongoDB 5.0+` }] }
        }
        
        const options = {
          timeseries: {
            timeField,
            granularity
          }
        }
        
        if (metaField) options.timeseries.metaField = metaField
        if (expireAfterSeconds) options.expireAfterSeconds = expireAfterSeconds
        
        const result = await createCollection(name, options)
        return {
          content: [{
            type: 'text',
            text: `Time series collection '${name}' created successfully.`
          }]
        }
      } catch (error) {
        return {
          content: [{
            type: 'text',
            text: `Error creating time series collection: ${error.message}`
          }],
          isError: true
        }
      }
    }
  )
  
  server.tool(
    'watch-changes',
    'Watch for changes in a collection using change streams',
    {
      collection: z.string().min(1).describe('Collection name'),
      operations: z.array(z.enum(['insert', 'update', 'delete', 'replace'])).default(['insert', 'update', 'delete']).describe('Operations to watch'),
      duration: z.number().int().min(1).max(60).default(10).describe('Duration to watch in seconds'),
      fullDocument: z.boolean().default(false).describe('Include full document in update events')
    },
    async ({ collection, operations, duration, fullDocument }) => {
      try {
        log(`Tool: Watching collection '${collection}' for changes…`)
  
        try {
          const adminDb = mongoClient.db('admin')
          await adminDb.command({ replSetGetStatus: 1 })
        } catch (err) {
          if (err.codeName === 'NotYetInitialized' || 
              err.codeName === 'NoReplicationEnabled' || 
              err.message.includes('not running with --replSet') ||
              err.code === 76 || err.code === 40573) {
            return {
              content: [{
                type: 'text',
                text: `Change streams are not supported on your MongoDB deployment.\n\nChange streams require MongoDB to be running as a replica set or sharded cluster. You appear to be running a standalone server.\n\nAlternative: You can set up a single-node replica set for development purposes by following these steps:\n\n1. Stop your MongoDB server\n2. Start it with the --replSet option: \`mongod --replSet rs0\`\n3. Connect to it and initialize the replica set: \`rs.initiate()\`\n\nThen try the watch-changes tool again.`
              }]
            }
          }
        }
        
        const pipeline = [
          { $match: { 'operationType': { $in: operations } } }
        ]
        
        const options = {}
        if (fullDocument) options.fullDocument = 'updateLookup'
        
        const coll = currentDb.collection(collection)
        const changeStream = coll.watch(pipeline, options)
        
        const changes = []
        const timeout = setTimeout(() => {
          changeStream.close()
        }, duration * 1000)
        
        changeStream.on('change', change => {
          changes.push(change)
        })
        
        return new Promise(resolve => {
          changeStream.on('close', () => {
            clearTimeout(timeout)
            resolve({
              content: [{
                type: 'text',
                text: formatChangeStreamResults(changes, duration)
              }]
            })
          })
        })
      } catch (error) {
        return {
          content: [{
            type: 'text',
            text: `Error watching for changes: ${error.message}`
          }],
          isError: true
        }
      }
    }
  )
  
  server.tool(
    'text-search',
    'Perform full-text search across text-indexed fields',
    {
      collection: z.string().min(1).describe('Collection name'),
      searchText: z.string().min(1).describe('Text to search for'),
      language: z.string().optional().describe('Optional language for text search'),
      caseSensitive: z.boolean().default(false).describe('Case sensitive search'),
      diacriticSensitive: z.boolean().default(false).describe('Diacritic sensitive search'),
      limit: z.number().int().min(1).default(10).describe('Maximum results to return')
    },
    async ({ collection, searchText, language, caseSensitive, diacriticSensitive, limit }) => {
      try {
        log(`Tool: Performing text search in collection '${collection}' for: "${searchText}"`)
        
        try {
          const coll = currentDb.collection(collection)
          const indexes = await coll.listIndexes().toArray()
          const hasTextIndex = indexes.some(idx => Object.values(idx.key).includes('text'))
          
          if (!hasTextIndex) {
            return {
              content: [{
                type: 'text',
                text: `No text index found on collection '${collection}'.\n\nText search requires a text index. Create one with:\n\ncreate-index {\n  "collection": "${collection}",\n  "keys": "{\\"fieldName\\": \\"text\\"}"\n}`
              }]
            }
          }
        } catch (indexError) {
          log(`Warning: Unable to check for text indexes: ${indexError.message}`, true)
        }
        
        const textSearchOptions = {}
        if (language) textSearchOptions.language = language
        if (caseSensitive) textSearchOptions.caseSensitive = true
        if (diacriticSensitive) textSearchOptions.diacriticSensitive = true
        
        const query = { $text: { $search: searchText, ...textSearchOptions } }
        const projection = { score: { $meta: 'textScore' } }
        const sort = { score: { $meta: 'textScore' } }
        
        const results = await findDocuments(collection, query, projection, limit, 0, sort)
        
        return {
          content: [{
            type: 'text',
            text: formatTextSearchResults(results, searchText)
          }]
        }
      } catch (error) {
        return {
          content: [{
            type: 'text',
            text: `Error performing text search: ${error.message}`
          }],
          isError: true
        }
      }
    }
  )
  
  server.tool(
    'transaction',
    'Execute multiple operations in a single transaction',
    {
      operations: z.string().describe('JSON array of operations with collection, operation type, and parameters')
    },
    async ({ operations }) => {
      try {
        log('Tool: Executing operations in a transaction…')
        
        try {
          const session = mongoClient.startSession()
          await session.endSession()
        } catch (error) {
          if (error.message.includes('not supported') || 
              error.message.includes('requires replica set') || 
              error.codeName === 'NotAReplicaSet') {
            return {
              content: [{
                type: 'text',
                text: `Transactions are not supported on your MongoDB deployment.\n\nTransactions require MongoDB to be running as a replica set or sharded cluster. You appear to be running a standalone server.\n\nAlternative: You can set up a single-node replica set for development purposes by following these steps:\n\n1. Stop your MongoDB server\n2. Start it with the --replSet option: \`mongod --replSet rs0\`\n3. Connect to it and initialize the replica set: \`rs.initiate()\`\n\nThen try the transaction tool again.`
              }]
            }
          }
          throw error
        }
        
        const parsedOps = JSON.parse(operations)
        const session = mongoClient.startSession()
        let results = []
        
        try {
          session.startTransaction({
            readConcern: { level: 'snapshot' },
            writeConcern: { w: 'majority' }
          })
          
          for (let i = 0; i < parsedOps.length; i++) {
            const op = parsedOps[i]
            log(`Tool: Transaction step ${i+1}: ${op.operation} on ${op.collection}`)
            
            let result
            const collection = currentDb.collection(op.collection)
            
            if (op.operation === 'insert') {
              result = await collection.insertOne(op.document, { session })
            } else if (op.operation === 'update') {
              result = await collection.updateOne(op.filter, op.update, { session })
            } else if (op.operation === 'delete') {
              result = await collection.deleteOne(op.filter, { session })
            } else if (op.operation === 'find') {
              result = await collection.findOne(op.filter, { session })
            } else {
              throw new Error(`Unsupported operation: ${op.operation}`)
            }
            
            results.push({ step: i+1, operation: op.operation, result })
          }
          
          await session.commitTransaction()
          log('Tool: Transaction committed successfully')
        } catch (error) {
          await session.abortTransaction()
          log(`Tool: Transaction aborted due to error: ${error.message}`)
          throw error
        } finally {
          await session.endSession()
        }
        
        return {
          content: [{
            type: 'text',
            text: formatTransactionResults(results)
          }]
        }
      } catch (error) {
        return {
          content: [{
            type: 'text',
            text: `Error executing transaction: ${error.message}`
          }],
          isError: true
        }
      }
    }
  )
  
  
  server.tool(
    'gridfs-operation',
    'Manage large files with GridFS',
    {
      operation: z.enum(['list', 'info', 'delete']).describe('GridFS operation type'),
      bucket: z.string().default('fs').describe('GridFS bucket name'),
      filename: z.string().optional().describe('Filename for info/delete operations'),
      limit: z.number().int().min(1).default(20).describe('Maximum files to list')
    },
    async ({ operation, bucket, filename, limit }) => {
      try {
        log(`Tool: Performing GridFS ${operation} operation on bucket '${bucket}'`)
        
        const gridFsBucket = new mongodb.GridFSBucket(currentDb, { bucketName: bucket })
        let result
        
        if (operation === 'list') {
          const files = await currentDb.collection(`${bucket}.files`).find({}).limit(limit).toArray()
          result = formatGridFSList(files)
        } else if (operation === 'info') {
          if (!filename) throw new Error('Filename is required for info operation')
          const file = await currentDb.collection(`${bucket}.files`).findOne({ filename })
          if (!file) throw new Error(`File '${filename}' not found`)
          result = formatGridFSInfo(file)
        } else if (operation === 'delete') {
          if (!filename) throw new Error('Filename is required for delete operation')
          await gridFsBucket.delete(await getFileId(bucket, filename))
          result = `File '${filename}' deleted successfully from bucket '${bucket}'`
        }
        
        return {
          content: [{
            type: 'text',
            text: result
          }]
        }
      } catch (error) {
        return {
          content: [{
            type: 'text',
            text: `Error performing GridFS operation: ${error.message}`
          }],
          isError: true
        }
      }
    }
  )
  
  server.tool(
    'collation-query',
    'Find documents with language-specific collation rules',
    {
      collection: z.string().min(1).describe('Collection name'),
      filter: z.string().default('{}').describe('Query filter as JSON string'),
      locale: z.string().min(2).describe('Locale code (e.g., "en", "fr", "de")'),
      strength: z.number().int().min(1).max(5).default(3).describe('Collation strength (1-5)'),
      caseLevel: z.boolean().default(false).describe('Consider case in first-level differences'),
      sort: z.string().optional().describe('Sort specification as JSON string')
    },
    async ({ collection, filter, locale, strength, caseLevel, sort }) => {
      try {
        log(`Tool: Running collation query on collection '${collection}' with locale '${locale}'`)
        
        const parsedFilter = JSON.parse(filter)
        const parsedSort = sort ? JSON.parse(sort) : null
        
        const collationOptions = {
          locale,
          strength,
          caseLevel
        }
        
        const coll = currentDb.collection(collection)
        let query = coll.find(parsedFilter).collation(collationOptions)
        
        if (parsedSort) query = query.sort(parsedSort)
        
        const results = await query.toArray()
        
        return {
          content: [{
            type: 'text',
            text: formatCollationResults(results, locale, strength, caseLevel)
          }]
        }
      } catch (error) {
        return {
          content: [{
            type: 'text',
            text: `Error running collation query: ${error.message}`
          }],
          isError: true
        }
      }
    }
  )
  
  server.tool(
    'shard-status',
    'Get sharding status for database or collections',
    {
      target: z.enum(['database', 'collection']).default('database').describe('Target type'),
      collection: z.string().optional().describe('Collection name (if target is collection)')
    },
    async ({ target, collection }) => {
      return withErrorHandling(async () => {
        log(`Tool: Getting shard status for ${target}${collection ? ` '${collection}'` : ''}`)
        
        try {
          const adminDb = mongoClient.db('admin')
          await adminDb.command({ listShards: 1 })
        } catch (error) {
          if (error.code === 72 || error.message.includes('not running with sharding') || 
              error.codeName === 'InvalidOptions') {
            return {
              content: [{
                type: 'text',
                text: `Sharding is not enabled on your MongoDB deployment.\n\nThis command requires MongoDB to be running as a sharded cluster.\nYou appear to be running a standalone server or replica set without sharding enabled.\n\nTo use sharding features, you need to set up a sharded cluster with:\n- Config servers\n- Mongos router(s)\n- Shard replica sets`
              }]
            }
          }
          throw error
        }
        
        const adminDb = mongoClient.db('admin')
        let result
        
        if (target === 'database') {
          const listShards = await adminDb.command({ listShards: 1 })
          const dbStats = await adminDb.command({ dbStats: 1, scale: 1 })
          const dbShardStatus = await getShardingDbStatus(currentDbName)
          
          result = formatShardDbStatus(listShards, dbStats, dbShardStatus, currentDbName)
        } else {
          if (!collection) throw new Error('Collection name is required when target is collection')
          
          const collStats = await currentDb.command({ collStats: collection })
          const collShardStatus = await getShardingCollectionStatus(currentDbName, collection)
          
          result = formatShardCollectionStatus(collStats, collShardStatus, collection)
        }
        
        return {
          content: [{
            type: 'text',
            text: result
          }]
        }
      }, `Error getting shard status for ${target}${collection ? ` '${collection}'` : ''}`)
    }
  )
  
  server.tool(
    'compare-schemas',
    'Compare schemas between two collections',
    {
      sourceCollection: z.string().min(1).describe('Source collection name'),
      targetCollection: z.string().min(1).describe('Target collection name'),
      sampleSize: z.number().int().min(1).default(100).describe('Number of documents to sample')
    },
    async ({ sourceCollection, targetCollection, sampleSize }) => {
      return withErrorHandling(async () => {
        log(`Tool: Comparing schemas between '${sourceCollection}' and '${targetCollection}'…`)

        const sourceSchema = await inferSchema(sourceCollection, sampleSize)
        const targetSchema = await inferSchema(targetCollection, sampleSize)

        const comparison = compareSchemas(sourceSchema, targetSchema)
        
        return {
          content: [{
            type: 'text',
            text: formatSchemaComparison(comparison, sourceCollection, targetCollection)
          }]
        }
      }, `Error comparing schemas between '${sourceCollection}' and '${targetCollection}'`)
    }
  )
  
  server.tool(
    'analyze-query-patterns',
    'Analyze query patterns and suggest optimizations',
    {
      collection: z.string().min(1).describe('Collection name to analyze'),
      duration: z.number().int().min(1).max(60).default(10).describe('Duration to analyze in seconds')
    },
    async ({ collection, duration }) => {
      return withErrorHandling(async () => {
        log(`Tool: Analyzing query patterns for collection '${collection}'…`)

        await throwIfCollectionNotExists(collection)
        const indexes = await getCollectionIndexes(collection)
        const schema = await inferSchema(collection)

        let queryStats = []
        try {
          const adminDb = mongoClient.db('admin')
          const profilerStatus = await currentDb.command({ profile: -1 })

          let prevProfileLevel = profilerStatus.was
          let prevSlowMs = profilerStatus.slowms

          await currentDb.command({ profile: 2, slowms: 0 })
          
          log(`Tool: Monitoring queries for ${duration} seconds…`)

          await new Promise(resolve => setTimeout(resolve, duration * 1000))

          queryStats = await currentDb.collection('system.profile')
            .find({ ns: `${currentDbName}.${collection}`, op: 'query' })
            .sort({ ts: -1 })
            .limit(100)
            .toArray()

          await currentDb.command({ profile: prevProfileLevel, slowms: prevSlowMs })
          
        } catch (profileError) {
          log(`Tool: Unable to use profiler: ${profileError.message}`)
        }

        const analysis = analyzeQueryPatterns(collection, schema, indexes, queryStats)
        
        return {
          content: [{
            type: 'text',
            text: formatQueryAnalysis(analysis)
          }]
        }
      }, `Error analyzing query patterns for '${collection}'`)
    }
  )
  
  server.tool(
    'generate-schema-validator',
    'Generate a JSON Schema validator for a collection',
    {
      collection: z.string().min(1).describe('Collection name'),
      strictness: z.enum(['strict', 'moderate', 'relaxed']).default('moderate').describe('Validation strictness level')
    },
    async ({ collection, strictness }) => {
      return withErrorHandling(async () => {
        log(`Tool: Generating schema validator for '${collection}' with ${strictness} strictness`)

        const schema = await inferSchema(collection, 200)

        const validator = generateJsonSchemaValidator(schema, strictness)

        const result = `# MongoDB JSON Schema Validator for '${collection}'

## Schema Validator
\`\`\`json
${JSON.stringify(validator, null, 2)}
\`\`\`

## How to Apply This Validator

### MongoDB Shell Command
\`\`\`javascript
db.runCommand({
  collMod: "${collection}",
  validator: ${JSON.stringify(validator, null, 2)},
  validationLevel: "${strictness === 'relaxed' ? 'moderate' : strictness}",
  validationAction: "${strictness === 'strict' ? 'error' : 'warn'}"
})
\`\`\`

### Using modify-document Tool in MongoDB Lens
\`\`\`
modify-document {
  "collection": "system.command",
  "operation": "insert",
  "document": {
    "collMod": "${collection}",
    "validator": ${JSON.stringify(validator)},
    "validationLevel": "${strictness === 'relaxed' ? 'moderate' : strictness}",
    "validationAction": "${strictness === 'strict' ? 'error' : 'warn'}"
  }
}
\`\`\`

This schema validator was generated based on ${schema.sampleSize} sample documents with ${Object.keys(schema.fields).length} fields.
`

        return {
          content: [{
            type: 'text',
            text: result
          }]
        }
      }, `Error generating schema validator for '${collection}'`)
    }
  )
}

const listDatabases = async () => {
  log('DB Operation: Listing databases…')
  const adminDb = mongoClient.db('admin')
  const result = await adminDb.admin().listDatabases()
  log(`DB Operation: Found ${result.databases.length} databases.`)
  return result.databases
}

const switchDatabase = async (dbName) => {
  log(`DB Operation: Switching to database '${dbName}'…`)
  try {
    const dbs = await listDatabases()
    const dbExists = dbs.some(db => db.name === dbName)
    if (!dbExists) throw new Error(`Database '${dbName}' does not exist`)
    currentDbName = dbName
    currentDb = mongoClient.db(dbName)
    log(`DB Operation: Successfully switched to database '${dbName}'.`)
    return currentDb
  } catch (error) {
    log(`DB Operation: Failed to switch to database '${dbName}': ${error.message}`)
    throw error
  }
}

const createUser = async (username, password, roles) => {
  log(`DB Operation: Creating user '${username}' with roles: ${JSON.stringify(roles)}…`)
  try {
    await currentDb.command({
      createUser: username,
      pwd: password,
      roles: roles
    })
    log(`DB Operation: User created successfully.`)
  } catch (error) {
    log(`DB Operation: Failed to create user: ${error.message}`)
    throw error
  }
}

const dropUser = async (username) => {
  log(`DB Operation: Dropping user '${username}'…`)
  try {
    await currentDb.command({
      dropUser: username
    })
    log(`DB Operation: User dropped successfully.`)
  } catch (error) {
    log(`DB Operation: Failed to drop user: ${error.message}`)
    throw error
  }
}

const listCollections = async () => {
  log(`DB Operation: Listing collections in database '${currentDbName}'…`)
  try {
    if (!currentDb) throw new Error("No database selected")

    const cacheKey = currentDbName
    const cachedData = memoryCache.collections.get(cacheKey)
    
    if (cachedData && 
        (Date.now() - cachedData.timestamp) < CACHE_TTL.COLLECTIONS) {
      log(`DB Operation: Using cached collections list for '${currentDbName}'`)
      return cachedData.data
    }

    const collections = await currentDb.listCollections().toArray()
    log(`DB Operation: Found ${collections.length} collections.`)

    memoryCache.collections.set(cacheKey, {
      data: collections,
      timestamp: Date.now()
    })
    
    return collections
  } catch (error) {
    log(`DB Operation: Failed to list collections: ${error.message}`)
    throw error
  }
}

const findDocuments = async (collectionName, filter = {}, projection = null, limit = 10, skip = 0, sort = null) => {
  log(`DB Operation: Finding documents in collection '${collectionName}'…`)
  try {
    await throwIfCollectionNotExists(collectionName)
    const collection = currentDb.collection(collectionName)
    let query = collection.find(filter)
    
    if (projection) query = query.project(projection)
    if (skip) query = query.skip(skip)
    if (limit) query = query.limit(limit)
    if (sort) query = query.sort(sort)
    
    const results = await query.toArray()
    log(`DB Operation: Found ${results.length} documents.`)
    return results
  } catch (error) {
    log(`DB Operation: Failed to find documents: ${error.message}`)
    throw error
  }
}

const countDocuments = async (collectionName, filter = {}) => {
  log(`DB Operation: Counting documents in collection '${collectionName}'…`)
  try {
    await throwIfCollectionNotExists(collectionName)
    const collection = currentDb.collection(collectionName)
    const count = await collection.countDocuments(filter)
    log(`DB Operation: Count result: ${count} documents.`)
    return count
  } catch (error) {
    log(`DB Operation: Failed to count documents: ${error.message}`)
    throw error
  }
}

const aggregateData = async (collectionName, pipeline) => {
  log(`DB Operation: Running aggregation on collection '${collectionName}'…`)
  try {
    await throwIfCollectionNotExists(collectionName)
    log(`DB Operation: Pipeline has ${pipeline.length} stages.`)
    const collection = currentDb.collection(collectionName)
    const results = await collection.aggregate(pipeline).toArray()
    log(`DB Operation: Aggregation returned ${results.length} results.`)
    return results
  } catch (error) {
    log(`DB Operation: Failed to run aggregation: ${error.message}`)
    throw error
  }
}

const getDatabaseStats = async () => {
  log(`DB Operation: Getting statistics for database '${currentDbName}'…`)
  const stats = await currentDb.stats()
  log(`DB Operation: Retrieved database statistics.`)
  return stats
}

const getCollectionStats = async (collectionName) => {
  log(`DB Operation: Getting statistics for collection '${collectionName}'…`)
  try {
    await throwIfCollectionNotExists(collectionName)
    const stats = await currentDb.collection(collectionName).stats()
    log(`DB Operation: Retrieved statistics for collection '${collectionName}'.`)
    return stats
  } catch (error) {
    log(`DB Operation: Failed to get statistics for collection '${collectionName}': ${error.message}`)
    throw error
  }
}

const getCollectionIndexes = async (collectionName) => {
  log(`DB Operation: Getting indexes for collection '${collectionName}'…`)
  try {
    await throwIfCollectionNotExists(collectionName)

    const cacheKey = `${currentDbName}.${collectionName}`
    const cachedData = memoryCache.indexes.get(cacheKey)
    
    if (cachedData && 
        (Date.now() - cachedData.timestamp) < CACHE_TTL.STATS) {
      log(`DB Operation: Using cached indexes for '${collectionName}'`)
      return cachedData.data
    }

    const indexes = await currentDb.collection(collectionName).indexes()
    log(`DB Operation: Retrieved ${indexes.length} indexes for collection '${collectionName}'.`)

    try {
      const stats = await currentDb.command({ collStats: collectionName, indexDetails: true })
      if (stats && stats.indexDetails) {
        for (const index of indexes) {
          if (stats.indexDetails[index.name]) {
            index.usage = stats.indexDetails[index.name]
          }
        }
      }
    } catch (statsError) {
      log(`DB Operation: Index usage stats not available: ${statsError.message}`)
    }

    memoryCache.indexes.set(cacheKey, {
      data: indexes,
      timestamp: Date.now()
    })
    
    return indexes
  } catch (error) {
    log(`DB Operation: Failed to get indexes for collection '${collectionName}': ${error.message}`)
    throw error
  }
}

const inferSchema = async (collectionName, sampleSize = 100) => {
  log(`DB Operation: Inferring schema for collection '${collectionName}' with sample size ${sampleSize}…`)
  try {
    await throwIfCollectionNotExists(collectionName)
    
    const cacheKey = `${currentDbName}.${collectionName}.${sampleSize}`
    const cachedSchema = memoryCache.schemas.get(cacheKey)
    
    if (cachedSchema && 
        (Date.now() - cachedSchema.timestamp) < CACHE_TTL.SCHEMAS) {
      log(`DB Operation: Using cached schema for '${collectionName}'`)
      return cachedSchema.data
    }
    
    const collection = currentDb.collection(collectionName)
    
    const pipeline = [
      { $sample: { size: sampleSize } }
    ]
    
    const cursor = collection.aggregate(pipeline, { 
      allowDiskUse: true,
      cursor: { batchSize: 50 }
    })
    
    const documents = []
    const fieldPaths = new Set()
    const schema = {}
    let processed = 0
    
    for await (const doc of cursor) {
      documents.push(doc)
      collectFieldPaths(doc, '', fieldPaths)
      processed++
      
      if (processed % 50 === 0) {
        log(`DB Operation: Processed ${processed} documents for schema inference…`)
      }
    }
    
    log(`DB Operation: Retrieved ${documents.length} sample documents for schema inference.`)
    
    if (documents.length === 0) throw new Error(`Collection '${collectionName}' is empty`)
    
    fieldPaths.forEach(path => {
      schema[path] = {
        types: new Set(),
        count: 0,
        sample: null,
        path: path
      }
    })
    
    documents.forEach(doc => {
      fieldPaths.forEach(path => {
        const value = getNestedValue(doc, path)
        if (value !== undefined) {
          if (!schema[path].sample) {
            schema[path].sample = value
          }
          schema[path].types.add(getTypeName(value))
          schema[path].count++
        }
      })
    })

    for (const key in schema) {
      schema[key].types = Array.from(schema[key].types)
      schema[key].coverage = Math.round((schema[key].count / documents.length) * 100)
    }
    
    const result = { 
      collectionName,
      sampleSize: documents.length,
      fields: schema,
      timestamp: new Date().toISOString()
    }
    
    memoryCache.schemas.set(cacheKey, {
      data: result,
      timestamp: Date.now()
    })
    
    const fieldsArray = Object.keys(schema)
    log(`DB Operation: Schema inference complete, identified ${fieldsArray.length} fields.`)
    
    memoryCache.fields.set(`${currentDbName}.${collectionName}`, {
      data: fieldsArray,
      timestamp: Date.now()
    })
    
    return result
  } catch (error) {
    log(`DB Operation: Failed to infer schema: ${error.message}`)
    throw error
  }
}

const collectFieldPaths = (obj, prefix = '', paths = new Set()) => {
  if (!obj || typeof obj !== 'object') return
  
  Object.entries(obj).forEach(([key, value]) => {
    const path = prefix ? `${prefix}.${key}` : key
    paths.add(path)
    
    if (value && typeof value === 'object') {
      if (Array.isArray(value)) {
        if (value.length > 0) {
          if (typeof value[0] === 'object' && value[0] !== null) {
            collectFieldPaths(value[0], `${path}[]`, paths)
          }
        }
      } else if (!(value instanceof ObjectId) && !(value instanceof Date)) {
        collectFieldPaths(value, path, paths)
      }
    }
  })
  
  return paths
}

const createIndex = async (collectionName, keys, options = {}) => {
  log(`DB Operation: Creating index on collection '${collectionName}'…`)
  log(`DB Operation: Index keys: ${JSON.stringify(keys)}`)
  if (Object.keys(options).length > 0) log(`DB Operation: Index options: ${JSON.stringify(options)}`)
  
  try {
    const collection = currentDb.collection(collectionName)
    const result = await collection.createIndex(keys, options)

    if (!result || typeof result !== 'string') {
      const errorMsg = "Index creation did not return a valid index name"
      log(`DB Operation: Index creation failed: ${errorMsg}`)
      throw new Error(errorMsg)
    }

    log(`DB Operation: Index created successfully: ${result}`)
    return result
  } catch (error) {
    log(`DB Operation: Index creation failed: ${error.message}`)
    throw error
  }
}

const dropIndex = async (collectionName, indexName) => {
  log(`DB Operation: Dropping index '${indexName}' from collection '${collectionName}'…`)
  try {
    await throwIfCollectionNotExists(collectionName)
    const collection = currentDb.collection(collectionName)
    await collection.dropIndex(indexName)
    log(`DB Operation: Index dropped successfully.`)
  } catch (error) {
    log(`DB Operation: Failed to drop index: ${error.message}`)
    throw error
  }
}

const explainQuery = async (collectionName, filter, verbosity = 'executionStats') => {
  log(`DB Operation: Explaining query on collection '${collectionName}'…`)
  try {
    await throwIfCollectionNotExists(collectionName)
    const collection = currentDb.collection(collectionName)
    const explanation = await collection.find(filter).explain(verbosity)
    if (!explanation) throw new Error(`Explain operation returned no result`)
    log(`DB Operation: Query explanation generated.`)
    return explanation
  } catch (error) {
    log(`DB Operation: Query explanation failed: ${error.message}`)
    throw error
  }
}

const getServerStatus = async () => {
  log('DB Operation: Getting server status…')
  try {
    const adminDb = mongoClient.db('admin')
    const status = await adminDb.command({ serverStatus: 1 })
    log('DB Operation: Retrieved server status.')
    return status
  } catch (error) {
    log(`DB Operation: Error getting server status: ${error.message}`)
    return {
      host: mongoClient.s.options.host || 'unknown',
      port: mongoClient.s.options.port || 'unknown',
      version: 'Information unavailable',
      error: error.message
    }
  }
}

const getReplicaSetStatus = async () => {
  log('DB Operation: Getting replica set status…')
  try {
    const adminDb = mongoClient.db('admin')
    const status = await adminDb.command({ replSetGetStatus: 1 })
    log('DB Operation: Retrieved replica set status.')
    return status
  } catch (error) {
    log(`DB Operation: Error getting replica set status: ${error.message}`)
    return {
      isReplicaSet: false,
      info: 'This server is not part of a replica set or you may not have permissions to view replica set status.',
      error: error.message,
      replicaSetRequired: true
    }
  }
}

const getCollectionValidation = async (collectionName) => {
  log(`DB Operation: Getting validation rules for collection '${collectionName}'…`)
  try {
    await throwIfCollectionNotExists(collectionName)
    const collections = await currentDb.listCollections({ name: collectionName }, { validator: 1 }).toArray()
    log(`DB Operation: Retrieved validation information for collection '${collectionName}'.`)
    if (collections.length === 0) return { hasValidation: false }
    return {
      hasValidation: !!collections[0].options?.validator,
      validator: collections[0].options?.validator || {},
      validationLevel: collections[0].options?.validationLevel || 'strict',
      validationAction: collections[0].options?.validationAction || 'error'
    }
  } catch (error) {
    log(`DB Operation: Error getting validation for ${collectionName}: ${error.message}`)
    throw error
  }
}

const getDatabaseUsers = async () => {
  log(`DB Operation: Getting users for database '${currentDbName}'…`)
  try {
    const users = await currentDb.command({ usersInfo: 1 })
    log(`DB Operation: Retrieved user information.`)
    return users
  } catch (error) {
    log(`DB Operation: Error getting users: ${error.message}`)
    return { 
      users: [],
      info: 'Could not retrieve user information. You may not have sufficient permissions.',
      error: error.message
    }
  }
}

const getStoredFunctions = async () => {
  log(`DB Operation: Getting stored JavaScript functions…`)
  try {
    const system = currentDb.collection('system.js')
    const functions = await system.find({}).toArray()
    log(`DB Operation: Retrieved ${functions.length} stored functions.`)
    return functions
  } catch (error) {
    log(`DB Operation: Error getting stored functions: ${error.message}`)
    return []
  }
}

const getPerformanceMetrics = async () => {
  try {
    const adminDb = mongoClient.db('admin')
    const serverStatus = await adminDb.command({ serverStatus: 1 })
    const profileStats = await currentDb.command({ profile: -1 })

    const currentOps = await adminDb.command({ 
      currentOp: 1, 
      active: true,
      secs_running: { $gt: 1 }
    })

    const perfStats = await currentDb.command({ dbStats: 1 })
    
    return {
      serverStatus: {
        connections: serverStatus.connections,
        network: serverStatus.network,
        opcounters: serverStatus.opcounters,
        wiredTiger: serverStatus.wiredTiger?.cache,
        mem: serverStatus.mem,
        locks: serverStatus.locks
      },
      profileSettings: profileStats,
      currentOperations: currentOps.inprog,
      performance: perfStats
    }
  } catch (error) {
    log(`Error getting performance metrics: ${error.message}`)
    return { error: error.message }
  }
}

const getDatabaseTriggers = async () => {
  try {
    try {
      const coll = currentDb.collection('system.version')
      const testStream = coll.watch()
      await testStream.close()
      
      const changeStreamInfo = {
        supported: true,
        resumeTokenSupported: true,
        updateLookupSupported: true,
        fullDocumentBeforeChangeSupported: true
      }
      
      const triggerCollections = await currentDb.listCollections({ name: /trigger|event|notification/i }).toArray()
      const system = currentDb.collection('system.js')
      const triggerFunctions = await system.find({ _id: /trigger|event|watch|notify/i }).toArray()
      
      return {
        changeStreams: changeStreamInfo,
        triggerCollections,
        triggerFunctions
      }
    } catch (error) {
      if (error.code === 40573 || error.message.includes('only supported on replica sets')) {
        return { 
          changeStreams: {
            supported: false,
            reason: "Change streams require a replica set or sharded cluster",
            howToEnable: "To enable change streams for development, configure MongoDB as a single-node replica set"
          },
          triggerCollections: [],
          triggerFunctions: []
        }
      }
      throw error
    }
  } catch (error) {
    log(`Error getting database triggers: ${error.message}`)
    return { 
      error: error.message,
      supported: false
    }
  }
}

const getDistinctValues = async (collectionName, field, filter = {}) => {
  log(`DB Operation: Getting distinct values for field '${field}' in collection '${collectionName}'…`)
  try {
    await throwIfCollectionNotExists(collectionName)
    if (!isValidFieldName(field)) throw new Error(`Invalid field name: ${field}`)
    const collection = currentDb.collection(collectionName)
    const values = await collection.distinct(field, filter)
    log(`DB Operation: Found ${values.length} distinct values.`)
    return values
  } catch (error) {
    log(`DB Operation: Failed to get distinct values: ${error.message}`)
    throw error
  }
}

const validateCollection = async (collectionName, full = false) => {
  log(`DB Operation: Validating collection '${collectionName}'…`)
  try {
    await throwIfCollectionNotExists(collectionName)    
    const result = await currentDb.command({ validate: collectionName, full })
    if (!result) throw new Error(`Validation returned no result`)
    log(`DB Operation: Collection validation complete.`)
    return result
  } catch (error) {
    log(`DB Operation: Collection validation failed: ${error.message}`)
    throw error
  }
}

const createCollection = async (name, options = {}) => {
  log(`DB Operation: Creating collection '${name}'…`)
  try {
    const result = await currentDb.createCollection(name, options)
    
    if (!result || !result.collectionName || result.collectionName !== name) {
      const errorMsg = "Collection creation did not return a valid collection"
      log(`DB Operation: Collection creation failed: ${errorMsg}`)
      throw new Error(errorMsg)
    }
    
    log(`DB Operation: Collection created successfully.`)
    return { success: true, name }
  } catch (error) {
    log(`DB Operation: Collection creation failed: ${error.message}`)
    throw error
  }
}

const dropCollection = async (name) => {
  log(`DB Operation: Dropping collection '${name}'…`)
  try {
    const result = await currentDb.collection(name).drop()

    if (result !== true) {
      const errorMsg = "Collection drop operation did not return success"
      log(`DB Operation: Collection drop failed: ${errorMsg}`)
      throw new Error(errorMsg)
    }

    log(`DB Operation: Collection dropped successfully.`)
    return { success: result, name }
  } catch (error) {
    log(`DB Operation: Collection drop failed: ${error.message}`)
    throw error
  }
}

const renameCollection = async (oldName, newName, dropTarget = false) => {
  log(`DB Operation: Renaming collection from '${oldName}' to '${newName}'…`)
  try {
    const result = await currentDb.collection(oldName).rename(newName, { dropTarget })

    if (!result || !result.collectionName || result.collectionName !== newName) {
      const errorMsg = "Collection rename did not return a valid collection"
      log(`DB Operation: Collection rename failed: ${errorMsg}`)
      throw new Error(errorMsg)
    }

    log(`DB Operation: Collection renamed successfully.`)
    return { success: true, oldName, newName }
  } catch (error) {
    log(`DB Operation: Collection rename failed: ${error.message}`)
    throw error
  }
}

const insertDocument = async (collectionName, document, options = {}) => {
  log(`DB Operation: Inserting document into collection '${collectionName}'…`)
  try {
    const collection = currentDb.collection(collectionName)
    const result = await collection.insertOne(document, options)
    
    if (!result || !result.acknowledged) {
      const errorMsg = "Insert operation was not acknowledged by MongoDB"
      log(`DB Operation: Document insertion failed: ${errorMsg}`)
      throw new Error(errorMsg)
    }
    
    log(`DB Operation: Document inserted successfully.`)
    return result
  } catch (error) {
    log(`DB Operation: Document insertion failed: ${error.message}`)
    throw error
  }
}

const updateDocument = async (collectionName, filter, update, options = {}) => {
  log(`DB Operation: Updating document(s) in collection '${collectionName}'…`)
  try {
    const collection = currentDb.collection(collectionName)
    const hasUpdateOperators = Object.keys(update).some(key => key.startsWith('$'))
    
    let result
    if (options.multi === true || options.many === true) {
      if (!hasUpdateOperators) {
        update = { $set: update }
      }
      result = await collection.updateMany(filter, update, options)
    } else {
      if (!hasUpdateOperators) {
        update = { $set: update }
      }
      result = await collection.updateOne(filter, update, options)
    }
    
    if (!result || !result.acknowledged) {
      const errorMsg = "Update operation was not acknowledged by MongoDB"
      log(`DB Operation: Document update failed: ${errorMsg}`)
      throw new Error(errorMsg)
    }
    
    log(`DB Operation: Document(s) updated successfully.`)
    return result
  } catch (error) {
    log(`DB Operation: Document update failed: ${error.message}`)
    throw error
  }
}

const deleteDocument = async (collectionName, filter, options = {}) => {
  log(`DB Operation: Deleting document(s) from collection '${collectionName}'…`)
  try {
    const collection = currentDb.collection(collectionName)
    
    let result
    if (options.many === true) {
      result = await collection.deleteMany(filter, options)
    } else {
      result = await collection.deleteOne(filter, options)
    }
    
    if (!result || !result.acknowledged) {
      const errorMsg = "Delete operation was not acknowledged by MongoDB"
      log(`DB Operation: Document deletion failed: ${errorMsg}`)
      throw new Error(errorMsg)
    }
    
    log(`DB Operation: Document(s) deleted successfully.`)
    return result
  } catch (error) {
    log(`DB Operation: Document deletion failed: ${error.message}`)
    throw error
  }
}

const formatExport = async (documents, format, fields = null) => {
  log(`DB Operation: Formatting ${documents.length} documents for export in ${format} format…`)
  try {
    if (format === 'json') {
      return JSON.stringify(documents, (key, value) => serializeForExport(value), 2)
    } else if (format === 'csv') {
      if (!fields || !fields.length) {
        if (documents.length > 0) {
          fields = Object.keys(documents[0])
        } else {
          return 'No documents found for export'
        }
      }
      
      let csv = fields.join(',') + '\n'
      
      for (const doc of documents) {
        const row = fields.map(field => {
          const value = getNestedValue(doc, field)
          return formatCsvValue(value)
        })
        csv += row.join(',') + '\n'
      }
      
      return csv
    }
    
    throw new Error(`Unsupported export format: ${format}`)
  } catch (error) {
    log(`DB Operation: Export formatting failed: ${error.message}`)
    throw error
  }
}

const runMapReduce = async (collectionName, map, reduce, options = {}) => {
  log(`DB Operation: Running MapReduce on collection '${collectionName}'…`)
  try {
    await throwIfCollectionNotExists(collectionName)
    const collection = currentDb.collection(collectionName)
    const results = await collection.mapReduce(map, reduce, options)
    if (!results) throw new Error(`MapReduce operation returned no result`)
    log(`DB Operation: MapReduce operation complete.`)
    return results.toArray()
  } catch (error) {
    log(`DB Operation: MapReduce operation failed: ${error.message}`)
    throw error
  }
}

const bulkOperations = async (collectionName, operations, ordered = true) => {
  log(`DB Operation: Performing bulk operations on collection '${collectionName}'…`)
  try {
    await throwIfCollectionNotExists(collectionName)
    const collection = currentDb.collection(collectionName)
    const bulk = ordered ? collection.initializeOrderedBulkOp() : collection.initializeUnorderedBulkOp()
    
    for (const op of operations) {
      if (op.insertOne) {
        bulk.insert(op.insertOne.document)
      } else if (op.updateOne) {
        bulk.find(op.updateOne.filter).updateOne(op.updateOne.update)
      } else if (op.updateMany) {
        bulk.find(op.updateMany.filter).update(op.updateMany.update)
      } else if (op.deleteOne) {
        bulk.find(op.deleteOne.filter).deleteOne()
      } else if (op.deleteMany) {
        bulk.find(op.deleteMany.filter).delete()
      } else if (op.replaceOne) {
        bulk.find(op.replaceOne.filter).replaceOne(op.replaceOne.replacement)
      }
    }

    const result = await bulk.execute()

    if (!result || !result.acknowledged) {
      throw new Error("Bulk operations were not acknowledged by MongoDB")
    }
    
    log(`DB Operation: Bulk operations complete.`)
    return result
  } catch (error) {
    log(`DB Operation: Bulk operations failed: ${error.message}`)
    throw error
  }
}

const throwIfCollectionNotExists = async (collectionName) => {
  if (!await collectionExists(collectionName)) {
    throw new Error(`Collection '${collectionName}' does not exist`)
  }
}

const collectionExists = async (collectionName) => {
  if (!currentDb) throw new Error('No database selected')
  const collections = await currentDb.listCollections().toArray()
  return collections.some(coll => coll.name === collectionName)
}

const formatDatabasesList = (databases) => {
  return `Databases (${databases.length}):\n` + 
    databases.map(db => `- ${db.name} (${formatSize(db.sizeOnDisk)})`).join('\n')
}

const formatCollectionsList = (collections) => {
  if (!collections || collections.length === 0) {
    return `No collections found in database '${currentDbName}'`
  }
  
  return `Collections in ${currentDbName} (${collections.length}):\n` +
    collections.map(coll => `- ${coll.name} (${coll.type})`).join('\n')
}

const formatDocuments = (documents, limit) => {
  if (!documents || documents.length === 0) {
    return 'No documents found'
  }
  
  const count = documents.length
  let result = `${count} document${count === 1 ? '' : 's'}`
  if (count === limit) {
    result += ` (limit: ${limit})`
  }
  result += ':\n'
  
  result += documents.map(doc => JSON.stringify(serializeDocument(doc), null, 2)).join('\n\n')
  return result
}

const formatSchema = (schema) => {
  const { collectionName, sampleSize, fields } = schema
  let result = `Schema for '${collectionName}' (sampled ${sampleSize} documents):\n`
  
  for (const [field, info] of Object.entries(fields)) {
    const types = info.types.join(' | ')
    const coverage = Math.round((info.count / sampleSize) * 100)
    let sample = ''
    
    if (info.sample !== null && info.sample !== undefined) {
      if (typeof info.sample === 'object') {
        sample = JSON.stringify(serializeDocument(info.sample))
      } else {
        sample = String(info.sample)
      }
      
      if (sample.length > 50) {
        sample = sample.substring(0, 47) + '…'
      }
      
      sample = ` (example: ${sample})`
    }
    
    result += `- ${field}: ${types} (${coverage}% coverage)${sample}\n`
  }
  
  return result
}

const formatStats = (stats) => {
  if (!stats) return 'No statistics available'
  
  const keyMetrics = [
    ['ns', 'Namespace'],
    ['count', 'Document Count'],
    ['size', 'Data Size'],
    ['avgObjSize', 'Average Object Size'],
    ['storageSize', 'Storage Size'],
    ['totalIndexSize', 'Total Index Size'],
    ['nindexes', 'Number of Indexes']
  ]
  
  let result = 'Statistics:\n'
  
  for (const [key, label] of keyMetrics) {
    if (stats[key] !== undefined) {
      let value = stats[key]
      if (key.toLowerCase().includes('size')) {
        value = formatSize(value)
      }
      result += `- ${label}: ${value}\n`
    }
  }
  
  return result
}

const formatIndexes = (indexes) => {
  if (!indexes || indexes.length === 0) {
    return 'No indexes found'
  }
  
  let result = `Indexes (${indexes.length}):\n`
  
  for (const idx of indexes) {
    const keys = Object.entries(idx.key)
      .map(([field, direction]) => `${field}: ${direction}`)
      .join(', ')
    
    result += `- ${idx.name}: { ${keys} }`
    
    if (idx.unique) result += ' (unique)'
    if (idx.sparse) result += ' (sparse)'
    if (idx.background) result += ' (background)'
    
    result += '\n'
  }
  
  return result
}

const formatExplanation = (explanation) => {
  let result = 'Query Explanation:\n'
  
  if (explanation.queryPlanner) {
    result += '\nQuery Planner:\n'
    result += `- Namespace: ${explanation.queryPlanner.namespace}\n`
    result += `- Index Filter: ${JSON.stringify(explanation.queryPlanner.indexFilterSet) || 'None'}\n`
    result += `- Winning Plan: ${JSON.stringify(explanation.queryPlanner.winningPlan, null, 2)}\n`
  }
  
  if (explanation.executionStats) {
    result += '\nExecution Stats:\n'
    result += `- Execution Success: ${explanation.executionStats.executionSuccess}\n`
    result += `- Documents Examined: ${explanation.executionStats.totalDocsExamined}\n`
    result += `- Keys Examined: ${explanation.executionStats.totalKeysExamined}\n`
    result += `- Execution Time: ${explanation.executionStats.executionTimeMillis}ms\n`
  }
  
  return result
}

const formatServerStatus = (status) => {
  if (!status) return 'Server status information not available'
  
  let result = 'MongoDB Server Status:\n'
  
  if (status.error) {
    result += `Note: Limited information available. ${status.error}\n\n`
  }

  result += '## Server Information\n'
  result += `- Host: ${status.host || 'Unknown'}\n`
  result += `- Version: ${status.version || 'Unknown'}\n`
  result += `- Process: ${status.process || 'Unknown'}\n`
  result += `- Uptime: ${formatUptime(status.uptime)}\n`

  if (status.connections) {
    result += '\n## Connections\n'
    result += `- Current: ${status.connections.current}\n`
    result += `- Available: ${status.connections.available}\n`
    result += `- Total Created: ${status.connections.totalCreated}\n`
  }

  if (status.mem) {
    result += '\n## Memory Usage\n'
    result += `- Resident: ${formatSize(status.mem.resident * 1024 * 1024)}\n`
    result += `- Virtual: ${formatSize(status.mem.virtual * 1024 * 1024)}\n`
    result += `- Page Faults: ${status.extra_info?.page_faults || 'N/A'}\n`
  }

  if (status.opcounters) {
    result += '\n## Operation Counters\n'
    result += `- Insert: ${status.opcounters.insert}\n`
    result += `- Query: ${status.opcounters.query}\n`
    result += `- Update: ${status.opcounters.update}\n`
    result += `- Delete: ${status.opcounters.delete}\n`
    result += `- Getmore: ${status.opcounters.getmore}\n`
    result += `- Command: ${status.opcounters.command}\n`
  }

  return result
}

const formatReplicaSetStatus = (status) => {
  if (!status) return 'Replica set status information not available'
  
  if (status.error) {
    if (status.replicaSetRequired) {
      return `Replica Set Status: Not available\n\n${status.info}\n\nYou can set up a single-node replica set for development purposes by following these steps:\n\n1. Stop your MongoDB server\n2. Start it with the --replSet option: \`mongod --replSet rs0\`\n3. Connect to it and initialize the replica set: \`rs.initiate()\``
    }
    return `Replica Set Status: Not available (${status.info})\n\n${status.error}`
  }
  
  let result = `Replica Set: ${status.set}\n`
  result += `Status: ${status.myState === 1 ? 'PRIMARY' : status.myState === 2 ? 'SECONDARY' : 'OTHER'}\n`
  result += `Current Time: ${new Date(status.date.$date || status.date).toISOString()}\n\n`
  
  result += '## Members:\n'
  if (status.members) {
    for (const member of status.members) {
      result += `- ${member.name} (${member.stateStr})\n`
      result += `  Health: ${member.health}\n`
      result += `  Uptime: ${formatUptime(member.uptime)}\n`
      if (member.syncingTo) {
        result += `  Syncing to: ${member.syncingTo}\n`
      }
      result += '\n'
    }
  }
  
  return result
}

const formatValidationRules = (validation) => {
  if (!validation) return 'Validation information not available'
  
  if (!validation.hasValidation) {
    return 'This collection does not have any validation rules configured.'
  }
  
  let result = 'Collection Validation Rules:\n'
  result += `- Validation Level: ${validation.validationLevel}\n`
  result += `- Validation Action: ${validation.validationAction}\n\n`
  
  result += 'Validator:\n'
  result += JSON.stringify(validation.validator, null, 2)
  
  return result
}

const formatDatabaseUsers = (usersInfo) => {
  if (!usersInfo) return 'User information not available'
  
  if (usersInfo.error) {
    return `Users: Not available\n\n${usersInfo.info}\n${usersInfo.error}`
  }
  
  const users = usersInfo.users || []
  if (users.length === 0) {
    return 'No users found in the current database.'
  }
  
  let result = `Users in database '${currentDbName}' (${users.length}):\n\n`
  
  for (const user of users) {
    result += `## ${user.user}${user.customData ? ' (' + JSON.stringify(user.customData) + ')' : ''}\n`
    result += `- User ID: ${user._id || 'N/A'}\n`
    result += `- Database: ${user.db}\n`
    
    if (user.roles && user.roles.length > 0) {
      result += '- Roles:\n'
      for (const role of user.roles) {
        result += `  - ${role.role} on ${role.db}\n`
      }
    } else {
      result += '- Roles: None\n'
    }
    
    result += '\n'
  }
  
  return result
}

const formatStoredFunctions = (functions) => {
  if (!functions || !Array.isArray(functions)) return 'Stored functions information not available'
  
  if (functions.length === 0) {
    return 'No stored JavaScript functions found in the current database.'
  }
  
  let result = `Stored Functions in database '${currentDbName}' (${functions.length}):\n\n`
  
  for (const func of functions) {
    result += `## ${func._id}\n`
    
    if (typeof func.value === 'function') {
      result += `${func.value.toString()}\n\n`
    } else {
      result += `${func.value}\n\n`
    }
  }
  
  return result
}

const formatDistinctValues = (field, values) => {
  if (!values || !Array.isArray(values)) return `No distinct values found for field '${field}'`
  let result = `Distinct values for field '${field}' (${values.length}):\n`
  for (const value of values) result += `- ${formatValue(value)}\n`
  return result
}

const formatValidationResults = (results) => {
  if (!results) return 'Validation results not available'
  
  let result = 'Collection Validation Results:\n'
  result += `- Collection: ${results.ns}\n`
  result += `- Valid: ${results.valid}\n`
  
  if (results.errors && results.errors.length > 0) {
    result += `- Errors: ${results.errors}\n`
  }
  
  if (results.warnings && results.warnings.length > 0) {
    result += `- Warnings: ${results.warnings}\n`
  }
  
  if (results.nrecords !== undefined) {
    result += `- Records Validated: ${results.nrecords}\n`
  }
  
  if (results.nInvalidDocuments !== undefined) {
    result += `- Invalid Documents: ${results.nInvalidDocuments}\n`
  }
  
  if (results.advice) {
    result += `- Advice: ${results.advice}\n`
  }
  
  return result
}

const formatModifyResult = (operation, result) => {
  if (!result) return `${operation} operation result not available`
  
  let output = ''
  
  switch (operation) {
    case 'insert':
      output = `Document inserted successfully\n`
      output += `- ID: ${result.insertedId}\n`
      output += `- Acknowledged: ${result.acknowledged}\n`
      break
    case 'update':
      output = `Document update operation complete\n`
      output += `- Matched: ${result.matchedCount}\n`
      output += `- Modified: ${result.modifiedCount}\n`
      output += `- Acknowledged: ${result.acknowledged}\n`
      if (result.upsertedId) {
        output += `- Upserted ID: ${result.upsertedId}\n`
      }
      break
    case 'delete':
      output = `Document delete operation complete\n`
      output += `- Deleted: ${result.deletedCount}\n`
      output += `- Acknowledged: ${result.acknowledged}\n`
      break
    default:
      output = `Operation ${operation} completed\n`
      output += JSON.stringify(result, null, 2)
  }
  
  return output
}

const formatMapReduceResults = (results) => {
  if (!results || !Array.isArray(results)) return 'MapReduce results not available'
  let output = `MapReduce Results (${results.length} entries):\n`
  for (const result of results) {
    output += `- Key: ${formatValue(result._id)}\n`
    output += `  Value: ${formatValue(result.value)}\n`
  }
  return output
}

const formatBulkResult = (result) => {
  if (!result) return 'Bulk operation results not available'
  
  let output = 'Bulk Operations Results:\n'
  output += `- Acknowledged: ${result.acknowledged}\n`
  
  if (result.insertedCount) output += `- Inserted: ${result.insertedCount}\n`
  if (result.matchedCount) output += `- Matched: ${result.matchedCount}\n`
  if (result.modifiedCount) output += `- Modified: ${result.modifiedCount}\n`
  if (result.deletedCount) output += `- Deleted: ${result.deletedCount}\n`
  if (result.upsertedCount) output += `- Upserted: ${result.upsertedCount}\n`
  
  if (result.insertedIds && Object.keys(result.insertedIds).length > 0) {
    output += '- Inserted IDs:\n'
    for (const [index, id] of Object.entries(result.insertedIds)) {
      output += `  - Index ${index}: ${id}\n`
    }
  }
  
  if (result.upsertedIds && Object.keys(result.upsertedIds).length > 0) {
    output += '- Upserted IDs:\n'
    for (const [index, id] of Object.entries(result.upsertedIds)) {
      output += `  - Index ${index}: ${id}\n`
    }
  }
  
  return output
}

const formatSize = (sizeInBytes) => {
  if (sizeInBytes < 1024) return `${sizeInBytes} bytes`
  if (sizeInBytes < 1024 * 1024) return `${(sizeInBytes / 1024).toFixed(2)} KB`
  if (sizeInBytes < 1024 * 1024 * 1024) return `${(sizeInBytes / (1024 * 1024)).toFixed(2)} MB`
  return `${(sizeInBytes / (1024 * 1024 * 1024)).toFixed(2)} GB`
}

const formatUptime = (seconds) => {
  if (seconds === undefined) return 'Unknown'
  
  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const remainingSeconds = Math.floor(seconds % 60)
  
  const parts = []
  if (days > 0) parts.push(`${days}d`)
  if (hours > 0) parts.push(`${hours}h`)
  if (minutes > 0) parts.push(`${minutes}m`)
  if (remainingSeconds > 0 || parts.length === 0) parts.push(`${remainingSeconds}s`)
  
  return parts.join(' ')
}

const formatValue = (value) => {
  if (value === null) return 'null'
  if (value === undefined) return 'undefined'
  
  if (typeof value === 'object') {
    return JSON.stringify(value)
  }
  
  return String(value)
}

const formatCsvValue = (value) => {
  if (value === null || value === undefined) return ''
  
  const stringValue = typeof value === 'object' ? JSON.stringify(value) : String(value)
  
  if (stringValue.includes(',') || stringValue.includes('\n') || stringValue.includes('"')) {
    return `"${stringValue.replace(/"/g, '""')}"`
  }
  
  return stringValue
}

const formatChangeStreamResults = (changes, duration) => {
  if (changes.length === 0) {
    return `No changes detected during ${duration} second window.`
  }
  
  let result = `Detected ${changes.length} changes during ${duration} second window:\n\n`
  
  for (const change of changes) {
    result += `Operation: ${change.operationType}\n`
    result += `Timestamp: ${new Date(change.clusterTime.high * 1000).toISOString()}\n`
    
    if (change.documentKey) {
      result += `Document ID: ${JSON.stringify(change.documentKey)}\n`
    }
    
    if (change.fullDocument) {
      result += `Document: ${JSON.stringify(change.fullDocument, null, 2)}\n`
    }
    
    if (change.updateDescription) {
      result += `Updated Fields: ${JSON.stringify(change.updateDescription.updatedFields, null, 2)}\n`
      result += `Removed Fields: ${JSON.stringify(change.updateDescription.removedFields)}\n`
    }
    
    result += '\n'
  }
  
  return result
}

const formatTextSearchResults = (results, searchText) => {
  if (results.length === 0) {
    return `No documents found matching: "${searchText}"`
  }
  
  let output = `Found ${results.length} documents matching: "${searchText}"\n\n`
  
  for (const doc of results) {
    const score = doc.score
    delete doc.score
    output += `Score: ${score.toFixed(2)}\n`
    output += `Document: ${JSON.stringify(serializeDocument(doc), null, 2)}\n\n`
  }
  
  output += `Note: Make sure text indexes exist on relevant fields. Create with: create-index {"collection": "yourCollection", "keys": "{\\"fieldName\\": \\"text\\"}"}`
  
  return output
}

const formatTransactionResults = (results) => {
  let output = 'Transaction completed successfully:\n\n'
  
  for (const result of results) {
    output += `Step ${result.step}: ${result.operation}\n`
    
    if (result.operation === 'insert') {
      output += `- Inserted ID: ${result.result.insertedId}\n`
    } else if (result.operation === 'update') {
      output += `- Matched: ${result.result.matchedCount}\n`
      output += `- Modified: ${result.result.modifiedCount}\n`
    } else if (result.operation === 'delete') {
      output += `- Deleted: ${result.result.deletedCount}\n`
    } else if (result.operation === 'find') {
      output += `- Document: ${JSON.stringify(serializeDocument(result.result), null, 2)}\n`
    }
    
    output += '\n'
  }
  
  return output
}

const getFileId = async (bucket, filename) => {
  const file = await currentDb.collection(`${bucket}.files`).findOne({ filename })
  if (!file) throw new Error(`File '${filename}' not found`)
  return file._id
}

const formatGridFSList = (files) => {
  if (files.length === 0) {
    return 'No files found in GridFS'
  }
  
  let result = `GridFS Files (${files.length}):\n\n`
  
  for (const file of files) {
    result += `Filename: ${file.filename}\n`
    result += `Size: ${formatSize(file.length)}\n`
    result += `Upload Date: ${file.uploadDate.toISOString()}\n`
    result += `ID: ${file._id}\n`
    if (file.metadata) result += `Metadata: ${JSON.stringify(file.metadata)}\n`
    result += '\n'
  }
  
  return result
}

const formatGridFSInfo = (file) => {
  let result = 'GridFS File Information:\n\n'
  
  result += `Filename: ${file.filename}\n`
  result += `Size: ${formatSize(file.length)}\n`
  result += `Chunk Size: ${formatSize(file.chunkSize)}\n`
  result += `Upload Date: ${file.uploadDate.toISOString()}\n`
  result += `ID: ${file._id}\n`
  result += `MD5: ${file.md5}\n`
  
  if (file.contentType) result += `Content Type: ${file.contentType}\n`
  if (file.aliases && file.aliases.length > 0) result += `Aliases: ${file.aliases.join(', ')}\n`
  if (file.metadata) result += `Metadata: ${JSON.stringify(file.metadata, null, 2)}\n`
  
  return result
}

const formatCollationResults = (results, locale, strength, caseLevel) => {
  if (results.length === 0) {
    return 'No documents found matching the query with the specified collation'
  }
  
  let output = `Found ${results.length} documents using collation:\n`
  output += `- Locale: ${locale}\n`
  output += `- Strength: ${strength} (${getStrengthDescription(strength)})\n`
  output += `- Case Level: ${caseLevel}\n\n`
  
  output += results.map(doc => JSON.stringify(serializeDocument(doc), null, 2)).join('\n\n')
  return output
}

const getStrengthDescription = (strength) => {
  const descriptions = {
    1: 'Primary - base characters only',
    2: 'Secondary - base + accents',
    3: 'Tertiary - base + accents + case + variants',
    4: 'Quaternary - base + accents + case + variants + punctuation',
    5: 'Identical - exact matches only'
  }
  return descriptions[strength] || 'Custom'
}

const getShardingDbStatus = async (dbName) => {
  try {
    const config = mongoClient.db('config')
    return await config.collection('databases').findOne({ _id: dbName })
  } catch (error) {
    log(`Error getting database sharding status: ${error.message}`)
    return null
  }
}

const getShardingCollectionStatus = async (dbName, collName) => {
  try {
    const config = mongoClient.db('config')
    return await config.collection('collections').findOne({ _id: `${dbName}.${collName}` })
  } catch (error) {
    log(`Error getting collection sharding status: ${error.message}`)
    return null
  }
}

const formatShardDbStatus = (shards, dbStats, dbShardStatus, dbName) => {
  let result = `Sharding Status for Database: ${dbName}\n\n`
  
  if (!shards || !shards.shards || shards.shards.length === 0) {
    return result + 'This MongoDB deployment is not a sharded cluster.'
  }
  
  result += `Cluster consists of ${shards.shards.length} shards:\n`
  for (const shard of shards.shards) {
    result += `- ${shard._id}: ${shard.host}\n`
  }
  result += '\n'
  
  if (dbShardStatus) {
    result += `Database Sharding Status: ${dbShardStatus.partitioned ? 'Enabled' : 'Not Enabled'}\n`
    if (dbShardStatus.primary) result += `Primary Shard: ${dbShardStatus.primary}\n\n`
  } else {
    result += 'Database is not sharded.\n\n'
  }
  
  if (dbStats && dbStats.raw) {
    result += 'Data Distribution:\n'
    for (const shard in dbStats.raw) {
      result += `- ${shard}: ${formatSize(dbStats.raw[shard].totalSize)} (${dbStats.raw[shard].objects} objects)\n`
    }
  }
  
  return result
}

const formatShardCollectionStatus = (stats, shardStatus, collName) => {
  let result = `Sharding Status for Collection: ${collName}\n\n`
  
  if (!stats.sharded) {
    return result + 'This collection is not sharded.'
  }
  
  result += 'Collection is sharded.\n\n'
  
  if (shardStatus) {
    result += `Shard Key: ${JSON.stringify(shardStatus.key)}\n`
    if (shardStatus.unique) result += 'Unique: true\n'
    result += `Distribution Mode: ${shardStatus.dropped ? 'Dropped' : shardStatus.distributionMode || 'hashed'}\n\n`
  }
  
  if (stats.shards) {
    result += 'Data Distribution:\n'
    for (const shard in stats.shards) {
      result += `- ${shard}: ${formatSize(stats.shards[shard].size)} (${stats.shards[shard].count} documents)\n`
    }
  }
  
  if (stats.chunks) {
    result += `\nTotal Chunks: ${stats.chunks}\n`
  }
  
  return result
}

const formatPerformanceMetrics = (metrics) => {
  let result = 'MongoDB Performance Metrics:\n\n'
  
  if (metrics.error) {
    return `Error retrieving metrics: ${metrics.error}`
  }

  result += '## Server Status\n'
  if (metrics.serverStatus.connections) {
    result += `- Current Connections: ${metrics.serverStatus.connections.current}\n`
    result += `- Available Connections: ${metrics.serverStatus.connections.available}\n`
  }
  
  if (metrics.serverStatus.opcounters) {
    result += '\n## Operation Counters (since server start)\n'
    for (const [op, count] of Object.entries(metrics.serverStatus.opcounters)) {
      result += `- ${op}: ${count}\n`
    }
  }
  
  if (metrics.serverStatus.wiredTiger) {
    result += '\n## Cache Utilization\n'
    result += `- Pages Read: ${metrics.serverStatus.wiredTiger.pages_read}\n`
    result += `- Max Bytes: ${formatSize(metrics.serverStatus.wiredTiger.maximum_bytes_configured)}\n`
    result += `- Current Bytes: ${formatSize(metrics.serverStatus.wiredTiger.bytes_currently_in_cache)}\n`
    result += `- Dirty Bytes: ${formatSize(metrics.serverStatus.wiredTiger.tracked_dirty_bytes)}\n`
  }

  result += '\n## Database Profiling\n'
  result += `- Profiling Level: ${metrics.profileSettings.was}\n`
  result += `- Slow Query Threshold: ${metrics.profileSettings.slowms}ms\n`

  if (metrics.currentOperations && metrics.currentOperations.length > 0) {
    result += '\n## Long-Running Operations\n'
    for (const op of metrics.currentOperations) {
      result += `- Op: ${op.op} running for ${op.secs_running}s\n`
      result += `  - Namespace: ${op.ns}\n`
      if (op.query) result += `  - Query: ${JSON.stringify(op.query)}\n`
      if (op.command) result += `  - Command: ${JSON.stringify(op.command)}\n`
      result += '\n'
    }
  }
  
  return result
}

const formatTriggerConfiguration = (triggers) => {
  if (triggers.error) {
    return `Trigger information not available: ${triggers.error}`
  }
  
  let result = 'MongoDB Event Trigger Configuration:\n\n'

  result += '## Change Stream Support\n'
  if (triggers.changeStreams.supported) {
    result += '- Change streams are supported in this MongoDB version\n'
    result += `- Resume token support: ${triggers.changeStreams.resumeTokenSupported ? 'Yes' : 'No'}\n`
    result += `- Update lookup support: ${triggers.changeStreams.updateLookupSupported ? 'Yes' : 'No'}\n`
    result += `- Full document before change: ${triggers.changeStreams.fullDocumentBeforeChangeSupported ? 'Yes' : 'No'}\n`
  } else {
    result += '- Change streams are not supported in this MongoDB deployment\n'
    if (triggers.changeStreams.reason) {
      result += `  Reason: ${triggers.changeStreams.reason}\n`
    }
    if (triggers.changeStreams.howToEnable) {
      result += `  How to Enable: ${triggers.changeStreams.howToEnable}\n`
    }
  }

  result += '\n## Potential Trigger Collections\n'
  if (triggers.triggerCollections && triggers.triggerCollections.length > 0) {
    for (const coll of triggers.triggerCollections) {
      result += `- ${coll.name} (${coll.type})\n`
    }
  } else {
    result += '- No collections found with trigger-related naming\n'
  }

  result += '\n## Stored Trigger Functions\n'
  if (triggers.triggerFunctions && triggers.triggerFunctions.length > 0) {
    for (const func of triggers.triggerFunctions) {
      result += `- ${func._id}\n`
      if (typeof func.value === 'function') {
        result += `  ${func.value.toString().split('\n')[0]}…\n`
      }
    }
  } else {
    result += '- No stored JavaScript functions with trigger-related naming found\n'
  }
  
  return result
}

const getTypeName = (value) => {
  if (value === null) return 'null'
  if (value === undefined) return 'undefined'
  if (Array.isArray(value)) return 'array'
  if (value instanceof ObjectId) return 'ObjectId'
  if (value instanceof Date) return 'Date'
  return typeof value
}

const serializeDocument = (doc) => {
  const result = {}
  
  for (const [key, value] of Object.entries(doc)) {
    if (value instanceof ObjectId) {
      result[key] = `ObjectId("${value.toString()}")`
    } else if (value instanceof Date) {
      result[key] = `ISODate("${value.toISOString()}")`
    } else if (typeof value === 'object' && value !== null) {
      result[key] = serializeDocument(value)
    } else {
      result[key] = value
    }
  }
  
  return result
}

const serializeForExport = (value) => {
  if (value instanceof ObjectId) {
    return value.toString()
  } else if (value instanceof Date) {
    return value.toISOString()
  }
  return value
}

const getNestedValue = (obj, path) => {
  const parts = path.split('.')
  let current = obj
  
  for (const part of parts) {
    if (current === null || current === undefined) {
      return undefined
    }
    current = current[part]
  }
  
  return current
}

const compareSchemas = (sourceSchema, targetSchema) => {
  const result = {
    source: sourceSchema.collectionName,
    target: targetSchema.collectionName,
    commonFields: [],
    sourceOnlyFields: [],
    targetOnlyFields: [],
    typeDifferences: []
  }

  const sourceFields = Object.keys(sourceSchema.fields)
  const targetFields = Object.keys(targetSchema.fields)

  sourceFields.forEach(field => {
    if (targetFields.includes(field)) {
      const sourceTypes = sourceSchema.fields[field].types
      const targetTypes = targetSchema.fields[field].types

      const typesMatch = arraysEqual(sourceTypes, targetTypes)
      
      result.commonFields.push({
        name: field,
        sourceTypes,
        targetTypes,
        typesMatch
      })
      
      if (!typesMatch) {
        result.typeDifferences.push({
          field,
          sourceTypes,
          targetTypes
        })
      }
    } else {
      result.sourceOnlyFields.push({
        name: field,
        types: sourceSchema.fields[field].types
      })
    }
  })

  targetFields.forEach(field => {
    if (!sourceFields.includes(field)) {
      result.targetOnlyFields.push({
        name: field,
        types: targetSchema.fields[field].types
      })
    }
  })

  result.stats = {
    sourceFieldCount: sourceFields.length,
    targetFieldCount: targetFields.length,
    commonFieldCount: result.commonFields.length,
    mismatchCount: result.typeDifferences.length
  }
  
  return result
}

const arraysEqual = (a, b) => {
  if (a.length !== b.length) return false
  const sortedA = [...a].sort()
  const sortedB = [...b].sort()
  return sortedA.every((item, i) => item === sortedB[i])
}

const formatSchemaComparison = (comparison, sourceCollection, targetCollection) => {
  const { source, target, commonFields, sourceOnlyFields, targetOnlyFields, typeDifferences, stats } = comparison
  
  let result = `# Schema Comparison: '${source}' vs '${target}'\n\n`

  result += `## Summary\n`
  result += `- Source Collection: ${source} (${stats.sourceFieldCount} fields)\n`
  result += `- Target Collection: ${target} (${stats.targetFieldCount} fields)\n`
  result += `- Common Fields: ${stats.commonFieldCount}\n`
  result += `- Fields Only in Source: ${sourceOnlyFields.length}\n`
  result += `- Fields Only in Target: ${targetOnlyFields.length}\n`
  result += `- Type Mismatches: ${typeDifferences.length}\n\n`

  if (typeDifferences.length > 0) {
    result += `## Type Differences\n`
    typeDifferences.forEach(diff => {
      result += `- ${diff.field}: ${diff.sourceTypes.join(', ')} (${source}) vs ${diff.targetTypes.join(', ')} (${target})\n`
    })
    result += '\n'
  }

  if (sourceOnlyFields.length > 0) {
    result += `## Fields Only in ${source}\n`
    sourceOnlyFields.forEach(field => {
      result += `- ${field.name}: ${field.types.join(', ')}\n`
    })
    result += '\n'
  }

  if (targetOnlyFields.length > 0) {
    result += `## Fields Only in ${target}\n`
    targetOnlyFields.forEach(field => {
      result += `- ${field.name}: ${field.types.join(', ')}\n`
    })
    result += '\n'
  }

  if (stats.commonFieldCount > 0) {
    result += `## Common Fields\n`
    commonFields.forEach(field => {
      const statusSymbol = field.typesMatch ? '✓' : '✗'
      result += `- ${statusSymbol} ${field.name}\n`
    })
  }
  
  return result
}

const analyzeQueryPatterns = (collection, schema, indexes, queryStats) => {
  const analysis = {
    collection,
    indexRecommendations: [],
    queryOptimizations: [],
    unusedIndexes: [],
    schemaIssues: [],
    queryStats: []
  }

  const indexMap = {}
  indexes.forEach(idx => {
    indexMap[idx.name] = {
      key: idx.key,
      unique: !!idx.unique,
      sparse: !!idx.sparse,
      fields: Object.keys(idx.key),
      usage: idx.usage || { ops: 0, since: new Date() }
    }
  })

  for (const [name, idx] of Object.entries(indexMap)) {
    if (name !== '_id_' && (!idx.usage || idx.usage.ops === 0)) {
      analysis.unusedIndexes.push({
        name,
        fields: idx.fields,
        properties: idx.unique ? 'unique' : ''
      })
    }
  }

  if (queryStats && queryStats.length > 0) {
    queryStats.forEach(stat => {
      if (stat.command && stat.command.filter) {
        const filter = stat.command.filter
        const queryFields = Object.keys(filter)
        const millis = stat.millis || 0

        analysis.queryStats.push({
          filter: JSON.stringify(filter),
          fields: queryFields,
          millis,
          scanType: stat.planSummary || 'Unknown',
          timestamp: stat.ts
        })

        const hasMatchingIndex = indexes.some(idx => {
          const indexFields = Object.keys(idx.key)
          return queryFields.every(field => indexFields.includes(field))
        })
        
        if (!hasMatchingIndex && queryFields.length > 0 && millis > 10) {
          analysis.indexRecommendations.push({
            fields: queryFields,
            filter: JSON.stringify(filter),
            millis
          })
        }
      }
    })
  }

  const schemaFields = Object.entries(schema.fields)

  schemaFields.forEach(([fieldName, info]) => {
    if (info.types.includes('array') && info.sample && Array.isArray(info.sample) && info.sample.length > 50) {
      analysis.schemaIssues.push({
        field: fieldName,
        issue: 'Large array',
        description: `Field contains arrays with ${info.sample.length}+ items, which can cause performance issues.`
      })
    }
  })

  const likelyQueryFields = schemaFields
    .filter(([name, info]) => {
      const lowerName = name.toLowerCase()
      return (
        lowerName.includes('id') || 
        lowerName.includes('key') || 
        lowerName.includes('date') || 
        lowerName.includes('time') ||
        lowerName === 'email' || 
        lowerName === 'name' ||
        lowerName === 'status'
      ) && !indexMap._id_ && !indexMap[name + '_1']
    })
    .map(([name]) => name)
    
  if (likelyQueryFields.length > 0) {
    analysis.indexRecommendations.push({
      fields: likelyQueryFields,
      filter: 'Common query field pattern',
      automatic: true
    })
  }
  
  return analysis
}

const formatQueryAnalysis = (analysis) => {
  const { collection, indexRecommendations, queryOptimizations, unusedIndexes, schemaIssues, queryStats } = analysis
  
  let result = `# Query Pattern Analysis for '${collection}'\n\n`

  if (indexRecommendations.length > 0) {
    result += `## Index Recommendations\n`
    indexRecommendations.forEach((rec, i) => {
      result += `### ${i+1}. Create index on: ${rec.fields.join(', ')}\n`
      if (rec.filter && !rec.automatic) {
        result += `- Based on query filter: ${rec.filter}\n`
        if (rec.millis) {
          result += `- Current execution time: ${rec.millis}ms\n`
        }
      } else if (rec.automatic) {
        result += `- Automatic recommendation based on field name patterns\n`
      }
      result += `- Create using: \`create-index {"collection": "${collection}", "keys": "{\\"${rec.fields[0]}\\": 1}"}\`\n\n`
    })
  }

  if (unusedIndexes.length > 0) {
    result += `## Unused Indexes\n`
    result += 'The following indexes appear to be unused and could potentially be removed:\n'
    unusedIndexes.forEach((idx) => {
      result += `- ${idx.name} on fields: ${idx.fields.join(', ')}\n`
    })
    result += '\n'
  }

  if (schemaIssues.length > 0) {
    result += `## Schema Concerns\n`
    schemaIssues.forEach((issue) => {
      result += `- ${issue.field}: ${issue.issue} - ${issue.description}\n`
    })
    result += '\n'
  }

  if (queryStats.length > 0) {
    result += `## Recent Queries\n`
    result += 'Most recent query patterns observed:\n'
    
    const uniquePatterns = {}
    queryStats.forEach(stat => {
      const key = stat.filter
      if (!uniquePatterns[key]) {
        uniquePatterns[key] = {
          filter: stat.filter,
          fields: stat.fields,
          count: 1,
          totalTime: stat.millis,
          avgTime: stat.millis,
          scanType: stat.scanType
        }
      } else {
        uniquePatterns[key].count++
        uniquePatterns[key].totalTime += stat.millis
        uniquePatterns[key].avgTime = uniquePatterns[key].totalTime / uniquePatterns[key].count
      }
    })
    
    Object.values(uniquePatterns)
      .sort((a, b) => b.avgTime - a.avgTime)
      .slice(0, 5)
      .forEach(pattern => {
        result += `- Filter: ${pattern.filter}\n`
        result += `  - Fields: ${pattern.fields.join(', ')}\n`
        result += `  - Count: ${pattern.count}\n`
        result += `  - Avg Time: ${pattern.avgTime.toFixed(2)}ms\n`
        result += `  - Scan Type: ${pattern.scanType}\n\n`
      })
  }
  
  return result
}

const generateJsonSchemaValidator = (schema, strictness) => {
  const validator = {
    $jsonSchema: {
      bsonType: "object",
      required: [],
      properties: {}
    }
  }

  const requiredThreshold = 
    strictness === 'strict' ? 90 :
    strictness === 'moderate' ? 75 :
    60
  
  Object.entries(schema.fields).forEach(([fieldPath, info]) => {
    if (fieldPath.includes('.')) return

    const cleanFieldPath = fieldPath.replace('[]', '')

    let bsonTypes = []
    info.types.forEach(type => {
      switch(type) {
        case 'string':
          bsonTypes.push('string')
          break
        case 'number':
          bsonTypes.push('number', 'double', 'int')
          break
        case 'boolean':
          bsonTypes.push('bool')
          break
        case 'array':
          bsonTypes.push('array')
          break
        case 'object':
          bsonTypes.push('object')
          break
        case 'null':
          bsonTypes.push('null')
          break
        case 'Date':
          bsonTypes.push('date')
          break
        case 'ObjectId':
          bsonTypes.push('objectId')
          break
      }
    })

    const fieldSchema = bsonTypes.length === 1 
      ? { bsonType: bsonTypes[0] }
      : { bsonType: bsonTypes }

    validator.$jsonSchema.properties[cleanFieldPath] = fieldSchema

    const coverage = info.coverage || Math.round((info.count / schema.sampleSize) * 100)
    if (coverage >= requiredThreshold && !info.types.includes('null')) {
      validator.$jsonSchema.required.push(cleanFieldPath)
    }
  })

  if (strictness === 'strict') {
    validator.$jsonSchema.additionalProperties = false
  }
  
  return validator
}

const log = (message, forceLog = false) => {
  if (forceLog || VERBOSE_LOGGING) console.error(message)
}

process.on('SIGTERM', async () => {
  log('Received SIGTERM, shutting down…')
  await cleanup()
  exit()
})

process.on('SIGINT', async () => {
  log('Received SIGINT, shutting down…')
  await cleanup()
  exit()
})

const createStreamingResultStream = () => {
  return new Transform({
    objectMode: true,
    transform(chunk, encoding, callback) {
      callback(null, chunk)
    }
  })
}

const streamResultsToMcp = async (resultStream, resultFormatter, resourceUri, streamingLimit = 10000) => {
  let count = 0
  const streamId = Math.random().toString(36).substring(2, 15)
  
  try {
    const stream = server.createStreamingResource(`${resourceUri}?stream=${streamId}`)
    
    for await (const item of resultStream) {
      count++
      
      if (count > streamingLimit) {
        stream.write({
          contents: [{
            uri: resourceUri,
            text: `Reached streaming limit of ${streamingLimit} items. Use a more specific query to reduce result size.`
          }]
        })
        break
      }
      
      const formattedItem = resultFormatter(item)
      
      stream.write({
        contents: [{
          uri: resourceUri,
          text: formattedItem
        }]
      })
    }
    
    stream.end()
    return count
  } catch (error) {
    log(`Error in streaming results: ${error.message}`, true)
    throw error
  }
}

const processAggregationPipeline = (pipeline) => {
  if (!pipeline || !Array.isArray(pipeline)) return pipeline
  
  return pipeline.map(stage => {
    for (const operator in stage) {
      const value = stage[operator]
      if (typeof value === 'object' && value !== null) {
        if (operator === '$match' && value.$text) {
          if (value.$text.$search && typeof value.$text.$search === 'string') {
            value.$text.$search = sanitizeTextSearch(value.$text.$search)
          }
        }
      }
    }
    return stage
  })
}

const sanitizeTextSearch = (searchText) => {
  if (!searchText) return ''
  return searchText.replace(/\$/g, '').replace(/[\u0000-\u001F\u007F-\u009F]/g, '')
}

const monitorBinarySize = (size) => {
  const mb = size / (1024 * 1024)
  if (mb > 10) {
    log(`Warning: Large binary data detected (${mb.toFixed(2)} MB)`, true)
  }
  return mb < 50
}

const cleanup = async () => {
  if (watchdog) {
    clearInterval(watchdog)
    watchdog = null
  }
  
  if (server) {
    try {
      log('Closing MCP server…')
      await server.close()
      log('MCP server closed.')
    } catch (error) {
      log(`Error closing MCP server: ${error.message}`, true)
    }
  }
  
  if (transport) {
    try {
      log('Closing transport…')
      await transport.close()
      log('Transport closed.')
    } catch (error) {
      log(`Error closing transport: ${error.message}`, true)
    }
  }
  
  if (mongoClient) {
    try {
      log('Closing MongoDB client…')
      await mongoClient.close()
      log('MongoDB client closed.')
    } catch (error) {
      log(`Error closing MongoDB client: ${error.message}`, true)
    }
  }
  
  memoryCache.schemas.clear()
  memoryCache.collections.clear()
  memoryCache.stats.clear()
  memoryCache.indexes.clear()
  memoryCache.serverStatus.clear()
  memoryCache.fields.clear()
}

const exit = (exitCode = 1) => {
  log('Exiting…', true)
  process.exit(exitCode)
}

main(process.env.MONGO_URI)