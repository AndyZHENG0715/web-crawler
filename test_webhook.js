#!/usr/bin/env node

/**
 * Test the n8n webhook trigger
 */

const https = require('https');
require('dotenv').config({ path: '.env' });

// Test webhook trigger
function testWebhook() {
  const data = JSON.stringify({
    trigger: 'api',
    timestamp: new Date().toISOString()
  });
  
  const options = {
    hostname: 'aitutorhk.app.n8n.cloud',
    path: '/webhook/policy-address-crawler',
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Content-Length': data.length
    }
  };
  
  console.log('🚀 Triggering webhook: https://aitutorhk.app.n8n.cloud/webhook/policy-address-crawler');
  
  const req = https.request(options, (res) => {
    console.log(`📊 Status: ${res.statusCode}`);
    console.log(`📋 Headers:`, res.headers);
    
    let responseData = '';
    res.on('data', (chunk) => {
      responseData += chunk;
    });
    
    res.on('end', () => {
      console.log('📄 Response:');
      try {
        const parsed = JSON.parse(responseData);
        console.log(JSON.stringify(parsed, null, 2));
      } catch (e) {
        console.log(responseData);
      }
    });
  });
  
  req.on('error', (error) => {
    console.error('❌ Error:', error);
  });
  
  req.write(data);
  req.end();
}

testWebhook();