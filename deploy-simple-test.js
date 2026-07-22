#!/usr/bin/env node

/**
 * Deploy simple webhook test to n8n
 */

const https = require('https');
const fs = require('fs');
require('dotenv').config({ path: '.env' });

const apiKey = process.env.N8N_API_KEY;
const baseUrl = 'https://aitutorhk.app.n8n.cloud/api/v1';

function makeRequest(method, endpoint, data = null) {
  return new Promise((resolve, reject) => {
    const url = new URL(`${baseUrl}${endpoint}`);
    
    console.log(`🌐 Making ${method} request to: ${url}`);
    
    const options = {
      method: method,
      headers: {
        'Content-Type': 'application/json',
        'X-N8N-API-KEY': apiKey
      }
    };
    
    const req = https.request(url, options, (res) => {
      let responseData = '';
      res.on('data', (chunk) => responseData += chunk);
      res.on('end', () => {
        console.log(`📊 Response status: ${res.statusCode}`);
        console.log(`📄 Response:`, responseData);
        try {
          const parsed = JSON.parse(responseData);
          resolve(parsed);
        } catch (e) {
          resolve(responseData);
        }
      });
    });
    
    req.on('error', reject);
    if (data) req.write(JSON.stringify(data));
    req.end();
  });
}

async function deploySimpleTest() {
  try {
    console.log('🔧 Deploying simple webhook test...');
    
    // Load the simple test workflow
    const workflow = JSON.parse(fs.readFileSync('simple-webhook-test.json', 'utf8'));
    
    // Create the workflow
    const result = await makeRequest('POST', '/workflows', workflow);
    console.log('✅ Simple test deployed:', result.id);
    
    // Activate it
    await makeRequest('POST', `/workflows/${result.id}/activate`);
    console.log('⚡ Simple test activated');
    
    console.log(`🔗 Test URL: https://aitutorhk.app.n8n.cloud/webhook/test-webhook`);
    
  } catch (error) {
    console.error('❌ Error:', error);
  }
}

deploySimpleTest();