#!/usr/bin/env node

/**
 * N8N Policy Address Crawler Deployment Script
 * 
 * This script replicates the Python crawler functionality in n8n
 * using the n8n API to create and manage workflows.
 */

const https = require('https');
const fs = require('fs');
const path = require('path');
require('dotenv').config({ path: '.env' });

class N8NCrawlerDeployer {
  constructor() {
    this.n8nUrl = process.env.N8N_INSTANCE_URL;
    this.apiKey = process.env.N8N_API_KEY;
    
    if (!this.n8nUrl || !this.apiKey) {
      console.error('❌ Missing N8N_INSTANCE_URL or N8N_API_KEY in .env file');
      process.exit(1);
    }
    
    // Remove trailing slash from URL
    this.n8nUrl = this.n8nUrl.replace(/\/$/, '');
    
    // For n8n cloud instances, the API is typically at /api/v1
    // For self-hosted, it might be different
    this.baseApiUrl = `${this.n8nUrl}/api/v1`;
    
    console.log(`🔗 Connecting to: ${this.n8nUrl}`);
    console.log(`🔑 Using API endpoint: ${this.baseApiUrl}`);
  }

  /**
   * Make HTTP request to n8n API
   */
  async makeRequest(method, endpoint, data = null) {
    return new Promise((resolve, reject) => {
      const fullUrl = `${this.baseApiUrl}${endpoint}`;
      const url = new URL(fullUrl);
      
      console.log(`🌐 Making ${method} request to: ${fullUrl}`);
      
      const options = {
        method: method,
        headers: {
          'Content-Type': 'application/json',
          'X-N8N-API-KEY': this.apiKey,
          'User-Agent': 'N8N-Policy-Crawler-CLI/1.0',
          'Accept': 'application/json'
        }
      };

      if (data) {
        const jsonData = JSON.stringify(data);
        options.headers['Content-Length'] = Buffer.byteLength(jsonData);
        console.log(`📦 Sending data: ${jsonData.substring(0, 200)}${jsonData.length > 200 ? '...' : ''}`);
      }

      const req = https.request(url, options, (res) => {
        let responseData = '';
        
        console.log(`📊 Response status: ${res.statusCode} ${res.statusMessage}`);
        console.log(`📋 Response headers:`, res.headers);
        
        res.on('data', (chunk) => {
          responseData += chunk;
        });
        
        res.on('end', () => {
          console.log(`📄 Raw response (first 500 chars):`, responseData.substring(0, 500));
          
          // Check if response looks like HTML
          if (responseData.trim().startsWith('<!DOCTYPE') || responseData.trim().startsWith('<html')) {
            reject(new Error(`API returned HTML instead of JSON. This usually means wrong endpoint or authentication issue. Response: ${responseData.substring(0, 200)}...`));
            return;
          }
          
          try {
            const parsed = responseData ? JSON.parse(responseData) : {};
            
            if (res.statusCode >= 200 && res.statusCode < 300) {
              resolve(parsed);
            } else {
              reject(new Error(`HTTP ${res.statusCode}: ${parsed.message || responseData}`));
            }
          } catch (error) {
            reject(new Error(`Failed to parse response: ${error.message}. Raw response: ${responseData.substring(0, 200)}`));
          }
        });
      });

      req.on('error', (error) => {
        reject(new Error(`Request failed: ${error.message}`));
      });

      if (data) {
        req.write(JSON.stringify(data));
      }
      
      req.end();
    });
  }

  /**
   * Test connection to n8n instance
   */
  async testConnection() {
    console.log('🔍 Testing connection to n8n instance...');
    
    try {
      const response = await this.makeRequest('GET', '/workflows');
      console.log(`✅ Connected to n8n instance: ${this.n8nUrl}`);
      console.log(`📊 Found ${response.data ? response.data.length : 0} existing workflows`);
      return true;
    } catch (error) {
      console.error(`❌ Connection failed: ${error.message}`);
      return false;
    }
  }

  /**
   * Load workflow definition from file
   */
  loadWorkflowDefinition() {
    const workflowPath = path.join(__dirname, 'n8n-workflows', 'policy-address-crawler.json');
    
    try {
      const rawWorkflowData = JSON.parse(fs.readFileSync(workflowPath, 'utf8'));
      
      // Clean up the workflow data for n8n API
      const workflowData = {
        name: rawWorkflowData.name,
        nodes: rawWorkflowData.nodes,
        connections: rawWorkflowData.connections,
        settings: rawWorkflowData.settings || {}
      };
      
      console.log(`📄 Loaded workflow definition: ${workflowData.name}`);
      console.log(`📊 Contains ${workflowData.nodes.length} nodes`);
      return workflowData;
    } catch (error) {
      console.error(`❌ Failed to load workflow: ${error.message}`);
      return null;
    }
  }

  /**
   * Check if workflow already exists
   */
  async findExistingWorkflow(workflowName) {
    try {
      const response = await this.makeRequest('GET', '/workflows');
      const workflows = response.data || [];
      
      return workflows.find(w => w.name === workflowName);
    } catch (error) {
      console.error(`❌ Failed to check existing workflows: ${error.message}`);
      return null;
    }
  }

  /**
   * Create new workflow
   */
  async createWorkflow(workflowData) {
    console.log(`🚀 Creating workflow: ${workflowData.name}`);
    
    try {
      const response = await this.makeRequest('POST', '/workflows', workflowData);
      console.log(`✅ Workflow created successfully with ID: ${response.id}`);
      return response;
    } catch (error) {
      console.error(`❌ Failed to create workflow: ${error.message}`);
      return null;
    }
  }

  /**
   * Update existing workflow
   */
  async updateWorkflow(workflowId, workflowData) {
    console.log(`🔄 Updating workflow ID: ${workflowId}`);
    
    try {
      const response = await this.makeRequest('PUT', `/workflows/${workflowId}`, workflowData);
      console.log(`✅ Workflow updated successfully`);
      return response;
    } catch (error) {
      console.error(`❌ Failed to update workflow: ${error.message}`);
      return null;
    }
  }

  /**
   * Activate workflow
   */
  async activateWorkflow(workflowId) {
    console.log(`⚡ Activating workflow ID: ${workflowId}`);
    
    try {
      await this.makeRequest('POST', `/workflows/${workflowId}/activate`);
      console.log(`✅ Workflow activated successfully`);
      return true;
    } catch (error) {
      console.error(`❌ Failed to activate workflow: ${error.message}`);
      return false;
    }
  }

  /**
   * Execute workflow manually
   */
  async executeWorkflow(workflowId) {
    console.log(`▶️ Executing workflow ID: ${workflowId}`);
    
    try {
      const response = await this.makeRequest('POST', `/workflows/${workflowId}/execute`);
      console.log(`✅ Workflow execution started`);
      console.log(`🔗 Execution ID: ${response.data.executionId}`);
      return response.data;
    } catch (error) {
      console.error(`❌ Failed to execute workflow: ${error.message}`);
      return null;
    }
  }

  /**
   * Main deployment process
   */
  async deploy() {
    console.log('🕷️ N8N Policy Address Crawler Deployment');
    console.log('==========================================\\n');

    // Test connection
    const connected = await this.testConnection();
    if (!connected) {
      return false;
    }

    // Load workflow definition
    const workflowData = this.loadWorkflowDefinition();
    if (!workflowData) {
      return false;
    }

    // Check if workflow exists
    const existingWorkflow = await this.findExistingWorkflow(workflowData.name);
    
    let deployedWorkflow;
    if (existingWorkflow) {
      console.log(`🔄 Found existing workflow, updating...`);
      deployedWorkflow = await this.updateWorkflow(existingWorkflow.id, workflowData);
    } else {
      console.log(`🆕 Creating new workflow...`);
      deployedWorkflow = await this.createWorkflow(workflowData);
    }

    if (!deployedWorkflow) {
      return false;
    }

    // Activate workflow
    const activated = await this.activateWorkflow(deployedWorkflow.id);
    if (!activated) {
      return false;
    }

    console.log('\\n🎉 Deployment completed successfully!');
    console.log(`🔗 Workflow URL: ${this.n8nUrl}/workflow/${deployedWorkflow.id}`);
    console.log(`📊 Workflow replicates Python crawler with 108 document capability`);
    
    // Optionally execute the workflow
    const shouldExecute = process.argv.includes('--execute') || process.argv.includes('-x');
    if (shouldExecute) {
      console.log('\\n🚀 Starting workflow execution...');
      await this.executeWorkflow(deployedWorkflow.id);
    } else {
      console.log('\\n💡 To execute the workflow, add --execute flag or run manually from n8n interface');
    }

    return true;
  }
}

// CLI execution
if (require.main === module) {
  const deployer = new N8NCrawlerDeployer();
  
  deployer.deploy().then(success => {
    process.exit(success ? 0 : 1);
  }).catch(error => {
    console.error(`💥 Deployment failed: ${error.message}`);
    process.exit(1);
  });
}

module.exports = N8NCrawlerDeployer;