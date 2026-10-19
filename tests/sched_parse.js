// Runs the real schedParse() from web/js/board.js on the JSON list of strings in argv[2]; prints the results as JSON.
const fs = require('fs'), vm = require('vm'), path = require('path');
const src = fs.readFileSync(path.join(__dirname, '..', 'web', 'js', 'board.js'), 'utf8');
const start = src.indexOf('function schedParse'), end = src.indexOf('const schedShow');
if (start < 0 || end < 0) throw new Error('board.js layout changed: update tests/sched_parse.js');
const ctx = vm.createContext({});
vm.runInContext(src.slice(start, end), ctx);
console.log(JSON.stringify(JSON.parse(process.argv[2]).map((t) => vm.runInContext('schedParse', ctx)(t))));
