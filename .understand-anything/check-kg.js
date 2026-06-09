const fs = require('fs');
const kg = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
console.log('version:', kg.version);
console.log('project keys:', Object.keys(kg.project || {}));
console.log('project.analyzedAt:', kg.project && kg.project.analyzedAt);
console.log('project.gitCommitHash:', kg.project && kg.project.gitCommitHash);
console.log('layers count:', (kg.layers||[]).length);
console.log('layers[0] nodeIds:', kg.layers && kg.layers[0] && kg.layers[0].nodeIds && kg.layers[0].nodeIds.length);
// Check node validity
const badNodes = (kg.nodes||[]).filter(n => !n.id || !n.type || !n.name || !n.summary);
console.log('bad nodes (missing fields):', badNodes.length);
if(badNodes.length > 0) console.log('first bad:', JSON.stringify(badNodes[0]).substring(0,200));
